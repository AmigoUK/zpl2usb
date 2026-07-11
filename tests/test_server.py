import socket
import time

import pytest

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


def test_raw_mode_forwards_verbatim():
    # Raw mode must pass the byte stream through 1:1, incl. ~ control commands
    # and inter-job bytes (flushed once on close).
    be = FakeBackend()
    mapping = Mapping(listen_port=0, target_printer="Zebra", mode="raw")
    srv = RawPrintServer(mapping, Router(be))
    srv.start()
    try:
        stream = b"~SD25^XA^FDa^XZ~JA^XA^FDb^XZ~HS"
        _send(srv.port, stream)
        assert _wait(lambda: be.raw_calls)
        time.sleep(0.15)  # allow any trailing flush
        joined = b"".join(d for _, d in be.raw_calls)
        assert joined == stream  # nothing dropped, order preserved
    finally:
        srv.stop()


def test_raw_mode_idle_flush():
    # A persistent connection that pauses should flush after the idle timeout,
    # without waiting for close.
    be = FakeBackend()
    mapping = Mapping(listen_port=0, target_printer="Zebra", mode="raw")
    srv = RawPrintServer(mapping, Router(be))
    srv.start()
    s = socket.create_connection(("127.0.0.1", srv.port), timeout=2)
    try:
        s.sendall(b"~SD20^XA^FDx^XZ")
        # do NOT close — expect idle flush (socket timeout ~1s)
        assert _wait(lambda: be.raw_calls, timeout=4.0)
        assert b"~SD20" in b"".join(d for _, d in be.raw_calls)
    finally:
        s.close()
        srv.stop()


def test_render_mode_splits_two_jobs_in_one_send():
    # Job framing is a render-mode concern: each ^XA..^XZ renders separately.
    be = FakeBackend()
    mapping = Mapping(listen_port=0, target_printer="Zebra", mode="render")
    srv = RawPrintServer(mapping, Router(be))
    srv.start()
    try:
        _send(srv.port, b"^XA^FDa^XZ^XA^FDb^XZ")
        assert _wait(lambda: len(be.image_calls) == 2)
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


def test_trailing_newline_no_warning():
    # Render mode: a newline after ^XZ is normal and must not warn.
    be = FakeBackend()
    events = []
    mapping = Mapping(listen_port=0, target_printer="Zebra", mode="render")
    srv = RawPrintServer(mapping, Router(be), on_event=events.append)
    srv.start()
    try:
        _send(srv.port, b"^XA^FDx^XZ\n")  # nowa linia po ^XZ jest normalna
        assert _wait(lambda: len(be.image_calls) == 1)
        time.sleep(0.1)  # daj czas na ewentualne ostrzeżenie po zamknięciu
        assert not any(e.level == "warning" for e in events), \
            [e.message for e in events if e.level == "warning"]
    finally:
        srv.stop()


def test_truncated_job_warns():
    # Render mode: an unterminated ^XA (no ^XZ) at disconnect warns.
    be = FakeBackend()
    events = []
    mapping = Mapping(listen_port=0, target_printer="Zebra", mode="render")
    srv = RawPrintServer(mapping, Router(be), on_event=events.append)
    srv.start()
    try:
        _send(srv.port, b"^XA^FDunfinished")  # brak ^XZ -> realnie ucięte
        assert _wait(lambda: any(e.level == "warning" for e in events))
    finally:
        srv.stop()


def test_server_binds_configured_host():
    be = FakeBackend()
    mapping = Mapping(listen_port=0, listen_host="127.0.0.1",
                      target_printer="Zebra", mode="raw")
    srv = RawPrintServer(mapping, Router(be))  # bez host= -> bierze z mapowania
    srv.start()
    try:
        assert srv.host == "127.0.0.1"
        _send(srv.port, b"^XA^FDx^XZ")
        assert _wait(lambda: len(be.raw_calls) == 1)
    finally:
        srv.stop()


def test_server_unavailable_host_raises_clear_error():
    be = FakeBackend()
    # Adres, którego z pewnością nie ma na tym komputerze.
    mapping = Mapping(listen_port=0, listen_host="203.0.113.7",
                      target_printer="Zebra", mode="raw")
    srv = RawPrintServer(mapping, Router(be))
    with pytest.raises(OSError, match="niedostępny"):
        srv.start()


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
        assert errors  # drugie mapowanie na tym samym porcie nie wstało
        assert any("nasłuchiwać" in e.lower() or "use" in e.lower() for e in errors)
    finally:
        app.stop()


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p
