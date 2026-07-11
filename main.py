#!/usr/bin/env python3
"""Punkt wejścia dla PyInstaller (import bezwzględny pakietu).

Uruchamianie ze źródeł nadal działa przez ``python -m zpl2usb`` (patrz
``zpl2usb/__main__.py``). Ten plik istnieje, bo zamrożona binarka uruchamia
skrypt jako top-level ``__main__`` — wtedy importy względne w pakiecie nie działają.
"""

from zpl2usb.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
