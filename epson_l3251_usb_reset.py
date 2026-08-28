#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epson_l3251_usb_reset.py  --  Epson L3251 Waste Ink Pad counter reset (USB)
================================================================================
Reaches the EEPROM over USB with the IEEE 1284.4 (D4) protocol, because the
Wi-Fi/SNMP path is closed in this printer's firmware. Talks to the Windows
printer channel (USBPRINT) directly: NO DRIVER REPLACEMENT (no Zadig) and NO
EXTERNAL DEPENDENCIES (Python's built-in ctypes only).

SAFETY
  * The default mode READS ONLY and takes a full backup. It writes nothing.
  * Resetting requires an explicit  --reset  ; a bank-0 backup is taken first.
  * --restore <file> writes the six counter cells back from a backup; a bank-0
    safety backup is taken first too, unless  --no-backup  is given.

USAGE
  Read state + take a backup (no writes):  py epson_l3251_usb_reset.py
  RESET (writes!):                         py epson_l3251_usb_reset.py --reset
  Restore from a backup:                   py epson_l3251_usb_reset.py --restore <file.json>
  With an explicit device id:               py epson_l3251_usb_reset.py --instance-id "USB\\VID_04B8&..."
  Show the full serial number:              py epson_l3251_usb_reset.py --show-serial
  Print the version:                        py epson_l3251_usb_reset.py --version
"""

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import struct
import sys
import time

__version__ = "0.1.0"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------- #
#  L3250-series EEPROM command parameters                                      #
# --------------------------------------------------------------------------- #
RKEY = [0x4A, 0x36]                                   # read/write model code (74,54)
WKEY = bytes([78, 98, 115, 106, 99, 98, 122, 98])    # "Nbsjcbzb"

# Waste ink counter groups: (addresses, divisor, label)
WASTE_COUNTERS = [
    ([0x30, 0x31], 6345, 'Main waste pad'),
    ([0x32, 0x33], 3416, 'Secondary pad'),
    ([0xFC, 0xFD], 1300, 'Borderless/platen pad'),
]
WASTE_ADDRS = [0x30, 0x31, 0x32, 0x33, 0xFC, 0xFD]


def build_read_cmd(addr):
    lo, hi = addr & 0xFF, (addr >> 8) & 0xFF
    payload = bytes([RKEY[0], RKEY[1], 0x41, 0xBE, 0xA0, lo, hi])
    return b"\x7c\x7c" + struct.pack("<H", len(payload)) + payload


def build_write_cmd(addr, val):
    lo, hi = addr & 0xFF, (addr >> 8) & 0xFF
    payload = bytes([RKEY[0], RKEY[1], 0x42, 0xBD, 0x21, lo, hi, val & 0xFF]) + WKEY
    return b"\x7c\x7c" + struct.pack("<H", len(payload)) + payload


# --------------------------------------------------------------------------- #
#  Win32                                                                       #
# --------------------------------------------------------------------------- #
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x1
FILE_SHARE_WRITE = 0x2
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
ERROR_IO_PENDING = 997
WAIT_TIMEOUT = 0x102
DIGCF_PRESENT = 0x02
DIGCF_DEVICEINTERFACE = 0x10


class GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]


USBPRINT_GUID = GUID(0x28d78fad, 0x5a12, 0x11d1,
                     (ctypes.c_ubyte * 8)(0xae, 0x5b, 0x00, 0x00, 0xf8, 0x03, 0xa8, 0xc2))


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("InterfaceClassGuid", GUID),
                ("Flags", wt.DWORD), ("Reserved", ctypes.POINTER(ctypes.c_ulong))]


class OVERLAPPED(ctypes.Structure):
    _fields_ = [("Internal", ctypes.c_void_p), ("InternalHigh", ctypes.c_void_p),
                ("Offset", wt.DWORD), ("OffsetHigh", wt.DWORD), ("hEvent", wt.HANDLE)]


setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
LPDWORD = ctypes.POINTER(wt.DWORD)
POVERLAPPED = ctypes.POINTER(OVERLAPPED)

kernel32.CreateFileW.restype = wt.HANDLE
kernel32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, wt.LPVOID, wt.DWORD, wt.DWORD, wt.HANDLE]
kernel32.CreateEventW.restype = wt.HANDLE
kernel32.CreateEventW.argtypes = [wt.LPVOID, wt.BOOL, wt.BOOL, wt.LPCWSTR]
kernel32.WriteFile.restype = wt.BOOL
kernel32.WriteFile.argtypes = [wt.HANDLE, wt.LPCVOID, wt.DWORD, LPDWORD, POVERLAPPED]
kernel32.ReadFile.restype = wt.BOOL
kernel32.ReadFile.argtypes = [wt.HANDLE, wt.LPVOID, wt.DWORD, LPDWORD, POVERLAPPED]
kernel32.WaitForSingleObject.restype = wt.DWORD
kernel32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
kernel32.GetOverlappedResult.restype = wt.BOOL
kernel32.GetOverlappedResult.argtypes = [wt.HANDLE, POVERLAPPED, LPDWORD, wt.BOOL]
kernel32.CancelIo.restype = wt.BOOL
kernel32.CancelIo.argtypes = [wt.HANDLE]
kernel32.CloseHandle.restype = wt.BOOL
kernel32.CloseHandle.argtypes = [wt.HANDLE]
setupapi.SetupDiGetClassDevsW.restype = wt.HANDLE
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.c_void_p, wt.LPCWSTR, wt.HWND, wt.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.restype = wt.BOOL
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, ctypes.c_void_p]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wt.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, LPDWORD, ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.restype = wt.BOOL
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [wt.HANDLE]


def find_usbprint_paths():
    paths = []
    hdev = setupapi.SetupDiGetClassDevsW(ctypes.byref(USBPRINT_GUID), None, None,
                                         DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if not hdev or hdev == INVALID_HANDLE_VALUE:
        return paths
    try:
        idx = 0
        while True:
            ifdata = SP_DEVICE_INTERFACE_DATA()
            ifdata.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
            if not setupapi.SetupDiEnumDeviceInterfaces(hdev, None, ctypes.byref(USBPRINT_GUID),
                                                        idx, ctypes.byref(ifdata)):
                break
            idx += 1
            req = wt.DWORD(0)
            setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(ifdata), None, 0,
                                                      ctypes.byref(req), None)
            if req.value == 0:
                continue
            buf = ctypes.create_string_buffer(req.value)
            cbsize = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
            ctypes.memmove(buf, struct.pack("I", cbsize), 4)
            if setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(ifdata), buf,
                                                         req.value, None, None):
                paths.append(ctypes.wstring_at(ctypes.addressof(buf) + 4))
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(hdev)
    return paths


def candidate_paths(instance_id=None):
    cands = list(find_usbprint_paths())
    # device instance id from the user or the environment variable (else: auto-discovery only)
    iid = instance_id or os.environ.get("EPSON_INSTANCE_ID")
    if iid:
        cands.append(r"\\?\%s#{28d78fad-5a12-11d1-ae5b-0000f803a8c2}" % iid.replace("\\", "#"))
    expanded = []
    for p in cands:
        expanded.append(p)
        for mi in ("mi_00", "mi_01", "mi_02"):
            expanded.append(re.sub(r"mi_0\d", mi, p, flags=re.IGNORECASE))
    seen, out = set(), []
    for p in expanded:
        if "VID_04B8" not in p.upper():
            continue
        k = p.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    out.sort(key=lambda p: (0 if "MI_01" in p.upper() else 1))
    return out


def open_device(path):
    h = kernel32.CreateFileW(path, GENERIC_READ | GENERIC_WRITE,
                             FILE_SHARE_READ | FILE_SHARE_WRITE, None,
                             OPEN_EXISTING, FILE_FLAG_OVERLAPPED, None)
    if not h or h == INVALID_HANDLE_VALUE:
        raise OSError('CreateFile failed: WinErr %s' % ctypes.get_last_error())
    return h


def _ov_io(func, h, data_or_len, timeout_ms, reading):
    ov = OVERLAPPED()
    ov.hEvent = kernel32.CreateEventW(None, True, False, None)
    try:
        nbytes = wt.DWORD(0)
        if reading:
            buf = ctypes.create_string_buffer(data_or_len)
            ok = func(h, buf, data_or_len, ctypes.byref(nbytes), ctypes.byref(ov))
        else:
            buf = ctypes.create_string_buffer(data_or_len, len(data_or_len))
            ok = func(h, buf, len(data_or_len), ctypes.byref(nbytes), ctypes.byref(ov))
        if not ok:
            err = ctypes.get_last_error()
            if err == ERROR_IO_PENDING:
                if kernel32.WaitForSingleObject(ov.hEvent, timeout_ms) == WAIT_TIMEOUT:
                    kernel32.CancelIo(h)
                    return None
                got = wt.DWORD(0)
                if not kernel32.GetOverlappedResult(h, ctypes.byref(ov), ctypes.byref(got), True):
                    return None
                nbytes = got
            else:
                raise OSError('I/O error WinErr %s' % err)
        return buf.raw[:nbytes.value] if reading else nbytes.value
    finally:
        kernel32.CloseHandle(ov.hEvent)


def write_all(h, data, timeout_ms=3000):
    return _ov_io(kernel32.WriteFile, h, data, timeout_ms, False)


def read_some(h, maxlen=1024, timeout_ms=2000):
    return _ov_io(kernel32.ReadFile, h, maxlen, timeout_ms, True)


# --------------------------------------------------------------------------- #
#  D4 (IEEE 1284.4) - packet-aligned reading                                   #
# --------------------------------------------------------------------------- #
CMD_ENTER_D4 = b"\x00\x00\x00\x1b\x01@EJL 1284.4\n@EJL\n@EJL\n"


class D4:
    def __init__(self, h):
        self.h = h
        self.buf = b""

    def _fill(self, timeout_ms):
        c = read_some(self.h, 1024, timeout_ms)
        if c:
            self.buf += c
            return True
        return False

    def drain(self, ms=300):
        while read_some(self.h, 1024, ms):
            pass
        self.buf = b""

    def send(self, psid, ssid, payload, credit=1, control=0):
        pkt = struct.pack(">BBHBB", psid, ssid, 6 + len(payload), credit, control) + payload
        write_all(self.h, pkt)

    def recv(self, timeout_ms=2500):
        while len(self.buf) < 6:
            if not self._fill(timeout_ms):
                return None
        psid, ssid, length, credit, control = struct.unpack(">BBHBB", self.buf[:6])
        if length < 6:
            self.buf = self.buf[6:]
            return (psid, ssid, length, credit, control, b"")
        while len(self.buf) < length:
            if not self._fill(timeout_ms):
                break
        payload = self.buf[6:length]
        self.buf = self.buf[length:]
        return (psid, ssid, length, credit, control, payload)


# --------------------------------------------------------------------------- #
#  D4 session: send a command / read the reply over the EPSON-CTRL channel     #
# --------------------------------------------------------------------------- #
class D4Session:
    def __init__(self, path):
        self.h = open_device(path)
        self.d = D4(self.h)
        self.rev = 0x20

    def close(self):
        try:
            kernel32.CloseHandle(self.h)
        except Exception:
            pass

    def connect(self):
        self.d.drain(300)
        write_all(self.h, CMD_ENTER_D4)
        time.sleep(0.2)
        self.d.recv(2500)                                   # enter reply
        # Init: 0x20 -> result 0x02 & rev 0x10 -> retry with 0x10
        rev, ok = 0x20, False
        for _ in range(3):
            self.d.send(0, 0, bytes([0x00, rev]), credit=1)
            r = self.d.recv(2500)
            pl = r[5] if r else b""
            if len(pl) >= 3 and pl[0] == 0x80:
                if pl[1] == 0x00:
                    ok = True
                    break
                if pl[2] and pl[2] != rev:
                    rev = pl[2]
                    continue
            break
        if not ok:
            raise IOError('D4 Init failed (the printer did not answer D4)')
        self.rev = rev
        # OpenChannel EPSON-CTRL socket 2 (rev 0x10 -> initCredit field included)
        if rev == 0x10:
            oc = struct.pack(">BBBHHHH", 0x01, 0x02, 0x02, 0x0100, 0x0100, 0x0000, 0x0000)
        else:
            oc = struct.pack(">BBBHHH", 0x01, 0x02, 0x02, 0x0100, 0x0100, 0x0000)
        self.d.send(0, 0, oc, credit=1)
        rep = self.d.recv(2500)
        pl = rep[5] if rep else b""
        if not (len(pl) >= 2 and pl[0] == 0x81 and pl[1] == 0x00):
            raise IOError('OpenChannel failed: %r' % (pl,))

    def _credit_request(self):
        'Take send-credit for the host (FROM the printer).'
        if self.rev == 0x10:
            cr = struct.pack(">BBBHH", 0x04, 0x02, 0x02, 0x0080, 0xFFFF)
        else:
            cr = struct.pack(">BBBH", 0x04, 0x02, 0x02, 0x0008)
        self.d.send(0, 0, cr, credit=1)
        for _ in range(4):
            r = self.d.recv(1500)
            if r is None:
                break
            if r[5] and r[5][0] == 0x84:
                break

    def cmd(self, payload, tries=14):
        'Send one command on the EPSON-CTRL channel and return the data reply.'
        self._credit_request()                                  # host -> send credit
        self.d.send(0, 0, struct.pack(">BBBH", 0x03, 0x02, 0x02, 0x0008), credit=1)  # reply credit for the printer
        self.d.recv(1200)                                       # CreditReply (ignored)
        self.d.send(0x02, 0x02, payload, credit=8)              # command
        for _ in range(tries):
            p = self.d.recv(2000)
            if p is None:
                continue
            if p[0] == 0x02 and p[5]:                           # data from the EPSON-CTRL channel
                return p[5]
        return None

    def read_eeprom(self, addr):
        resp = self.cmd(build_read_cmd(addr))
        if not resp:
            return None
        m = re.search(rb"EE:([0-9A-Fa-f]{6})", resp)
        if not m:
            return None
        h = m.group(1).decode()
        ra = int(h[0:4], 16)
        val = int(h[4:6], 16)
        if ra != addr:
            return None
        return val

    def write_eeprom(self, addr, val):
        resp = self.cmd(build_write_cmd(addr, val))
        return bool(resp) and (b":OK;" in resp)


# --------------------------------------------------------------------------- #
#  High-level operations                                                       #
# --------------------------------------------------------------------------- #
def read_waste(sess):
    print('\n  Waste ink counters:')
    out = []
    for addrs, div, label in WASTE_COUNTERS:
        vals = []
        for a in addrs:
            v = sess.read_eeprom(a)
            vals.append(v)
        if None in vals:
            print('    - %-26s: READ FAILED (%r)' % (label, vals))
            out.append((label, None, None))
            continue
        raw = int("".join("%02X" % v for v in vals), 16)
        pct = (raw / div) * 100.0
        flag = '   <-- FULL' if pct >= 100 else ""
        print('    - %-26s: %%%6.2f  (raw=%d)%s' % (label, pct, raw, flag))
        out.append((label, raw, pct))
    return out


def read_serial(sess):
    try:
        chars = []
        for a in range(0x0644, 0x064E):
            v = sess.read_eeprom(a)
            if v and 32 <= v < 127:
                chars.append(chr(v))
        return "".join(chars).strip()
    except Exception:
        return '(unreadable)'


def mask_serial(serial):
    """Show only the last 4 characters; empty/unreadable values pass through unchanged."""
    if not serial or serial == '(unreadable)':
        return serial
    if len(serial) <= 4:
        return '*' * len(serial)
    return '*' * (len(serial) - 4) + serial[-4:]


def backup_bank0(sess):
    print('\n  Taking a full bank-0 EEPROM backup (0x00-0xFF)...')
    cells = {}
    for a in range(0x00, 0x100):
        v = sess.read_eeprom(a)
        cells["%02X" % a] = v
        if a % 32 == 31:
            print('    ...0x%02X done' % a)
    ok = sum(1 for v in cells.values() if v is not None)
    print('    %d/256 cells read.' % ok)
    return cells


def save_backup_file(cells):
    """Write a bank-0 backup next to the script (not the caller's CWD) and print its absolute path."""
    ts = time.strftime("%Y%m%d_%H%M%S")
    bkp = "epson_backup_bank0_%s.json" % ts
    bkp_path = os.path.join(SCRIPT_DIR, bkp)
    with open(bkp_path, "w", encoding="utf-8") as f:
        json.dump({"time": ts, "bank0": cells}, f, indent=2)
    print('  Backup saved: %s' % bkp_path)
    return bkp_path


def do_reset(sess):
    print('\n  >>> RESET: writing 0 to the waste counter cells...')
    all_ok = True
    for a in WASTE_ADDRS:
        ok = sess.write_eeprom(a, 0)
        after = sess.read_eeprom(a)
        status = "OK" if (ok and after == 0) else 'FAILED (read back=%r)' % after
        print("    - 0x%04X <- 0   [%s]" % (a, status))
        all_ok &= (ok and after == 0)
    return all_ok


def resolve_input_path(path):
    """A bare filename (no directory component) is looked up in the CWD first, then next to the script."""
    if os.path.isfile(path):
        return path
    if not os.path.dirname(path):
        candidate = os.path.join(SCRIPT_DIR, path)
        if os.path.isfile(candidate):
            return candidate
    return path


def do_restore(sess, path):
    path = resolve_input_path(path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    cells = data.get("bank0", {})
    print('\n  Restoring from backup: %s' % path)
    n = 0
    for a in WASTE_ADDRS:
        key = "%02X" % a
        if key in cells and cells[key] is not None:
            if sess.write_eeprom(a, int(cells[key])):
                print("    - 0x%04X <- %d" % (a, cells[key]))
                n += 1
    print('    %d cells restored.' % n)


# --------------------------------------------------------------------------- #
def connect_any(instance_id=None):
    paths = candidate_paths(instance_id)
    last = None
    for p in paths:
        try:
            s = D4Session(p)
        except OSError as e:
            last = e
            continue
        try:
            s.connect()
            return s, p
        except Exception as e:
            last = e
            s.close()
    raise IOError('Could not establish a D4 session. Last error: %s' % last)


def main():
    if sys.platform != "win32":
        print('Windows only.')
        sys.exit(1)
    ap = argparse.ArgumentParser(description='Epson L3251 waste ink pad counter reset over USB (D4)')
    ap.add_argument("--reset", action="store_true", help='RESET the counters (writes to the printer!)')
    ap.add_argument("--restore", metavar='FILE', help='Write the six counter cells back from a backup JSON')
    ap.add_argument("--no-backup", action="store_true", help='Do NOT take a backup before writing')
    ap.add_argument("--instance-id", metavar="IID",
                     default=os.environ.get("EPSON_INSTANCE_ID"),
                     help='Device instance id (example: USB\\VID_04B8&PID_118A&MI_00\\<INSTANCE>). If omitted, only automatic discovery is used.')
    ap.add_argument("--show-serial", action="store_true", help='Print the full serial number instead of the masked form')
    ap.add_argument("--version", action="version", version="%(prog)s " + __version__)
    args = ap.parse_args()

    print("=" * 70)
    print('  EPSON L3251  Waste Ink Pad  USB/D4 counter reset  v%s' % __version__)
    print("=" * 70)

    try:
        sess, path = connect_any(args.instance_id)
    except Exception as e:
        print('\n  !! Could not connect:', e)
        print('  Is the printer connected over USB and powered on? Another program may be holding it.')
        sys.exit(2)

    print('  Connected (USB/D4, revision 0x%02X).' % sess.rev)
    serial = read_serial(sess)
    print('  Serial:', serial if args.show_serial else mask_serial(serial))

    try:
        if args.restore:
            read_waste(sess)
            if args.no_backup:
                print('\n  --no-backup given: skipping the safety backup before restore.')
            else:
                cells = backup_bank0(sess)
                save_backup_file(cells)
            do_restore(sess, args.restore)
            print('\n  After restore:')
            read_waste(sess)
            return

        before = read_waste(sess)

        if not args.reset:
            print('\n  (READ-ONLY mode - nothing was written.)')
            if not args.no_backup:
                cells = backup_bank0(sess)
                save_backup_file(cells)
            print('\n  Add  --reset  to the command to reset the counters.')
            return

        # --- reset path ---
        if not args.no_backup:
            cells = backup_bank0(sess)
            save_backup_file(cells)

        ok = do_reset(sess)
        print('\n  State after the reset:')
        read_waste(sess)
        if ok:
            print('\n  DONE. Power the printer OFF and ON with its own button, then check the error.')
        else:
            print('\n  WARNING: some cells could not be reset; check the state above.')
    finally:
        sess.close()


if __name__ == "__main__":
    main()
