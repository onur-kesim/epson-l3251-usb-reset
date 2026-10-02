#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run ``epson_print_conf`` over USB instead of SNMP.

This is the whole integration, in one file: `epson_print_conf` reaches the
printer through a single method (``fetch_oid_values``), the OID carries an
EPSON-CTRL frame, and ``epson_usb.compat`` overrides that one method to send the
frame over the USB cable instead of wrapping it in SNMP.

Read-only unless you pass ``--reset`` or ``--temp-reset``.

    python examples/epson_print_conf_over_usb.py                   # status report
    python examples/epson_print_conf_over_usb.py --model L3251
    python examples/epson_print_conf_over_usb.py --temp-reset      # WRITES (temporary)
    python examples/epson_print_conf_over_usb.py --reset-full      # WRITES the cell set
    python examples/epson_print_conf_over_usb.py --interface 1     # only USB interface 1

Requirements: this package, plus ``epson_print_conf`` and its dependencies
(``pysnmp``, ``pysnmp-sync-adapter``, ``pyyaml``, ``pyprintlpr``,
``epson_escp2``). Point ``EPSON_PRINT_CONF_PATH`` at the directory holding
``epson_print_conf.py`` if it is not installed.
"""

import argparse
import pprint
import sys

from epson_usb.compat import load_epson_print_conf, patch_epson_print_conf


def build_printer(model_name, dry_run, backend=None, device=None, interface=None):
    """Return a USB-capable ``EpsonPrinter`` subclass instance.

    ``epson_print_conf`` is imported here rather than at module import time, so
    that ``--help`` works on a machine where it is not installed.
    """
    upstream = load_epson_print_conf()
    # The library adds the USB transport; the parameters stay upstream's own,
    # taken from its configuration for the model in use. No model tables are
    # involved, which is exactly why the library can be hosted here.
    usb_epson_printer = patch_epson_print_conf(upstream)
    # `interface` is a transport option: it travels through `usb_options` to
    # the backend (libusb / pyusb), which then claims that interface and no
    # other. Without it the backend chooses, and libusb falls back to the next
    # candidate when D4 does not answer.
    return usb_epson_printer(
        model=model_name,
        backend=backend,
        device=device,
        dry_run=dry_run,
        usb_options={"interface": interface} if interface is not None else None,
    )


def interface_number(text):
    """``argparse`` type for ``--interface``: a USB interface number, 0-255."""
    try:
        number = int(text, 0)
    except ValueError:
        raise argparse.ArgumentTypeError("%r is not a number" % text)
    if not 0 <= number <= 255:
        raise argparse.ArgumentTypeError("%d is not a USB interface number (0-255)" % number)
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-m", "--model", default=None,
                        help="printer model (default: the one this host knows)")
    parser.add_argument("--backend", default=None,
                        help="usbprint | libusb | pyusb | raw | mock")
    parser.add_argument("--device", default=None, help="explicit device path")
    parser.add_argument("--interface", type=interface_number, default=None, metavar="N",
                        help="USB interface number to use (libusb and pyusb backends). "
                             "Only that interface is tried: the automatic choice and the "
                             "fallback to the next candidate when D4 does not answer are "
                             "both off. Without it the library chooses (and falls back).")
    parser.add_argument("--dry-run", action="store_true",
                        help="never write, whatever else is asked for")
    parser.add_argument("--temp-reset", action="store_true",
                        help="WRITES: the firmware `rw` command (temporary reset)")
    parser.add_argument("--reset-full", action="store_true",
                        help="WRITES: the full reset cell set (permanent, survives "
                             "a power cycle)")
    parser.add_argument("--status", action="store_true",
                        help="decode and print the full @BDC ST2 status block")
    parser.add_argument("--waste", action="store_true",
                        help="print only the waste ink levels")
    args = parser.parse_args(argv)

    if args.interface is not None:
        if args.backend in ("usbprint", "raw", "mock"):
            parser.error("--interface needs the libusb or pyusb backend: %s has no "
                         "interface to choose" % args.backend)
        if args.backend is None:
            # usbprint (tried first on Windows) and raw cannot pick an
            # interface, so asking for one means asking for libusb.
            args.backend = "libusb"
            print("note: --interface given without --backend: using libusb")

    if args.backend == "mock":
        print("note: using the in-memory fake printer (no hardware involved)")

    printer = build_printer(args.model, args.dry_run, args.backend, args.device,
                            args.interface)
    try:
        print("transport:", printer.usb_describe())
        if not printer.parm:
            print("unknown printer model: %s" % args.model, file=sys.stderr)
            return 1
        print("model    : %s" % args.model)
        print("serial   : %s" % printer.get_serial_number())

        if args.status:
            pprint.pprint(printer.get_printer_status())
        elif args.waste:
            pprint.pprint(printer.get_waste_ink_levels())
        else:
            pprint.pprint(printer.get_waste_ink_levels())
            try:
                print("firmware : %s" % printer.get_firmware_version())
            except Exception as exc:
                # Upstream's regex for this one field has no re.DOTALL, so the
                # `@BDC PS` header every EPSON-CTRL reply carries makes it fail
                # (over SNMP as well as over USB: it is not a transport issue).
                # The library's own parser handles the same bytes, see
                # printer.py get_firmware_version().
                print("firmware : unavailable (%s)" % exc)

        if args.temp_reset:
            print("temporary waste reset (rw): %s"
                  % ("OK" if printer.temporary_reset_waste() else "not accepted"))
        if args.reset_full:
            # Upstream's own method, unchanged -- driven over USB by the bridge.
            print("full waste reset: %s"
                  % ("OK" if printer.reset_waste_ink_levels() else "FAILED"))
    finally:
        printer.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
