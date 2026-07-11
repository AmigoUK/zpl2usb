"""Testy okna Tkinter — pomijane, gdy brak środowiska graficznego (DISPLAY)."""

import pytest

from zpl2usb.app import App
from zpl2usb.config import Config, Mapping
from tests.test_router import FakeBackend

tk = pytest.importorskip("tkinter")


@pytest.fixture(autouse=True)
def _no_modal_dialogs(monkeypatch):
    """Zamień modalne okienka na no-op, żeby testy się nie blokowały."""
    import zpl2usb.gui.window as win
    for name in ("showinfo", "showerror", "showwarning"):
        monkeypatch.setattr(win.messagebox, name, lambda *a, **k: None)


@pytest.fixture()
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("Brak środowiska graficznego (DISPLAY)")
    r.withdraw()
    yield r
    r.destroy()


def _make_app():
    cfg = Config(mappings=[Mapping(listen_host="0.0.0.0", listen_port=9100,
                 target_printer="Zebra", mode="raw")], autostart=True)
    return App(cfg=cfg, backend=FakeBackend())


def test_window_lists_initial_mapping(root):
    from zpl2usb.gui.window import SettingsWindow
    app = _make_app()
    w = SettingsWindow(app, root)
    assert w.listbox.size() == 1
    assert "Zebra" in w.listbox.get(0)


def test_window_add_remove_mapping(root):
    from zpl2usb.gui.window import SettingsWindow
    app = _make_app()
    w = SettingsWindow(app, root)
    w.add_mapping()
    assert w.listbox.size() == 2
    w.remove_mapping()
    assert w.listbox.size() == 1


def test_window_cannot_remove_last(root):
    from zpl2usb.gui.window import SettingsWindow
    app = _make_app()
    w = SettingsWindow(app, root)
    w.remove_mapping()  # tylko jedno — nie usuwa
    assert w.listbox.size() == 1


def test_window_save_builds_config(root, monkeypatch):
    from zpl2usb.gui.window import SettingsWindow
    app = _make_app()
    captured = {}

    def fake_apply(cfg):
        captured["cfg"] = cfg
        return []

    monkeypatch.setattr(app, "apply_config", fake_apply)
    monkeypatch.setattr(app, "set_autostart", lambda enabled: captured.__setitem__("as", enabled))
    w = SettingsWindow(app, root)
    w.add_mapping()
    w._vars["listen_host"].set("192.168.1.50")
    w._vars["listen_port"].set("9101")
    w._vars["target_printer"].set("Toshiba")
    w.autostart_var.set(False)
    w.save_and_restart()
    assert len(captured["cfg"].mappings) == 2
    assert captured["as"] is False
