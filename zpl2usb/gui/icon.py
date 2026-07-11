"""Generowanie ikony aplikacji (bez plików zewnętrznych)."""

from __future__ import annotations

from PIL import Image, ImageDraw


def make_icon(size: int = 64, running: bool = True) -> Image.Image:
    """Prosta ikona: stylizowana etykieta z kodem kreskowym.

    Zielony akcent gdy aplikacja działa, szary gdy zatrzymana.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    accent = (34, 160, 74, 255) if running else (120, 120, 120, 255)

    m = size // 8
    # korpus etykiety
    d.rounded_rectangle([m, m, size - m, size - m], radius=size // 10,
                        fill=(255, 255, 255, 255), outline=accent, width=max(2, size // 20))
    # paski "kodu kreskowego"
    bar_top = size // 3
    bar_bottom = size - size // 3
    x = m + size // 8
    widths = [2, 1, 3, 1, 2, 1, 1, 3, 2]
    for w in widths:
        bw = max(1, w * size // 40)
        d.rectangle([x, bar_top, x + bw, bar_bottom], fill=(20, 20, 20, 255))
        x += bw + max(2, size // 32)
        if x > size - m - size // 8:
            break
    return img
