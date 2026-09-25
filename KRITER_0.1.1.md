# KRITER 0.1.1 — `epson-usb` PyPI paketi

> **DONDURULDU — 25 Eyl 2026.** Bu dosya `epson-usb` **0.1.1** işinin **İLK commit'idir** ve koddan ÖNCE gelir.
> Bu commit'ten sonra değişirse deneme **BAŞARISIZ** sayılır.
> Kaynak: `EPSON_USB_0.1.1_IS_EMRI_2026-09-25.md` ADIM 1. Tetik: Ircama'nın
> `epson_print_conf` #35 yorumu (issuecomment-5822154925) — iki kusur (gereksiz
> `requires-python >=3.10`; belgede isteğe bağlı olan PyUSB'nin meta veride zorunlu olması).

## Yürürlükteki: K1–K4 (`KRITER.md`, 24 Eyl 2026 — aynen)

- **K1** CI'da `python -m unittest discover -s epson_usb/tests -t .` → **Ran ≥ 66**, **skipped = 0**, çıkış 0.
- **K2** CI'da bir test sınıfı atlanırsa (örn. `epson_print_conf` test bağımlılığından çıkarılırsa) CI **kırmızı**.
  Kanıt: bu mutantın uygulandığı dalda CI'ın kırmızıya düştüğü koşu linki.
- **K3** `python epson_usb/tests/mutant_run.py` → **2/2 mutant yakalandı**, çıkış 0 (CI adımı).
- **K4** Temiz venv'de kurulmuş wheel: `import epson_usb` çalışır, paket meta verisinde lisans `MIT`.

## Yeni: K5, K6

- **K5** Wheel meta verisi: `Requires-Dist: pyusb` YALNIZ `extra == "pyusb"` koşuluyla. Temiz venv'de `pip install epson-usb` pyusb KURMAZ ve
  `import epson_usb` çalışır; `pip install "epson-usb[pyusb]"` pyusb'yi KURAR. (Belgede yazan kurulum yolu meta veride VAR olmalı.)
- **K6** `Requires-Python: >=3.9`. CI'da Python **3.9** işi K1 (Ran ≥ 66, skipped = 0) ve K3'ü (2/2) yeşil geçer.
  3.9'da host program kurulamazsa K6 BAŞARISIZ sayılır, "atla" DENMEZ.
