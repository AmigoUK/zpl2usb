"""Ikona w zasobniku systemowym (pystray)."""

from __future__ import annotations

from typing import Callable

from .icon import make_icon


class Tray:
    """Cienka otoczka na pystray.Icon z menu: Ustawienia / Start / Stop / Zakończ."""

    def __init__(
        self,
        app,
        on_open: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        import pystray

        self.app = app
        self._on_open = on_open
        self._on_quit = on_quit
        self._pystray = pystray

        menu = pystray.Menu(
            pystray.MenuItem("Ustawienia…", self._open, default=True),
            pystray.MenuItem("Uruchom", self._start,
                             checked=lambda item: self.app.is_running()),
            pystray.MenuItem("Zatrzymaj", self._stop),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Zakończ", self._quit),
        )
        self.icon = pystray.Icon(
            "zpl2usb",
            icon=make_icon(running=app.is_running()),
            title="zpl2usb — wirtualna drukarka ZPL",
            menu=menu,
        )

    def _open(self, icon=None, item=None) -> None:
        self._on_open()

    def _start(self, icon=None, item=None) -> None:
        self.app.start()
        self._update_icon()

    def _stop(self, icon=None, item=None) -> None:
        self.app.stop()
        self._update_icon()

    def _quit(self, icon=None, item=None) -> None:
        self.icon.stop()
        self._on_quit()

    def _update_icon(self) -> None:
        self.icon.icon = make_icon(running=self.app.is_running())

    def run_detached(self) -> None:
        """Uruchom ikonę w osobnym wątku (Tk trzyma główny wątek)."""
        self.icon.run_detached()

    def run(self) -> None:
        self.icon.run()

    def stop(self) -> None:
        self.icon.stop()
