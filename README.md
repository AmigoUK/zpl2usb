# zpl2usb

**A virtual networked ZPL printer (Zebra, port 9100)** that bridges print jobs to
any printer installed on your computer — on Windows, Linux and macOS.

Warehouse and ERP systems often can only print labels to a networked ZPL printer
(RAW port 9100). zpl2usb pretends to be one: the computer listens on
`<its-own-IP>:9100`, receives the ZPL stream and forwards each label to a printer
you select in the system, in one of two modes:

- **raw** — the raw ZPL bytes, sent 1:1 (for printers that speak ZPL natively, e.g. Zebra),
- **render** — local (offline) rendering of the ZPL to a bitmap, printed through the
  system driver (for printers that do not understand ZPL, e.g. Toshiba B-EX).

The application lives in the system tray and has a simple settings window. It can
manage **several virtual printers at once** (each on its own address/port → its own
system printer) and can **start automatically with the system**.

![Example of a rendered label](examples/sample_100x40.png)

## How it works

The machine acts as a bypass between the network and the locally attached printer:

```
WMS/ERP system                     This computer (bypass)               Printer
prints to 192.168.1.50:9100  ──▶   listens on 192.168.1.50:9100   ──▶   USB / system
                                   splits stream into ^XA…^XZ jobs       (Zebra = raw,
                                   → mode raw or render                   Toshiba = render)
```

You pick which of the computer's own IP addresses to listen on, so in your WMS you
configure printing to that exact address (e.g. `192.168.1.50:9100`) rather than a
wildcard.

## Install & run (end users) — no Python needed

1. Open the [**Releases**](https://github.com/AmigoUK/zpl2usb/releases) page.
2. Download the file for your system:
   - **Windows** → `zpl2usb-windows.exe` — double-click it.
   - **macOS** → `zpl2usb-macos.zip` — unzip, then open `zpl2usb.app`.
   - **Linux** → `zpl2usb-linux` — `chmod +x zpl2usb-linux`, then run it.
3. A tray icon appears. Click it → **Ustawienia…** (Settings) to choose the listening
   address, the target printer and the mode. That's it — it also starts with your system
   by default.

No installer, no Python, no dependencies — it's a single self-contained file.
(Windows SmartScreen / macOS Gatekeeper may warn about an unsigned app the first time:
"More info → Run anyway" / right-click → "Open".)

Releases are built automatically for all three systems by
[`.github/workflows/release.yml`](.github/workflows/release.yml) when a `v*` tag is pushed.

## Running from source

```bash
python3 -m venv .venv
. .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m zpl2usb              # start the app (tray + listener)
```

- **Windows**: also run `pip install pywin32`.
- **Linux**: requires CUPS (`lp`/`lpr`) and `python3-tk` for the GUI.
- **macOS**: CUPS is built in; `tkinter` ships with the python.org installer.

## Building a standalone binary

Build on the **target** operating system (PyInstaller does not cross-compile):

```bash
pip install -r requirements.txt pyinstaller
python packaging/build.py
# result: dist/zpl2usb  (Windows: dist/zpl2usb.exe)
```

## Configuration

Stored as JSON in the per-user configuration directory (via `platformdirs`).
Fields of a mapping:

Top-level:

| Field | Meaning | Default |
|---|---|---|
| `autostart` | start the app when the system starts | `true` |
| `mappings` | list of virtual printers (see below) | one default mapping |

Each mapping:

| Field | Meaning | Default |
|---|---|---|
| `listen_host` | which of this computer's IPv4 addresses to listen on | `0.0.0.0` (all) |
| `listen_port` | RAW listening port | `9100` |
| `target_printer` | name of the system printer | — |
| `mode` | `raw` or `render` | `raw` |
| `dpi` | 203 / 300 / 600 | `203` |
| `default_label_mm` | label size when the ZPL omits `^PW`/`^LL` | `100 × 40` |
| `enabled` | whether this mapping listens | `true` |

## Multiple virtual printers

The settings window shows a list of virtual printers on the left and an edit panel on
the right. Use **Add**, **Duplicate** and **Remove** to manage them. Each one binds to
its own `address:port` and forwards to its own system printer, so you can, for example,
route one label stream to a Zebra (raw) and another to a Toshiba B-EX (render) on the
same machine. Every `(address, port)` pair must be unique.

## Autostart

"Start with the system" is **enabled by default**; untick it in the settings window to
turn it off. It is registered per platform: an XDG `.desktop` file on Linux, a
LaunchAgent on macOS, and a `Run` registry entry on Windows. Automatic registration
only happens for the packaged binary; running from source never modifies the system
unless you toggle the option yourself.

## Supported ZPL subset (render mode)

The renderer is local/offline and handles the most common commands:

- structure: `^XA` `^XZ` `^FS`
- settings: `^PW` `^LL` `^LH` `^CF` `^CI`
- positioning: `^FO` `^FT`
- text: `^A` (scalable font), `^FD`
- graphics: `^GB` (boxes/lines), `^GF` (ASCII-hex bitmap), `^FR`
- barcodes: `^BY`, `^BC` (Code128), `^BQ` (QR)

Unsupported commands are **skipped** and logged — the rest of the label still
renders. For printers that speak ZPL natively, use **raw** mode (full fidelity, no
renderer limitations).

### Known limitations of render mode

These are inherent to the offline renderer. **raw** mode has none of them — for a real
Zebra, use raw and everything is byte-exact.

- **Font width is not applied independently** — `^A`/`^CF` height is honoured but the
  glyphs scale isotropically (the width field is ignored).
- **`^FR` reverse** only shows where it overlaps an already-black region (there is no
  full field-level compositing).
- **`^BQ` QR data** follows the ZPL `<error-correction>,<data>` convention, so a payload
  that literally begins e.g. `H,` may have that prefix stripped.
- **Very large single labels** (heavy `^GF` graphics over ~8 MB in one `^XA…^XZ`) are
  dropped with a logged error — send them in raw mode instead.

Raw mode forwards the stream verbatim, including `~` control commands (`~SD`, `~JA`, …)
and any bytes between labels — nothing is reframed or dropped.

## Previewing the render (without a printer)

```bash
python tools/render_zpl.py examples/sample_100x40.zpl -o preview.png --dpi 203 --size 100x40
```

## Tests

```bash
pip install pytest
pytest
```

## Licence

MIT. See also the design specification:
[`docs/superpowers/specs/2026-07-11-zpl2usb-design.md`](docs/superpowers/specs/2026-07-11-zpl2usb-design.md).
