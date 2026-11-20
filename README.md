# au75-rgb

AULA AU75 klavyenin ışıklarını macOS'tan kontrol eden komut satırı aracı. AULA'nın sadece Windows sürücüsü var, bu araç onun protokolünden çıkarıldı.

**Klavye USB kabloyla bağlı olmalı.** Ayarlar klavyenin hafızasına yazılır, sonra kablosuz kullanınca da kalır.

```sh
python3 -m venv .venv && .venv/bin/pip install hidapi
./au75 side off     # kenar ışığını kapat
./au75 side on      # aç
./au75 readled      # LED bloğunu göster
./au75 restore      # led_backup.bin yedeğine dön
./au75 help
```

Bir sorun olursa: `./au75 restore` ya da Fn+Esc'e 5 saniye basılı tut (fabrika ayarları).

Protokol detayları: [CLAUDE.md](CLAUDE.md)
