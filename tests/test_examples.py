from pathlib import Path

from zpl2usb.renderer import render

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_sample_label_renders_cleanly():
    data = (EXAMPLES / "sample_100x40.zpl").read_bytes()
    result = render(data, dpi=203, default_label_mm=(100, 40))
    assert result.image.size == (799, 320)
    # są czarne piksele (coś się wyrenderowało)
    assert result.image.getextrema()[0] == 0
    # przykład używa wyłącznie obsługiwanych poleceń
    assert result.unsupported == []
