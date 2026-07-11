"""Punkt wejścia aplikacji zpl2usb.

Uruchamia orkiestrację (App), okno ustawień (Tkinter na głównym wątku) oraz
ikonę w zasobniku (pystray w wątku pobocznym). Serwery startują automatycznie,
jeśli w konfiguracji wskazano drukarkę docelową.
"""

from __future__ import annotations

import sys


def main() -> int:
    from .app import App

    app = App()

    # Autostart, jeśli mapowanie ma wskazaną drukarkę.
    if any(m.enabled and m.target_printer for m in app.config.mappings):
        app.start()

    try:
        import tkinter as tk
    except Exception as exc:  # pragma: no cover
        print(f"Brak biblioteki tkinter (GUI): {exc}", file=sys.stderr)
        print("Zainstaluj pakiet systemowy python3-tk.", file=sys.stderr)
        return 2

    root = tk.Tk()
    root.withdraw()  # główne okno ukryte — pracujemy z Toplevel + tray

    from .gui.window import SettingsWindow

    window = SettingsWindow(app, root)
    window.hide()

    tray = None
    try:
        from .gui.tray import Tray

        tray = Tray(
            app,
            on_open=lambda: root.after(0, window.show),
            on_quit=lambda: root.after(0, root.destroy),
        )
        tray.run_detached()
    except Exception as exc:  # pragma: no cover - brak środowiska tray
        print(f"Nie udało się uruchomić ikony w zasobniku: {exc}", file=sys.stderr)
        print("Otwieram okno ustawień.", file=sys.stderr)
        window.show()

    try:
        root.mainloop()
    finally:
        app.stop()
        if tray is not None:
            try:
                tray.stop()
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
