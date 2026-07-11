#!/usr/bin/env python3
"""Renderuj plik ZPL do PNG (podgląd offline, do testów renderera).

python tools/render_zpl.py etykieta.zpl -o wynik.png --dpi 203 --size 100x40
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zpl2usb.renderer import render  # noqa: E402


def _parse_size(text: str) -> tuple[float, float]:
    w, h = text.lower().split("x")
    return float(w), float(h)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Renderuj ZPL do PNG.")
    ap.add_argument("input", help="plik .zpl")
    ap.add_argument("-o", "--output", help="plik wyjściowy PNG (domyślnie: <input>.png)")
    ap.add_argument("--dpi", type=int, default=203, choices=(203, 300, 600))
    ap.add_argument("--size", default="100x40", help="domyślny rozmiar etykiety mm, np. 100x40")
    args = ap.parse_args(argv)

    data = Path(args.input).read_bytes()
    result = render(data, dpi=args.dpi, default_label_mm=_parse_size(args.size))
    out = Path(args.output) if args.output else Path(args.input).with_suffix(".png")
    result.image.save(out)
    print(f"Zapisano {out} ({result.image.size[0]}x{result.image.size[1]} px)")
    if result.unsupported:
        print("Pominięte polecenia:", ", ".join(result.unsupported))
    for w in result.warnings:
        print("Ostrzeżenie:", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
