#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
testler/test_cozucu.py -- EF-2: donanimsiz, agsiz cozucu testleri.

Yalniz stdlib `unittest`. Bu dosya hicbir noktada gercek USB/D4 baglantisi
acmaz: epson_l3251_usb_reset'in saf-bayt fonksiyonlarini ve sahte (fake) bir
EEPROM oturumuyla read_waste/read_extras/main() akisini sinar. Donanim YOK,
ag YOK. GOREV_CLAUDE_CODE_EF_testler_ve_ci.md / EF-2.
"""
import contextlib
import hashlib
import io
import json
import os
import struct
import sys
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import epson_l3251_usb_reset as ep

GOLDEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "altin_kume_cozucu.json")


def _load_golden():
    with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class FakeSession:
    """D4Session'i donanimsiz taklit eder: EEPROM durumu duz bir dict, yazmalar
    gercek yazicIya degil write_calls listesine gider."""

    def __init__(self, values=None, default=0):
        self.values = dict(values or {})
        self.default = default
        self.write_calls = []
        self.rev = 0x20

    def read_eeprom(self, addr):
        return self.values.get(addr, self.default)

    def write_eeprom(self, addr, val):
        self.write_calls.append((addr, val))
        self.values[addr] = val
        return True

    def close(self):
        pass


class GoldenSetDecodeTests(unittest.TestCase):
    """EF-2.1: altin kumenin her satiri icin LE cozme ve yuzde dogru mu."""

    def test_every_row_decodes_correctly(self):
        golden = _load_golden()
        self.assertGreaterEqual(len(golden["vakalar"]), 4)
        for i, case in enumerate(golden["vakalar"]):
            with self.subTest(case=i, kaynak=case.get("kaynak")):
                self.assertTrue(case.get("kaynak"), "kaynak alani zorunlu")
                lo = int(case["0x30"], 16)
                hi = int(case["0x31"], 16)
                fake = FakeSession({0x30: lo, 0x31: hi})
                with contextlib.redirect_stdout(io.StringIO()):
                    out = ep.read_waste(fake)
                label, raw, pct = out[0]
                self.assertEqual(label, ep.WASTE_COUNTERS[0][3])
                self.assertEqual(raw, case["beklenen_le"])
                self.assertAlmostEqual(pct, case["beklenen_yuzde"], places=2)
                self.assertEqual(pct >= 100.0, bool(case["yazici_hata_verdi_mi"]))

    def test_mirror_case_all_agree_at_seventeen(self):
        golden = _load_golden()
        mirror = golden["ayna_vakasi"]
        self.assertTrue(mirror.get("kaynak"))
        values = {}
        for lo_hex, hi_hex in mirror["adres_ciftleri"]:
            values[int(lo_hex, 16)] = mirror["beklenen_deger"]
            values[int(hi_hex, 16)] = 0
        fake = FakeSession(values)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ep.read_extras(fake)
        self.assertNotIn("DISAGREE", buf.getvalue())
        for lo_hex, _ in mirror["adres_ciftleri"]:
            self.assertEqual(fake.read_eeprom(int(lo_hex, 16)), mirror["beklenen_deger"])


class FrameBuilderTests(unittest.TestCase):
    """EF-2.2 / EF-2.3: komut cerceveleri bayt bayt beklenen degerde mi."""

    def test_build_read_cmd_0x30(self):
        # 7c7c + uzunluk(LE) + rkey(0x4A,0x36) + opcode 0x41 + tumleyen 0xBE +
        # donduren 0xA0 + adres(lo,hi) -- bkz. build_read_cmd docstring/yorum.
        expected = bytes.fromhex("7c7c07004a3641bea03000")
        self.assertEqual(ep.build_read_cmd(0x30), expected)

    def test_build_write_cmd_0x30_zero(self):
        # ayni cerceve + deger baytI + WKEY ("Nbsjcbzb").
        expected = bytes.fromhex("7c7c10004a3642bd213000004e62736a63627a62")
        self.assertEqual(ep.build_write_cmd(0x30, 0), expected)

    def test_build_service_rw_cmd_frame(self):
        serial = "TEST-SERIAL-01"
        cmd = ep.build_service_rw_cmd(serial)
        digest = hashlib.sha1(serial.encode("ascii")).digest()
        self.assertEqual(len(digest), 20)
        self.assertEqual(len(cmd), 2 + 2 + 21)
        self.assertEqual(cmd[:2], b"rw")
        self.assertEqual(struct.unpack("<H", cmd[2:4])[0], 21)
        self.assertEqual(cmd[4], 0x00)
        self.assertEqual(cmd[5:], digest)


class CellTableTests(unittest.TestCase):
    """EF-2.4: FULL_RESET_CELLS / RESTORE_ADDRS."""

    def test_full_reset_cells_has_14_entries(self):
        self.assertEqual(len(ep.FULL_RESET_CELLS), 14)

    def test_three_cells_reset_to_0x5e(self):
        d = dict(ep.FULL_RESET_CELLS)
        for addr in (0x36, 0x37, 0xFF):
            self.assertEqual(d[addr], 0x5E)

    def test_restore_addrs_covers_full_reset_and_waste(self):
        expected = set(a for a, _ in ep.FULL_RESET_CELLS) | set(ep.WASTE_ADDRS)
        self.assertEqual(set(ep.RESTORE_ADDRS), expected)


class MirrorCellsTests(unittest.TestCase):
    """EF-2.5: MIRROR_CELLS uc cift; uyusmazlik uyarisi tetikleniyor."""

    def test_mirror_cells_has_three_pairs(self):
        self.assertEqual(len(ep.MIRROR_CELLS), 3)

    def test_mismatch_triggers_warning(self):
        fake = FakeSession({0x30: 17, 0x31: 0, 0x34: 17, 0x35: 0, 0xC0: 5, 0xC1: 0})
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ep.read_extras(fake)
        self.assertIn("DISAGREE", buf.getvalue())

    def test_agreement_does_not_trigger_warning(self):
        fake = FakeSession({0x30: 17, 0x31: 0, 0x34: 17, 0x35: 0, 0xC0: 17, 0xC1: 0})
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ep.read_extras(fake)
        self.assertNotIn("DISAGREE", buf.getvalue())


class SecurityGateTests(unittest.TestCase):
    """EF-2.6: argumansiz main() yolunun hicbir yazma cagrisi uretmedigi.

    write_eeprom sahte bir nesneyle sarilir; cagri sayisi 0 olmali.
    main() Windows disinda hemen cikar (main() basindaki platform kontrolu),
    bu yuzden CI (ubuntu-latest) uzerinde de asil write-path mantigini
    sinayabilmek icin sys.platform "win32" olarak yamanir -- gercek Win32
    API'lerine (setupapi/kernel32/cfgmgr32) hic dokunulmaz, cunku
    connect_any() da FakeSession donduren bir sahteyle degistirilir.
    """

    def test_main_with_no_args_never_writes(self):
        fake = FakeSession()
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch.object(ep, "connect_any", return_value=(fake, "FAKE-PATH")), \
             mock.patch.object(ep, "save_backup_file", return_value="dummy-backup.json"), \
             mock.patch.object(sys, "argv", ["epson_l3251_usb_reset.py"]), \
             contextlib.redirect_stdout(io.StringIO()):
            ep.main()
        self.assertEqual(fake.write_calls, [], "write_eeprom cagri sayisi 0 olmali")


if __name__ == "__main__":
    unittest.main()
