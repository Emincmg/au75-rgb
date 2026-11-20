#!/usr/bin/env python3
"""AULA AU75 macOS tool (wired mode, VID 0x258a PID 0x010C).
Protocol reverse-engineered from the official Windows driver (OemDrv.exe, CDevG5KB).
See CLAUDE.md for the full protocol notes.
"""
import os, sys, time, json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # the launcher runs python -I, which drops the script dir
import hid
import keymap as km
import macro as mc

VID, PID = 0x258a, 0x010C
PKT = 0x208
BACKUPS = os.path.join(HERE, "backups")


# ---------------------------------------------------------------- transport
def open_dev():
    for d in hid.enumerate(VID, PID):
        if d['usage_page'] == 0xff00:
            h = hid.device()
            h.open_path(d['path'])
            return h, 6, d
    sys.exit("AU75 kablolu modda bulunamadı. USB kablosuyla bağlayıp kablolu moda alın.")


def access(h, rid, cmd, sub, length, data=None):
    """Write when data is given (cmd < 0x80), else read (cmd | 0x80).
    Packet: [rid][cmd][sub][0][nchunks][chunk][len lo][len hi] + up to 0x200 data."""
    out = bytearray()
    nchunks = (length + 0x1ff) // 0x200
    for i in range(nchunks):
        n = min(0x200, length - i * 0x200)
        pkt = bytearray(PKT)
        pkt[0:8] = bytes([rid, cmd, sub, 0, nchunks, i, n & 0xff, n >> 8])
        if data is not None:
            pkt[8:8 + n] = data[i * 0x200:i * 0x200 + n]
        h.send_feature_report(bytes(pkt))
        time.sleep(0.02)
        if data is None:
            r = bytes(h.get_feature_report(rid, PKT))
            out += r[8:8 + n]
    return bytes(out)


def hexdump(b):
    for i in range(0, len(b), 16):
        print(f"{i:04x}: " + " ".join(f"{x:02x}" for x in b[i:i+16]))


def load_keys():
    return json.load(open(os.path.join(HERE, "keys.json"), encoding="utf-8"))


def key_index(name):
    for k in load_keys():
        if k["name"].lower() == name.lower():
            return k["led"]
    sys.exit(f"bilinmeyen tuş: {name} (liste: au75 keys)")


# ---------------------------------------------------------------- LED block
LED_LEN = 0x80


def read_led(h, rid):
    b = access(h, rid, 0x84, 0, LED_LEN)
    if b[0x7e:0x80] != b"\x5a\xa5":
        sys.exit("LED bloğu geçersiz okundu, yazma iptal.")
    return bytearray(b)


def write_led(h, rid, b):
    access(h, rid, 0x04, 0, LED_LEN, bytes(b))


EFFECTS = {  # id -> name (driver text.xml / KB.ini LedOpt)
    1: "Sabit", 2: "Nefes", 3: "Gökkuşağı", 4: "Kaybolan flaş", 5: "Yağmur damlası",
    6: "Gökkuşağı çarkı", 7: "Parlayan dalgalar", 8: "Yıldızlar", 9: "Kaybolan gölge",
    10: "Retro yılan", 11: "Neon akış", 12: "Tepki", 13: "Sinüs dalgası",
    14: "Tarama", 15: "Dönen yel değirmeni", 16: "Renkli şelale", 17: "Çiçeklenme",
    18: "Dönen fırtına",
}
EFFECT_ORDER = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 21]
COLORS = ["kırmızı", "yeşil", "mavi", "sarı", "mor", "turkuaz", "beyaz", "renkli"]
MAIN_EFFECT, MAIN_GROUP, MAIN_FLAG, PAIRS = 0x0a, 0x0b, 0x09, 0x3a
SLEEP, DEBOUNCE = 0x18, 0x03
SLEEP_CHOICES = [30, 60, 90, 120, 180, 240, 300, 600, 900, 1200]  # seconds; stored as seconds/30, 0 = never


