Not affiliated with Seiko Epson.

# epson_usb

USB (IEEE 1284.4 / D4) access to Epson printers.

```console
pip install epson-usb
```

The distribution is called `epson-usb`; the import name is `epson_usb`.

**Status.** This package is a demonstration of what has been measured, not a
supported product. No maintenance is promised: patches are welcome, but fixes for
models the maintainer cannot reproduce are not, and no dates are given (in the
maintainer's own words on the tracker: "for those I can take patches but cannot
promise fixes, and I would rather not put a date on it",
[#35](https://github.com/Ircama/epson_print_conf/issues/35#issuecomment-5798831443)).

## What has been measured on real hardware

Each row is one physical unit. "Standalone tool" means
[`epson_l3251_usb_reset.py`](https://github.com/onur-kesim/epson-l3251-usb-reset),
the program this library was extracted from, **not** the code in this package.

| # | Printer | OS | Who | Code that ran | What was observed | Source |
|---|---|---|---|---|---|---|
| 1 | L3251 | Windows | Onur Kesim | standalone tool | D4 session with the credit handshake over the Windows `USBPRINT` interface, no driver replacement. EEPROM reads and writes are answered on the secondary USB interface (`MI_01` on this unit). Full 256-cell bank-0 backup; counter reset with read-back verification. | [#35, 28 Aug 2026](https://github.com/Ircama/epson_print_conf/issues/35#issuecomment-5452048045) |
| 2 | L3251 | Windows | Onur Kesim | standalone tool | The waste counter is little-endian. What settled it was the printer's own error state: `0xCC 0x18` reads 6348 (100.0 %) little-endian and the printer was in the error state; `0x3B 0x18` reads 6203 (97.7 %) and it was not. | [#35, 4 Sep 2026](https://github.com/Ircama/epson_print_conf/issues/35#issuecomment-5538152419) |
| 3 | L3251 | Windows | Onur Kesim | standalone tool | The main waste counter is mirrored in three cells. After ten bordered photo pages, `0x30/0x31`, `0x34/0x35` and `0xC0/0xC1` each went 0 → 17 (`0xFC/0xFD` stayed 0). After zeroing the full set, all three stayed at 0 across two power cycles. | [#35, 4 Sep 2026](https://github.com/Ircama/epson_print_conf/issues/35#issuecomment-5538152419) |
| 4 | L3250 (firmware XF26P8, USB ID 04B8:118A) | Linux | endafk | `epson_usb` from `epson_print_conf` v8.0.0 | Printer at 100 % (`0x30/0x31` = 6346, status error `0x10`). Reset over USB by writing the 14-cell ET-2810 `raw_waste_reset` set (not `0xC0/0xC1`). After a power cycle everything stayed at 0, and `0xC0/0xC1` went to 0 by itself, as on the L3251. The maintainer of `epson_print_conf` replied: "it looks like the reset works as expected." | [#35, 24 Sep 2026](https://github.com/Ircama/epson_print_conf/issues/35#issuecomment-5810314920), [reply](https://github.com/Ircama/epson_print_conf/issues/35#issuecomment-5810422246) |
| 5 | XP-205 | Not reported | Ircama | `epson-usb` 0.1.0 from PyPI, on Python 3.9.13 (installed with `--ignore-requires-python`) | The report reads: "I successfully installed 0.1.0 on Python 3.9.13 with `--ignore-requires-python` and used it to drive an XP-205 over USB." Nothing more was reported: no OS, no backend, no operations, no firmware. | [#35, 24 Sep 2026](https://github.com/Ircama/epson_print_conf/issues/35#issuecomment-5822154925) |

Row 4 ran the library code of v8.0.0. The code in this package is identical to it
apart from docstrings and comments (the parsed syntax trees of the five changed
library modules are equal once docstrings are removed; compared on 24 Sep 2026);
the tests are newer.

## What has not been measured

| What | Status |
|---|---|
| This release (`epson-usb` 0.1.1) against a real printer | No record of it. Row 5 is a report on 0.1.0, whose library modules 0.1.1 does not change (the version number, the packaging metadata and this file are what differ), but it says no more than the sentence quoted there. Rows 1-3 used the standalone tool; row 4 used the earlier code described above. That this library behaves like the standalone tool is checked by hardware-free tests (`tests/test_fidelity.py`, against a frozen copy of the tool), not by a hardware run. |
| Printer models other than the L3251, L3250 and XP-205 units above | Not measured. One unit of each; the L3251's firmware version was not recorded, and for the XP-205 only the sentence quoted in row 5 exists. |
| Firmware versions other than XF26P8 (L3250) | Not measured. |
| macOS | No backend measured. |
| Windows: the `libusb`, `pyusb` and `raw` backends | Not measured. Only the native `usbprint` route was used (rows 1-3, by the standalone tool). |
| Linux: which backend row 4 used | Not reported. `libusb`, `pyusb` and `raw` were not measured individually. |
| The `rw` service command over USB | Not measured. |
| Persistence beyond the power cycles listed | Not measured (two on the L3251, one on the L3250). |
| The test suite (no hardware) on platforms other than Linux / Python 3.9 and 3.10 (CI) and Windows / Python 3.14 (maintainer's machine, 24 Sep 2026) | Not run. |

The sections below were written for the copy of this package that lives inside
[`epson_print_conf`](https://github.com/Ircama/epson_print_conf). Where they
mention `epson_print_conf.py`, `ui.py`, `find_printers.py` or "the repository
root", they mean that project; those files are not part of this distribution.
The backends are described as that project describes them: only the rows above
were measured by the people named in them.

## Platforms and backends

The library talks to the device through a *transport*; five are registered, and
the right one is chosen per platform, so the common case needs no options.

| backend | what it uses | available on |
|---|---|---|
| `usbprint` | Windows `USBPRINT` device interface, `ctypes` over SetupAPI + kernel32 — **no driver change** (no Zadig, no WinUSB) | Windows (tried first) |
| `libusb` | `libusb-1.0` through the package's own `ctypes` binding (no PyUSB needed) | Linux, macOS (on Windows: fallback, see below) |
| `pyusb` | PyUSB, if you prefer it (`pip install "epson-usb[pyusb]"`) | Linux, macOS (on Windows: fallback) |
| `raw` | a POSIX character device (`/dev/usb/lp0`) | Linux, macOS |
| `mock` | the in-memory fake printer | everywhere (tests, demos) |

**On Windows the native backend is tried first.** `usbprint` talks to the channel
the installed Epson driver already publishes, so nothing has to be installed and
the driver is never replaced; that is what was verified on hardware. `libusb` and
`pyusb` stay available, but come after it in the default order, because both reach
the printer's vendor-specific interface directly and would therefore need that
driver swapped for WinUSB (Zadig) — plus a `libusb-1.0.dll` on the machine. Ask
for one explicitly if you have set that up:

```console
python epson_print_conf.py -m XP-205 --usb --backend libusb -i    # Windows: only if
python epson_print_conf.py -m XP-205 --usb --backend usbprint -i   # the usual choice
```

On Linux and macOS the order is `libusb` → `pyusb` → `raw`. `mock` is never
chosen automatically, so a test can never be mistaken for a printer.

```console
python -c "from epson_usb.backends import describe_environment; print(describe_environment())"
```

## Quick start

`import epson_usb` works from the repository root,
because the package sits next to the scripts.

### From the command line

`--usb` switches the transport; `-a/--address` is then not required (and is not
used). `--backend` and `--device` imply `--usb`:

```console
python epson_print_conf.py -m XP-205 --usb -i                    # read the printer
python epson_print_conf.py -m XP-205 --usb --backend libusb -i     # force a backend
python epson_print_conf.py -m XP-205 --usb --device 1:4 -i         # force a device
python epson_print_conf.py -m XP-205 --backend mock -i             # no hardware at all
python epson_print_conf.py -m XP-205 -a 192.168.1.87 -i            # unchanged: SNMP
```

On Windows `--backend` is rarely needed: `usbprint` is tried first, and
`libusb`/`pyusb` are the fallbacks. On Linux and macOS it chooses between
libusb, PyUSB and a character device.

### From the GUI

`ui.py` has a **Printer Connection** box with two choices, `TCP/IP` and `USB`
(in the same row as the model and the address). Selecting USB replaces the
address field with a **`USB Port`** list: the devices found on this machine
*that can actually be opened*, refreshed by the ⟳ button next to it and by
`Detect Printers`. That filter is the point of the list — the enumeration
reports candidate paths, and on a Windows XP-205 three of the five candidates
are interface paths that `CreateFile` cannot open at all. Leave the first entry,
`Auto: first device found`, to let the library choose the device (its default
backend order); choose one to pin it, which is what tells two attached printers
apart or picks another interface of a multi-interface device. The choice is
handed to the transport as `backend`/`device`, the same two options the command
line fills from `--backend`/`--device`.

Selecting USB also disables the features that need the network, with a tooltip
explaining why each one is off: the printer web interface, the print tests and
nozzle cleaning (they print through LPR), and the configuration detection (it
reads SNMP-only MIB values). Everything else — status, EEPROM read/write, waste
resets, serial/MAC/TI/power-off parameters, access-key detection — works over
USB.

`Detect Printers` becomes a USB device listing in this mode (the backends
available on the machine, and every candidate the library enumerated), and the
transport can also be preselected from the command line:

```console
python ui.py --usb -m XP-205          # or: python ui.py --usb
```

### From any other tool: the environment variable

`find_printers.py`, `parse_devices.py` and anything else that does
`from epson_print_conf import EpsonPrinter` follows automatically when
`EPSON_USB` is set, because the hook at the end of `epson_print_conf.py`
replaces the class at import time:

```console
EPSON_USB=1 python3 find_printers.py
```

## Using the library directly

The library can also be used on its own, without `epson_print_conf`.

### Opening a printer

Read and write keys are per-model facts, and the library carries none: it asks
for them. A host program does not even need them, because its OIDs already
contain the frames it built from its own configuration.

```python
from epson_usb import EpsonUsbPrinter

with EpsonUsbPrinter(read_key=(0x11, 0x22),     # your model's keys, not ours
                     write_key=b"example8") as printer:
    print(printer.describe())                   # e.g. "usbprint ... (D4 revision 0x10)"
```

To take the keys from the parameters `epson_print_conf` already has:

```python
from epson_print_conf import EpsonPrinter

parm = EpsonPrinter(model="XP-205").parm
printer = EpsonUsbPrinter(read_key=parm["read_key"], write_key=parm["write_key"])
```

Useful constructor arguments: `device=` (a path or `bus:address`), `backend=`
(`usbprint`, `libusb`, `pyusb`, `raw`, `mock`), `transport=` (an already-built
transport, which is how the tests inject the fake printer), `dry_run=True`,
`timeouts=Timeouts.scaled(...)`, and anything the chosen backend needs.

### Reading and writing EEPROM

```python
printer.read_eeprom(0x30)          # '3B'  (two hex digits, like epson_print_conf)
printer.read_cell(0x30)            # 59    (an int)
printer.read_serial(range(0x644, 0x64E))     # printable characters only
printer.dump_eeprom(0x00, 0xFF)    # {address: value} for a whole bank
printer.write_eeprom(0x30, 0x00)   # True only when the printer answered ':OK;'
printer.write_cells([(0x30, 0), (0x31, 0)])  # a set, each write read back
```

Safety rules, unchanged from the tool this grew out of: nothing here writes
unless a write method is called; `dry_run=True` turns every write into a read
and logs what it would have done; a write that is not confirmed by `:OK;` is
reported as a failure, never as success.

### Backups

```python
path = printer.save_backup()                       # bank 0 -> JSON
report = printer.restore_backup(path, addresses=[0x30, 0x31, 0x1C])
print(report)      # e.g. "3 written, 0 failed, 0 missing from the backup"
```

The file format (`{"time": ..., "bank0": {"00": 12, ..., "FF": 94}}`) is the
historical one, so backups stay interchangeable with the source project's tool.
`addresses` is the caller's set: which cells a write path can touch is model
knowledge. A safety backup is taken before restoring unless told otherwise.

### Status, serial, identification

```python
printer.get_printer_status()        # the @BDC ST2 block, decoded
printer.get_serial_number()         # epson_print_conf's format, '?' for unreadable cells
printer.get_firmware_version()      # 'AB11I5 11 May 2018'
printer.get_device_identification() # {Manufacturer: [...], Model: [...], ...}
printer.get_cartridges()            # ['18XL', ...]
```

`get_printer_status()` delegates to `epson_print_conf.status_parser` when that
package is importable, so USB users get the full decode rather than a second,
drifting copy of it. Without it, `epson_usb.status.parse_st2()` extracts a
documented subset.

### The `rw` service command

```python
printer.service_rw("SERIAL")        # temporary waste reset, raw reply
```

`rw` needs only the serial number, which is why it still works on firmware that
locks the EEPROM. Which serial string to hash is the caller's decision: the
EEPROM serial and the USB descriptor serial are not the same string. On Windows,
`epson_usb.backends.usbprint_win.usb_serial_candidates()` lists the forms the
USB stack reports.

### The SNMP-shaped door (for host programs)

A host that already speaks the SNMP dialect can keep building OIDs and hand them
to the USB transport, which is exactly how the `epson_print_conf` integration
works:

```python
oid = printer.eeprom_oid_read_address(0x30)   # the OID SNMP would have used
printer.fetch_oid_values(oid)                 # [(OctetString, b'...')] over USB
```

`epson_usb.epson_ctrl.snmp_oid()` and `parse_snmp_oid()` are the two directions
of that translation, and `is_epson_ctrl_oid()` tells an EPSON-CTRL OID apart
from a plain MIB one. Plain MIB OIDs cannot travel over a cable: they are
answered `(None, False)` and logged.

### Bridging an existing class

```python
from epson_usb.compat import patch_epson_print_conf, usb_printer

patch_epson_print_conf()          # epson_print_conf.EpsonPrinter is now USB-capable
UsbPrinter = usb_printer()        # or build the subclass without touching upstream
printer = UsbPrinter(model="XP-205")   # no hostname: the device is on the USB bus
```

`epson_print_conf.enable_usb_transport()` (used by the CLI and by the GUI) is a
thin wrapper around `patch_epson_print_conf()`, and the original class is kept as
`epson_print_conf.NetworkEpsonPrinter`.

A note on the reply check, because it cost a session. `epson_print_conf`'s own
`invalid_response()` required the leading zero byte that some firmwares pad
`@BDC` blocks with. A real XP-205 sends none -- it answers
`@BDC PS\r\nEE:01660F;\x0C` -- so every EEPROM value came back `None` on a printer
that had answered correctly, over SNMP *and* over USB, since the bridge
deliberately does not override that method. The library's rule was always the
tolerant one: `EpsonUsbPrinter.read_eeprom()` answered `0F` where the host
printed `None`. That firmware also answers *bare* blocks, with no `@BDC PS`
header (`b'ii:NA;\x0C'` for an empty ink slot, `b'||:41:NA;\x0C'` for a read it
refuses), so an element is now looked for anywhere in the reply — and the element
itself may contain colons, because a write is confirmed with the write opcode in
the middle: `b'||:42:OK;\x0C'`. A `:NA;` reply
is an *answer* -- the printer saying no (wrong key, locked EEPROM) -- not a
malformed one, so a wrong access key is reported as `Invalid read key` at info
level instead of one error per attempt, which is what makes the 65536 attempts of
`--detect-key` readable.

### Errors

Everything raised derives from `epson_usb.EpsonUsbError`, with three names that
ask for different action: `DeviceNotFoundError` (nothing on the USB tree looks
like the printer, or the backend is not available here), `DeviceBusyError`
(something else holds it), `ProtocolError` (we reached it, the conversation did
not make sense). Transport errors also derive from `OSError`. The host program
converts them to its own `TimeoutError`, so a GUI or CLI user learns that the
printer is missing instead of seeing every value silently become `None`.

## Choosing a backend

```console
--backend usbprint | libusb | pyusb | raw | mock
--device  1:4                    # bus:address (libusb/pyusb)
--device  /dev/usb/lp0           # character device (raw)
--device  '\\?\usb#vid_04b8&pid_...'   # Windows interface path (usbprint)
```

Environment variables, for the cases where a flag is inconvenient:

| variable | effect |
|---|---|
| `EPSON_USB` | any value: the host tools use the USB transport |
| `EPSON_PRINT_CONF_PATH` | directory holding `epson_print_conf.py`, when it is not installed |
| `EPSON_USB_LIBUSB` | path of the `libusb-1.0` shared library, if discovery fails (needed on Windows only for the `libusb`/`pyusb` fallbacks) |
| `EPSON_USB_RAW_DEVICE` | extra character device for the `raw` backend |
| `EPSON_INSTANCE_ID` | Windows device instance id, for the `usbprint` backend |
| `EPSON_USB_REQUIRE_UPSTREAM` | tests only: `1` turns the skipped host-program test classes into errors (see *Tests*) |

Permissions and packages:

* **Windows** — the `usbprint` backend needs nothing at all: SetupAPI and
  kernel32 ship with the system, and the printer keeps working normally without
  touching its driver. The `libusb`/`pyusb` fallbacks, if you ever need them,
  would require replacing that driver with WinUSB (Zadig) and a
  `libusb-1.0.dll` on the machine.
* **Linux** — install `libusb-1.0-0` (`apt`) or `libusb1` (`dnf`), and let your
  user write the device:
  `SUBSYSTEM=="usb", ATTR{idVendor}=="04b8", MODE="0666"` in a udev rule. The
  kernel's `usblp` driver is detached automatically and re-attached on close.
* **macOS** — `brew install libusb`; no device node is involved.

When none of the three is available there, selecting USB would only fail on the
first command: `epson_print_conf.usb_transport_warning()` answers with what is
missing, and both the GUI (a line in the status box as soon as USB is chosen) and
the command line (`--usb`) ask it. On Windows it always answers `None`, because
the native backend needs nothing installed.

A USB session that is left behind (an interrupted command, a device the system
re-enumerated) answers nothing instead of failing: the key scan notices, closes
it so the next command opens a fresh one, and gives up with a message when
silence continues — a scan of 65536 attempts is not the place to discover that
the cable is not connected.

## Tests

Everything runs without hardware:

```console
python -m unittest discover -s epson_usb/tests -t .
python epson_usb/tests/mutant_run.py     # proves the suite would catch a porting mistake
```

Seven test classes need the host program, `epson_print_conf`. Without it they are
skipped, and `unittest` summarises that as `Ran 30 tests ... OK (skipped=7)` even
though 36 of the 66 tests never ran (it counts one skip per class and none of the
tests inside). Set `EPSON_USB_REQUIRE_UPSTREAM=1` and that skip becomes an error, so
a green run always means all 66 ran. CI does this; because `epson_print_conf` is not
on PyPI, CI checks it out at a pinned commit and puts it on `PYTHONPATH`.

They all rest on the `mock` backend: an in-memory printer that consumes the same
bytes a real one receives and produces the same framing back, so the protocol
code under test never learns that it is talking to a fake.

| file | what it pins |
| --- | --- |
| `tests/test_epson_usb.py` | the package's own behaviour: sessions, keys, safety gates, the EEPROM convention, backups, the upstream bridge, the OID bridge (`OidBridgeTests`) and end-to-end parity between the USB and SNMP envelopes (`TransportParityTests`). |
| `tests/test_fidelity.py` | that this is a *port*: it replays the historical implementation frozen in `tests/referans/` against the same fake printer and compares key agreement, handshake packets, frame builders and golden hex. |
| `tests/mutant_run.py` | that the suite is not vacuous: it flips the counter's byte order and the write frame's byte order, expects the suite to go red both times, and restores the files byte for byte. |

Both transports are driven through the same printer in `TransportParityTests`:
the question is never "does USB work?" but "does USB ask the printer exactly
what the network transport asked, and get the same answer?".

## What does not work over USB

* **Plain MIB queries** (`get_snmp_info()`, the model/MAC/power-off values the
  GUI shows in a status report) — there is no SNMP agent on a cable. They answer
  "unavailable" and are logged; the corresponding GUI features are disabled in
  USB mode.
* **Printing** (`print_check_nozzles()`, `print_clean_nozzles()`,
  `print_test_color_pattern()`) — the host sends those through LPR to a network
  address and raises `NotImplementedError` over USB.

**## onur-kesim/epson-l3251-usb-reset**

The implementation in the `epson_usb` directory currently reuses and extends code from [`onur-kesim/epson-l3251-usb-reset`](https://github.com/onur-kesim/epson-l3251-usb-reset).

Ideally, the `epson_usb` directory could serve as a preliminary implementation of a possible future backend layer for `epson-l3251-usb-reset`.

The `epson_usb` implementation is not intended to remain permanently embedded in `epson_print_conf`. A possible future approach would be to rely on an evolution of `onur-kesim/epson-l3251-usb-reset`, with its USB functionality exposed as a reusable backend/library.

We are deeply grateful to `onur-kesim/epson-l3251-usb-reset` for providing the USB D4 protocol implementation and the native Windows interface on which this work builds.
