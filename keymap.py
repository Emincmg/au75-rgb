"""Key matrix encoding for the AU75 (cmd 0x03 write / 0x83 read, sub = layer).
Layer 0 = normal, layer 1 = Fn layer. 128 entries x 4 bytes = 0x200 bytes,
the last entry (index 127) is the validity marker 00 00 5a a5.
Entry: [type][b1][b2][b3]
  type 0x00: keyboard. b1 = modifier mask, b3 = HID usage (b2 seems unused / 0)
  type 0x02: consumer (media). b2b3 = consumer usage (big endian)
  type 0x07 / 0x08 / 0x03: keyboard-internal functions (BT channels, lighting, knob)
  type 0x0d: Fn key
"""
MATRIX_LEN = 0x200
MARKER = bytes([0, 0, 0x5a, 0xa5])

MODS = {"lctrl": 0x01, "ctrl": 0x01, "lshift": 0x02, "shift": 0x02, "lalt": 0x04, "alt": 0x04,
        "option": 0x04, "opt": 0x04, "lgui": 0x08, "lcmd": 0x08, "cmd": 0x08, "win": 0x08, "gui": 0x08,
        "rctrl": 0x10, "rshift": 0x20, "ralt": 0x40, "roption": 0x40, "rgui": 0x80, "rcmd": 0x80, "rwin": 0x80}

HID = {}
for i, c in enumerate("abcdefghijklmnopqrstuvwxyz"): HID[c] = 0x04 + i
for i, c in enumerate("1234567890"): HID[c] = 0x1e + i
for i in range(12): HID[f"f{i+1}"] = 0x3a + i
for i in range(12): HID[f"f{i+13}"] = 0x68 + i
HID.update({
    "enter": 0x28, "return": 0x28, "esc": 0x29, "escape": 0x29, "backspace": 0x2a, "tab": 0x2b,
    "space": 0x2c, "-": 0x2d, "minus": 0x2d, "=": 0x2e, "equal": 0x2e, "[": 0x2f, "]": 0x30,
    "\\": 0x31, "backslash": 0x31, ";": 0x33, "semicolon": 0x33, "'": 0x34, "quote": 0x34,
    "`": 0x35, "grave": 0x35, ",": 0x36, "comma": 0x36, ".": 0x37, "period": 0x37, "/": 0x38,
    "slash": 0x38, "capslock": 0x39, "caps": 0x39, "printscreen": 0x46, "prtsc": 0x46,
    "scrolllock": 0x47, "pause": 0x48, "insert": 0x49, "ins": 0x49, "home": 0x4a, "pgup": 0x4b,
    "pageup": 0x4b, "delete": 0x4c, "del": 0x4c, "end": 0x4d, "pgdn": 0x4e, "pagedown": 0x4e,
    "right": 0x4f, "left": 0x50, "down": 0x51, "up": 0x52, "numlock": 0x53, "iso\\": 0x64,
    "intl": 0x64, "menu": 0x65, "app": 0x65,
})

MEDIA = {"play": 0xcd, "playpause": 0xcd, "next": 0xb5, "prev": 0xb6, "previous": 0xb6, "stop": 0xb7,
         "mute": 0xe2, "volup": 0xe9, "voldown": 0xea, "mail": 0x18a, "calc": 0x192, "calculator": 0x192,
         "browser": 0x223, "www": 0x223, "search": 0x221, "brightup": 0x6f, "brightdown": 0x70,
         "mycomputer": 0x194}

