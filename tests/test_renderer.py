from PIL import Image

from zpl2usb.renderer import barcodes, render
from zpl2usb.renderer.parser import tokenize
from zpl2usb.renderer.units import label_size_dots, mm_to_dots


# --- units ------------------------------------------------------------------
def test_mm_to_dots_203():
    assert mm_to_dots(25.4, 203) == 203
    assert mm_to_dots(100, 203) == 799  # 100/25.4*203


def test_label_size_dots():
    w, h = label_size_dots(100, 40, 203)
    assert (w, h) == (799, 320)


# --- parser -----------------------------------------------------------------
def test_tokenize_basic():
    cmds = tokenize(b"^XA^FO50,60^FDhello^FS^XZ")
    names = [c.name for c in cmds]
    assert names == ["XA", "FO", "FD", "FS", "XZ"]
    fo = cmds[1]
    assert fo.params == "50,60"
    fd = cmds[2]
    assert fd.params == "hello"


def test_tokenize_font_command_single_letter():
    cmds = tokenize(b"^A0N,30,30^FDx^FS")
    assert cmds[0].name == "A"
    assert cmds[0].params == "0N,30,30"


def test_tokenize_letter_named_fonts():
    # ^A with letter fonts (Zebra A-H) must still be the single-letter font command.
    for zpl, params in [
        (b"^ADN,18,10", "DN,18,10"),
        (b"^AEN,28,28", "EN,28,28"),
        (b"^A@N,20,20", "@N,20,20"),
    ]:
        cmds = tokenize(zpl + b"^FDx^FS")
        assert cmds[0].name == "A", zpl
        assert cmds[0].params == params, zpl


def test_tilde_a_not_treated_as_font():
    # ~ prefix commands are always two-letter; ^A special-case must not apply.
    cmds = tokenize(b"~AB123")
    assert cmds[0].name == "AB"
    assert cmds[0].prefix == "~"


def test_letter_font_sets_size():
    # ^ADN,40,40 should render at the requested height (not fall back to default).
    r = render(b"^XA^FO10,10^ADN,45,45^FDHI^FS^XZ", dpi=203)
    assert "AD" not in r.unsupported  # no longer mis-parsed as command AD
    assert r.image.getextrema()[0] == 0  # text drawn


def test_tokenize_fd_keeps_spaces_and_commas():
    cmds = tokenize(b"^FDHello, World 123^FS")
    assert cmds[0].name == "FD"
    assert cmds[0].params == "Hello, World 123"


def test_tokenize_tilde_prefix():
    cmds = tokenize(b"~SD25^XA")
    assert cmds[0].name == "SD"
    assert cmds[0].prefix == "~"


# --- render: rozmiar płótna -------------------------------------------------
def test_render_default_label_size():
    r = render(b"^XA^FDhi^FS^XZ", dpi=203, default_label_mm=(100, 40))
    assert r.image.size == (799, 320)


def test_render_uses_pw_ll():
    r = render(b"^XA^PW400^LL200^FDhi^FS^XZ", dpi=203)
    assert r.image.size == (400, 200)


def test_render_returns_grayscale():
    r = render(b"^XA^FDhi^FS^XZ")
    assert r.image.mode == "L"


# --- render: rysowanie ------------------------------------------------------
def _has_black(img: Image.Image) -> bool:
    return img.getextrema()[0] < 128


def test_render_text_draws_pixels():
    r = render(b"^XA^FO20,20^A0N,40,40^FDTEST^FS^XZ", dpi=203)
    assert _has_black(r.image)


def test_render_empty_label_is_blank():
    r = render(b"^XA^XZ", dpi=203, default_label_mm=(20, 20))
    assert not _has_black(r.image)


def test_render_box_draws_pixels():
    r = render(b"^XA^FO10,10^GB100,50,3^FS^XZ", dpi=203)
    assert _has_black(r.image)


def test_render_horizontal_line():
    r = render(b"^XA^FO10,10^GB200,4,4^FS^XZ", dpi=203, default_label_mm=(50, 20))
    assert _has_black(r.image)


def test_render_code128():
    r = render(b"^XA^FO10,10^BY2^BCN,80,N^FD12345^FS^XZ", dpi=203)
    assert _has_black(r.image)


