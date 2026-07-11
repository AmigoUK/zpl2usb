"""Dostarczanie fontów dla renderera.

ZPL font ``0`` jest skalowalny. Mapujemy go na skalowalny font TrueType.
Używamy wbudowanego w Pillow ``load_default(size=...)`` (od Pillow 10 zwraca
prawdziwy font TrueType), dzięki czemu nie trzeba dołączać plików fontów i wynik
jest deterministyczny dla danej wersji Pillow.
"""

from __future__ import annotations

from functools import lru_cache

from PIL import ImageFont


@lru_cache(maxsize=64)
def get_font(height_dots: int) -> ImageFont.FreeTypeFont:
    """Zwróć skalowalny font o wysokości ~``height_dots`` pikseli."""
    size = max(6, int(height_dots))
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        # Bardzo stare Pillow bez parametru size — fallback do bitmapowego domyślnego.
        return ImageFont.load_default()
