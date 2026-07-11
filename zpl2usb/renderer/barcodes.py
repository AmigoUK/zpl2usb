"""Generowanie obrazów kodów kreskowych dla renderera ZPL.

Code128 (``^BC``) przez bibliotekę ``python-barcode``.
QR (``^BQ``) przez bibliotekę ``qrcode``.
Zwracane obrazy są w trybie "L" (skala szarości, czarny na białym).
"""

from __future__ import annotations

import re

import barcode
import qrcode
from barcode.writer import ImageWriter
from PIL import Image

from .units import dots_to_mm


def code128(
    data: str,
    *,
    module_width_dots: int,
    height_dots: int,
    dpi: int,
    write_text: bool = True,
) -> Image.Image:
    """Wyrenderuj Code128 do obrazu PIL.

    ``module_width_dots`` odpowiada szerokości najwęższego modułu (^BY),
    ``height_dots`` wysokości kodu (^BY lub ^BC).
    """
    writer = ImageWriter(format="PNG")
    options = {
        "module_width": dots_to_mm(max(1, module_width_dots), dpi),
        "module_height": dots_to_mm(max(1, height_dots), dpi),
        "quiet_zone": 0,
        "write_text": bool(write_text),
        "dpi": dpi,
    }
    if write_text:
        options["font_size"] = max(6, round(height_dots * 0.15))
        options["text_distance"] = dots_to_mm(max(2, round(height_dots * 0.1)), dpi)
    img = barcode.Code128(data, writer=writer).render(writer_options=options)
    return img.convert("L")


_QR_PREFIX = re.compile(r"^(?:\d)?([HQML])?([AM])?,")
_ERR_MAP = {
    "L": qrcode.constants.ERROR_CORRECT_L,
    "M": qrcode.constants.ERROR_CORRECT_M,
    "Q": qrcode.constants.ERROR_CORRECT_Q,
    "H": qrcode.constants.ERROR_CORRECT_H,
}


def parse_qr_field(field_data: str) -> tuple[str, int]:
    """Rozdziel dane pola ^FD dla QR na (payload, error_correction).

    ZPL koduje QR jako np. ``LA,https://...`` gdzie pierwszy znak to poziom
    korekcji (L/M/Q/H), drugi tryb wejścia (A/M). Prefiks jest opcjonalny.
    """
    m = _QR_PREFIX.match(field_data)
    if m:
        level = m.group(1) or "M"
        payload = field_data[m.end():]
        return payload, _ERR_MAP.get(level, qrcode.constants.ERROR_CORRECT_M)
    return field_data, qrcode.constants.ERROR_CORRECT_M


def qr(data: str, *, magnification: int = 3, error_correction: int | None = None) -> Image.Image:
    """Wyrenderuj kod QR do obrazu PIL. ``magnification`` = punkty na moduł."""
    payload, err = parse_qr_field(data)
    if error_correction is not None:
        err = error_correction
    qrc = qrcode.QRCode(
        error_correction=err,
        box_size=max(1, magnification),
        border=0,
    )
    qrc.add_data(payload)
    qrc.make(fit=True)
    img = qrc.make_image(fill_color="black", back_color="white")
    return img.convert("L")