# Keyboard-internal functions, named from the factory Fn layer and AULA manuals.
SPECIAL = {
    "07000001": "win-kilidi", "07000004": "fabrika-ayarı", "07000005": "bt1", "07000006": "bt2",
    "07000007": "bt3", "07000008": "2.4g", "0700000a": "oyun-modu?", "0700000e": "windows-modu",
    "0700000f": "mac-modu", "07000016": "android-modu", "07000011": "pil-göstergesi",  # Fn+B: F1-F10 light up, ~10% each (confirmed)
    "07000013": "07000013?", "07000014": "düğme-basma",
    "03000000": "düğme-sola", "03000001": "düğme-sağa",
    "08000000": "ışık-efekt", "08000001": "kenar-ışık-efekt?", "08020000": "ışık-renk?",
    "08020001": "kenar-ışık-renk?", "08030100": "ışık-parlaklık+", "08030200": "ışık-parlaklık-",
    "08030001": "kenar-ışık-parlaklık?", "08040100": "ışık-hız+", "08040200": "ışık-hız-",
    "08040001": "kenar-ışık-hız?", "0d000000": "fn",
}
SPECIAL_BY_NAME = {v.rstrip("?"): k for k, v in SPECIAL.items()}

_HID_NAME = {}
for k, v in HID.items(): _HID_NAME.setdefault(v, k)
_MOD_NAME = {0x01: "ctrl", 0x02: "shift", 0x04: "alt", 0x08: "cmd", 0x10: "rctrl", 0x20: "rshift",
             0x40: "ralt", 0x80: "rcmd"}
_MEDIA_NAME = {}
for k, v in MEDIA.items(): _MEDIA_NAME.setdefault(v, k)


def encode(spec):
    """'a', 'ctrl+c', 'cmd+shift+4', 'shift', 'media:volup', 'none' -> 4 bytes."""
    s = spec.strip().lower()
    if s in ("none", "off", "disable", "0"):
        return bytes(4)
    if s.startswith("media:"):
        u = MEDIA.get(s[6:])
        if u is None:
            raise ValueError(f"bilinmeyen medya tuşu: {s[6:]} ({', '.join(MEDIA)})")
        return bytes([0x02, 0, u >> 8, u & 0xff])
    if s.startswith("fn:"):
        k = SPECIAL_BY_NAME.get(s[3:])
        if k is None:
            raise ValueError(f"bilinmeyen özel fonksiyon: {s[3:]} ({', '.join(SPECIAL_BY_NAME)})")
        return bytes.fromhex(k)
    if s.startswith("macro:"):
        # macro:<no>[:once|toggle|hold[:repeat]]  (no is 1-based)
        parts = s.split(":")[1:]
        no = int(parts[0]); mode = parts[1] if len(parts) > 1 else "once"
        rep = int(parts[2]) if len(parts) > 2 else 1
        m = {"once": 1, "toggle": 2, "hold": 4}.get(mode)
        if m is None or not 1 <= no <= 32: raise ValueError("macro:<1-32>[:once|toggle|hold[:tekrar]]")
        return bytes([0x03, m, (rep if m == 1 else 1) & 0xff, no - 1])
    if s.startswith("raw:"):
        b = bytes.fromhex(s[4:])
        if len(b) != 4: raise ValueError("raw: 8 hex karakter olmalı")
        return b
    parts = s.split("+") if s != "+" else ["+"]
    mod, code = 0, 0
    for p in parts:
        if p in MODS: mod |= MODS[p]
        elif p in HID:
            if code: raise ValueError(f"bir kombinasyonda tek normal tuş olabilir: {spec}")
            code = HID[p]
        else:
            raise ValueError(f"bilinmeyen tuş: {p}")
    return bytes([0, mod, 0, code])


def decode(e):
    t = e[0]
    if e == bytes(4): return "(boş)"
    if t == 0x00:
        names = [n for bit, n in _MOD_NAME.items() if e[1] & bit]
        if e[3]: names.append(_HID_NAME.get(e[3], f"hid:{e[3]:#04x}"))
        return "+".join(names) if names else f"raw:{e.hex()}"
    if t == 0x02:
        u = (e[2] << 8) | e[3]
        return "media:" + _MEDIA_NAME.get(u, f"{u:#06x}")
    if e.hex() in SPECIAL: return "fn:" + SPECIAL[e.hex()]
    if t == 0x03 and e[1] in (1, 2, 4):
        mode = {1: "once", 2: "toggle", 4: "hold"}[e[1]]
        return f"macro:{e[3] + 1}:{mode}" + (f":{e[2]}" if e[1] == 1 and e[2] != 1 else "")
    return f"raw:{e.hex()}"
