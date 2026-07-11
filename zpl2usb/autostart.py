"""Rejestracja autostartu aplikacji przy starcie systemu.

Wieloplatformowo:
  * Linux : plik XDG ``~/.config/autostart/zpl2usb.desktop``
  * macOS : LaunchAgent ``~/Library/LaunchAgents/com.zpl2usb.plist``
  * Windows: klucz rejestru ``HKCU\\...\\CurrentVersion\\Run``

Ścieżki bazowe (Linux/macOS) są wstrzykiwalne, żeby dało się testować bez
modyfikowania prawdziwego systemu.
"""

from __future__ import annotations

import shlex
import sys
from abc import ABC, abstractmethod
from pathlib import Path

APP_ID = "zpl2usb"
APP_NAME = "zpl2usb"
MAC_LABEL = "com.zpl2usb"


def launch_command() -> list[str]:
    """Polecenie uruchamiające aplikację.

    Dla binarki PyInstaller: sama ścieżka do pliku wykonywalnego.
    Ze źródeł: ``python -m zpl2usb``.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "zpl2usb"]


class AutostartBackend(ABC):
    @abstractmethod
    def enable(self) -> None: ...

    @abstractmethod
    def disable(self) -> None: ...

    @abstractmethod
    def is_enabled(self) -> bool: ...


class LinuxAutostart(AutostartBackend):
    def __init__(self, base_dir: Path | None = None, command: list[str] | None = None):
        self.dir = Path(base_dir) if base_dir else Path.home() / ".config" / "autostart"
        self.file = self.dir / f"{APP_ID}.desktop"
        self.command = command or launch_command()

    def content(self) -> str:
        exec_line = " ".join(shlex.quote(c) for c in self.command)
        return (
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={APP_NAME}\n"
            "Comment=Wirtualna sieciowa drukarka ZPL\n"
            f"Exec={exec_line}\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n"
        )

    def enable(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file.write_text(self.content(), encoding="utf-8")

    def disable(self) -> None:
        self.file.unlink(missing_ok=True)

    def is_enabled(self) -> bool:
        return self.file.exists()


class MacAutostart(AutostartBackend):
    def __init__(self, base_dir: Path | None = None, command: list[str] | None = None):
        self.dir = Path(base_dir) if base_dir else Path.home() / "Library" / "LaunchAgents"
        self.file = self.dir / f"{MAC_LABEL}.plist"
        self.command = command or launch_command()

    def content(self) -> str:
        args = "".join(f"        <string>{c}</string>\n" for c in self.command)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0">\n'
            "<dict>\n"
            "    <key>Label</key>\n"
            f"    <string>{MAC_LABEL}</string>\n"
            "    <key>ProgramArguments</key>\n"
            "    <array>\n"
            f"{args}"
            "    </array>\n"
            "    <key>RunAtLoad</key>\n"
            "    <true/>\n"
            "</dict>\n"
            "</plist>\n"
        )

    def enable(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file.write_text(self.content(), encoding="utf-8")

    def disable(self) -> None:
        self.file.unlink(missing_ok=True)

    def is_enabled(self) -> bool:
        return self.file.exists()


class WindowsAutostart(AutostartBackend):  # pragma: no cover - tylko Windows
    _KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

    def __init__(self, command: list[str] | None = None):
        self.command = command or launch_command()

    def _value(self) -> str:
        return " ".join(f'"{c}"' if " " in c else c for c in self.command)

    def enable(self) -> None:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_ID, 0, winreg.REG_SZ, self._value())

    def disable(self) -> None:
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self._KEY, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, APP_ID)
        except FileNotFoundError:
            pass

    def is_enabled(self) -> bool:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._KEY) as key:
                winreg.QueryValueEx(key, APP_ID)
            return True
        except FileNotFoundError:
            return False


def get_autostart(
    platform: str | None = None, base_dir: Path | None = None, command: list[str] | None = None
) -> AutostartBackend:
    """Zwróć backend autostartu właściwy dla systemu."""
    plat = platform or sys.platform
    if plat.startswith("win"):
        return WindowsAutostart(command=command)
    if plat == "darwin":
        return MacAutostart(base_dir=base_dir, command=command)
    return LinuxAutostart(base_dir=base_dir, command=command)


def set_autostart(enabled: bool, **kwargs) -> None:
    """Włącz lub wyłącz autostart wg flagi."""
    backend = get_autostart(**kwargs)
    backend.enable() if enabled else backend.disable()
