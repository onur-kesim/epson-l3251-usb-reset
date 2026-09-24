# KRITER — `epson-usb` PyPI paketi

> **DONDURULDU — 24 Eyl 2026.** Bu dosya `epson-usb` işinin **İLK commit'idir** ve koddan ÖNCE gelir.
> Bu commit'ten sonra değişirse deneme **BAŞARISIZ** sayılır.
> Kaynak: `EPSON_USB_PYPI_IS_EMRI_2026-09-24.md` ADIM 1 (Onur'un kararları, 24 Eyl 2026).

- **K1** CI'da `python -m unittest discover -s epson_usb/tests -t .` → **Ran ≥ 66**, **skipped = 0**, çıkış 0.
- **K2** CI'da bir test sınıfı atlanırsa (örn. `epson_print_conf` test bağımlılığından çıkarılırsa) CI **kırmızı**.
  Kanıt: bu mutantın uygulandığı dalda CI'ın kırmızıya düştüğü koşu linki.
- **K3** `python epson_usb/tests/mutant_run.py` → **2/2 mutant yakalandı**, çıkış 0 (CI adımı).
- **K4** Temiz venv'de kurulmuş wheel: `import epson_usb` çalışır, paket meta verisinde lisans `MIT`.
