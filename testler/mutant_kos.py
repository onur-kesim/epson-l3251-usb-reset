#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
testler/mutant_kos.py -- EF-3: mutant kaniti.

read_waste() icindeki LE (little-endian) cozme satirini bilerek big-endian'a
cevirir, testleri ayri bir alt-surecte tekrar kosar (beklenen: KIRMIZI),
sonra hedef dosyayi harfiyen eski haline dondurur -- calisma dizini
mutasyondan etkilenmeden temiz kalir. Kirmizi yanmiyorsa test kordur ve bu
script BASARISIZ (nonzero exit code) ile biter.

Donanim YOK, ag YOK, gercek yaziciya YAZMA -- yalnizca kaynak dosyada bir
metin degisikligi yapip geri alir ve `python -m unittest discover testler`i
iki kez calistirir. GOREV_CLAUDE_CODE_EF_testler_ve_ci.md / EF-3.
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET = REPO_ROOT / "epson_l3251_usb_reset.py"

ORIGINAL_LINE = "        raw = sum(v << (8 * i) for i, v in enumerate(vals))     # little-endian\n"
MUTANT_LINE = (
    "        raw = sum(v << (8 * (len(vals) - 1 - i)) for i, v in enumerate(vals))"
    "     # MUTANT (EF-3): big-endian -- kasitli hata, mutant_kos.py tarafindan geri alinir\n"
)


def run_tests():
    """testler/ altindaki tum testleri ayri bir alt-surecte kosar.
    Donus kodu 0 ise yesil (SAGLAM), degilse kirmizidir (MUTANT beklenen hali)."""
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


def main():
    original_bytes = TARGET.read_bytes()

    print("== 1/2: SAGLAM kod ile testler ==")
    rc_good, out_good, err_good = run_tests()
    sys.stdout.write(out_good)
    if err_good.strip():
        sys.stderr.write(err_good)
    saglam = "yesil" if rc_good == 0 else "kirmizi"

    print("\n== 2/2: MUTANT (big-endian) kod ile testler ==")
    _swap(ORIGINAL_LINE, MUTANT_LINE)
    try:
        rc_mut, out_mut, err_mut = run_tests()
    finally:
        # Dosyayi ne olursa olsun harfiyen eski haline dondur.
        _swap(MUTANT_LINE, ORIGINAL_LINE)
        restored_bytes = TARGET.read_bytes()
        if restored_bytes != original_bytes:
            sys.stderr.write("MUTANT_KOS HATA: dosya tam olarak eski haline donmedi!\n")
            sys.exit(3)
    sys.stdout.write(out_mut)
    if err_mut.strip():
        sys.stderr.write(err_mut)
    mutant = "yesil" if rc_mut == 0 else "kirmizi"

    print("\nSAGLAM=%s MUTANT=%s" % (saglam, mutant))

    if saglam != "yesil":
        sys.stderr.write("BASARISIZ: saglam kod testleri gecmiyor.\n")
        sys.exit(1)
    if mutant == "yesil":
        sys.stderr.write("BASARISIZ: mutant KIRMIZI yanmadi -- test kor. Gorev BASARISIZ.\n")
        sys.exit(1)

    print("OK: mutant kanitlandi (saglam kod yesil, big-endian mutant kirmizi).")


if __name__ == "__main__":
    main()
