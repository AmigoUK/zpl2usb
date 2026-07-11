from zpl2usb import netutil
from zpl2usb.netutil import _is_usable, list_local_ipv4, order_addresses


def test_is_usable_filters():
    assert _is_usable("192.168.1.10")
    assert _is_usable("10.0.0.5")
    assert not _is_usable("127.0.0.1")  # loopback
    assert not _is_usable("169.254.1.1")  # link-local
    assert not _is_usable("0.0.0.0")  # unspecified
    assert not _is_usable("garbage")


def test_order_addresses_primary_first():
    out = order_addresses(["10.0.0.5", "192.168.1.10"], primary="192.168.1.10")
    assert out == ["192.168.1.10", "10.0.0.5"]


def test_order_addresses_dedupes():
    out = order_addresses(["10.0.0.5", "10.0.0.5", "192.168.1.10"], primary=None)
    assert out == ["10.0.0.5", "192.168.1.10"]


def test_order_addresses_ignores_bad_primary():
    out = order_addresses(["10.0.0.5"], primary="127.0.0.1")
    assert out == ["10.0.0.5"]


def test_list_local_ipv4_includes_all_interfaces_option():
    addrs = list_local_ipv4()
    assert addrs[-1] == "0.0.0.0"
    # wszystkie pozostałe są użyteczne
    assert all(_is_usable(a) for a in addrs[:-1])


def test_list_uses_socket_fallback_when_no_psutil(monkeypatch):
    monkeypatch.setattr(netutil, "_collect_via_psutil", lambda: [])
    monkeypatch.setattr(netutil, "_collect_via_socket", lambda: ["192.168.5.5"])
    monkeypatch.setattr(netutil, "default_route_ip", lambda: None)
    assert list_local_ipv4() == ["192.168.5.5", "0.0.0.0"]


def test_list_prefers_default_route(monkeypatch):
    monkeypatch.setattr(netutil, "_collect_via_psutil", lambda: ["10.0.0.9", "192.168.1.20"])
    monkeypatch.setattr(netutil, "default_route_ip", lambda: "192.168.1.20")
    assert list_local_ipv4() == ["192.168.1.20", "10.0.0.9", "0.0.0.0"]
