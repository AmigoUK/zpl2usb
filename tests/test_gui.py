import importlib

import pytest
from PIL import Image

from zpl2usb.config import Mapping
from zpl2usb.gui.formstate import (
    form_to_mapping,
    mapping_label,
    mapping_to_form,
    wms_hint,
)
from zpl2usb.gui.icon import make_icon


# --- formstate --------------------------------------------------------------
def test_form_roundtrip():
    m = Mapping(
        listen_port=9100,
        target_printer="Toshiba B-EX",
        mode="render",
        dpi=300,
        default_label_mm=(60.0, 30.0),
    )
    form = mapping_to_form(m)
    assert form["listen_port"] == "9100"
    assert form["dpi"] == "300"
    assert form["label_w"] == "60"
    back = form_to_mapping(form)
    assert back == m


def test_form_includes_listen_host():
    m = Mapping(listen_host="192.168.1.50")
    form = mapping_to_form(m)
    assert form["listen_host"] == "192.168.1.50"
    assert form_to_mapping(form).listen_host == "192.168.1.50"


def test_form_invalid_host_rejected():
    form = mapping_to_form(Mapping())
    form["listen_host"] = "999.1.1.1"
    with pytest.raises(ValueError):
        form_to_mapping(form)


def test_wms_hint_specific_ip():
    assert wms_hint("192.168.1.50", "9100") == "W systemie WMS ustaw druk na:  192.168.1.50:9100"


def test_wms_hint_all_interfaces():
    hint = wms_hint("0.0.0.0", "9100")
    assert "adres IP tego komputera" in hint
    assert "9100" in hint


def test_wms_hint_empty_host():
    assert wms_hint("", "9100") == ""


def test_mapping_label():
    m = Mapping(listen_host="192.168.1.50", listen_port=9100, target_printer="Zebra", mode="raw")
    assert mapping_label(m) == "192.168.1.50:9100 → Zebra (raw)"


def test_mapping_label_no_printer_and_disabled():
    m = Mapping(
        listen_host="0.0.0.0", listen_port=9101, target_printer="", mode="render", enabled=False
    )
    label = mapping_label(m)
    assert "(brak drukarki)" in label
    assert "[wył.]" in label


def test_form_default_label_formatting():
    form = mapping_to_form(Mapping())
    assert form["label_w"] == "100"
    assert form["label_h"] == "40"


def test_form_accepts_comma_decimal():
    form = mapping_to_form(Mapping())
    form["label_w"] = "50,5"
    m = form_to_mapping(form)
    assert m.default_label_mm[0] == 50.5


def test_form_invalid_port_message():
    form = mapping_to_form(Mapping())
    form["listen_port"] = "abc"
    with pytest.raises(ValueError, match="Port"):
        form_to_mapping(form)


def test_form_invalid_dpi():
    form = mapping_to_form(Mapping())
    form["dpi"] = "150"
    with pytest.raises(ValueError, match="DPI"):
        form_to_mapping(form)


def test_form_invalid_mode():
    form = mapping_to_form(Mapping())
    form["mode"] = "xxx"
    with pytest.raises(ValueError, match="tryb"):
        form_to_mapping(form)


# --- icon -------------------------------------------------------------------
def test_make_icon_returns_image():
    img = make_icon(64, running=True)
    assert isinstance(img, Image.Image)
    assert img.size == (64, 64)


def test_make_icon_running_vs_stopped_differ():
    a = make_icon(64, running=True).tobytes()
    b = make_icon(64, running=False).tobytes()
    assert a != b


# --- importowalność modułów GUI (bez tworzenia okien) -----------------------
def test_window_module_imports():
    mod = importlib.import_module("zpl2usb.gui.window")
    assert hasattr(mod, "SettingsWindow")


def test_tray_module_imports_without_pystray():
    # Import modułu nie może wymagać pystray (import jest leniwy w __init__).
    mod = importlib.import_module("zpl2usb.gui.tray")
    assert hasattr(mod, "Tray")


# --- logika tray z podstawionym pystray (bez prawdziwego zasobnika) ---------
class _FakePystray:
    SEPARATOR = object()

    class Menu:
        SEPARATOR = object()

        def __init__(self, *items):
            self.items = items

    class MenuItem:
        def __init__(self, text, action, default=False, checked=None):
            self.text, self.action, self.checked = text, action, checked

    class Icon:
        def __init__(self, name, icon=None, title=None, menu=None):
            self.name, self.icon, self.title, self.menu = name, icon, title, menu
            self.running = False

        def run_detached(self):
            self.running = True

        def stop(self):
            self.running = False


class _StubApp:
    def __init__(self):
        self._running = False

    def is_running(self):
        return self._running

    def start(self):
        self._running = True
        return []

    def stop(self):
        self._running = False


def _make_tray(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "pystray", _FakePystray)
    from zpl2usb.gui.tray import Tray

    events = {"open": 0, "quit": 0}
    app = _StubApp()
    tray = Tray(
        app,
        on_open=lambda: events.__setitem__("open", events["open"] + 1),
        on_quit=lambda: events.__setitem__("quit", events["quit"] + 1),
    )
    return tray, app, events


def test_tray_start_stop_callbacks(monkeypatch):
    tray, app, _ = _make_tray(monkeypatch)
    assert not app.is_running()
    tray._start()
    assert app.is_running()
    tray._stop()
    assert not app.is_running()


def test_tray_open_and_quit_callbacks(monkeypatch):
    tray, app, events = _make_tray(monkeypatch)
    tray._open()
    assert events["open"] == 1
    tray._quit()
    assert events["quit"] == 1
    assert tray.icon.running is False  # _quit zatrzymuje ikonę


def test_tray_update_icon_changes_image(monkeypatch):
    tray, app, _ = _make_tray(monkeypatch)
    before = tray.icon.icon
    app._running = True
    tray._update_icon()
    assert tray.icon.icon is not before


def test_tray_title_is_latin1_safe(monkeypatch):
    # Backend Xorg pystray koduje tytuł jako latin-1 — musi być bez znaków spoza.
    tray, _, _ = _make_tray(monkeypatch)
    tray.icon.title.encode("latin-1")  # nie może rzucić UnicodeEncodeError