def settings_state(b):
    sl = b[SLEEP]
    sleep = "hiç" if sl == 0 else (f"{sl*30} sn" if sl * 30 < 60 else f"{sl*30/60:g} dk")
    return f"uyku: {sleep}   debounce: {b[DEBOUNCE]}"


SIDE = {"mode": 0x12, "color": 0x13, "light": 0x14, "speed": 0x15}


def set_main(b, effect=None, light=None, speed=None, color=None):
    """effect 0 = off. Per-effect pair at PAIRS + 2*ui: [brightness][speed<<4 | color]."""
    if effect is not None:
        if effect == 0:
            b[MAIN_EFFECT] = 0
        else:
            ui = EFFECT_ORDER.index(effect)
            b[MAIN_EFFECT] = effect
            b[MAIN_GROUP] = 0x20 + ui
            b[MAIN_FLAG] = 1 if effect == 21 else 0
    cur = b[MAIN_EFFECT]
    if cur in EFFECT_ORDER and (light is not None or speed is not None or color is not None):
        i = PAIRS + 2 * EFFECT_ORDER.index(cur)
        if light is not None:
            b[i] = light
        sp, co = b[i + 1] >> 4, b[i + 1] & 0xf
        if speed is not None: sp = speed
        if color is not None: co = color
        b[i + 1] = (sp << 4) | co


def main_state(b):
    e = b[MAIN_EFFECT]
    if not e:
        return "kapalı"
    if e not in EFFECTS:
        return f"efekt #{e}"
    i = PAIRS + 2 * EFFECT_ORDER.index(e)
    co = b[i + 1] & 0xf
    return (f"{EFFECTS[e]} (#{e}), parlaklık {b[i]}, hız {b[i+1] >> 4}, "
            f"renk {COLORS[co] if co < len(COLORS) else co}")


# ---------------------------------------------------------------- key matrix
def read_matrix(h, rid, layer):
    m = access(h, rid, 0x83, layer, km.MATRIX_LEN)
    if m[-4:] != km.MARKER:
        sys.exit("Tuş haritası geçersiz okundu, yazma iptal.")
    return bytearray(m)


def write_matrix(h, rid, layer, m):
    assert len(m) == km.MATRIX_LEN and bytes(m[-4:]) == km.MARKER
    access(h, rid, 0x03, layer, km.MATRIX_LEN, bytes(m))
    if access(h, rid, 0x83, layer, km.MATRIX_LEN) != bytes(m):
        sys.exit("Yazma doğrulanamadı!")


def factory_matrix(layer):
    return bytearray(open(os.path.join(BACKUPS, f"matrix_backup_l{layer}.bin"), "rb").read())


USAGE = """kullanım: au75 <komut>

Işık
  main                         ana ışığın durumu
  main off                     tuş ışıklarını kapat
  main effect <1-18>           efekt seç (liste: au75 effects)
  main light|speed <0-4>       parlaklık / hız
  main color <0-7>             0 kırmızı 1 yeşil 2 mavi 3 sarı 4 mor 5 turkuaz 6 beyaz 7 renkli
  side off|on                  kenar ışığını kapat / aç
  side color|light|speed <n>   kenar ışığı ayarı
  backup [dosya] / restore [dosya]   LED bloğu yedekle / geri yükle

Tuş atama  (--fn: Fn katmanı)
  keys                         tuş adlarını listele
  keymap [--fn]                mevcut atamaları göster
  map [--fn] <tuş> <hedef> [<tuş> <hedef> ...]
        hedef örnekleri: a, f13, esc, cmd, ctrl+c, cmd+shift+4, media:volup, fn:bt1, none
  unmap [--fn] <tuş> [...]     tuşu fabrika atamasına döndür
  keymap reset                 tüm tuş haritasını fabrika ayarına döndür
  targets                      kullanılabilir hedef adları

Ayarlar
  settings                     uyku süresi ve debounce
  sleep <saniye|never>         uyku süresi: 30 60 90 120 180 240 300 600 900 1200 ya da never
  debounce <1-4>               tuş titreşim filtresi (yüksek = daha uzun)

Makro  (adımlar: tap:<tuş> down:<tuş> up:<tuş> text:<yazı> wait:<ms> click:left|right|middle)
  macros                       kayıtlı makroları listele
  macro set <no> <ad> <adım> [<adım> ...]   makro yaz (no: 1-32)
        örnek: au75 macro set 1 kopyala tap:cmd+c
               au75 macro set 2 imza "text:Selamlar, Emin" tap:enter
  macro del <no>               makroyu sil (sonrakiler bir kayar, atamalar düzeltilir)
  map <tuş> macro:<no>[:once|toggle|hold[:tekrar]]   tuşa makro ata

Diğer
  info                         HID arayüzlerini listele
  readled                      ham LED bloğu
  watch [saniye]               LED bloğundaki değişiklikleri izle
"""


