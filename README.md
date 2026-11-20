# au75-rgb

AULA AU75 klavyeyi macOS'tan (ve Chrome olan her bilgisayardan) yönetmek için araçlar: ışık, tuş atama, makro, uyku süresi. AULA'nın sadece Windows sürücüsü var, bu araçlar o sürücünün protokolünden çıkarıldı.

**Klavye USB kabloyla bağlı olmalı.** Ayarlar klavyenin hafızasına yazılır, kablosuz kullanınca da kalır.

## Arayüz

https://emincmg.github.io/au75-rgb/

Chrome, Edge ya da Opera ile aç, "Klavyeye bağlan"a bas. Kurulum gerekmez. Komut satırı aracı açıkken bağlanamaz.

## Komut satırı (macOS)

```sh
python3 -m venv .venv && .venv/bin/pip install hidapi

./au75 main off                    # tuş ışıklarını kapat
./au75 main effect 1               # sabit ışık (liste: ./au75 effects)
./au75 main color 2                # mavi
./au75 side off                    # kenar ışığını kapat

./au75 keymap                      # tuş atamaları
./au75 map capslock esc            # CapsLock -> Esc
./au75 map --fn p media:play       # Fn+P -> oynat/durdur
./au75 unmap capslock              # fabrika atamasına dön
./au75 keymap reset                # tüm tuşlar fabrika ayarına

./au75 macro set 1 imza "text:Selamlar" tap:enter
./au75 map --fn s macro:1          # Fn+S makroyu çalıştırır
./au75 macros

./au75 sleep 600                   # 10 dk sonra uyu
./au75 help
```

## Pil

Klavye pil seviyesini bilgisayara göndermiyor (resmi sürücü de okuyamıyor). Kablosuz modda **Fn + B** basılı tut: F1–F10'dan yanan her tuş yaklaşık %10.

## Sorun olursa

`./au75 restore` (ışık), `./au75 keymap reset` (tuşlar) ya da Fn+Esc'e 5 saniye basılı tut (fabrika ayarları).

Protokol detayları: [CLAUDE.md](CLAUDE.md)
