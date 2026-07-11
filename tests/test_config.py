import json

import pytest

from zpl2usb.config import (
    Config,
    ConfigError,
    Mapping,
    load,
    save,
)


def test_default_config_valid():
    cfg = Config()
    cfg.validate()
    assert len(cfg.mappings) == 1
    m = cfg.mappings[0]
    assert m.listen_port == 9100
    assert m.mode == "raw"
    assert m.dpi == 203
    assert m.default_label_mm == (100.0, 40.0)


def test_roundtrip_dict():
    cfg = Config(mappings=[
        Mapping(listen_port=9100, target_printer="Zebra", mode="raw", dpi=203),
        Mapping(listen_port=9101, target_printer="Toshiba", mode="render", dpi=300,
                default_label_mm=(60.0, 30.0)),
    ])
    cfg.validate()
    restored = Config.from_dict(cfg.to_dict())
    assert restored == cfg


def test_save_load_roundtrip(tmp_path):
    p = tmp_path / "config.json"
    cfg = Config(mappings=[Mapping(target_printer="Toshiba B-EX", mode="render")])
    save(cfg, p)
    assert p.exists()
    loaded = load(p)
    assert loaded == cfg


def test_load_missing_returns_default(tmp_path):
    loaded = load(tmp_path / "nope.json")
    assert loaded == Config()


def test_load_corrupt_raises(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{ not valid json", encoding="utf-8")
    with pytest.raises(ConfigError):
        load(p)


def test_default_listen_host():
    assert Mapping().listen_host == "0.0.0.0"


def test_listen_host_valid_ip():
    m = Mapping(listen_host="192.168.1.50")
    m.validate()
    assert m.listen_host == "192.168.1.50"


def test_listen_host_invalid_ip():
    with pytest.raises(ConfigError, match="IPv4"):
        Mapping(listen_host="not.an.ip").validate()


def test_listen_host_roundtrip(tmp_path):
    p = tmp_path / "config.json"
    cfg = Config(mappings=[Mapping(listen_host="10.0.0.12", target_printer="X")])
    save(cfg, p)
    assert load(p).mappings[0].listen_host == "10.0.0.12"


def test_invalid_port():
    with pytest.raises(ConfigError):
        Mapping(listen_port=70000).validate()


def test_invalid_mode():
    with pytest.raises(ConfigError):
        Mapping(mode="bogus").validate()


def test_invalid_dpi():
    with pytest.raises(ConfigError):
        Mapping(dpi=150).validate()


def test_invalid_label_size():
    with pytest.raises(ConfigError):
        Mapping(default_label_mm=(0, 40)).validate()


def test_duplicate_host_port_rejected():
    cfg = Config(mappings=[Mapping(listen_port=9100), Mapping(listen_port=9100)])
    with pytest.raises(ConfigError):
        cfg.validate()


def test_same_port_different_host_allowed():
    cfg = Config(mappings=[
        Mapping(listen_host="192.168.1.10", listen_port=9100, target_printer="A"),
        Mapping(listen_host="10.0.0.5", listen_port=9100, target_printer="B"),
    ])
    cfg.validate()  # nie rzuca — różne adresy


def test_autostart_default_true():
    assert Config().autostart is True


def test_autostart_roundtrip(tmp_path):
    p = tmp_path / "config.json"
    cfg = Config(mappings=[Mapping(target_printer="X")], autostart=False)
    save(cfg, p)
    assert load(p).autostart is False


def test_autostart_from_dict_default():
    cfg = Config.from_dict({"mappings": [{"target_printer": "X"}]})
    assert cfg.autostart is True


def test_empty_mappings_from_dict_gets_default():
    cfg = Config.from_dict({"mappings": []})
    assert cfg == Config()


def test_from_dict_partial_fields():
    cfg = Config.from_dict({"mappings": [{"target_printer": "X"}]})
    m = cfg.mappings[0]
    assert m.target_printer == "X"
    assert m.listen_port == 9100  # domyślne uzupełnione


def test_saved_json_is_readable(tmp_path):
    p = tmp_path / "config.json"
    save(Config(), p)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["mappings"][0]["default_label_mm"] == [100.0, 40.0]
