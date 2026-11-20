"""Macro storage for the AU75 (cmd 0x05 write / 0x85 read).

Buffer layout (from OemDrv.exe CDevG5KB ApplySetting / 0x4907b0):
  header: N entries of [addr u16 LE][size u16 LE], addr counted from buffer start
  per macro: [name_len_bytes][name UTF-16LE] then events, 4 bytes each:
    byte0 = type<<4 | (delay>>16 & 0xf) | 0x80 if release (types 1, 2)
    byte1 = delay >> 8 & 0xff, byte2 = delay & 0xff   (delay in ms, after the event)
    byte3 = code
  types: 0 keyboard key (HID usage), 1 modifier (HID 0xe0-0xe7), 2 mouse button (1 L, 2 R, 4 M, 8, 0x10),
         3/4 mouse move x/y, 5 wheel
Matrix entry that runs macro i: [0x03][mode][repeat][i]
  mode 1 = run `repeat` times, 2 = toggle (until pressed again), 4 = while held
"""
import keymap as km

MACRO_BUF = 0x800        # bytes we read/write; the device area read back as zeros beyond this
MAX_MACROS = 32

MOUSE = {"left": 1, "right": 2, "middle": 4, "back": 8, "forward": 0x10}

# US layout characters -> (HID usage, shift)
_CHARS = {}
for i, c in enumerate("abcdefghijklmnopqrstuvwxyz"):
    _CHARS[c] = (0x04 + i, False); _CHARS[c.upper()] = (0x04 + i, True)
for i, c in enumerate("1234567890"): _CHARS[c] = (0x1e + i, False)
for i, c in enumerate("!@#$%^&*()"): _CHARS[c] = (0x1e + i, True)
for c, u, s in [(" ", 0x2c, 0), ("\n", 0x28, 0), ("\t", 0x2b, 0), ("-", 0x2d, 0), ("_", 0x2d, 1),
                ("=", 0x2e, 0), ("+", 0x2e, 1), ("[", 0x2f, 0), ("{", 0x2f, 1), ("]", 0x30, 0),
                ("}", 0x30, 1), ("\\", 0x31, 0), ("|", 0x31, 1), (";", 0x33, 0), (":", 0x33, 1),
                ("'", 0x34, 0), ('"', 0x34, 1), ("`", 0x35, 0), ("~", 0x35, 1), (",", 0x36, 0),
                ("<", 0x36, 1), (".", 0x37, 0), (">", 0x37, 1), ("/", 0x38, 0), ("?", 0x38, 1)]:
    _CHARS[c] = (u, bool(s))

_MOD_HID = {0x01: 0xe0, 0x02: 0xe1, 0x04: 0xe2, 0x08: 0xe3, 0x10: 0xe4, 0x20: 0xe5, 0x40: 0xe6, 0x80: 0xe7}
_HID_MOD_NAME = {0xe0: "ctrl", 0xe1: "shift", 0xe2: "alt", 0xe3: "cmd", 0xe4: "rctrl", 0xe5: "rshift",
                 0xe6: "ralt", 0xe7: "rcmd"}


def _ev(typ, code, release=False, delay=10):
    delay = max(0, min(int(delay), 0xfffff))
    if typ == 0 and 0xe0 <= code <= 0xe7:
        typ = 1  # the driver encodes modifiers as type 1, other keys as type 0
    b0 = (typ << 4) | ((delay >> 16) & 0xf) | (0x80 if release and typ in (0, 1, 2) else 0)
    return bytes([b0, (delay >> 8) & 0xff, delay & 0xff, code & 0xff])


def _key_codes(spec):
    """'ctrl+shift+a' -> list of HID usages, modifiers first."""
    raw = km.encode(spec)
    if raw[0] != 0:
        raise ValueError(f"makroda sadece klavye tuşları kullanılabilir: {spec}")
    codes = [_MOD_HID[bit] for bit in _MOD_HID if raw[1] & bit]
    if raw[3]: codes.append(raw[3])
    return codes


