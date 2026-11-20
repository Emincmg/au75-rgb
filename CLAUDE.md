# au75-rgb

macOS command-line tool for the lighting of the AULA AU75 3-in-1 keyboard. AULA only ships a Windows driver. The protocol here was reverse-engineered from that driver (`OemDrv.exe`, class `CDevG5KB`, Inno Setup installer "AULA AU75 3 IN 1 Setup v2.0 20250805").

## Layout
- `au75.py`: the whole tool (Python 3 + `hidapi`).
- `au75`: shell launcher that runs `au75.py` with the local `.venv`.
- `led_backup.bin`: the 128-byte LED block read from the user's keyboard before the first write (factory-ish state, side light ON, mode 1). `./au75 restore` writes it back.

Setup: `python3 -m venv .venv && .venv/bin/pip install hidapi`

## Device
- Wired: VID `0x258a`, PID `0x010C` (Sinowealth). **Config only works over USB cable.** The 2.4G dongle (VID `0x3554`, PID `0xfa09`) and Bluetooth don't expose the config interface.
- Config interface: usage page `0xFF00`, usage `0x01`, **feature report ID 6**, 0x208 bytes including the ID.
- On macOS, open it with `hid.device().open_path()` on the `0xFF00` entry. Opening other interfaces of the keyboard can fail ("open failed"), which is harmless.

## Protocol (feature reports)
Packet = `[0x06][cmd][sub][0][nchunks][chunk_idx][len_lo][len_hi]` + up to 0x200 data bytes, total 0x208.
- Write: send the packet with data.
- Read: send the packet with `cmd | 0x80` (no data), wait ~20 ms, then `get_feature_report(6, 0x208)`. The data starts at offset 8.

Known commands (write / read):
| cmd | len | meaning |
|---|---|---|
| 0x03 / 0x83 | 0x14 | general cfg |
| 0x04 / 0x84 | 0x80 | LED block |
| 0x05 / 0x85 | – | macro |
| 0x06 / 0x86 | – | game mode |
| 0x0A / 0x8A | 0x1a4 | per-key RGB table (140 keys × RGB) |
| 0x0B | – | screen param |
| 0x11 | 1 | reset device |

Firmware update commands are deliberately NOT implemented. Don't add them.

## LED block (0x80 bytes)
- `0x7e..0x7f` = `5a a5`, the validity marker. The tool refuses to write if a read doesn't end with it.
- `0x0b` = current main effect (base + mode index).
- `0x12` side light mode (0 = off, verified), `0x13` color index (0–6, 7 = rainbow), `0x14` brightness, `0x15` speed. Only "mode 0 = off" has been tested on hardware.
- `0x38..0x39` = `ff ff`, then from `0x3a` there are 19 pairs `[speed][color<<4 | brightness]`, one per main effect (see `LedOpt*` in the driver's `KB.ini`).

Always read-modify-write the whole block. Never build it from scratch.

## Not done yet
- Main per-key effect/color/brightness commands (the protocol is known, the byte meanings for `0x0b` and the pairs aren't verified).
- Per-key RGB writing (cmd 0x0A).

## Safety
Recovery: `./au75 restore`, or hold Fn+Esc for 5 s (factory reset).
