#!/usr/bin/env python3
"""AULA AU75 RGB tool for macOS (wired mode, VID 0x258a PID 0x010C).
Protocol reverse-engineered from the official Windows driver (OemDrv.exe, CDevG5KB):
  Feature report, 0x208 bytes incl. report ID:
  [id][cmd][sub][0][nchunks][chunk][len lo][len hi] + up to 0x200 data
  cmd 0x04/0x84 = set/get LED block (0x80 bytes), 0x0A/0x8A = set/get per-key RGB table (0x1a4 bytes)
"""
import sys, time, hid

VID, PID = 0x258a, 0x010C
PKT = 0x208

def open_dev():
    for d in hid.enumerate(VID, PID):
        if d['usage_page'] == 0xff00:
            h = hid.device()
            h.open_path(d['path'])
            return h, 6, d
    sys.exit("AU75 kablolu modda bulunamadı. USB kablosuyla bağlayıp kablolu moda alın.")

def access(h, rid, cmd, sub, length, data=None):
    """write when data given (cmd without 0x80), else read (cmd|0x80)."""
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

LED_LEN = 0x80

def read_led(h, rid):
    b = access(h, rid, 0x84, 0, LED_LEN)
    if b[0x7e:0x80] != b"\x5a\xa5":
        sys.exit("LED bloğu geçersiz okundu, yazma iptal.")
    return bytearray(b)

def write_led(h, rid, b):
    access(h, rid, 0x04, 0, LED_LEN, bytes(b))

USAGE = """kullanım: au75.py <komut>
  info                 HID arayüzlerini listele
  readled              LED bloğunu göster
  backup [dosya]       LED bloğunu yedekle (varsayılan led_backup.bin)
  restore [dosya]      yedeği geri yükle
  side off|on          kenar ışığını kapat / aç
  side mode|color|light|speed <değer>   kenar ışığı ayarı
"""

SIDE = {"mode": 0x12, "color": 0x13, "light": 0x14, "speed": 0x15}

if __name__ == "__main__":
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "help"):
        sys.exit(USAGE)
    if a[0] == "info":
        for d in hid.enumerate(VID, PID):
            print(hex(d['usage_page']), hex(d['usage']), d['interface_number'])
        sys.exit()
    h, rid, d = open_dev()
    if a[0] == "readled":
        hexdump(read_led(h, rid))
    elif a[0] == "readrgb":
        hexdump(access(h, rid, 0x8a, 0, 0x1a4))
    elif a[0] == "backup":
        f = a[1] if len(a) > 1 else os.path.join(here, "led_backup.bin")
        open(f, "wb").write(read_led(h, rid)); print("yedeklendi:", f)
    elif a[0] == "restore":
        f = a[1] if len(a) > 1 else os.path.join(here, "led_backup.bin")
        b = open(f, "rb").read()
        assert len(b) == LED_LEN and b[-2:] == b"\x5a\xa5"
        write_led(h, rid, b); print("geri yüklendi")
    elif a[0] == "side":
        b = read_led(h, rid)
        if a[1] == "off":
            b[SIDE["mode"]] = 0
        elif a[1] == "on":
            b[SIDE["mode"]] = int(a[2]) if len(a) > 2 else 1
        else:
            b[SIDE[a[1]]] = int(a[2], 0)
        write_led(h, rid, b)
        hexdump(read_led(h, rid)[0x10:0x20])
    else:
        sys.exit(USAGE)
