---
name: run-zpl2usb
description: Build, run, and drive zpl2usb — a virtual networked ZPL printer (tray + Tkinter GUI). Use when asked to start zpl2usb, run its tests, build the binary, screenshot its settings window, or exercise the ZPL print pipeline.
---

zpl2usb is a cross-platform desktop app (system-tray icon + Tkinter settings window)
that emulates a networked Zebra ZPL printer on port 9100 and forwards jobs to a system
printer (raw, or by rendering ZPL to a bitmap). It is headless-hostile: the GUI needs an
X server. Drive it with **`.claude/skills/run-zpl2usb/driver.py` under `xvfb-run`** —
`screenshot` captures the settings window, `netcheck` exercises the full TCP→render→print
pipeline with no display, `render` rasterises a `.zpl` file.

All paths below are relative to the repo root (`zpl2usb/`).

## Prerequisites

Ubuntu packages actually used this session:

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv python3-tk xvfb scrot
```

- `python3-tk` — Tkinter GUI (missing by default; the app prints a clear error and
  exits 3 without it).
- `xvfb` + `scrot` — only needed to screenshot the GUI headlessly.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

This installs the runtime deps (Pillow, python-barcode, qrcode, platformdirs, pystray,
psutil) plus pytest. No env vars, no config, no feature gates.

## Run (agent path)

The driver is the handle. Run it with the venv Python.

**Screenshot the settings window** (needs an X server → wrap in `xvfb-run`; use a
24-bit screen or colours render wrong):

```bash
xvfb-run -a -s "-screen 0 1100x760x24" \
  .venv/bin/python .claude/skills/run-zpl2usb/driver.py screenshot /tmp/zpl2usb-gui.png
```

Prints `screenshot saved: /tmp/zpl2usb-gui.png`. The window shows the virtual-printer
list (two demo mappings), the edit panel (target printer, listen address, WMS hint,
mode, DPI, port, label size), the autostart checkbox and the log pane. A rendered
reference is committed at `.claude/skills/run-zpl2usb/example-screenshot.png`.

**Exercise the print pipeline** (no display needed — proves TCP→split→render→print):

```bash
.venv/bin/python .claude/skills/run-zpl2usb/driver.py netcheck /tmp/zpl2usb-out.png
```

It binds an ephemeral port on 127.0.0.1 in render mode, sends
`examples/sample_100x40.zpl` over TCP, and saves the printed bitmap. Expect
`OK: printed (799, 320) bitmap` and `[info] Wydrukowano (render) ...`.

**Rasterise a ZPL file** to preview the renderer:

```bash
.venv/bin/python .claude/skills/run-zpl2usb/driver.py render examples/sample_100x40.zpl /tmp/label.png
```

## Direct invocation

The renderer is pure and importable without the app or a display:

```bash
.venv/bin/python -c "from zpl2usb.renderer import render; r=render(b'^XA^FO20,20^A0N,40,40^FDHELLO^FS^XZ', dpi=203, default_label_mm=(100,40)); print(r.image.size, r.unsupported)"
```

The tray/window entry point is `zpl2usb.__main__:main`; the GUI logic lives in
`zpl2usb/gui/window.py` (`SettingsWindow`), driven against `zpl2usb/app.py` (`App`) with
any `PrinterBackend`. `driver.py`'s `DemoBackend` shows the fake-backend pattern for
tests/screenshots.

## Run (human path)

On a real desktop:

```bash
.venv/bin/python -m zpl2usb
```

A tray icon appears; click it → "Ustawienia…" opens the settings window. Headless this
exits 3 with "Nie można uruchomić GUI (brak środowiska graficznego)" — expected; use the
driver instead.

## Build (standalone binary)

Builds on the current OS only (PyInstaller does not cross-compile):

```bash
.venv/bin/python -m pip install pyinstaller
.venv/bin/python packaging/build.py
# -> dist/zpl2usb  (Windows: dist/zpl2usb.exe)
```

The built binary also exits 3 headless; run it on a machine with a display.

## Test

```bash
.venv/bin/python -m pytest -q          # 112 passed, 4 skipped (GUI tests skip w/o DISPLAY)
xvfb-run -a .venv/bin/python -m pytest -q tests/test_gui_window.py   # runs the 4 skipped
```

## Gotchas

- **`import pystray` fails at import time when headless** (`Xlib.error.DisplayNameError:
  Bad display name ""`). This is why `driver.py screenshot` uses Tkinter directly and
  never imports the tray. Under `xvfb-run` pystray imports fine.
- **`xvfb-run` default screen is 8-bit** → scrot/colours come out wrong. Always pass
  `-s "-screen 0 <W>x<H>x24"`.
- **Screenshot capture is same-process**: the driver builds the Tk window, pumps events,
  then shells out to `scrot` while the window is still mapped. Don't background it.
- **GUI modal dialogs block headless.** In tests, `tkinter.messagebox.*` is monkeypatched
  to no-ops (see `tests/test_gui_window.py`); a raw `remove_mapping()` on the last mapping
  would otherwise hang under xvfb.
- **`0.0.0.0` bind vs a specific IP**: the app lets the user pick which local IP to listen
  on. `netcheck` binds `127.0.0.1` so it works with no network. Real use picks a LAN IP
  (`zpl2usb/netutil.py` lists them via psutil).
- **Autostart writes real files.** `App.set_autostart(True)` on Linux drops
  `~/.config/autostart/zpl2usb.desktop`; `sync_autostart()` only auto-applies for frozen
  binaries. The screenshot driver uses a `DemoBackend` and never calls these.
- **Comments/log messages are Polish**; the code and this skill are the English surface.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No module named pip` / `ensurepip` | `apt-get install -y python3-pip python3-venv`, recreate `.venv` |
| `ModuleNotFoundError: tkinter` | `apt-get install -y python3-tk` |
| App exits 3, "brak środowiska graficznego" | No X display — use the driver under `xvfb-run`, or run on a desktop |
| `scrot: failed to grab` / black-ish PNG | Use `-s "-screen 0 1100x760x24"` (24-bit) with `xvfb-run` |
| `Bad display name ""` importing pystray | Expected headless; run under `xvfb-run` or use `driver.py` |
