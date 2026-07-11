"""Serwer TCP RAW emulujący sieciową drukarkę ZPL (port 9100).

Każde mapowanie ma własny ``RawPrintServer`` nasłuchujący na swoim porcie.
Dane z połączenia są dzielone na zadania ZPL (``JobSplitter``) i przekazywane
do ``Router``. Zdarzenia (druk/ostrzeżenia/błędy) trafiają do callbacku ``on_event``.
"""

from __future__ import annotations

import errno
import socket
import threading
from dataclasses import dataclass
from typing import Callable

from .config import Mapping
from .jobs import START, JobSplitter
from .router import RouteResult, Router


@dataclass
class ServerEvent:
    level: str          # "info" | "warning" | "error"
    message: str
    mapping_port: int


EventHandler = Callable[[ServerEvent], None]


class RawPrintServer:
    """Nasłuch TCP RAW dla jednego mapowania."""

    def __init__(
        self,
        mapping: Mapping,
        router: Router,
        on_event: EventHandler | None = None,
        host: str | None = None,
    ) -> None:
        self.mapping = mapping
        self.router = router
        self.on_event = on_event or (lambda e: None)
        # Domyślnie bind na adres z mapowania; parametr host pozwala nadpisać (testy).
        self.host = host if host is not None else mapping.listen_host
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._conn_threads: list[threading.Thread] = []
        self.port: int = mapping.listen_port

    # --- cykl życia ---------------------------------------------------------
    def start(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((self.host, self.mapping.listen_port))
        except OSError as exc:
            sock.close()
            if exc.errno == errno.EADDRNOTAVAIL:
                raise OSError(
                    f"Adres {self.host} niedostępny na tym komputerze "
                    f"(np. zmiana sieci/DHCP) — odśwież listę i wybierz ponownie."
                ) from exc
            raise OSError(
                f"Nie można nasłuchiwać na {self.host}:{self.mapping.listen_port}: {exc}"
            ) from exc
        sock.listen(8)
        sock.settimeout(0.5)
        self._sock = sock
        # Rzeczywisty port (istotne, gdy listen_port == 0 w testach).
        self.port = sock.getsockname()[1]
        self._stop.clear()
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()
        self._emit("info", f"Nasłuch na {self.host}:{self.port} "
                           f"(tryb {self.mapping.mode}, drukarka '{self.mapping.target_printer}')")

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2)
        for t in list(self._conn_threads):
            t.join(timeout=1)
        self._emit("info", f"Zatrzymano nasłuch na porcie {self.port}")

    # --- wewnętrzne ---------------------------------------------------------
    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            try:
                conn, addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            t = threading.Thread(target=self._handle_conn, args=(conn, addr), daemon=True)
            self._conn_threads.append(t)
            t.start()

    def _handle_conn(self, conn: socket.socket, addr) -> None:
        splitter = JobSplitter()
        conn.settimeout(1.0)
        try:
            while not self._stop.is_set():
                try:
                    chunk = conn.recv(65536)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not chunk:
                    break  # klient zamknął połączenie
                try:
                    jobs = splitter.feed(chunk)
                except BufferError as exc:
                    self._emit("error", f"{addr[0]}: {exc}")
                    splitter.reset()
                    continue
                for job in jobs:
                    self._process(job)
            # Ostrzeż tylko, gdy w buforze pozostało realnie rozpoczęte zadanie
            # (zawiera ^XA). Sam biały znak/nowa linia po ^XZ to nie błąd.
            pending = splitter.pending
            if START in pending:
                self._emit("warning",
                           f"{addr[0]}: rozłączenie z niekompletnym zadaniem "
                           f"({len(pending)} B odrzucone)")
        finally:
            try:
                conn.close()
            except OSError:
                pass
            self._conn_threads = [t for t in self._conn_threads
                                  if t is not threading.current_thread()]

    def _process(self, job: bytes) -> None:
        result: RouteResult = self.router.handle_job(self.mapping, job)
        if result.ok:
            msg = f"Wydrukowano ({result.mode}) na '{result.printer}'"
            self._emit("info", msg)
            for w in result.warnings:
                self._emit("warning", w)
        else:
            self._emit("error", f"Błąd druku na '{result.printer}': {result.error}")

    def _emit(self, level: str, message: str) -> None:
        self.on_event(ServerEvent(level=level, message=message,
                                  mapping_port=self.mapping.listen_port))
