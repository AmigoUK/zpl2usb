import socket
import time

from zpl2usb.config import Config, Mapping
from zpl2usb.router import Router
from zpl2usb.server import RawPrintServer
from zpl2usb.app import App

from tests.test_router import FakeBackend


def _wait(cond, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def _send(port: int, data: bytes):
    s = socket.create_connection(("127.0.0.1", port), timeout=2)
    try:
        s.sendall(data)
    finally:
        s.close()


def test_server_routes_raw_job():
    be = FakeBackend()
    mapping = Mapping(listen_port=0, target_printer="Zebra", mode="raw")
    srv = RawPrintServer(mapping, Router(be))
    srv.start()
    try:
        _send(srv.port, b"^XA^FDhello^XZ")
        assert _wait(lambda: len(be.raw_calls) == 1)
        assert be.raw_calls[0] == ("Zebra", b"^XA^FDhello^XZ")
    finally:
        srv.stop()


def test_server_splits_two_jobs_in_one_send():
    be = FakeBackend()
    mapping = Mapping(listen_port=0, target_printer="Zebra", mode="raw")
    srv = RawPrintServer(mapping, Router(be))
    srv.start()
    try:
        _send(srv.port, b"^XA^FDa^XZ^XA^FDb^XZ")
        assert _wait(lambda: len(be.raw_calls) == 2)
        assert be.raw_calls[0][1] == b"^XA^FDa^XZ"
        assert be.raw_calls[1][1] == b"^XA^FDb^XZ"
    finally:
        srv.stop()


def test_server_emits_events():
    be = FakeBackend()
    events = []
    mapping = Mapping(listen_port=0, target_printer="Zebra", mode="raw")
    srv = RawPrintServer(mapping, Router(be), on_event=events.append)
    srv.start()
    try:
        _send(srv.port, b"^XA^FDx^XZ")
        assert _wait(lambda: any("Wydrukowano" in e.message for e in events))
    finally:
        srv.stop()


def test_server_error_event_when_no_printer():
    be = FakeBackend()
    events = []
    mapping = Mapping(listen_port=0, target_printer="", mode="raw")
    srv = RawPrintServer(mapping, Router(be), on_event=events.append)
    srv.start()
    try:
        _send(srv.port, b"^XA^FDx^XZ")
        assert _wait(lambda: any(e.level == "error" for e in events))
    finally:
        srv.stop()


def test_app_start_stop_with_fake_backend():
    be = FakeBackend()
    cfg = Config(mappings=[Mapping(listen_port=0, target_printer="Zebra", mode="raw")])
    app = App(cfg=cfg, backend=be)
    errors = app.start()
    assert errors == []
    assert app.is_running()
    port = app._servers[0].port
    _send(port, b"^XA^FDz^XZ")
    assert _wait(lambda: len(be.raw_calls) == 1)
    app.stop()
    assert not app.is_running()


def test_app_port_conflict_reports_error():
    be = FakeBackend()
    # dwa mapowania na tym samym stałym porcie -> drugie nie wstanie
    port = _free_port()
    cfg = Config(mappings=[
        Mapping(listen_port=port, target_printer="A", mode="raw"),
        Mapping(listen_port=port, target_printer="B", mode="raw", enabled=True),
    ])
    # walidacja Config odrzuca duplikaty portów, więc omijamy ją i testujemy start
    app = App(cfg=Config(mappings=[cfg.mappings[0]]), backend=be)
    app.config.mappings.append(cfg.mappings[1])
    errors = app.start()
    try:
        assert any("porcie" in e or "port" in e.lower() for e in errors)
    finally:
        app.stop()


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p
