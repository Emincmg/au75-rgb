# au75-rgb

macOS tooling for the AULA AU75 3-in-1 keyboard: lighting, key remapping, macros, sleep/debounce. AULA only ships a Windows driver. The protocol here was reverse-engineered from that driver (`OemDrv.exe`, class `CDevG5KB`, Inno Setup installer "AULA AU75 3 IN 1 Setup v2.0 20250805"). The driver binary itself is not in the repo.

## Layout
- `au75.py`: CLI entry point and transport (Python 3 + `hidapi`). `au75` is the launcher that runs it with the local `.venv` using `python -I`, so `au75.py` adds its own directory to `sys.path`.
- `keymap.py`: key matrix entry encode/decode.
- `macro.py`: macro buffer pack/unpack and step compiler.
- `keys.json`: physical keys (name, layout rect from the driver's `KB.ini`, `led` = matrix/LED index). `WheelLeft`/`WheelRight` (85/86) were added by hand for the knob rotation.
- `index.html`: WebHID UI, served by GitHub Pages at https://emincmg.github.io/au75-rgb/. It reimplements the same encoders in JS and fetches `keys.json` and `backups/matrix_backup_l*.bin` (the factory keymap) from the same origin. The JS encoders were cross-checked against the Python ones byte for byte (run the pure functions in node). Keep them in sync.
- `backups/`: the user's factory-state dumps. `led_backup.bin` (LED block, side light on), `matrix_backup_l0/l1/l2.bin` (keymap layers, used as "factory" for unmap/reset), `rgb_backup.bin` (per-effect palette, cmd 0x8A), `led_before_main.bin`.

Setup: `python3 -m venv .venv && .venv/bin/pip install hidapi`

## Device
- Wired: VID `0x258a`, PID `0x010C` (Sinowealth). **Config only works over USB cable.** The 2.4G dongle (VID `0x3554`, PID `0xfa09`) and Bluetooth don't expose the config interface.
- Config interface: usage page `0xFF00`, **feature report ID 6**, 0x208 bytes including the ID.
- macOS hidapi opens the device exclusively. While the CLI (especially `watch`) runs, Chrome's WebHID can't open it ("failed to connect").

## Transport
Packet = `[0x06][cmd][sub][0][nchunks][chunk_idx][len_lo][len_hi]` + up to 0x200 data bytes.
- Write: send it with data (cmd < 0x80).
- Read: send it with `cmd | 0x80` and no data, wait about 20 ms, then get feature report 6. The reply echoes the 8-byte header and is only header + data long (e.g. 136 bytes for the LED block), not 0x208. In WebHID, Chrome may or may not prepend the report ID, so the JS finds the data offset from the echoed cmd byte.
- Data larger than 0x200 is sent in chunks (nchunks / chunk_idx).

| cmd (w / r) | sub | len | meaning |
|---|---|---|---|
| 0x03 / 0x83 | layer | 0x200 | key matrix (layer 0 normal, 1 Fn; 2 is empty) |
| 0x04 / 0x84 | 0 | 0x80 | LED + general config block |
| 0x05 / 0x85 | 0 | 0x800 used | macro buffer |
| 0x06 / 0x86 | – | – | game mode (not used) |
| 0x08, 0x0E | – | 7 | real-time data (not used) |
| 0x0A / 0x8A | 0 | 0x1a4 | **per-effect colour palette**: 19 effects × 7 RGB colours. NOT per-key colours. |
| 0x0B | – | – | screen param (no screen on AU75) |
| 0x0C | – | paged | AccessData_Page (GIF/screen upload, not used) |
| 0x11 | – | 1 | reset device |

Firmware update commands are deliberately NOT implemented. Don't add them.

## LED / config block (0x80 bytes)
Always read-modify-write the whole block. Never build it from scratch. `0x7e..0x7f` = `5a a5`, the validity marker.
- `0x03` debounce (driver range 1–4, from `ShowDebounce=0x04000101`). Writes and reads back; the effect on typing isn't verified.
- `0x09` = 1 when effect 21 (custom / "Gaoshou") is active.
- `0x0a` main effect id (0 = off, 1–18 = effects named in `EFFECTS`, 21 = custom). **Verified**: effect 1, colour 0, brightness 2 gives solid red.
- `0x0b` = 0x20 (`StartGp`) + effect's position in `EFFECT_ORDER`.
- `0x12` side light mode (0 = off, **verified**), `0x13` colour (0 red, 1 green, 2 blue, 3 yellow, 4 magenta, 5 cyan, 6 white, 7 rainbow; COLORREF/BGR in the driver), `0x14` brightness, `0x15` speed. Only on/off is verified on hardware.
- `0x18` sleep timeout in units of 30 s (0 = never). Driver choices: 30, 60, 90, 120, 180, 240, 300, 600, 900, 1200 s. Factory value is 4 (2 min).
- `0x3a + 2*i` per effect (i = index in `EFFECT_ORDER`): `[brightness 0–4][speed<<4 | colour]`, where colour indexes the palette from cmd 0x0A.

## Key matrix (cmd 0x03/0x83, sub = layer)
128 entries × 4 bytes. Index = the `led` number in `keys.json` (it comes from the last field of the `K<n>=` lines in `KB.ini`). Entry 127 = `00 00 5a a5` marker.
- `00 mm 00 kk`: keyboard key. mm = modifier mask (01 ctrl, 02 shift, 04 alt, 08 cmd/win, 10/20/40/80 right side), kk = HID usage.
- `02 00 uu uu`: consumer/media usage (big endian).
- `03 mode rep idx`: run macro idx (0-based). mode 1 = `rep` times, 2 = toggle, 4 = while held. The factory knob rotation entries `03 00 00 00/01` share this type with mode 0. Leave them alone.
- `07 ...`, `08 ...`: keyboard-internal functions (BT channels, OS mode, lighting keys, battery indicator). See `SPECIAL` in `keymap.py`, named from the factory Fn layer.
- `0d 00 00 00`: Fn.

Writing round-trips were verified on hardware (CapsLock→Esc written and read back). Actual keypress behaviour hasn't been confirmed by the user yet.

Open question: once, both layers read back as factory while the macro buffer and the LED block (side light still off) had kept their changes. The user had been unplugging the keyboard and probably testing the web UI, which has a "reset all keys" button. It's not yet known whether matrix writes survive a power cycle. If they don't, look for a save/commit command in the driver.

## Macros (cmd 0x05/0x85)
Header: N × `[addr u16 LE][size u16 LE]` (addr from buffer start), then per macro `[name_len_bytes][name UTF-16LE]` followed by 4-byte events:
`[type<<4 | delay>>16&0xf | 0x80 if release][delay>>8][delay&0xff][code]`, with the delay in ms after the event.
Types: 0 key (HID usage), 1 modifier (HID 0xe0–0xe7), 2 mouse button (1 L, 2 R, 4 M, 8, 0x10), 3/4 mouse move, 5 wheel. Taken from `OemDrv.exe` 0x4907b0. The macro→matrix tagging is at 0x490eb3 and the matrix entry builder at 0x4900d0.
A test macro "deneme" (types "au75 makro calisiyor") is stored as macro 1. Typing behaviour isn't confirmed yet.

## Battery
The AU75 does not report battery to the host. `KB.ini` has `ShowPower=0` and `CDevG5KB`'s ReadPower vtable slot (+0x20) is a stub (`xor eax,eax; ret 4`). On the keyboard, Fn+B in wireless mode lights F1–F10 green, about 10% each (confirmed by the user).

## Not done yet
- Per-key custom colours (effect 21). The per-key data path for G5KB hasn't been found. Cmd 0x0A is the palette, not per-key.
- Knob mode (`WheelMode`), polling rate, game mode.
- A native macOS app. The WebHID page covers the GUI use case.

## Safety
Recovery: `./au75 restore` (LED), `./au75 keymap reset` (keys), or hold Fn+Esc for 5 s (factory reset).
