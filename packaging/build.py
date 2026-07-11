#!/usr/bin/env python3
"""Budowa samodzielnej binarki zpl2usb przez PyInstaller.

Uruchom w aktywnym środowisku z zainstalowanymi zależnościami:

    pip install -r requirements.txt pyinstaller
    python packaging/build.py

Binarka trafia do ``dist/``. Uruchamiać należy na docelowym systemie
(PyInstaller nie robi cross-kompilacji: Windows buduj na Windows, itd.).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "packaging" / "zpl2usb.spec"


def main() -> int:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Brak PyInstaller. Zainstaluj: pip install pyinstaller", file=sys.stderr)
        return 2
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(SPEC)]
    print("Uruchamiam:", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
