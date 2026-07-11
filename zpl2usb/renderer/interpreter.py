"""Interpreter podzbioru ZPL -> obraz rastrowy (PIL).

Obsługiwany podzbiór (MVP):
  struktura  : ^XA ^XZ ^FS
  ustawienia : ^PW ^LL ^LH ^CF ^CI (^CI ignorowane poza deklaracją)
  pozycja    : ^FO ^FT
  tekst      : ^A (font 0 skalowalny), ^FD
  grafika    : ^GB (ramki/linie), ^GF (bitmapa ASCII-hex), ^FR (odwrócenie)
  kody       : ^BY, ^BC (Code128), ^BQ (QR)

Nieobsługiwane polecenia są pomijane i raportowane w ``RenderResult.warnings``.
"""

from __future__ import annotations

import binascii
from dataclasses import dataclass, field

from PIL import Image, ImageDraw

from . import barcodes
from .fonts import get_font
from .parser import Command, tokenize
from .units import mm_to_dots

WHITE = 255
BLACK = 0

DEFAULT_FONT_HEIGHT = 30


@dataclass
class RenderResult:
    image: Image.Image
    warnings: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)


@dataclass
class _Field:
    """Stan budowanego pola między ^FO/^A/^FD a ^FS."""

    x: int = 0
    y: int = 0
    baseline: bool = False  # True dla ^FT (pozycja = linia bazowa)
    data: str = ""
    kind: str = "text"  # text | box | code128 | qr | graphic
    reverse: bool = False
    # font
    font_h: int = DEFAULT_FONT_HEIGHT
    font_w: int = DEFAULT_FONT_HEIGHT
    # box (^GB)
    box_w: int = 0
    box_h: int = 0
    box_t: int = 1
    box_color: str = "B"
    # barcode
    bc_module: int = 2
    bc_height: int = 100
    bc_line: bool = True  # linia interpretacji (tekst pod kodem)
    qr_mag: int = 3
    # graphic (^GF)
    gf_data: str = ""
    gf_bytes_per_row: int = 0
    gf_total_bytes: int = 0
    gf_compression: str = "A"


def _ints(params: str) -> list[int]:
    out = []
    for part in params.split(","):
        part = part.strip()
        try:
            out.append(int(part))
        except ValueError:
            out.append(0)
    return out