def main(a):
    if not a or a[0] in ("-h", "help", "--help"):
        print(USAGE); return
    if a[0] == "info":
        for d in hid.enumerate(VID, PID):
            print(hex(d['usage_page']), hex(d['usage']), d['interface_number'])
        return
    if a[0] == "effects":
        for k, v in EFFECTS.items(): print(f"{k:3}  {v}")
        return
    if a[0] == "keys":
        print(" ".join(k["name"] for k in load_keys())); return
    if a[0] == "targets":
        print("Normal :", " ".join(sorted(km.HID, key=lambda k: km.HID[k])))
        print("Modifier:", " ".join(km.MODS))
        print("Medya  :", " ".join("media:" + m for m in km.MEDIA))
        print("Özel   :", " ".join("fn:" + n for n in km.SPECIAL_BY_NAME))
        print("Diğer  : none, raw:XXXXXXXX")
        return

    fn = "--fn" in a
    a = [x for x in a if x != "--fn"]
    layer = 1 if fn else 0
    h, rid, _ = open_dev()
    cmd = a[0]

    if cmd == "readled":
        hexdump(read_led(h, rid))
    elif cmd == "backup":
        f = a[1] if len(a) > 1 else os.path.join(BACKUPS, "led_backup.bin")
        open(f, "wb").write(read_led(h, rid)); print("yedeklendi:", f)
    elif cmd == "restore":
        f = a[1] if len(a) > 1 else os.path.join(BACKUPS, "led_backup.bin")
        b = open(f, "rb").read()
        if len(b) != LED_LEN or b[-2:] != b"\x5a\xa5": sys.exit("geçersiz yedek")
        write_led(h, rid, b); print("geri yüklendi")
    elif cmd == "side":
        b = read_led(h, rid)
        if a[1] == "off": b[SIDE["mode"]] = 0
        elif a[1] == "on": b[SIDE["mode"]] = int(a[2]) if len(a) > 2 else 1
        else: b[SIDE[a[1]]] = int(a[2], 0)
        write_led(h, rid, b)
        s = read_led(h, rid)
        print("kenar ışığı:", "kapalı" if not s[SIDE["mode"]] else
              f"mod {s[0x12]}, renk {s[0x13]}, parlaklık {s[0x14]}, hız {s[0x15]}")
    elif cmd == "main":
        b = read_led(h, rid)
        if len(a) > 1:
            if a[1] == "off": set_main(b, effect=0)
            else: set_main(b, **{a[1]: int(a[2], 0)})
            write_led(h, rid, b)
            b = read_led(h, rid)
        print(main_state(b))
    elif cmd == "keymap" and len(a) > 1 and a[1] == "reset":
        for l in (0, 1): write_matrix(h, rid, l, factory_matrix(l))
        print("tuş haritası fabrika ayarına döndü")
    elif cmd == "keymap":
        m = read_matrix(h, rid, layer)
        f = factory_matrix(layer)
        for k in load_keys():
            i = k["led"]; e = bytes(m[i*4:i*4+4])
            mark = "" if e == bytes(f[i*4:i*4+4]) else "   * değiştirildi"
            if fn and e == bytes(4) and not mark: continue
            print(f"{k['name']:>10} -> {km.decode(e)}{mark}")
    elif cmd in ("map", "unmap"):
        m = read_matrix(h, rid, layer)
        f = factory_matrix(layer)
        pairs = zip(a[1::2], a[2::2]) if cmd == "map" else ((n, None) for n in a[1:])
        for name, target in pairs:
            i = key_index(name)
            try:
                m[i*4:i*4+4] = km.encode(target) if target else f[i*4:i*4+4]
            except ValueError as e:
                sys.exit(str(e))
            print(f"{name} -> {km.decode(bytes(m[i*4:i*4+4]))}" + (" (Fn)" if fn else ""))
        write_matrix(h, rid, layer, m)
        print("yazıldı ✓")
    elif cmd in ("settings", "sleep", "debounce"):
        b = read_led(h, rid)
        if cmd == "sleep":
            if a[1] in ("never", "0", "hiç"): b[SLEEP] = 0
            else:
                sec = int(a[1])
                if sec not in SLEEP_CHOICES: sys.exit(f"seçenekler: {' '.join(map(str, SLEEP_CHOICES))} ya da never")
                b[SLEEP] = sec // 30
            write_led(h, rid, b)
        elif cmd == "debounce":
            v = int(a[1])
            if not 1 <= v <= 4: sys.exit("debounce 1-4 arası olmalı")
            b[DEBOUNCE] = v
            write_led(h, rid, b)
        print(settings_state(read_led(h, rid)))
    elif cmd == "macros":
        ms = mc.unpack(access(h, rid, 0x85, 0, mc.MACRO_BUF))
        if not ms: print("kayıtlı makro yok")
        for i, (name, ev) in enumerate(ms, 1):
            print(f"{i:2}. {name}: {mc.describe(ev)}")
    elif cmd == "macro":
        ms = mc.unpack(access(h, rid, 0x85, 0, mc.MACRO_BUF))
        try:
            if a[1] == "set":
                no, name, steps = int(a[2]), a[3], a[4:]
                if not 1 <= no <= len(ms) + 1:
                    sys.exit(f"makro no 1 ile {len(ms) + 1} arasında olmalı")
                item = (name, mc.compile_steps(steps))
                if no <= len(ms): ms[no - 1] = item
                else: ms.append(item)
            elif a[1] == "del":
                no = int(a[2])
                if not 1 <= no <= len(ms): sys.exit("böyle bir makro yok")
                del ms[no - 1]
                # fix key assignments: drop ones pointing at the deleted macro, shift later ones
                for l in (0, 1):
                    m = read_matrix(h, rid, l); f = factory_matrix(l); changed = False
                    for i in range(0, km.MATRIX_LEN - 4, 4):
                        e = m[i:i+4]
                        if e[0] == 0x03 and e[1] in (1, 2, 4):
                            if e[3] == no - 1: m[i:i+4] = f[i:i+4]; changed = True
                            elif e[3] > no - 1: m[i+3] -= 1; changed = True
                    if changed: write_matrix(h, rid, l, m)
            else:
                sys.exit(USAGE)
            buf = mc.pack(ms)
        except ValueError as e:
            sys.exit(str(e))
        data = buf + bytes(mc.MACRO_BUF - len(buf))
        access(h, rid, 0x05, 0, mc.MACRO_BUF, data)
        if access(h, rid, 0x85, 0, mc.MACRO_BUF) != data:
            sys.exit("Makro yazma doğrulanamadı!")
        for i, (name, ev) in enumerate(mc.unpack(data), 1):
            print(f"{i:2}. {name}: {mc.describe(ev)}")
        print("yazıldı ✓")
    elif cmd == "watch":
        secs = float(a[1]) if len(a) > 1 else 60
        prev = read_led(h, rid); t0 = time.time()
        print("izleniyor...", flush=True)
        while time.time() - t0 < secs:
            time.sleep(0.4)
            cur = read_led(h, rid)
            diff = [f"{i:#04x}:{prev[i]:02x}->{cur[i]:02x}" for i in range(LED_LEN) if prev[i] != cur[i]]
            if diff:
                print(f"[{time.time()-t0:6.1f}s] " + "  ".join(diff), flush=True)
                prev = cur
    else:
        print(USAGE); sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
