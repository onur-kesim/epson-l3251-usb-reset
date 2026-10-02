#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""USB interface selection and fallback (KRITER_0.1.2.md, K7-K9).

Run with the rest of the suite from the repository root::

    python -m unittest discover -s epson_usb/tests -t .

No hardware, no network, no ``libusb`` library needed. What is checked, and
what that does *not* show:

* **K7** -- the candidate list, against the golden case W1 (a field report on
  ``Ircama/epson_print_conf`` issue #35), and the old single-value
  ``select_interface_and_endpoints`` behaviour, unchanged. Pure functions over
  descriptors: this is the real code.
* **K8** -- the opening path walks the candidates when D4 does not answer.
  The fake printer is a ``MockTransport`` with several interfaces; it picks its
  candidates through the same ``resolve_candidates`` the ``libusb`` backend
  uses, so the selection is the real one, but the USB claim itself is not
  exercised. ``LibusbTransport.next_candidate`` is tested with its ``open``
  replaced (the loop logic, not libusb).
* **K9** -- the command-line flag, and that an explicit interface turns the
  fallback off.

What no test here can show: that the fallback works on a real printer. See
"What has not been measured" in the package README.
"""

import importlib.util
import io
import logging
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock


def _repo_root(start):
    directory = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(directory, "epson_usb", "__init__.py")):
            return directory
        parent = os.path.dirname(directory)
        if parent == directory:
            return os.path.abspath(start)
        directory = parent


HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = _repo_root(HERE)
for path in (REPO_ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

from epson_usb import EpsonUsbPrinter
from epson_usb.backends.libusb import (
    EndpointDescriptor,
    InterfaceDescriptor,
    LibusbTransport,
    candidate_interfaces,
    resolve_candidates,
    select_interface_and_endpoints,
)
from epson_usb.backends.mock import MockConfig, MockTransport
from epson_usb.compat import factory_kwargs
from epson_usb.d4 import Timeouts
from epson_usb.epson_ctrl import eeprom_read_payload, snmp_oid
from epson_usb.errors import D4Error, DeviceBusyError, DeviceNotFoundError
from epson_usb.printer import read_oid_values_from_transport

EXAMPLE = os.path.join(REPO_ROOT, "epson_usb", "examples", "epson_print_conf_over_usb.py")

READ_KEY = (0x4A, 0x36)
#: A handshake against a fake takes a few milliseconds at this scale.
FAST = Timeouts.scaled(0.02)

USB_CLASS_PRINTER = 0x07
USB_CLASS_VENDOR_SPECIFIC = 0xFF


def endpoints(number):
    """A bulk IN and a bulk OUT endpoint. Addresses are synthetic."""
    return (
        EndpointDescriptor(address=0x80 | (number + 1), attributes=0x02, max_packet_size=512),
        EndpointDescriptor(address=number + 1, attributes=0x02, max_packet_size=512),
    )


def interface(number, interface_class, subclass=0, protocol=0, alternate=0, bulk=True):
    return InterfaceDescriptor(
        number=number,
        alternate=alternate,
        interface_class=interface_class,
        interface_subclass=subclass,
        interface_protocol=protocol,
        endpoints=endpoints(number) if bulk else (),
    )


def w1_interfaces():
    """Golden case W1: the L3251 of Witton-431 (identifies as "L3250 Series").

    Source: ``Ircama/epson_print_conf`` issue #35, comment 5936448547,
    1 Oct 2026 (a third party, "one unit, one firmware"). What the report says,
    and what this reproduces:

    * interface 0: vendor-specific, class/subclass/protocol 255/255/255;
    * interface 1: printer class;
    * interface 2: vendor-specific, subclass 170;
    * bulk IN and OUT on all three (stated for the case in KRITER_0.1.2.md).

    What the report does **not** say and is therefore left at 0 here: the
    subclass and protocol of interface 1 and the protocol of interface 2. The
    endpoint addresses and packet sizes are synthetic.
    """
    return (
        interface(0, USB_CLASS_VENDOR_SPECIFIC, subclass=0xFF, protocol=0xFF),
        interface(1, USB_CLASS_PRINTER),
        interface(2, USB_CLASS_VENDOR_SPECIFIC, subclass=0xAA),
    )


def numbers(candidates):
    return [c[0].number for c in candidates]


def w1_printer(d4_interfaces, **kwargs):
    """An ``EpsonUsbPrinter`` over a fake device with the W1 interfaces.

    ``d4_interfaces`` are the interfaces on which the fake answers D4.
    Returns ``(config, transport)``; the transport is handed over separately
    because a failed open leaves no printer to ask which interfaces were tried.
    """
    config = MockConfig(
        eeprom={0x30: 0x3B, 0x31: 0x18},
        interfaces=w1_interfaces(),
        d4_interfaces=d4_interfaces,
    )
    transport = MockTransport(config, **kwargs)
    return config, transport


class W1CandidateListTests(unittest.TestCase):
    """K7: an ordered list of candidate interfaces, W1 as the golden case."""

    def test_the_list_holds_all_three_interfaces_and_interface_1_is_in_it(self):
        candidates = candidate_interfaces(w1_interfaces())
        self.assertEqual(sorted(numbers(candidates)), [0, 1, 2])
        self.assertIn(1, numbers(candidates))

    def test_order_is_vendor_specific_first_then_the_rest_lowest_number_first(self):
        self.assertEqual(numbers(candidate_interfaces(w1_interfaces())), [0, 2, 1])

    def test_every_candidate_carries_a_bulk_in_and_a_bulk_out_endpoint(self):
        for chosen, bulk_in, bulk_out in candidate_interfaces(w1_interfaces()):
            self.assertTrue(bulk_in.is_in and bulk_in.is_bulk, chosen.number)
            self.assertFalse(bulk_out.is_in)
            self.assertTrue(bulk_out.is_bulk, chosen.number)
            self.assertIn(bulk_in, chosen.endpoints)
            self.assertIn(bulk_out, chosen.endpoints)

    def test_the_order_does_not_depend_on_the_order_of_the_descriptors(self):
        shuffled = tuple(reversed(w1_interfaces()))
        self.assertEqual(numbers(candidate_interfaces(shuffled)), [0, 2, 1])


class SingleValueBehaviourTests(unittest.TestCase):
    """K7: ``select_interface_and_endpoints`` keeps answering with one value."""

    def test_w1_still_selects_interface_0_the_first_candidate(self):
        # This is what the field report ran into: the single value is
        # interface 0, where D4 never answered. It must not change here; the
        # fix is that the opening path no longer stops at it.
        chosen, bulk_in, bulk_out = select_interface_and_endpoints(w1_interfaces())
        self.assertEqual(chosen.number, 0)
        self.assertEqual((bulk_in, bulk_out), endpoints(0))
        self.assertEqual(
            (chosen, bulk_in, bulk_out), candidate_interfaces(w1_interfaces())[0])

    def test_a_lone_printer_class_interface_is_selected(self):
        only = (interface(1, USB_CLASS_PRINTER),)
        self.assertEqual(select_interface_and_endpoints(only)[0].number, 1)

    def test_vendor_specific_beats_printer_class_even_with_a_higher_number(self):
        mixed = (interface(0, USB_CLASS_PRINTER), interface(3, USB_CLASS_VENDOR_SPECIFIC))
        self.assertEqual(select_interface_and_endpoints(mixed)[0].number, 3)
        self.assertEqual(numbers(candidate_interfaces(mixed)), [3, 0])

    def test_among_vendor_specific_interfaces_the_lowest_number_wins(self):
        two = (interface(4, USB_CLASS_VENDOR_SPECIFIC), interface(2, USB_CLASS_VENDOR_SPECIFIC))
        self.assertEqual(select_interface_and_endpoints(two)[0].number, 2)

    def test_interfaces_without_both_bulk_endpoints_are_not_candidates(self):
        no_endpoints = interface(0, USB_CLASS_VENDOR_SPECIFIC, bulk=False)
        in_only = InterfaceDescriptor(
            number=1, interface_class=USB_CLASS_VENDOR_SPECIFIC, endpoints=(endpoints(1)[0],))
        usable = interface(2, USB_CLASS_PRINTER)
        self.assertEqual(numbers(candidate_interfaces((no_endpoints, in_only, usable))), [2])

    def test_alternate_settings_are_not_candidates(self):
        alternate = interface(0, USB_CLASS_VENDOR_SPECIFIC, alternate=1)
        self.assertEqual(candidate_interfaces((alternate,)), [])

    def test_nothing_usable_is_none_and_an_empty_list(self):
        self.assertIsNone(select_interface_and_endpoints(()))
        self.assertEqual(candidate_interfaces(()), [])
        self.assertIsNone(select_interface_and_endpoints((interface(0, 0xFF, bulk=False),)))


class ExplicitInterfaceTests(unittest.TestCase):
    """K9, library half: naming an interface leaves exactly one candidate."""

    def test_an_explicit_interface_is_the_only_candidate_whatever_its_class(self):
        candidates = resolve_candidates(w1_interfaces(), interface=1)
        self.assertEqual(numbers(candidates), [1])

    def test_without_an_explicit_interface_it_is_the_whole_list(self):
        self.assertEqual(numbers(resolve_candidates(w1_interfaces())), [0, 2, 1])

    def test_an_interface_the_device_lacks_is_an_error_that_names_it(self):
        with self.assertRaises(DeviceNotFoundError) as caught:
            resolve_candidates(w1_interfaces(), interface=7, where="device 1:4")
        self.assertIn("device 1:4 has no interface 7", str(caught.exception))

    def test_an_interface_without_bulk_endpoints_is_an_error(self):
        with self.assertRaises(DeviceNotFoundError) as caught:
            resolve_candidates((interface(0, 0xFF, bulk=False),), interface=0)
        self.assertIn("no usable bulk endpoints", str(caught.exception))

    def test_a_device_with_nothing_usable_is_an_error(self):
        with self.assertRaises(DeviceNotFoundError):
            resolve_candidates(())

    def test_endpoint_addresses_can_be_pinned_within_the_interface(self):
        wanted_in, wanted_out = endpoints(1)
        _, bulk_in, bulk_out = resolve_candidates(
            w1_interfaces(), interface=1,
            endpoint_in=wanted_in.address, endpoint_out=wanted_out.address)[0]
        self.assertEqual((bulk_in, bulk_out), (wanted_in, wanted_out))
        with self.assertRaises(DeviceNotFoundError):
            resolve_candidates(w1_interfaces(), interface=1, endpoint_in=0x8F)


class FallbackTests(unittest.TestCase):
    """K8: the opening path tries the next candidate when D4 does not answer."""

    def test_d4_silent_on_interface_0_answers_on_1_so_the_open_ends_on_interface_1(self):
        config, transport = w1_printer(d4_interfaces=(1,))
        printer = EpsonUsbPrinter(transport=transport, timeouts=FAST, read_key=READ_KEY)
        self.addCleanup(printer.close)
        self.assertTrue(printer.connected)
        self.assertEqual(printer.device_info.interface, 1)
        self.assertEqual(transport.info.interface, 1)
        self.assertIn("if=1", printer.describe())

    def test_the_candidates_are_tried_in_list_order_and_each_is_claimed_once(self):
        _, transport = w1_printer(d4_interfaces=(1,))
        printer = EpsonUsbPrinter(transport=transport, timeouts=FAST, read_key=READ_KEY)
        self.addCleanup(printer.close)
        self.assertEqual(transport.claimed_interfaces, [0, 2, 1])

    def test_the_session_it_ends_with_is_a_working_one(self):
        _, transport = w1_printer(d4_interfaces=(1,))
        printer = EpsonUsbPrinter(transport=transport, timeouts=FAST, read_key=READ_KEY)
        self.addCleanup(printer.close)
        self.assertEqual(printer.revision, 0x10)
        self.assertEqual(printer.read_cell(0x30), 0x3B)
        self.assertEqual(printer.read_cell(0x31), 0x18)

    def test_the_first_candidate_answering_means_no_fallback(self):
        _, transport = w1_printer(d4_interfaces=(0,))
        printer = EpsonUsbPrinter(transport=transport, timeouts=FAST, read_key=READ_KEY)
        self.addCleanup(printer.close)
        self.assertEqual(transport.claimed_interfaces, [0])
        self.assertEqual(printer.device_info.interface, 0)

    def test_a_later_candidate_is_reached_even_when_it_is_not_the_last(self):
        _, transport = w1_printer(d4_interfaces=(2,))
        printer = EpsonUsbPrinter(transport=transport, timeouts=FAST, read_key=READ_KEY)
        self.addCleanup(printer.close)
        self.assertEqual(transport.claimed_interfaces, [0, 2])
        self.assertEqual(printer.device_info.interface, 2)

    def test_when_the_candidates_run_out_the_error_lists_every_one(self):
        _, transport = w1_printer(d4_interfaces=())
        with self.assertRaises(D4Error) as caught:
            EpsonUsbPrinter(transport=transport, timeouts=FAST, read_key=READ_KEY)
        message = str(caught.exception)
        for number in (0, 1, 2):
            self.assertIn("interface %d:" % number, message)
        self.assertIn("D4 Init failed", message)
        self.assertIn("--interface", message)
        self.assertEqual(transport.claimed_interfaces, [0, 2, 1])
        self.assertFalse(transport.opened)

    def test_a_printer_that_failed_to_open_holds_no_session(self):
        _, transport = w1_printer(d4_interfaces=())
        printer = EpsonUsbPrinter(
            transport=transport, timeouts=FAST, read_key=READ_KEY, auto_open=False)
        with self.assertRaises(D4Error):
            printer.open()
        self.assertIsNone(printer.session)
        self.assertFalse(printer.connected)

    def test_a_device_with_a_single_pipe_fails_exactly_as_before(self):
        transport = MockTransport(MockConfig(refuse_d4=True))
        with self.assertRaises(D4Error) as caught:
            EpsonUsbPrinter(transport=transport, timeouts=FAST)
        message = str(caught.exception)
        self.assertTrue(message.startswith("D4 Init failed (the printer did not answer D4)"))
        self.assertNotIn("no candidate interface", message)
        self.assertEqual(transport.claimed_interfaces, [])

    def test_the_one_shot_helper_falls_back_too(self):
        _, transport = w1_printer(d4_interfaces=(1,))
        oid = snmp_oid("||", eeprom_read_payload(READ_KEY, 0x30))
        (kind, reply), = read_oid_values_from_transport(transport, oid, timeouts=FAST)
        self.assertEqual(kind, "OctetString")
        self.assertIn(b"EE:00303B", reply)
        self.assertEqual(transport.claimed_interfaces, [0, 2, 1])

    def test_each_switch_is_logged(self):
        _, transport = w1_printer(d4_interfaces=(1,))
        with self.assertLogs("epson_usb.printer", level=logging.INFO) as logs:
            printer = EpsonUsbPrinter(transport=transport, timeouts=FAST, read_key=READ_KEY)
        self.addCleanup(printer.close)
        switches = [line for line in logs.output if "trying interface" in line]
        self.assertEqual(len(switches), 2)
        self.assertIn("failed on interface 0", switches[0])
        self.assertIn("trying interface 2", switches[0])
        self.assertIn("trying interface 1", switches[1])


class ExplicitInterfaceDisablesTheFallbackTests(unittest.TestCase):
    """K9: with an interface named, only that one is tried."""

    def test_naming_the_silent_interface_fails_without_trying_the_others(self):
        _, transport = w1_printer(d4_interfaces=(1,), interface=0)
        with self.assertRaises(D4Error) as caught:
            EpsonUsbPrinter(transport=transport, timeouts=FAST, read_key=READ_KEY)
        self.assertEqual(transport.claimed_interfaces, [0])
        self.assertNotIn("no candidate interface", str(caught.exception))

    def test_naming_the_answering_interface_claims_only_that_one(self):
        _, transport = w1_printer(d4_interfaces=(1,), interface=1)
        printer = EpsonUsbPrinter(transport=transport, timeouts=FAST, read_key=READ_KEY)
        self.addCleanup(printer.close)
        self.assertEqual(transport.claimed_interfaces, [1])
        self.assertEqual(printer.device_info.interface, 1)

    def test_naming_an_interface_the_device_lacks_fails_before_any_d4(self):
        _, transport = w1_printer(d4_interfaces=(1,), interface=7)
        with self.assertRaises(DeviceNotFoundError):
            EpsonUsbPrinter(transport=transport, timeouts=FAST, read_key=READ_KEY)
        self.assertEqual(transport.claimed_interfaces, [])

    def test_the_interface_keyword_reaches_the_transport_through_the_printer(self):
        config = MockConfig(
            eeprom={0x30: 0x3B}, interfaces=w1_interfaces(), d4_interfaces=(1,))
        printer = EpsonUsbPrinter(
            backend="mock", config=config, interface=1, timeouts=FAST, read_key=READ_KEY)
        self.addCleanup(printer.close)
        self.assertEqual(printer.device_info.interface, 1)
        with self.assertRaises(D4Error):
            EpsonUsbPrinter(
                backend="mock", config=config, interface=0, timeouts=FAST, read_key=READ_KEY)

    def test_the_host_programs_usb_options_route_delivers_the_keyword(self):
        # compat.UsbEpsonPrinterMixin builds the printer through factory_kwargs,
        # and --interface travels in usb_options: it must arrive, the model
        # name (which is not a transport option) must not.
        delivered = factory_kwargs(EpsonUsbPrinter, {"interface": 1, "model": "L3251"})
        self.assertEqual(delivered, {"interface": 1})


class LibusbNextCandidateTests(unittest.TestCase):
    """``LibusbTransport.next_candidate`` with ``open``/``close`` replaced.

    This is the walking logic only; no libusb library is involved, and the
    real claim is not exercised.
    """

    def make(self, interface=None):
        transport = LibusbTransport("1:4", interface=interface)
        transport._candidates = [0, 2, 1]
        return transport

    def patched(self, fail_at=()):
        """Replace open/close; ``opened`` records the candidate index of each open."""
        opened = []

        def fake_open(transport):
            if transport._candidate_index in fail_at:
                raise DeviceBusyError("busy at index %d" % transport._candidate_index)
            opened.append(transport._candidate_index)

        patches = (
            mock.patch.object(LibusbTransport, "open", fake_open),
            mock.patch.object(LibusbTransport, "close", lambda transport: None),
        )
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        return opened

    def test_an_explicit_interface_has_no_next_candidate(self):
        transport = LibusbTransport("1:4", interface=1)
        self.assertFalse(transport.next_candidate())

    def test_it_walks_the_candidates_in_order_and_then_runs_out(self):
        opened = self.patched()
        transport = self.make()
        self.assertTrue(transport.next_candidate())
        self.assertTrue(transport.next_candidate())
        self.assertFalse(transport.next_candidate())
        self.assertEqual(opened, [1, 2])

    def test_when_it_runs_out_the_next_open_starts_from_the_best_candidate_again(self):
        self.patched()
        transport = self.make()
        while transport.next_candidate():
            pass
        self.assertEqual(transport._candidate_index, 0)

    def test_a_candidate_that_cannot_be_claimed_is_noted_and_skipped(self):
        opened = self.patched(fail_at=(1,))
        transport = self.make()
        self.assertTrue(transport.next_candidate())
        self.assertEqual(opened, [2])
        self.assertEqual(len(transport.skipped_candidates), 1)
        number, reason = transport.skipped_candidates[0]
        self.assertEqual(number, 2)
        self.assertIn("busy at index 1", reason)

    def test_if_none_of_the_rest_can_be_claimed_it_reports_that_none_is_left(self):
        self.patched(fail_at=(1, 2))
        transport = self.make()
        self.assertFalse(transport.next_candidate())
        self.assertEqual([n for n, _ in transport.skipped_candidates], [2, 1])

    def test_without_a_candidate_list_there_is_nothing_to_walk(self):
        self.patched()
        self.assertFalse(LibusbTransport("1:4").next_candidate())


class CommandLineFlagTests(unittest.TestCase):
    """K9: ``--interface N`` in the example command line."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("epson_print_conf_over_usb_example", EXAMPLE)
        cls.example = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.example)

    class FakePrinter:
        parm = {"fake": True}

        def usb_describe(self):
            return "fake"

        def get_serial_number(self):
            return "SERIAL"

        def get_waste_ink_levels(self):
            return {}

        def close(self):
            pass

    def run_main(self, *argv):
        """Run ``main`` with ``build_printer`` replaced; return (exit, calls, stdout, stderr)."""
        calls = []

        def fake_build(*args, **kwargs):
            calls.append(args)
            return self.FakePrinter()

        out, err = io.StringIO(), io.StringIO()
        code = None
        with mock.patch.object(self.example, "build_printer", fake_build), \
                redirect_stdout(out), redirect_stderr(err):
            try:
                code = self.example.main(list(argv))
            except SystemExit as exit_:
                code = exit_.code
        return code, calls, out.getvalue(), err.getvalue()

    def test_help_lists_the_flag(self):
        code, _, out, _ = self.run_main("--help")
        self.assertEqual(code, 0)
        self.assertIn("--interface N", out)
        self.assertIn("fallback", out)

    def test_the_number_reaches_build_printer(self):
        code, calls, _, _ = self.run_main("--interface", "1", "--backend", "libusb", "--waste")
        self.assertEqual(code, 0)
        # build_printer(model, dry_run, backend, device, interface)
        self.assertEqual(calls, [(None, False, "libusb", None, 1)])

    def test_pyusb_accepts_it_too(self):
        code, calls, _, _ = self.run_main("--interface", "2", "--backend", "pyusb", "--waste")
        self.assertEqual(code, 0)
        self.assertEqual(calls, [(None, False, "pyusb", None, 2)])

    def test_without_the_flag_nothing_changes(self):
        code, calls, out, _ = self.run_main("--waste")
        self.assertEqual(code, 0)
        self.assertEqual(calls, [(None, False, None, None, None)])
        self.assertNotIn("--interface", out)

    def test_without_a_backend_the_flag_means_libusb_and_says_so(self):
        code, calls, out, _ = self.run_main("--interface", "1", "--waste")
        self.assertEqual(code, 0)
        self.assertEqual(calls, [(None, False, "libusb", None, 1)])
        self.assertIn("using libusb", out)

    def test_a_backend_that_cannot_choose_an_interface_is_refused(self):
        for backend in ("usbprint", "raw", "mock"):
            with self.subTest(backend=backend):
                code, calls, _, err = self.run_main("--interface", "1", "--backend", backend)
                self.assertEqual(code, 2)
                self.assertEqual(calls, [])
                self.assertIn("--interface needs the libusb or pyusb backend", err)

    def test_a_value_that_is_not_an_interface_number_is_refused(self):
        for value in ("x", "-1", "256"):
            with self.subTest(value=value):
                code, calls, _, err = self.run_main("--interface", value)
                self.assertEqual(code, 2)
                self.assertEqual(calls, [])
                self.assertIn("--interface", err)


if __name__ == "__main__":
    unittest.main()