class Interpreter:
    def __init__(self, dpi: int, label_w: int, label_h: int):
        self.dpi = dpi
        self.image = Image.new("L", (max(1, label_w), max(1, label_h)), WHITE)
        self.draw = ImageDraw.Draw(self.image)
        self.warnings: list[str] = []
        self.unsupported: list[str] = []
        # stan globalny
        self.lh_x = 0
        self.lh_y = 0
        self.cf_h = DEFAULT_FONT_HEIGHT
        self.cf_w = DEFAULT_FONT_HEIGHT
        self.by_module = 2
        self.by_height = 100
        self.field: _Field | None = None

    # --- pomocnicze ---------------------------------------------------------
    def _new_field(self) -> _Field:
        return _Field(
            font_h=self.cf_h, font_w=self.cf_w, bc_module=self.by_module, bc_height=self.by_height
        )

    def _ensure_field(self) -> _Field:
        if self.field is None:
            self.field = self._new_field()
        return self.field

    # --- obsługa poleceń ----------------------------------------------------
    def run(self, commands: list[Command]) -> None:
        for cmd in commands:
            handler = getattr(self, f"_cmd_{cmd.name}", None)
            if handler is None:
                if cmd.name not in self.unsupported:
                    self.unsupported.append(cmd.name)
                continue
            handler(cmd.params)

    def _cmd_XA(self, params: str) -> None:
        self.field = None

    def _cmd_XZ(self, params: str) -> None:
        self.field = None

    def _cmd_LH(self, params: str) -> None:
        v = _ints(params)
        if len(v) >= 2:
            self.lh_x, self.lh_y = v[0], v[1]

    def _cmd_PW(self, params: str) -> None:
        pass  # rozmiar płótna ustalany przed uruchomieniem (patrz render())

    def _cmd_LL(self, params: str) -> None:
        pass

    def _cmd_CI(self, params: str) -> None:
        pass  # zestaw znaków — pomijamy (traktujemy dane jako tekst)

    def _cmd_CF(self, params: str) -> None:
        # ^CF f,h,w — domyślny font. Wysokość ustawia też szerokość, chyba że
        # podano osobną szerokość (3. pole).
        parts = params.split(",")
        if len(parts) >= 2 and parts[1].strip().isdigit():
            self.cf_h = int(parts[1])
            self.cf_w = self.cf_h
        if len(parts) >= 3 and parts[2].strip().isdigit():
            self.cf_w = int(parts[2])

    def _cmd_FO(self, params: str) -> None:
        self._set_position(params, baseline=False)

    def _cmd_FT(self, params: str) -> None:
        self._set_position(params, baseline=True)

    def _set_position(self, params: str, baseline: bool) -> None:
        f = self._ensure_field()
        v = _ints(params)
        if len(v) >= 2:
            f.x, f.y = v[0], v[1]
        f.baseline = baseline

    def _cmd_A(self, params: str) -> None:
        # ^A f,o,h,w  — font id (1 znak), orientacja, wysokość, szerokość
        f = self._ensure_field()
        f.kind = "text"
        rest = params[1:] if params else ""
        parts = [p.strip() for p in rest.split(",") if p.strip() != ""]
        # opcjonalna orientacja (litera) na początku
        nums = []
        for p in parts:
            if p.isalpha():
                continue
            try:
                nums.append(int(p))
            except ValueError:
                pass
        if nums:
            f.font_h = nums[0]
            f.font_w = nums[1] if len(nums) > 1 else nums[0]

    def _cmd_BY(self, params: str) -> None:
        v = _ints(params)
        if v and v[0] > 0:
            self.by_module = v[0]
        if len(v) >= 3 and v[2] > 0:
            self.by_height = v[2]

    def _cmd_BC(self, params: str) -> None:
        f = self._ensure_field()
        f.kind = "code128"
        f.bc_module = self.by_module
        parts = params.split(",")
        # ^BCo,h,f,g,e,m : o orient, h height, f linia interpretacji (Y/N)
        if len(parts) >= 2 and parts[1].strip().isdigit():
            f.bc_height = int(parts[1])
        else:
            f.bc_height = self.by_height
        if len(parts) >= 3:
            f.bc_line = parts[2].strip().upper() != "N"

    def _cmd_BQ(self, params: str) -> None:
        f = self._ensure_field()
        f.kind = "qr"
        # ^BQa,b,c : b model, c magnification
        v = _ints(params)
        if len(v) >= 3 and v[2] > 0:
            f.qr_mag = v[2]

    def _cmd_GB(self, params: str) -> None:
        f = self._ensure_field()
        f.kind = "box"
        v = _ints(params)
        f.box_w = v[0] if len(v) > 0 else 0
        f.box_h = v[1] if len(v) > 1 else 0
        f.box_t = v[2] if len(v) > 2 and v[2] > 0 else 1
        # kolor: parts[3] litera
        parts = params.split(",")
        if len(parts) >= 4 and parts[3].strip():
            f.box_color = parts[3].strip().upper()[0]

    def _cmd_GF(self, params: str) -> None:
        f = self._ensure_field()
        f.kind = "graphic"
        # ^GFa,b,c,d,data — a=kompresja, b=liczba bajtów, d=bajty/wiersz, data=hex.
        comp = "A"
        b = d = 0
        parts = params.split(",", 4)
        if len(parts) >= 1 and parts[0].strip():
            comp = parts[0].strip().upper()[0]
        if len(parts) >= 2 and parts[1].strip().isdigit():
            b = int(parts[1])
        if len(parts) >= 4 and parts[3].strip().isdigit():
            d = int(parts[3])
        data = parts[4] if len(parts) >= 5 else ""
        f.gf_compression = comp
        f.gf_total_bytes = b
        f.gf_bytes_per_row = d
        f.gf_data = data

    def _cmd_FR(self, params: str) -> None:
        self._ensure_field().reverse = True

    def _cmd_FH(self, params: str) -> None:
        pass  # heksadecymalne escapowanie danych — pomijamy (rzadkie)

    def _cmd_FD(self, params: str) -> None:
        self._ensure_field().data = params

    def _cmd_FS(self, params: str) -> None:
        if self.field is not None:
            self._render_field(self.field)
        self.field = None

    # --- rysowanie ----------------------------------------------------------
    def _render_field(self, f: _Field) -> None:
        x = f.x + self.lh_x
        y = f.y + self.lh_y
        try:
            if f.kind == "text":
                self._render_text(f, x, y)
            elif f.kind == "box":
                self._render_box(f, x, y)
            elif f.kind == "code128":
                self._render_code128(f, x, y)
            elif f.kind == "qr":
                self._render_qr(f, x, y)
            elif f.kind == "graphic":
                self._render_graphic(f, x, y)
        except Exception as exc:  # render best-effort — nie przerywamy etykiety
            self.warnings.append(f"Pole {f.kind} @({x},{y}) pominięte: {exc}")

    def _render_text(self, f: _Field, x: int, y: int) -> None:
        if not f.data:
            return
        font = get_font(f.font_h)
        color = WHITE if f.reverse else BLACK
        anchor = "ls" if f.baseline else "la"
        self.draw.text((x, y), f.data, fill=color, font=font, anchor=anchor)

    def _render_box(self, f: _Field, x: int, y: int) -> None:
        color = WHITE if f.box_color == "W" else BLACK
        w, h, t = f.box_w, f.box_h, f.box_t
        if w <= 0 or h <= 0:
            return
        if w <= t or h <= t:  # linia (pionowa lub pozioma) — wypełniony prostokąt
            self.draw.rectangle([x, y, x + w, y + h], fill=color)
        else:
            self.draw.rectangle([x, y, x + w, y + h], outline=color, width=t)

    def _render_code128(self, f: _Field, x: int, y: int) -> None:
        img = barcodes.code128(
            f.data,
            module_width_dots=f.bc_module,
            height_dots=f.bc_height,
            dpi=self.dpi,
            write_text=f.bc_line,
        )
        self.image.paste(img, (x, y))

    def _render_qr(self, f: _Field, x: int, y: int) -> None:
        img = barcodes.qr(f.data, magnification=f.qr_mag)
        self.image.paste(img, (x, y))

    def _render_graphic(self, f: _Field, x: int, y: int) -> None:
        if f.gf_compression != "A":
            self.warnings.append(f"^GF kompresja {f.gf_compression!r} nieobsługiwana")
            return
        if f.gf_bytes_per_row <= 0:
            return
        hexstr = "".join(ch for ch in f.gf_data if ch in "0123456789abcdefABCDEF")
        try:
            raw = binascii.unhexlify(hexstr[: (len(hexstr) // 2) * 2])
        except binascii.Error as exc:
            self.warnings.append(f"^GF błędne dane hex: {exc}")
            return
        bpr = f.gf_bytes_per_row
        rows = len(raw) // bpr
        if rows == 0:
            return
        width = bpr * 8
        bitmap = Image.new("L", (width, rows), WHITE)
        px = bitmap.load()
        for r in range(rows):
            for byte_i in range(bpr):
                byte = raw[r * bpr + byte_i]
                for bit in range(8):
                    if byte & (0x80 >> bit):
                        px[byte_i * 8 + bit, r] = BLACK
        self.image.paste(bitmap, (x, y))


def _resolve_label_size(commands, dpi, default_label_mm):
    """Ustal rozmiar płótna: ^PW/^LL jeśli obecne, inaczej domyślny z mm."""
    width = height = None
    for c in commands:
        if c.name == "PW":
            v = _ints(c.params)
            if v and v[0] > 0:
                width = v[0]
        elif c.name == "LL":
            v = _ints(c.params)
            if v and v[0] > 0:
                height = v[0]
    if width is None:
        width = mm_to_dots(default_label_mm[0], dpi)
    if height is None:
        height = mm_to_dots(default_label_mm[1], dpi)
    return width, height


def render(zpl, dpi: int = 203, default_label_mm=(100.0, 40.0)) -> RenderResult:
    """Wyrenderuj pierwsze zadanie ZPL do obrazu.

    Zwraca ``RenderResult`` z obrazem oraz listami ostrzeżeń i nieobsługiwanych
    poleceń. Jeśli strumień zawiera wiele ^XA..^XZ, renderowany jest cały wsad
    na jednym płótnie (kolejne etykiety nadpisują pozycje) — router woła render
    per zadanie, więc w praktyce trafia tu jedno zadanie.
    """
    commands = tokenize(zpl)
    label_w, label_h = _resolve_label_size(commands, dpi, default_label_mm)
    interp = Interpreter(dpi, label_w, label_h)
    interp.run(commands)
    return RenderResult(
        image=interp.image,
        warnings=interp.warnings,
        unsupported=interp.unsupported,
    )
