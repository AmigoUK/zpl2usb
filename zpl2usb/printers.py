"""Międzyplatformowy backend druku.

Interfejs:
  * ``list_printers()``            -> nazwy drukarek zainstalowanych w systemie
  * ``print_raw(name, data)``      -> wyślij surowe bajty (np. ZPL) do drukarki
  * ``print_image(name, image)``   -> wydrukuj obraz PIL przez sterownik systemowy

Linux/macOS: przez CUPS (polecenia ``lp``/``lpstat``).
Windows: przez ``win32print`` (pakiet pywin32).

Konstrukcja poleceń jest oddzielona od wykonania (``runner``), żeby można było
testować logikę bez prawdziwej drukarki.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Protocol


class PrintError(RuntimeError):
    """Błąd wysyłki zadania do drukarki."""


class _Completed(Protocol):
    returncode: int
    stdout: bytes
    stderr: bytes


Runner = Callable[[list[str], bytes | None], _Completed]


def _default_runner(args: list[str], data: bytes | None) -> subprocess.CompletedProcess:
    return subprocess.run(args, input=data, capture_output=True, check=False)


class PrinterBackend(ABC):
    @abstractmethod
    def list_printers(self) -> list[str]:
        ...

    @abstractmethod
    def print_raw(self, name: str, data: bytes) -> None:
        ...

    @abstractmethod
    def print_image(self, name: str, image, *, dpi: int = 203) -> None:
        ...


# --- CUPS (Linux / macOS) ---------------------------------------------------
class CupsBackend(PrinterBackend):
    def __init__(self, runner: Runner | None = None) -> None:
        self._run = runner or _default_runner

    def list_printers(self) -> list[str]:
        res = self._run(["lpstat", "-e"], None)
        if res.returncode != 0:
            # Fallback: część systemów nie wspiera -e.
            res = self._run(["lpstat", "-a"], None)
            if res.returncode != 0:
                return []
            names = []
            for line in _text(res.stdout).splitlines():
                line = line.strip()
                if line:
                    names.append(line.split()[0])
            return names
        return [ln.strip() for ln in _text(res.stdout).splitlines() if ln.strip()]

    def print_raw(self, name: str, data: bytes) -> None:
        res = self._run(["lp", "-d", name, "-o", "raw"], data)
        if res.returncode != 0:
            raise PrintError(f"lp raw nie powiódł się dla {name!r}: {_text(res.stderr)}")

    def print_image(self, name: str, image, *, dpi: int = 203) -> None:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            path = Path(tmp.name)
        try:
            image.save(path, format="PNG", dpi=(dpi, dpi))
            res = self._run(["lp", "-d", name, str(path)], None)
            if res.returncode != 0:
                raise PrintError(
                    f"lp image nie powiódł się dla {name!r}: {_text(res.stderr)}"
                )
        finally:
            path.unlink(missing_ok=True)


# --- Windows ----------------------------------------------------------------
class WindowsBackend(PrinterBackend):
    def __init__(self) -> None:
        try:
            import win32print  # noqa: F401
        except ImportError as exc:  # pragma: no cover - tylko Windows
            raise PrintError(
                "Backend Windows wymaga pakietu pywin32 (pip install pywin32)."
            ) from exc

    def list_printers(self) -> list[str]:  # pragma: no cover - tylko Windows
        import win32print

        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        return [p[2] for p in win32print.EnumPrinters(flags)]

    def print_raw(self, name: str, data: bytes) -> None:  # pragma: no cover - Windows
        import win32print

        handle = win32print.OpenPrinter(name)
        try:
            win32print.StartDocPrinter(handle, 1, ("zpl2usb", None, "RAW"))
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, data)
            win32print.EndPagePrinter(handle)
            win32print.EndDocPrinter(handle)
        except Exception as exc:
            raise PrintError(f"Druk RAW nie powiódł się dla {name!r}: {exc}") from exc
        finally:
            win32print.ClosePrinter(handle)

    def print_image(self, name: str, image, *, dpi: int = 203) -> None:  # pragma: no cover
        import win32con
        import win32ui
        from PIL import ImageWin

        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(name)
        try:
            hdc.StartDoc("zpl2usb")
            hdc.StartPage()
            dib = ImageWin.Dib(image.convert("RGB"))
            w, h = image.size
            dib.draw(hdc.GetHandleOutput(), (0, 0, w, h))
            hdc.EndPage()
            hdc.EndDoc()
        except Exception as exc:
            raise PrintError(f"Druk obrazu nie powiódł się dla {name!r}: {exc}") from exc
        finally:
            hdc.DeleteDC()


def _text(data) -> str:
    if isinstance(data, bytes):
        return data.decode("utf-8", "replace")
    return str(data or "")


def get_backend(platform: str | None = None, runner: Runner | None = None) -> PrinterBackend:
    """Zwróć backend właściwy dla systemu."""
    plat = platform or sys.platform
    if plat.startswith("win"):
        return WindowsBackend()
    return CupsBackend(runner=runner)
