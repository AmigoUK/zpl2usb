from PIL import Image

from zpl2usb.config import Mapping
from zpl2usb.printers import PrinterBackend, PrintError
from zpl2usb.router import Router


class FakeBackend(PrinterBackend):
    def __init__(self, fail=False):
        self.raw_calls = []
        self.image_calls = []
        self.fail = fail

    def list_printers(self):
        return ["Zebra", "Toshiba"]

    def print_raw(self, name, data):
        if self.fail:
            raise PrintError("printer offline")
        self.raw_calls.append((name, data))

    def print_image(self, name, image, *, dpi=203):
        if self.fail:
            raise PrintError("driver error")
        self.image_calls.append((name, image, dpi))


def test_raw_mode_sends_bytes():
    be = FakeBackend()
    r = Router(be)
    m = Mapping(target_printer="Zebra", mode="raw")
    res = r.handle_job(m, b"^XA^FDhi^XZ")
    assert res.ok and res.mode == "raw"
    assert be.raw_calls == [("Zebra", b"^XA^FDhi^XZ")]
    assert be.image_calls == []


def test_render_mode_prints_image():
    be = FakeBackend()
    r = Router(be)
    m = Mapping(target_printer="Toshiba", mode="render", dpi=203)
    res = r.handle_job(m, b"^XA^FO10,10^A0N,30,30^FDhi^FS^XZ")
    assert res.ok and res.mode == "render"
    assert len(be.image_calls) == 1
    name, image, dpi = be.image_calls[0]
    assert name == "Toshiba"
    assert isinstance(image, Image.Image)
    assert dpi == 203
    assert be.raw_calls == []


def test_no_printer_selected_returns_error():
    be = FakeBackend()
    res = Router(be).handle_job(Mapping(target_printer="", mode="raw"), b"^XA^XZ")
    assert not res.ok
    assert "drukark" in res.error.lower()


def test_print_error_captured():
    be = FakeBackend(fail=True)
    res = Router(be).handle_job(Mapping(target_printer="Zebra", mode="raw"), b"^XA^XZ")
    assert not res.ok
    assert "offline" in res.error


def test_render_unsupported_reported_in_warnings():
    be = FakeBackend()
    m = Mapping(target_printer="Toshiba", mode="render")
    res = Router(be).handle_job(m, b"^XA^ZZ99^FDhi^FS^XZ")
    assert res.ok
    assert any("ZZ" in w for w in res.warnings)
