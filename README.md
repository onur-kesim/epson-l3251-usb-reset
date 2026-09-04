# Epson L3251 — Waste Ink Pad counter reset over USB (pure Python, Windows)

Reads, backs up and — only when you explicitly ask — resets the waste ink pad
counters of an **Epson L3251** over **USB**, speaking IEEE 1284.4 (D4) directly
to the Windows printer channel.

* No driver replacement (no Zadig, no libusb).
* No external dependencies — Python standard library only (`ctypes`).
* Read-only by default. Writing requires an explicit `--reset`, `--reset-full`
  or `--service-reset`.

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
| Write zeros to the six known counter cells | **no** | `--reset` |
| Write the full spec cell set (14 cells, three of them to `0x5E`) | **no** | `--reset-full` |
| Run the firmware-level Epson `rw` service command | **no** | `--service-reset` |
| Force the serial string hashed by `--service-reset` | **no** | `--serial <SN>` |
| Skip the backup | **no** | `--no-backup` |
| Write every waste-related cell back from a backup file (a safety backup is taken first) | **no** | `--restore <file.json>` |
| Print the serial number in full (only the last 4 characters are shown by default) | **no** | `--show-serial` |

Running the script with no arguments **cannot write anything**.

`--reset` writes zeros to six cells (`0x30 0x31 0x32 0x33 0xFC 0xFD`).
`--reset-full` writes the whole cell set the reinkpy spec lists for this model
group (`0x1C 0x2F 0x30 0x31 0x32 0x33 0x34 0x35 0x36 0x37 0xFC 0xFD 0xFE 0xFF`),
and **three of those reset to `0x5E`, not to zero** (`0x36 0x37 0xFF`). Both
paths read every cell back to confirm. The two flags are mutually exclusive.

`--service-reset` writes nothing to EEPROM directly: it sends the firmware's own
`rw` (reset waste) command. Per a report on `epson_print_conf` issue #35 that is
a **temporary** reset which does not survive a power cycle, so `--reset-full` is
the real path and this is a fallback. See the verification section.

`epson_usb_probe.py` is a strictly read-only diagnostic: it contains no EEPROM
write command at all. It issues one EEPROM read per candidate interface and
prints the full D4 handshake, for when the main script cannot connect.

## Usage

