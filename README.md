# Epson L3251 — Waste Ink Pad counter reset over USB (pure Python, Windows)

Reads, backs up and — only when you explicitly ask — resets the waste ink pad
counters of an **Epson L3251** over **USB**, speaking IEEE 1284.4 (D4) directly
to the Windows printer channel.

* No driver replacement (no Zadig, no libusb).
* No external dependencies — Python standard library only (`ctypes`).
* Read-only by default. Writing requires an explicit `--reset`.

---

## Why this exists

The L3250 generation is a documented gap in the **Python** tooling:

* [`epson_print_conf`](https://github.com/Ircama/epson_print_conf) lists **L3250**
  under **"Known incompatible models"**, and describes its transport as:

  > *"SNMP Interface: Connect and manage Epson printers using SNMP over TCP/IP,
  > supporting Wi-Fi connections (**not USB**)."*

  So there is no USB path there at all. *(Quotes read from the project README on
  2026-08-28.)*

* [`reinkpy`](https://codeberg.org/atufi/reinkpy) issue #16 (*"Non-linux
  platforms"*) marks **Windows + USB** as `~ (install backend manually)`.

On the unit this was written against, the Wi-Fi/SNMP path is closed in firmware,
which left USB as the remaining route. This tool takes that route.

## What this is *not*

This is **not** the first or only open-source approach to either problem, and it
does not claim to be:

* [`abrasive/epson-reversing`](https://github.com/abrasive/epson-reversing)
  already contains a Python IEEE 1284.4 implementation, credit-based flow control
  included, over raw device nodes (Linux-style `os.open`/`os.read`/`os.write`).
* [`RxNaison/Epson-Waste-Reset`](https://github.com/RxNaison/Epson-Waste-Reset)
  already does the *Windows-native, no-custom-driver* part — in C++, using
  `SetupAPI` and overlapped I/O. **Its model database includes L3250, L3251,
  ET-2810 and ET-2820, and its Windows USB code names L3250 explicitly as the
  "printer engine on secondary interface" case.** If you simply want this
  printer's counter reset today, use EWR — it is a finished, maintained tool
  and it covers this model.

What is different here is narrower than "nobody has done this", and worth stating
plainly: this is a **pure-Python** (`ctypes` only) D4 transport over the Windows
`USBPRINT` interface, with no driver change and no build step. `epson_print_conf`
is a Python project with no USB path; a C++ implementation cannot be moved into
it, and a Python one can. That is the whole reason this repository exists.

## Requirements

* **Windows** — the transport uses Win32 `SetupAPI` and the `USBPRINT` device
  interface class. There is no Linux/macOS path in this code.
* **Python 3** — standard library only. Nothing to `pip install`.
* The printer connected over **USB** and visible to Windows as a printer.

## Safety model

| Behaviour | Default | Flag |
|---|---|---|
| Read counters | yes | *(none)* |
| Full bank-0 EEPROM backup (0x00–0xFF, 256 cells) written to a timestamped JSON | yes | *(none)* |
| Write to EEPROM | **no** | `--reset` |
| Skip the backup | **no** | `--no-backup` |
| Write the six counter cells back from a backup file (a safety backup is taken first) | **no** | `--restore <file.json>` |
| Print the serial number in full (only the last 4 characters are shown by default) | **no** | `--show-serial` |

Running the script with no arguments **cannot write anything**. The reset path
writes zeros only to the six waste-counter cells (`0x30 0x31 0x32 0x33 0xFC 0xFD`)
and reads each one back to confirm.

`epson_usb_probe.py` is a strictly read-only diagnostic: it contains no EEPROM
write command at all. It issues one EEPROM read per candidate interface and
prints the full D4 handshake, for when the main script cannot connect.

## Usage

```
# Read state and take a backup — writes nothing to the printer
py epson_l3251_usb_reset.py

# Reset the waste ink pad counters (writes!)
py epson_l3251_usb_reset.py --reset

# Restore counter cells from a previous backup
py epson_l3251_usb_reset.py --restore epson_backup_bank0_<timestamp>.json

# Show the full serial number (only the last 4 characters are shown by default)
py epson_l3251_usb_reset.py --show-serial

# Print the version
py epson_l3251_usb_reset.py --version

# Diagnostics only — single read, full protocol trace
py epson_usb_probe.py
```

If automatic device discovery does not find the printer, pass its device
instance ID explicitly:

```
py epson_l3251_usb_reset.py --instance-id "USB\VID_04B8&..."
```

You can copy that string from Device Manager → the printer → Details → Device
instance path. The `EPSON_INSTANCE_ID` environment variable is accepted as a
default for the same value.

## Backups

A read, a reset or a restore run writes `epson_backup_bank0_<timestamp>.json`
**next to the script** — not into the directory you happen to call it from — and
prints the absolute path it used. The file holds all 256 cells of bank 0 as
`address -> value`. These files describe your specific printer's state, so they
are git-ignored by default. Keep them: `--restore` needs one.

Three things to know before you rely on this:

* **`--restore` takes its own safety backup first**, unless you pass
  `--no-backup`. Restoring from a stale file no longer costs you the current
  values without warning.
* **A bare filename passed to `--restore`** is looked up in the current
  directory first, then next to the script.
* **`--restore` writes back the six waste-counter cells only**, not all 256.

The tool never writes outside bank 0 (`0x00`–`0xFF`), and within it only to the
six waste-counter cells.

## What has been verified — and what has not

Verified on an Epson L3251 over USB on Windows (2026-08-28): D4 connect with
the credit handshake, EEPROM reads, waste-counter decoding, a full 256-cell
bank-0 backup, and one successful `--reset` run — the six cells were written
and read back as zero.

Not verified: any other model, any other OS, and any behaviour of this code
outside the L3251 it was written against. The waste-counter addresses and the
EEPROM command parameters come from prior open-source work (see Credits) and
have not been independently re-derived for other models — do not assume they
transfer.

## Credits

The EEPROM command format and the waste-counter addresses for this printer
generation come from existing open-source reverse-engineering work:

* [`reinkpy`](https://codeberg.org/atufi/reinkpy) (AGPL-3.0) — model database
  (`epson.toml`), which is where the addresses and divisors used here come from.
* [`epson_print_conf`](https://github.com/Ircama/epson_print_conf) — protocol
  documentation and model data.
* [`abrasive/epson-reversing`](https://github.com/abrasive/epson-reversing) —
  IEEE 1284.4 protocol analysis.

This repository contributes the Windows USB transport and the tooling around it,
not the protocol knowledge itself.

## License

This repository is licensed under the **GNU Affero General Public License v3.0** —
see `LICENSE`.

That choice is deliberate rather than a default. The EEPROM command parameters and
the waste-counter addresses used here were taken from prior open-source
reverse-engineering work, `reinkpy` (AGPL-3.0) among it. Licensing this repository
under AGPL-3.0 means it cannot end up offering weaker terms than the work it builds
on. If you maintain a project under different terms and want to use this code, open
an issue — the code here is mine to relicense, the reverse-engineered constants are
not mine to speak for.

## Disclaimer

Resetting the waste ink pad counter does **not** empty the physical waste ink
pad. It only tells the printer to stop reporting the pad as full. If the pad is
genuinely saturated, ink can overflow inside the printer and onto the surface it
stands on. Replace or service the pad — this tool is for the case where the
counter is wrong or the pad has already been dealt with.

This software writes to your printer's EEPROM. It may void your warranty, and it
can brick the device if it is used on hardware it was not written for. It is
provided **as is, with no warranty of any kind**. You are responsible for what
you run it on. Take the backup, keep the backup.
