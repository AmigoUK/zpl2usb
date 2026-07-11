# zpl2usb — Virtual networked ZPL printer (design specification)

- **Date:** 2026-07-11
- **Status:** Approved; implemented

## 1. Purpose and problem

Warehouse/ERP systems can often only print labels to a networked ZPL printer
(Zebra, RAW port 9100). In practice the printer attached to the computer is
frequently a different device: an ordinary office printer, or an industrial label
printer from another vendor (e.g. **Toshiba B-EX**, which speaks TPCL natively) that
does not understand ZPL.

**zpl2usb** is a simple, cross-platform (Windows/Linux/macOS) Python application that
emulates a networked Zebra ZPL printer on port `9100`. It receives the ZPL stream
over TCP and forwards it to any printer installed on the system — either raw, or by
rendering the ZPL locally to a bitmap for printers without native ZPL support.
The application has a system-tray icon and a simple settings window, and is
distributed as a standalone binary (users do not install Python).

## 2. Design decisions

| Topic | Decision |
|---|---|
| Target printer | Any — the mode is chosen by the user (raw ZPL **or** render) |
| Printing method | Only via **system-installed printers** (driver/queue) |
| ZPL rendering | **Local/offline only** (no online services such as Labelary) |
| Number of virtual printers | Start with **one**; architecture designed for many (list of mappings) |
| Listening address | User selects one of **this computer's own IP addresses** (not a hardcoded wildcard) |
| Interface | **System-tray icon** (pystray) + settings/log window (Tkinter) |
| Distribution | **Standalone binary** per OS (PyInstaller) |
| DPI | Configured **per printer** (203/300/600), default 203 |
| Default label size | **100 × 40 mm** (when the ZPL omits `^PW`/`^LL`) |

## 3. Architecture and data flow

The computer acts as a bypass between the network and the locally attached printer:

```
WMS/ERP system                     This computer (bypass)               Printer
prints to 192.168.1.50:9100  ──▶   listens on 192.168.1.50:9100   ──▶   USB / system
                                   splits stream into ^XA…^XZ jobs       (Zebra = raw,
                                   → router: raw or render               Toshiba = render)
```

1. The system sends ZPL to `<computer-IP>:9100` (RAW/JetDirect protocol — plain
   bytes, no handshake).
2. The listener collects the bytes from the connection and splits the stream into
   `^XA`…`^XZ` jobs.
3. The router checks the configuration for that port → **raw** or **render** mode.
4. **raw** → the bytes go 1:1 to the system printer.
   **render** → the local ZPL interpreter produces a bitmap at the configured DPI →
   the image is printed through the system driver.
5. Results and errors are recorded in the log and the application window.

## 4. Modules (each with a single responsibility)

- **`server.py`** — RAW TCP listener for a mapping (start/stop, multiple ports in
  future); binds to the configured `listen_host`; collects bytes from the connection.
- **`jobs.py`** — splits the stream into individual ZPL jobs (`^XA`…`^XZ`); resilient
  to concatenated and fragmented TCP packets.
- **`router.py`** — decides raw vs render from the configuration; calls the print
  backend.
- **`printers.py`** — cross-platform layer: `list_printers()`, `print_raw(name, bytes)`,
  `print_image(name, image)`. Windows → `win32print`; macOS/Linux → CUPS (`lp`/`lpr`).
- **`netutil.py`** — detects the computer's local IPv4 addresses for the listening-
  address selector (psutil, with a socket-based fallback).
- **`renderer/`** — ZPL interpreter → PIL image:
  - `parser` — command tokenisation
  - `interpreter` — `^FO/^FT`, `^A` (text), `^GB` (boxes/lines), `^GF` (graphics)
  - `barcodes` — `^BC` (Code128), `^BQ` (QR), `^BY`
  - `units`/`fonts` — canvas sizing by DPI and label size, scalable font
- **`config.py`** — load/save JSON (`platformdirs`); mapping dataclasses.
- **`app.py`** — wires configuration → servers → router; application lifecycle.
- **`gui/`** — system-tray icon (`pystray`) + settings and log window (`Tkinter`).

