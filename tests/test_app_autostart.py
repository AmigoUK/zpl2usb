from zpl2usb import app as app_mod
from zpl2usb.app import App
from zpl2usb.config import Config, Mapping

from tests.test_router import FakeBackend


def _app():
    cfg = Config(mappings=[Mapping(listen_port=0, target_printer="Zebra")], autostart=True)
    return App(cfg=cfg, backend=FakeBackend())


def test_set_autostart_saves_and_applies(monkeypatch):
    saved = {}
    applied = {}
    monkeypatch.setattr(app_mod.config_mod, "save", lambda cfg: saved.update(v=cfg.autostart))
    monkeypatch.setattr(app_mod.autostart_mod, "set_autostart",
                        lambda enabled, **kw: applied.update(v=enabled))
    app = _app()
    app.set_autostart(False)
    assert app.config.autostart is False
    assert saved["v"] is False
    assert applied["v"] is False


def test_sync_autostart_noop_when_not_frozen(monkeypatch):
    called = {"enable": 0, "disable": 0}

    class Fake:
        def is_enabled(self): return False
        def enable(self): called["enable"] += 1
        def disable(self): called["disable"] += 1

    monkeypatch.setattr(app_mod.autostart_mod, "get_autostart", lambda: Fake())
    monkeypatch.setattr(app_mod.sys, "frozen", False, raising=False)
    _app().sync_autostart()
    assert called == {"enable": 0, "disable": 0}  # ze źródeł nie ruszamy systemu


def test_sync_autostart_enables_when_frozen(monkeypatch):
    called = {"enable": 0, "disable": 0}

    class Fake:
        def is_enabled(self): return False
        def enable(self): called["enable"] += 1
        def disable(self): called["disable"] += 1

    monkeypatch.setattr(app_mod.autostart_mod, "get_autostart", lambda: Fake())
    monkeypatch.setattr(app_mod.sys, "frozen", True, raising=False)
    app = _app()
    app.config.autostart = True
    app.sync_autostart()
    assert called["enable"] == 1
