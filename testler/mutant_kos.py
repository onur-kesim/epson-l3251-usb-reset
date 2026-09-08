#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
testler/mutant_kos.py -- EF-3: mutant kaniti (iki hedef).

epson_l3251_usb_reset.py'de LE (little-endian) cozme aritmetigi IKI ayri
yerde tekrarlanir:
  - read_waste()  icinde `raw = sum(v << (8 * i) ...)`   (ana atik sayaci)
  - read_extras() icinde `val = sum(v << (8 * i) ...)`   (MIRROR_CELLS aynalari)
Ilk surumde yalniz birincisi mutasyona ugratiliyordu; bagimsiz bir mutant
taramasi ikincisinin testsiz/kor kaldigini buldu (testler read_extras'i
cagiriyordu ama COZULEN sayiyi degil, yalniz uyari metnini veya sahte
oturumun ham girdisini kontrol ediyordu). Bu surum HER IKI hedefi de ayri
ayri mutasyona ugratir; ikisinden HANGISI bozulursa bozulsun suit KIRMIZI
yanmalidir.

Her hedef icin: satiri bilerek big-endian'a cevirir, testleri ayri bir
alt-surecte tekrar kosar (beklenen: KIRMIZI), sonra hedef dosyayi harfiyen
eski haline dondurur -- calisma dizini mutasyondan etkilenmeden temiz
kalir. Herhangi bir hedef kirmizi yanmiyorsa o hedefteki test kordur ve bu
script BASARISIZ (nonzero exit code) ile biter.

Donanim YOK, ag YOK, gercek yaziciya YAZMA -- yalnizca kaynak dosyada bir
metin degisikligi yapip geri alir ve her hedef icin
`python -m unittest discover testler`i calistirir.
GOREV_CLAUDE_CODE_EF_testler_ve_ci.md / EF-3 + kor-nokta duzeltmesi.
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET = REPO_ROOT / "epson_l3251_usb_reset.py"

# id'ler ilk bulunduklari satir numaralarindan geliyor (okunabilirlik icin);
# eslesme satir numarasina degil, tam metin icerigine gore yapilir, bu
# yuzden dosya ileride kayiverse de bu script kirilmaz -- yalniz TARGETS
# icindeki `original` satiri bulamazsa acikca hata verir.
TARGETS = [
    {
        "id": "587",
        "aciklama": "read_waste() ana atik sayaci LE cozme satiri",
        "original": "        raw = sum(v << (8 * i) for i, v in enumerate(vals))     # little-endian\n",
        "mutant": (
            "        raw = sum(v << (8 * (len(vals) - 1 - i)) for i, v in enumerate(vals))"
            "     # MUTANT (EF-3, 587): big-endian -- kasitli hata, mutant_kos.py geri alir\n"
        ),
    },
    {
        "id": "619",
        "aciklama": "read_extras() MIRROR_CELLS ayna LE cozme satiri",
        "original": "        val = sum(v << (8 * i) for i, v in enumerate(vals))\n",
        "mutant": (
            "        val = sum(v << (8 * (len(vals) - 1 - i)) for i, v in enumerate(vals))"
            "     # MUTANT (EF-3, 619): big-endian -- kasitli hata, mutant_kos.py geri alir\n"
        ),
    },
]


def run_tests():
    """testler/ altindaki tum testleri ayri bir alt-surecte kosar.
    Donus kodu 0 ise yesil, degilse kirmizidir."""
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "testler"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def _swap(old, new):
    text = TARGET.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(
            "MUTANT_KOS HATA: beklenen satir kaynak dosyada bulunamadi:\n  %r\n"
            "Kod degismis olabilir -- mutant_kos.py guncellenmeli." % old
        )
    text = text.replace(old, new, 1)
    TARGET.write_text(text, encoding="utf-8", newline="")


def run_mutant(target, original_bytes):
    """Tek bir hedefi mutasyona ugratir, testleri kosar, HER durumda (hata
    dahil) dosyayi bayt-bayt eski haline dondurur."""
    _swap(target["original"], target["mutant"])
    try:
        rc, out, err = run_tests()
    finally:
        _swap(target["mutant"], target["original"])
        restored = TARGET.read_bytes()
        if restored != original_bytes:
            sys.stderr.write(
                "MUTANT_KOS HATA: dosya hedef %s sonrasi tam olarak eski "
                "haline donmedi!\n" % target["id"]
            )
            sys.exit(3)
    return rc, out, err


def main():
    original_bytes = TARGET.read_bytes()

    print("== SAGLAM kod ile testler ==")
    rc_good, out_good, err_good = run_tests()
    sys.stdout.write(out_good)
    if err_good.strip():
        sys.stderr.write(err_good)
    saglam = "yesil" if rc_good == 0 else "kirmizi"

    mutant_results = {}
    for target in TARGETS:
        print("\n== MUTANT-%s (%s) ile testler ==" % (target["id"], target["aciklama"]))
        rc_mut, out_mut, err_mut = run_mutant(target, original_bytes)
        sys.stdout.write(out_mut)
        if err_mut.strip():
            sys.stderr.write(err_mut)
        mutant_results[target["id"]] = "yesil" if rc_mut == 0 else "kirmizi"

    summary = "SAGLAM=%s " % saglam + " ".join(
        "MUTANT-%s=%s" % (t["id"], mutant_results[t["id"]]) for t in TARGETS
    )
    print("\n" + summary)

    ok = True
    if saglam != "yesil":
        sys.stderr.write("BASARISIZ: saglam kod testleri gecmiyor.\n")
        ok = False
    for target in TARGETS:
        if mutant_results[target["id"]] == "yesil":
            sys.stderr.write(
                "BASARISIZ: MUTANT-%s (%s) KIRMIZI yanmadi -- test kor. "
                "Gorev BASARISIZ.\n" % (target["id"], target["aciklama"])
            )
            ok = False

    if not ok:
        sys.exit(1)

    print("OK: her iki mutant da kanitlandi (saglam=yesil, iki hedef de kirmizi).")


if __name__ == "__main__":
    main()
