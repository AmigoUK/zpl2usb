"""Konwersje jednostek dla renderera ZPL.

ZPL operuje w punktach (dots). Rozdzielczość (DPI) drukarki decyduje, ile punktów
przypada na milimetr/cal.
"""

from __future__ import annotations

MM_PER_INCH = 25.4


def mm_to_dots(mm: float, dpi: int) -> int:
    """Milimetry -> punkty przy zadanym DPI (zaokrąglone)."""
    return round(mm / MM_PER_INCH * dpi)


def dots_to_mm(dots: float, dpi: int) -> float:
    """Punkty -> milimetry przy zadanym DPI."""
    return dots / dpi * MM_PER_INCH


def label_size_dots(width_mm: float, height_mm: float, dpi: int) -> tuple[int, int]:
    """Rozmiar etykiety w mm -> (szerokość, wysokość) w punktach."""
    return mm_to_dots(width_mm, dpi), mm_to_dots(height_mm, dpi)