```
# Read state and take a backup — writes nothing to the printer
py epson_l3251_usb_reset.py

# Reset the six known counter cells (writes!)
py epson_l3251_usb_reset.py --reset

# Reset the full cell set from the reinkpy spec (writes!)
py epson_l3251_usb_reset.py --reset-full

# Firmware-level "rw" service reset (writes!)
py epson_l3251_usb_reset.py --service-reset

# ...with an explicit serial string to hash
py epson_l3251_usb_reset.py --service-reset --serial <SN>

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
* **`--restore` writes back every cell any write path can touch** — the same
  fourteen `--reset-full` uses — not all 256. So a `--reset-full` run is
  undoable from a backup taken before it.

`--reset-full` reaches eight cells `--reset` never touched, so take a backup
before the first run — the default behaviour already does.

The tool never writes outside bank 0 (`0x00`–`0xFF`), and within it only to the
six waste-counter cells.

## What has been verified — and what has not

Verified on an Epson L3251 over USB on Windows (2026-08-28): D4 connect with
the credit handshake, EEPROM reads, waste-counter decoding, a full 256-cell
bank-0 backup, and one successful `--reset` run — the six cells were written
and read back as zero.

Measured on 2026-09-04, third session, same printer:

* **The byte order was wrong, not the divisors.** Up to v0.2.0 each counter
  pair was decoded big-endian. It is little-endian: the first address holds the
  low byte. The error state makes this decidable, because the printer either
  shows "service required" or it does not:

  | `0x30` | `0x31` | big-endian | little-endian | printer showed the error? |
  |---|---|---|---|---|
  | `0xCC` | `0x18` | 52248 (823%) | **6348 (100.0%)** | **yes** |
  | `0x3B` | `0x18` | 15128 (238%) | **6203 (97.7%)** | **no** |

  Big-endian calls both readings "full" and cannot explain the error clearing.
  Little-endian puts the boundary exactly where the printer puts it. An
  independent report on `epson_print_conf` issue #35 measured `0x18CA` = 6346 as
  exactly 100.00% on the same family, which anchors the main divisor. **The
  first diagnosis in this project blamed the divisors and was wrong; the bug was
  one line of decoding.** The other two divisors still have no anchor and are
  printed with a leading `~`.
* **The firmware restores the main pad counter across a power cycle.** After a
  successful `--reset` all six cells read back as 0, but after switching the
  printer off and on `0x30 0x31` came back as 6203 (97.7%). The secondary and
  platen cells stayed at 0. The RAM-write-back theory this first suggested was
  **wrong**: see the `--reset-full` result below. The firmware was re-deriving
  the counter from cells `--reset` never wrote.
* **`--reset` was incomplete.** The reinkpy spec group for this model
  (`rkey=0x364A`, `wkey="Nbsjcbzb"`, model list includes L3251) lists fourteen
  cells; the tool wrote six. Eight cells were never touched, and five of them
  measured away from their spec reset values (`0x1C=20`, `0x34=131`, `0x35=47`,
  `0x36=104`, `0xFF=104`). Whether that is what the power-on write-back reads
  from is **unmeasured** — it is the reason `--reset-full` exists.
* **The two serial numbers do not agree.** The EEPROM holds ten printable
  characters at 0x0644-0x064D. The USB device descriptor reports a longer
  string: the ASCII-hex of the first eight of those characters plus a trailing
  `00` byte. Shape only, with a made-up serial: EEPROM `ABCD012345` would appear
  on the USB side as `414243443031323300`. This printer's own serial is not
  printed here, and the tool masks it in its output by default. reinkpy hashes the **USB descriptor** string, and Windows does not
  preserve that string's letter case, so `--service-reset` tries four candidates
  in order and stops at the first reply containing `:OK;`.

Not verified: what the `rw` command actually does. reinkpy's own docstring reads
*"Run generic \"rw\" command (for \"reset waste\"?)"* — the question mark is
the author's. Every raw reply is printed verbatim rather than interpreted.

### The `--reset-full` result (2026-09-04)

* **The full cell set survives a power cycle.** All fourteen cells were written
  and read back as intended, the printer was switched off and on at its own
  button, and the main pad still read `0`. The earlier run, which wrote only six
  cells, came back at 97.7% after exactly the same test. The single variable
  between the two runs is the eight extra cells. **One trial on each side** —
  strong, not conclusive.
* **The firmware changed seven other cells by itself** in the same window:
  `0xC0 0xC1` went `303 -> 0` read as a little-endian pair, `0xD4 0xD5` and
  `0xD8 0xD9` each dropped by exactly **720**, and `0x58` went `168 -> 174`
  (that cell has been seen oscillating between those two values across runs).
  None of them is identified.
* GUESS, not measurement: `0xC0 0xC1` is a countdown that reached zero and
  triggered a power-on cleaning, and the two pairs that dropped by 720 are ink
  or usage counters spent by it.
* **Open question.** If a cleaning did run at power-on, the waste counters
  should have moved off zero. They did not. Either the increment is deferred, or
  no cleaning ran. Worth watching on the next read.

### Second power cycle, same day

A second off/on with no printing in between, measured by diffing two full
bank-0 backups:

* **All three waste counters: `0 -> 0`.** The reset held a second time, and a
  plain power cycle costs the waste pads **nothing**. The `52248 -> 52504` climb
  seen in the first session was therefore not power-cycle cost — it was the
  counter being re-derived from the cells `--reset` never wrote.
* `0xD4 0xD5` and `0xD8 0xD9` moved in lockstep again, `-144` each this time
  against `-720` on the previous cycle — exactly five times as much. Consistent
  with the first power-on running some larger operation and this one being an
  ordinary start. Neither pair is identified.
* `0xC0 0xC1` stayed at `0`; it did **not** reload a new value. That weakens the
  countdown guess above rather than confirming it.
* `0x92` went `0 -> 2`. Unidentified.

Two power cycles, zero pad movement, so the earlier open question resolves the
dull way: whatever the printer did at power-on, it did not charge the waste
pads for it.

### Ten bordered photo pages, from a clean zero (2026-09-04)

With every counter at 0, ten photo pages were printed **with borders**, in one
uninterrupted run, no power cycle and no manual cleaning. Diffing the full
bank-0 backups taken before and after:

* **The main counter is mirrored in three places.** `0x30 0x31`, `0x34 0x35` and
  `0xC0 0xC1` each moved by exactly **+17**, in lockstep. That is the whole
  explanation for the reset saga in this file: zeroing `0x30 0x31` alone left
  the value sitting in a mirror, and the firmware restored it at the next
  power-on. `0xC0 0xC1` is not in the reinkpy spec set, was never written by
  this tool, and was observed being synced *down* to zero by the firmware at
  the first power-on after `--reset-full` — so it is derived, not authoritative.
  An earlier note in this file guessed `0xC0 0xC1` was a countdown timer. It is
  not; that guess is withdrawn.
* **1.7 units per photo page.** 17 units for ten pages, cleaning during the run
  included. Against a threshold of 6346 that is roughly 3700 photo pages, though
  a text page will not cost the same as a photo.
* **Bordered printing does not touch the platen pad.** `0xFC 0xFD` stayed at 0
  through all ten pages, as did the secondary counter. The platen pad really is
  fed by borderless printing, and its physical part on this chassis is a
  separate one: Epson `1746666`, "POROUS PAD, PAPERGUIDE, FRONT".
* Two other pairs moved a lot and are still unidentified: `0xD4 0xD5` +4199 and
  `0xD8 0xD9` +11458. They had previously moved in lockstep on power cycles
  (−144, then −720) but did not here, so they are two different quantities, not
  one duplicated. Photo pages use a lot of ink; that is as far as the evidence
  goes.

### Reset only what you actually serviced

`--reset-full` zeroes every waste-related cell in one go, which is what makes it
survive a power cycle. The consequence is worth stating plainly: **a counter you
zero for a pad you did not replace now under-reports by exactly the value you
erased.** The pads in the waste ink tank and the platen pad
(Epson part `1746666`, "POROUS PAD, PAPERGUIDE, FRONT" on this chassis) are
different physical parts with different counters, and people usually replace the
tank pads only.

If that applies to you, take the reading from a backup taken *before* the reset
and keep it: that number is the offset you must add to every later reading of
that counter for the rest of that pad's life. The backup JSON already holds it,
which is one more reason the tool takes one before every write.

Still not verified: behaviour across normal printing over days, and across a
borderless photo run, which is what fills the platen pad. `--service-reset`
(the `rw` command) has **never been executed** on this printer — the full cell
reset made it unnecessary.

Not verified: any other model, any other OS, and any behaviour of this code
outside the L3251 it was written against. The waste-counter addresses and the
EEPROM command parameters come from prior open-source work (see Credits) and
have not been independently re-derived for other models — do not assume they
transfer.

## Credits

The EEPROM command format and the waste-counter addresses for this printer
generation come from existing open-source reverse-engineering work:

* [`reinkpy`](https://codeberg.org/atufi/reinkpy) (AGPL-3.0) — model database
  (`epson.toml`), which is where the EEPROM addresses, the read/write keys and
  the `--reset-full` cell set come from, plus `epson.py`, the reference for the
  `rw` service command frame. The **divisors are not from reinkpy** — reinkpy's
  spec has none; they came from a public gist. The main one was later
  corroborated by a third-party measurement on `epson_print_conf` issue #35; the
  other two still are not. See the verification section.
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
