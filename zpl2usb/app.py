"""Orkiestracja: spina konfigurację, backend druku, router i serwery.

``App`` zarządza cyklem życia wszystkich wirtualnych drukarek (serwerów RAW)
i udostępnia log zdarzeń dla GUI.
"""

from __future__ import annotations

import sys
import threading
from collections import deque
from typing import Callable

from . import autostart as autostart_mod
from . import config as config_mod
from .config import Config
from .printers import PrinterBackend, get_backend
from .router import Router
from .server import RawPrintServer, ServerEvent

LogHandler = Callable[[ServerEvent], None]


class App:
    def __init__(
        self,
        cfg: Config | None = None,
        backend: PrinterBackend | None = None,
        log_size: int = 500,
    ) -> None:
        self.config = cfg or config_mod.load()
        self.backend = backend or get_backend()
        self.router = Router(self.backend)
        self._servers: list[RawPrintServer] = []
        self._log: deque[ServerEvent] = deque(maxlen=log_size)
        self._log_handlers: list[LogHandler] = []
        self._lock = threading.Lock()

    # --- log ----------------------------------------------------------------
    def add_log_handler(self, handler: LogHandler) -> None:
        self._log_handlers.append(handler)

    def _on_event(self, event: ServerEvent) -> None:
        self._log.append(event)
        for h in list(self._log_handlers):
            try:
                h(event)
            except Exception:
                pass

    @property
    def log(self) -> list[ServerEvent]:
        return list(self._log)

    # --- serwery ------------------------------------------------------------
    def list_printers(self) -> list[str]:
        return self.backend.list_printers()

    def start(self) -> list[str]:
        """Uruchom serwery dla włączonych mapowań. Zwróć listę błędów startu."""
        errors: list[str] = []
        with self._lock:
            self._stop_locked()
            for mapping in self.config.mappings:
                if not mapping.enabled:
                    continue
                srv = RawPrintServer(mapping, self.router, on_event=self._on_event)
                try:
                    srv.start()
                    self._servers.append(srv)
                except OSError as exc:
                    errors.append(str(exc))
                    self._on_event(ServerEvent("error", str(exc), mapping.listen_port))
        return errors

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()

    def _stop_locked(self) -> None:
        for srv in self._servers:
            srv.stop()
        self._servers.clear()

    def is_running(self) -> bool:
        return bool(self._servers)

    def apply_config(self, cfg: Config) -> list[str]:
        """Zapisz nową konfigurację i zrestartuj serwery. Zwróć błędy startu."""
        cfg.validate()
        config_mod.save(cfg)
        self.config = cfg
        return self.start()

    def reload_backend(self) -> None:
        self.router.backend = self.backend

    # --- autostart ----------------------------------------------------------
    def set_autostart(self, enabled: bool) -> None:
        """Ustaw autostart (zapisuje config i stosuje w systemie)."""
        self.config.autostart = enabled
        try:
            config_mod.save(self.config)
        except Exception as exc:
            self._on_event(ServerEvent("error", f"Zapis konfiguracji: {exc}", 0))
        try:
            autostart_mod.set_autostart(enabled)
        except Exception as exc:
            self._on_event(ServerEvent("error", f"Autostart: {exc}", 0))

    def sync_autostart(self) -> None:
        """Zsynchronizuj autostart systemu z konfiguracją.

        Automatycznie działa tylko dla zbudowanej binarki (frozen), żeby nie
        modyfikować systemu deweloperskiego przy uruchomieniu ze źródeł.
        """
        if not getattr(sys, "frozen", False):
            return
        try:
            backend = autostart_mod.get_autostart()
            if self.config.autostart and not backend.is_enabled():
                backend.enable()
            elif not self.config.autostart and backend.is_enabled():
                backend.disable()
        except Exception as exc:
            self._on_event(ServerEvent("warning", f"Autostart: {exc}", 0))