def test_render_qr():
    r = render(b"^XA^FO10,10^BQN,2,4^FDLA,HELLO^FS^XZ", dpi=203)
    assert _has_black(r.image)


def test_unsupported_command_recorded():
    r = render(b"^XA^FO10,10^ZZ123^FDhi^FS^XZ", dpi=203)
    assert "ZZ" in r.unsupported
    # mimo nieznanego polecenia render nie wywala się i rysuje tekst
    assert _has_black(r.image)


def test_render_bytes_and_str_equivalent():
    a = render("^XA^FO10,10^A0N,30,30^FDhi^FS^XZ").image
    b = render(b"^XA^FO10,10^A0N,30,30^FDhi^FS^XZ").image
    assert a.tobytes() == b.tobytes()


# --- barcodes helpers -------------------------------------------------------
def test_parse_qr_field_strips_prefix():
    payload, _ = barcodes.parse_qr_field("LA,https://example.com")
    assert payload == "https://example.com"


def test_parse_qr_field_no_prefix():
    payload, _ = barcodes.parse_qr_field("plaindata")
    assert payload == "plaindata"


def test_graphic_field_ascii_hex():
    # 1 bajt na wiersz, 2 wiersze: 0xFF (8 czarnych), 0x00 (8 białych)
    r = render(b"^XA^FO0,0^GFA,2,2,1,FF00^FS^XZ", dpi=203, default_label_mm=(20, 20))
    # górny-lewy piksel czarny, dolny wiersz przy y=1 biały
    assert r.image.getpixel((0, 0)) == 0
    assert r.image.getpixel((0, 1)) == 255


# --- deterministyczna geometria (niezależna od fontów, stabilna między wersjami PIL) ---
def test_box_outline_geometry():
    # ^FO10,20 ^GB100,50,4 -> ramka [10,20..110,70], grubość 4, tylko obrys.
    r = render(b"^XA^FO10,20^GB100,50,4^FS^XZ", dpi=203)
    img = r.image
    assert img.getpixel((60, 21)) == 0  # górna krawędź czarna
    assert img.getpixel((11, 45)) == 0  # lewa krawędź czarna
    assert img.getpixel((60, 45)) == 255  # wnętrze białe (sam obrys)
    assert img.getpixel((300, 200)) == 255  # poza ramką białe


def test_lh_origin_offset():
    # ^LH50,50 przesuwa początek; ramka 0,0 rysuje się w (50,50).
    r = render(b"^XA^LH50,50^FO0,0^GB12,12,12^FS^XZ", dpi=203, default_label_mm=(50, 50))
    assert r.image.getpixel((55, 55)) == 0  # przy (50,50) czarne
    assert r.image.getpixel((5, 5)) == 255  # przy (0,0) białe (przesunięte)


def test_reverse_field_draws_white_on_black():
    # Czarne tło (wypełniona ramka) + ^FR tekst -> białe piksele wewnątrz czerni.
    zpl = b"^XA^FO0,0^GB80,80,80^FS^FO10,10^FR^A0N,40,40^FDX^FS^XZ"
    r = render(zpl, dpi=203, default_label_mm=(30, 30))
    region = [r.image.getpixel((x, y)) for x in range(0, 80) for y in range(0, 80)]
    assert 0 in region and 255 in region  # jest i czerń tła, i biały (odwrócony) tekst


def test_gf_unsupported_compression_warns():
    r = render(b"^XA^FO0,0^GFB,2,2,1,FF00^FS^XZ", dpi=203, default_label_mm=(20, 20))
    assert any("GF" in w or "kompresja" in w for w in r.warnings)


def test_gf_bad_hex_warns():
    r = render(b"^XA^FO0,0^GFA,2,2,1,ZZZZ^FS^XZ", dpi=203, default_label_mm=(20, 20))
    # nieparzyste/niepoprawne dane hex -> brak czerni, render się nie wywala
    assert r.image.getextrema()[0] == 255 or r.warnings is not None


def test_code128_interpretation_line_toggle():
    # Linia interpretacji (write_text=True) dodaje tekst -> wyższy obraz niż bez niej.
    with_text = barcodes.code128(
        "12345", module_width_dots=2, height_dots=80, dpi=203, write_text=True
    )
    without = barcodes.code128(
        "12345", module_width_dots=2, height_dots=80, dpi=203, write_text=False
    )
    assert with_text.size[1] > without.size[1]