Configuration model (one mapping today, a list ready for many):

```json
{
  "mappings": [
    {
      "listen_host": "192.168.1.50",
      "listen_port": 9100,
      "target_printer": "Toshiba B-EX",
      "mode": "render",            // "raw" | "render"
      "dpi": 203,                  // 203 | 300 | 600
      "default_label_mm": [100, 40]
    }
  ]
}
```

## 5. Technology stack

- **Python 3.11+**
- **Pillow** — canvas and rasterisation
- **python-barcode** (Code128) + **qrcode** (QR)
- **psutil** — reliable, cross-platform detection of local IP addresses
- **pystray** — system-tray icon (Win/Mac/Linux)
- **Tkinter** — settings window (built in, packages well)
- **platformdirs** — per-system configuration and log paths
- **pywin32** (Windows) / CUPS commands `lp`/`lpr` (macOS/Linux) — print backend
- **PyInstaller** — building standalone binaries

## 6. Supported ZPL subset (render mode)

A deliberate subset — full ZPL is too large, and the mode is offline:

- structure: `^XA`, `^XZ`, `^FS`
- settings: `^PW` (width), `^LL` (length), `^LH` (home), `^CF`, `^CI`; DPI from configuration
- positioning: `^FO`, `^FT`
- text: `^A` (scalable font → embedded TrueType font), `^FD`, `^FH`
- graphics: `^GB` (boxes/lines/rectangles), `^GF` (ASCII-hex bitmap), `^FR`
- barcodes: `^BY`, `^BC` (Code128), `^BQ` (QR)
- **Unsupported commands** → skipped and logged (best-effort rendering; the job is
  not aborted).

Known and accepted limitation: more exotic ZPL commands may not render perfectly.
The **raw** path (for printers with native ZPL) is always fully faithful.

## 7. Listening address (bypass)

The listener binds to a user-selected `listen_host` — one of this computer's own
IPv4 addresses — rather than a hardcoded `0.0.0.0`. This makes the bypass explicit:
the WMS is configured to print to that exact address (e.g. `192.168.1.50:9100`).

- The settings window offers a drop-down of detected local IPv4 addresses (LAN
  address first), plus `0.0.0.0` (all interfaces) as a fallback option, and a
  "Refresh" button.
- A hint shows the user exactly what to configure in the WMS: `IP:port`.
- If the saved address is no longer available (e.g. a DHCP change), the server start
  fails with a clear message asking the user to refresh and reselect.

## 8. Error handling

The application never crashes; everything goes to the log and the window:

- Address/port unavailable or in use at start → clear message in the GUI, the user can
  change the address or port.
- No target printer selected / printer offline → the job is marked as failed in the
  log, the application keeps running.
- Client disconnected mid-job (incomplete `^XA…^XZ`) → the fragment is discarded with a
  warning (a trailing newline after `^XZ` is not treated as an error).
- Unsupported ZPL command (render) → skipped and logged, the rest of the label renders.
- Print backend failure → logged with the error text; the job does not block others.

## 9. Tests

- **Unit:** `jobs` (stream splitting, concatenated/fragmented TCP packets),
  `config` (save/load, validation), `printers` (backend mocked per OS),
  `netutil` (address filtering/ordering, mocked).
- **Renderer:** "golden image" tests for sample labels (text, box, Code128, QR) —
  comparing dimensions and image content.
- **Integration:** sending sample ZPL to a real local socket → verifying the router
  reaches the mocked backend in both modes; binding to a specific `listen_host`.
- **GUI:** pure form/hint logic tested directly; the Tkinter window smoke-tested under
  a virtual display.
- **Manual:** a real Toshiba B-EX (render) + a real Zebra (raw).

## 10. Out of scope (YAGNI for now)

- ZPL → TPCL / other printer-language conversion (solved by rendering to a bitmap).
- Managing multiple virtual printers in the UI (the architecture is ready; UI later).
- Advanced label preview in the GUI, queueing with retries, authentication.
