#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
epson_usb_probe.py  --  Epson L3251 USB EEPROM READ probe (READ-ONLY)
============================================================================
Brings up the D4 (IEEE 1284.4) transport correctly, with packet-aligned reads
and the credit handshake, then sends the printer a single EEPROM READ (0x0030).
IT WRITES NOTHING. Talks to the Windows printer channel (USBPRINT) directly,
so no driver replacement is needed (no Zadig).

  py epson_usb_probe.py
  py epson_usb_probe.py --instance-id "USB\\VID_04B8&..."

Include the whole report below when you open an issue.
"""

import argparse
import ctypes
import ctypes.wintypes as wt
import os
import re
import struct
import sys
import time

__version__ = "0.1.0"

# ---- L3250-series EEPROM READ command --------------------------------------- #
RKEY = [0x4A, 0x36]
TEST_ADDR = 0x0030

def build_read_cmd(addr):
    lo, hi = addr & 0xFF, (addr >> 8) & 0xFF
    payload = bytes([RKEY[0], RKEY[1], 0x41, 0xBE, 0xA0, lo, hi])
    return b"\x7c\x7c" + struct.pack("<H", len(payload)) + payload

# ---- Win32 --------------------------------------------------------------- #
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

def winerr(code):
    names = {2: "FILE_NOT_FOUND", 5: "ACCESS_DENIED", 6: "INVALID_HANDLE",
             31: "GEN_FAILURE", 87: "INVALID_PARAMETER", 1117: "IO_DEVICE"}
    return "%s (%s)" % (code, names.get(code, "?"))

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

def derive_path_from_instanceid(instance_id):
    if not instance_id:
        return None
    return r"\\?\%s#{28d78fad-5a12-11d1-ae5b-0000f803a8c2}" % instance_id.replace("\\", "#")

def open_device(path):
    h = kernel32.CreateFileW(path, GENERIC_READ | GENERIC_WRITE,
                             FILE_SHARE_READ | FILE_SHARE_WRITE, None,
                             OPEN_EXISTING, FILE_FLAG_OVERLAPPED, None)
    if not h or h == INVALID_HANDLE_VALUE:
        raise OSError('CreateFile failed: WinErr %s' % winerr(ctypes.get_last_error()))
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
                raise OSError('I/O error: WinErr %s' % winerr(err))
        return buf.raw[:nbytes.value] if reading else nbytes.value
    finally:
        kernel32.CloseHandle(ov.hEvent)

def write_all(h, data, timeout_ms=3000):
    return _ov_io(kernel32.WriteFile, h, data, timeout_ms, False)

def read_some(h, maxlen=1024, timeout_ms=2500):
    return _ov_io(kernel32.ReadFile, h, maxlen, timeout_ms, True)

def hx(b):
    if b is None:
        return '(none/timeout)'
    if not b:
        return '(empty)'
    txt = "".join(chr(c) if 32 <= c < 127 else "." for c in b)
    return " ".join("%02x" % c for c in b) + "   |" + txt + "|"

# --------------------------------------------------------------------------- #
#  D4 (IEEE 1284.4) - packet aligned                                           #
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

    def drain(self, ms=400):
        while read_some(self.h, 1024, ms):
            pass
        self.buf = b""

    def send(self, psid, ssid, payload, credit=0, control=0):
        pkt = struct.pack(">BBHBB", psid, ssid, 6 + len(payload), credit, control) + payload
        write_all(self.h, pkt)
        return pkt

    def recv(self, timeout_ms=3000):
        'Read one complete D4 packet, packet-aligned: 6-byte header + payload per length.'
        while len(self.buf) < 6:
            if not self._fill(timeout_ms):
                return None
        psid, ssid, length, credit, control = struct.unpack(">BBHBB", self.buf[:6])
        if length < 6:
            self.buf = self.buf[6:]     # malformed/short packet, drop it
            return (psid, ssid, length, credit, control, b"")
        need = length
        while len(self.buf) < need:
            if not self._fill(timeout_ms):
                break
        payload = self.buf[6:need]
        self.buf = self.buf[need:]
        return (psid, ssid, length, credit, control, payload)

def show_pkt(tag, p):
    if p is None:
        print('      %s: (no reply)' % tag)
        return
    psid, ssid, length, credit, control, payload = p
    print("      %s: sock=%d/%d len=%d credit=%d ctrl=0x%02x  payload=%s"
          % (tag, psid, ssid, length, credit, control,
             hx(payload) if payload else '(empty)'))

def run_d4(path):
    print('--- D4 connection ---')
    try:
        h = open_device(path)
    except OSError as e:
        print('  Could not open device:', e)
        return None
    try:
        d = D4(h)
        d.drain(300)

        # 1) Leave packet mode / enter D4
        print("  [1] Enter-D4 (EJL)...")
        write_all(h, CMD_ENTER_D4)
        time.sleep(0.2)
        show_pkt("enter", d.recv(2500))

        # 2) Init: try 0x20; result=0x02 & rev=0x10 -> set ACTIVE revision to 0x10 and retry
        print("  [2] Init...")
        rev, init_ok = 0x20, False
        for _ in range(3):
            d.send(0, 0, bytes([0x00, rev]), credit=1)
            r = d.recv(2500)
            show_pkt("init(rev=0x%02x)" % rev, r)
            pl = r[5] if r else b""
            if len(pl) >= 3 and pl[0] == 0x80:
                result, prev = pl[1], pl[2]
                print('      -> result=0x%02x, printer revision=0x%02x' % (result, prev))
                if result == 0x00:
                    init_ok = True
                    break
                if prev and prev != rev:
                    rev = prev
                    continue
            break
        if not init_ok:
            print('      Init failed.')
            return None
        print('      -> ACTIVE REVISION = 0x%02x (later commands use this format)' % rev)

        # 3) OpenChannel (EPSON-CTRL socket 2). On REV 0x10 an initCredit field IS ADDED (8 fields).
        print('  [3] OpenChannel (EPSON-CTRL=2, rev 0x%02x format)...' % rev)
        if rev == 0x10:
            oc = struct.pack(">BBBHHHH", 0x01, 0x02, 0x02, 0x0100, 0x0100, 0x0000, 0x0000)
        else:
            oc = struct.pack(">BBBHHH", 0x01, 0x02, 0x02, 0x0100, 0x0100, 0x0000)
        d.send(0, 0, oc, credit=1)
        rep = d.recv(2500)
        show_pkt("open", rep)
        pl = rep[5] if rep else b""
        if not (len(pl) >= 2 and pl[0] == 0x81):
            print('      No OpenChannelReply.')
            return None
        result = pl[1]
        granted = struct.unpack(">H", pl[10:12])[0] if len(pl) >= 12 else 0
        print("      -> result=0x%02x, grantedCredit=%d" % (result, granted))
        # EPSON-CTRL channel credit: grantedCredit + the piggyback credit of the incoming packet
        ch_credit = granted + (rep[3] if rep else 0)

        # 4) UNCONDITIONAL CreditRequest: take send-credit from the printer for the EPSON-CTRL channel.
        #    (Without it the command is refused with 'no credit granted' = error 0x81.)
        print('  [4] CreditRequest (take credit for the channel)...')
        if rev == 0x10:
            cr = struct.pack(">BBBHH", 0x04, 0x02, 0x02, 0x0080, 0xFFFF)
        else:
            cr = struct.pack(">BBBH", 0x04, 0x02, 0x02, 0x0008)
        d.send(0, 0, cr, credit=1)
        for _ in range(4):
            crr = d.recv(2000)
            show_pkt("creditreq", crr)
            if crr is None:
                break
            cpl = crr[5]
            if cpl and cpl[0] == 0x84:            # CreditRequestReply
                add = struct.unpack(">H", cpl[4:6])[0] if len(cpl) >= 6 else 0
                print('      -> addCredit granted to the channel = %d' % add)
                break

        # 5a) Give the printer REPLY credit (Credit 0x03) so that it can send its answer
        print('  [5a] Credit -> printer (so it can send its reply)...')
        d.send(0, 0, struct.pack(">BBBH", 0x03, 0x02, 0x02, 0x0008), credit=1)
        show_pkt("credit->printer", d.recv(1500))

        # 5b) Send the EEPROM READ command and read the reply PERSISTENTLY (it can arrive late)
        print('  [5b] Sending EEPROM READ (0x0030)...')
        d.send(0x02, 0x02, build_read_cmd(TEST_ADDR), credit=8)
        got = None
        for i in range(10):
            p = d.recv(2000)
            show_pkt("read#%d" % (i + 1), p)
            if p and p[5] and b"EE:" in p[5]:
                got = p[5]
                break
        if got:
            print('  >>> SUCCESS: EEPROM reply received. The USB path is open.')
            return ("d4", got)
        return None
    finally:
        kernel32.CloseHandle(h)

# --------------------------------------------------------------------------- #
def candidate_paths(instance_id=None):
    cands = []
    try:
        cands.extend(find_usbprint_paths())
    except Exception as e:
        print('  SetupAPI error:', e)
    derived = derive_path_from_instanceid(instance_id)
    if derived:
        cands.append(derived)
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
    # MI_01 was the only reachable channel on this printer -> try it first
    out.sort(key=lambda p: (0 if "MI_01" in p.upper() else 1))
    return out

def main():
    if sys.platform != "win32":
        print('Windows only.')
        sys.exit(1)
    print("=" * 68)
    print('  EPSON L3251  USB EEPROM READ PROBE  (READ-ONLY)  v%s' % __version__)
    print("=" * 68)
    ap = argparse.ArgumentParser(description='Epson L3251 USB EEPROM read probe (READ-ONLY)')
    ap.add_argument("--instance-id", metavar="IID",
                     default=os.environ.get("EPSON_INSTANCE_ID"),
                     help='Device instance id (example: USB\\VID_04B8&PID_118A&MI_00\\<INSTANCE>). If omitted, only automatic discovery is used.')
    ap.add_argument("--version", action="version", version="%(prog)s " + __version__)
    args = ap.parse_args()
    paths = candidate_paths(args.instance_id)
    if not paths:
        print('No Epson USBPRINT path found. Is the printer connected over USB and powered on?')
        sys.exit(2)
    print('Interfaces to try (MI_01 first):')
    for p in paths:
        print("   -", p)
    result = used = None
    for target in paths:
        print("\n" + "#" * 68)
        print('# INTERFACE:', target)
        try:
            r = run_d4(target)
        except Exception as e:
            print('  error:', e)
            r = None
        if r:
            result, used = r, target
            break
    print("\n" + "=" * 68)
    if result:
        print('  RESULT: SUCCESS. Working interface:', used)
        print('  Next step: full read + safe reset via epson_l3251_usb_reset.py')
    else:
        print('  RESULT: EEPROM read failed. Include the FULL packet trace above when reporting this.')
    print("=" * 68)

if __name__ == "__main__":
    main()
