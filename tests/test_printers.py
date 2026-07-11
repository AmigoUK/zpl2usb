import subprocess

import pytest
from PIL import Image

from zpl2usb.printers import CupsBackend, PrintError, get_backend


class FakeRunner:
    """Nagrywa wywołania i zwraca zaprogramowane wyniki."""

    def __init__(self, results):
        # results: dict[str_cmd0, (returncode, stdout, stderr)]
        self.results = results
        self.calls = []

    def __call__(self, args, data):
        self.calls.append((args, data))
        key = args[0]
        rc, out, err = self.results.get(key, (0, b"", b""))
        return subprocess.CompletedProcess(args, rc, stdout=out, stderr=err)


def test_list_printers_lpstat_e():
    runner = FakeRunner({"lpstat": (0, b"Zebra\nToshiba_B_EX\n", b"")})
    be = CupsBackend(runner=runner)
    assert be.list_printers() == ["Zebra", "Toshiba_B_EX"]
    assert runner.calls[0][0] == ["lpstat", "-e"]


def test_list_printers_fallback_lpstat_a():
    results = {}
    calls = {"n": 0}

    def runner(args, data):
        # -e faila, -a zwraca listę w formacie "name accepting..."
        if args == ["lpstat", "-e"]:
            return subprocess.CompletedProcess(args, 1, b"", b"unsupported")
        return subprocess.CompletedProcess(
            args, 0, b"Zebra accepting requests\nHP accepting\n", b""
        )

    be = CupsBackend(runner=runner)
    assert be.list_printers() == ["Zebra", "HP"]


def test_list_printers_empty_on_failure():
    def runner(args, data):
        return subprocess.CompletedProcess(args, 1, b"", b"no cups")

    assert CupsBackend(runner=runner).list_printers() == []


def test_print_raw_builds_correct_command():
    runner = FakeRunner({"lp": (0, b"request id is Zebra-1", b"")})
    be = CupsBackend(runner=runner)
    be.print_raw("Zebra", b"^XA^FDhi^XZ")
    args, data = runner.calls[0]
    assert args == ["lp", "-d", "Zebra", "-o", "raw"]
    assert data == b"^XA^FDhi^XZ"


def test_print_raw_raises_on_failure():
    runner = FakeRunner({"lp": (1, b"", b"printer offline")})
    be = CupsBackend(runner=runner)
    with pytest.raises(PrintError, match="offline"):
        be.print_raw("Zebra", b"data")


def test_print_image_saves_and_calls_lp(tmp_path):
    runner = FakeRunner({"lp": (0, b"", b"")})
    be = CupsBackend(runner=runner)
    img = Image.new("L", (100, 50), 255)
    be.print_image("Toshiba", img, dpi=203)
    args, data = runner.calls[0]
    assert args[:3] == ["lp", "-d", "Toshiba"]
    # ostatni argument to ścieżka pliku PNG (już usuniętego)
    assert args[-1].endswith(".png")
    assert data is None


def test_print_image_raises_on_failure():
    runner = FakeRunner({"lp": (1, b"", b"driver error")})
    be = CupsBackend(runner=runner)
    with pytest.raises(PrintError, match="driver error"):
        be.print_image("X", Image.new("L", (10, 10), 255))


def test_get_backend_linux_returns_cups():
    be = get_backend(platform="linux")
    assert isinstance(be, CupsBackend)