def compile_steps(steps, delay=10):
    """Steps (space separated in the CLI):
      tap:<tuş>      press+release, combos allowed (tap:cmd+c)
      down:<tuş> / up:<tuş>
      text:<yazı>    type text (US layout); use '_' for space inside one CLI token or quote it
      wait:<ms>      add delay to the previous event
      click:left|right|middle|back|forward
    """
    ev = []
    for st in steps:
        kind, _, arg = st.partition(":")
        kind = kind.lower()
        if kind == "wait":
            if not ev: raise ValueError("wait ilk adım olamaz")
            last = ev[-1]
            d = ((last[0] & 0xf) << 16 | last[1] << 8 | last[2]) + int(arg)
            ev[-1] = _ev(last[0] >> 4 & 0x7, last[3], bool(last[0] & 0x80), d)
        elif kind == "tap":
            codes = _key_codes(arg)
            ev += [_ev(0, c, False, delay) for c in codes]
            ev += [_ev(0, c, True, delay) for c in reversed(codes)]
        elif kind in ("down", "up"):
            for c in _key_codes(arg):
                ev.append(_ev(0, c, kind == "up", delay))
        elif kind == "text":
            for ch in arg:
                if ch not in _CHARS: raise ValueError(f"yazılamayan karakter: {ch!r} (sadece US klavye karakterleri)")
                u, sh = _CHARS[ch]
                if sh: ev.append(_ev(0, 0xe1, False, 0))
                ev += [_ev(0, u, False, delay), _ev(0, u, True, delay)]
                if sh: ev.append(_ev(0, 0xe1, True, 0))
        elif kind == "click":
            b = MOUSE.get(arg.lower())
            if b is None: raise ValueError(f"bilinmeyen fare tuşu: {arg} ({', '.join(MOUSE)})")
            ev += [_ev(2, b, False, delay), _ev(2, b, True, delay)]
        else:
            raise ValueError(f"bilinmeyen adım: {st}")
    if not ev:
        raise ValueError("makro boş")
    return b"".join(ev)


def pack(macros):
    """macros: list of (name, events_bytes) -> buffer bytes."""
    if len(macros) > MAX_MACROS: raise ValueError("çok fazla makro")
    bodies = []
    for name, events in macros:
        nm = name[:30].encode("utf-16-le")
        bodies.append(bytes([len(nm)]) + nm + events)
    head = bytearray()
    addr = 4 * len(macros)
    for b in bodies:
        head += addr.to_bytes(2, "little") + len(b).to_bytes(2, "little")
        addr += len(b)
    buf = bytes(head) + b"".join(bodies)
    if len(buf) > MACRO_BUF: raise ValueError(f"makrolar sığmıyor ({len(buf)} > {MACRO_BUF} bayt)")
    return buf


def unpack(buf):
    """-> list of (name, events_bytes). Stops at the first invalid header entry."""
    out = []
    if not any(buf): return out
    first = int.from_bytes(buf[0:2], "little")
    n = first // 4
    for i in range(n):
        addr = int.from_bytes(buf[i*4:i*4+2], "little")
        size = int.from_bytes(buf[i*4+2:i*4+4], "little")
        if size == 0 or addr + size > len(buf): break
        body = buf[addr:addr+size]
        nl = body[0]
        name = body[1:1+nl].decode("utf-16-le", "replace")
        out.append((name, bytes(body[1+nl:])))
    return out


def describe(events):
    parts = []
    for i in range(0, len(events) - 3, 4):
        b0, d1, d2, code = events[i:i+4]
        typ, rel = (b0 >> 4) & 0x7, bool(b0 & 0x80)
        delay = (b0 & 0xf) << 16 | d1 << 8 | d2
        if typ in (0, 1):
            name = _HID_MOD_NAME.get(code) or km._HID_NAME.get(code, f"hid:{code:#04x}")
            parts.append(f"{'↑' if rel else '↓'}{name}")
        elif typ == 2:
            name = {v: k for k, v in MOUSE.items()}.get(code, code)
            parts.append(f"{'↑' if rel else '↓'}fare-{name}")
        else:
            parts.append(f"tip{typ}:{code}")
        if delay and delay != 10: parts.append(f"({delay}ms)")
    return " ".join(parts)


MODES = {"once": 1, "toggle": 2, "hold": 4}


def matrix_entry(index, mode="once", repeat=1):
    m = MODES.get(mode)
    if m is None: raise ValueError(f"mod: {', '.join(MODES)}")
    return bytes([0x03, m, (repeat if m == 1 else 1) & 0xff, index & 0xff])
