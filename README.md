# zpl2usb

**Wirtualna sieciowa drukarka ZPL (Zebra, port 9100)** mostkująca druk na dowolną
drukarkę zainstalowaną w systemie — na Windows, Linux i macOS.

Systemy magazynowe/ERP potrafią drukować etykiety tylko na sieciową drukarkę ZPL
(port RAW/9100). zpl2usb udaje taką drukarkę: nasłuchuje na `IP_komputera:9100`,
przyjmuje strumień ZPL i kieruje go na wybraną drukarkę systemową:

- **raw** — surowe bajty ZPL 1:1 (dla drukarek natywnie ZPL, np. Zebra),
- **render** — lokalne (offline) renderowanie ZPL do bitmapy i druk przez
  sterownik systemowy (dla drukarek bez ZPL, np. Toshiba B-EX).

Aplikacja ma ikonę w zasobniku systemowym i proste okno ustawień.

## Status

W budowie. Zobacz spec: [`docs/superpowers/specs/2026-07-11-zpl2usb-design.md`](docs/superpowers/specs/2026-07-11-zpl2usb-design.md).

## Uruchomienie ze źródeł

```bash
python3 -m venv .venv
. .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m zpl2usb              # start aplikacji (tray + nasłuch)
```

Na Windows dodatkowo: `pip install pywin32`.
Na Linux wymagany jest CUPS (`lp`/`lpr`) oraz `python3-tk` dla GUI.

## Testy

```bash
pip install pytest
pytest
```

## Konfiguracja

Zapisywana jako JSON w katalogu konfiguracji użytkownika (wg systemu, przez
`platformdirs`). Domyślne mapowanie: port `9100`, tryb `raw`, DPI `203`,
rozmiar etykiety `100 × 40 mm`.
