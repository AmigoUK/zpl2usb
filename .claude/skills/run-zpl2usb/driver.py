#!/usr/bin/env python3
"""Driver for the zpl2usb app — launch the GUI, screenshot it, or exercise the
network print pipeline, all headless.

Commands:
  screenshot [out.png]   Build the Tkinter settings window (with demo printers +
                         two virtual-printer mappings), render it, capture the X
                         display to a PNG. Requires an X display (run under xvfb).
  netcheck   [out.png]   Start a RAW listener on 127.0.0.1:<ephemeral> in RENDER
                         mode, send examples/sample_100x40.zpl over TCP, and save
                         the printed bitmap. Proves the full bypass: TCP -> split
                         -> render -> print backend. No X display needed.
  render <in.zpl> [out]  Render a ZPL file to PNG via the local renderer.

Run with the project venv: .venv/bin/python .claude/skills/run-zpl2usb/driver.py <cmd>
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # driver -> run-zpl2usb -> skills -> .claude -> repo
sys.path.insert(0, str(ROOT))

from zpl2usb.config import Config, Mapping  # noqa: E402
from zpl2usb.printers import PrinterBackend  # noqa: E402
from zpl2usb.router import Router  # noqa: E402
from zpl2usb.server import RawPrintServer  # noqa: E402


class DemoBackend(PrinterBackend):
    """Fake backend: realistic printer names for screenshots; saves images."""

    def __init__(self, out: Path | None = None):
        self.out = out
        self.raw_calls: list[tuple[str, bytes]] = []
        self.image_calls: list[tuple] = []

    def list_printers(self):
        return ["Zebra ZD420", "Toshiba B-EX4T1", "HP LaserJet M110"]

    def print_raw(self, name, data):
        self.raw_calls.append((name, data))

    def print_image(self, name, image, *, dpi=203):
        self.image_calls.append((name, image, dpi))
        if self.out:
            image.save(self.out)


def cmd_screenshot(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else ROOT / "screenshot.png"
    import tkinter as tk

    from zpl2usb.app import App
    from zpl2usb.gui.window import SettingsWindow

    cfg = Config(
        mappings=[
            Mapping(listen_host="0.0.0.0", listen_port=9100,
                    target_printer="Zebra ZD420", mode="raw", dpi=203),
            Mapping(listen_host="0.0.0.0", listen_port=9101,
                    target_printer="Toshiba B-EX4T1", mode="render", dpi=300,
                    default_label_mm=(100.0, 40.0)),
        ],
        autostart=True,
    )
    app = App(cfg=cfg, backend=DemoBackend())

    root = tk.Tk()
    root.withdraw()
    win = SettingsWindow(app, root)
    win.win.geometry("+0+0")
    win.show()
    for _ in range(10):
        root.update_idletasks()
        root.update()
        time.sleep(0.05)

    # Capture the X display (scrot grabs the whole virtual screen).
    res = subprocess.run(["scrot", "-o", str(out)], capture_output=True)
    root.destroy()
    if res.returncode != 0:
        print("scrot failed:", res.stderr.decode(), file=sys.stderr)
        return 1
    print(f"screenshot saved: {out}")
    return 0


def cmd_netcheck(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else ROOT / "netcheck_out.png"
    backend = DemoBackend(out=out)
    mapping = Mapping(listen_host="127.0.0.1", listen_port=0,
                      target_printer="Toshiba B-EX4T1", mode="render",
                      dpi=203, default_label_mm=(100.0, 40.0))
    events: list = []
    srv = RawPrintServer(mapping, Router(backend), on_event=events.append)
    srv.start()
    print(f"listening on 127.0.0.1:{srv.port} (render mode, emulating Zebra 9100)")
    try:
        zpl = (ROOT / "examples" / "sample_100x40.zpl").read_bytes()
        s = socket.create_connection(("127.0.0.1", srv.port), timeout=2)
        s.sendall(zpl)
        s.close()
        print("sent ZPL over TCP")
        deadline = time.time() + 3
        while time.time() < deadline and not backend.image_calls:
            time.sleep(0.02)
    finally:
        srv.stop()
    for e in events:
        print(f"  [{e.level}] {e.message}")
    if backend.image_calls:
        img = backend.image_calls[0][1]
        print(f"OK: printed {img.size} bitmap -> {out}")
        return 0
    print("FAIL: no print produced", file=sys.stderr)
    return 1


def cmd_render(argv: list[str]) -> int:
    if not argv:
        print("usage: driver.py render <in.zpl> [out.png]", file=sys.stderr)
        return 2
    from zpl2usb.renderer import render

    src = Path(argv[0])
    out = Path(argv[1]) if len(argv) > 1 else src.with_suffix(".png")
    result = render(src.read_bytes(), dpi=203, default_label_mm=(100.0, 40.0))
    result.image.save(out)
    print(f"rendered {out} ({result.image.size[0]}x{result.image.size[1]} px)")
    if result.unsupported:
        print("skipped commands:", ", ".join(result.unsupported))
    return 0


COMMANDS = {"screenshot": cmd_screenshot, "netcheck": cmd_netcheck, "render": cmd_render}


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in COMMANDS:
        print(__doc__)
        return 2
    return COMMANDS[argv[0]](argv[1:])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
