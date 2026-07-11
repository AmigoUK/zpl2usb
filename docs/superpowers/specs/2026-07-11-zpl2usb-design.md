# zpl2usb — Wirtualna sieciowa drukarka ZPL (spec projektowy)

- **Data:** 2026-07-11
- **Status:** Zaakceptowany do planowania implementacji

## 1. Cel i problem

Systemy magazynowe/ERP potrafią drukować etykiety tylko na sieciową drukarkę ZPL
(Zebra, port RAW/9100). W praktyce drukarka podłączona do komputera bywa inna:
zwykła drukarka biurowa albo przemysłowa etykieciarka innego producenta
(np. **Toshiba B-EX**, natywnie TPCL), która nie rozumie ZPL.

**zpl2usb** to prosta, wieloplatformowa (Windows/Linux/macOS) aplikacja w Pythonie,
która emuluje sieciową drukarkę ZPL Zebra na porcie `9100`. Przyjmuje strumień ZPL
po TCP i kieruje go na dowolną drukarkę zainstalowaną w systemie — surowo (raw)
lub renderując lokalnie ZPL do bitmapy dla drukarek bez natywnego ZPL.
Aplikacja ma ikonę w zasobniku systemowym i proste okno ustawień, dystrybuowana
jako samodzielna binarka (bez instalacji Pythona przez użytkownika).

## 2. Decyzje projektowe (ustalenia)

| Zagadnienie | Decyzja |
|---|---|
| Drukarka docelowa | Dowolna — tryb wybierany przez użytkownika (raw ZPL **lub** render) |
| Sposób druku | Wyłącznie przez **drukarki zainstalowane w systemie** (sterownik/kolejka) |
| Renderowanie ZPL | **Tylko lokalnie/offline** (bez usług online typu Labelary) |
| Liczba wirtualnych drukarek | Start od **jednej**; architektura zaprojektowana pod wiele (lista mapowań) |
| Interfejs | **Ikona w zasobniku** (pystray) + okno ustawień/log (Tkinter) |
| Dystrybucja | **Samodzielna binarka** per system (PyInstaller) |
| DPI | Ustawiane **per drukarka** (203/300/600), domyślnie 203 |
| Domyślny rozmiar etykiety | **100 × 40 mm** (gdy brak `^PW`/`^LL` w ZPL) |

## 3. Architektura i przepływ danych

```
System (WMS/ERP)  --ZPL po TCP-->  :9100 nasłuch  -->  podział na zadania (^XA…^XZ)
                                                             |
                                                        router (tryb?)
                                              raw /                    \ render
                                     backend druku            renderer ZPL->bitmapa (DPI)
                                     (surowe bajty)                     |
                                              \___ drukarka systemowa __/
                                                    (Win/Mac/Linux)
```

1. System wysyła ZPL na `0.0.0.0:9100` (protokół RAW/JetDirect — czyste bajty,
   bez handshake).
2. Nasłuch zbiera bajty z połączenia i dzieli strumień na zadania `^XA`…`^XZ`.
3. Router sprawdza konfigurację danego portu → tryb **raw** lub **render**.
4. **raw** → bajty 1:1 do drukarki systemowej.
   **render** → lokalny interpreter ZPL tworzy bitmapę w zadanym DPI →
   druk obrazu przez sterownik systemowy.
5. Wynik i błędy trafiają do logu i okna aplikacji.

## 4. Moduły (każdy o jednej odpowiedzialności)

- **`server.py`** — nasłuch TCP RAW dla mapowania (start/stop, wiele portów w przyszłości);
  zbiera bajty z połączenia.
- **`jobs.py`** — dzieli strumień na pojedyncze zadania ZPL (`^XA`…`^XZ`);
  odporny na sklejone i pofragmentowane pakiety TCP.
- **`router.py`** — decyzja raw vs render wg konfiguracji; wywołanie backendu druku.
- **`printers.py`** — warstwa międzyplatformowa: `list_printers()`,
  `print_raw(name, bytes)`, `print_image(name, image)`.
  Windows → `win32print`; macOS/Linux → CUPS (`lp`/`lpr`).
- **`renderer/`** — interpreter ZPL → obraz PIL:
  - `parser` — tokenizacja poleceń
  - `commands` — `^FO/^FT`, `^A` (tekst), `^GB` (ramki/linie), `^GF` (grafika)
  - `barcodes` — `^BC` (Code128), `^BQ` (QR), `^BY`
  - `canvas` — płótno wg DPI i rozmiaru etykiety
- **`config.py`** — wczytywanie/zapis JSON (`platformdirs`); dataklasy mapowań.
- **`app.py`** — spina konfigurację → serwery → router; cykl życia aplikacji.
- **`gui/`** — ikona w zasobniku (`pystray`) + okno ustawień i log (`Tkinter`).

Model konfiguracji (jedno mapowanie dziś, lista pod wiele):

```json
{
  "mappings": [
    {
      "listen_port": 9100,
      "target_printer": "Toshiba B-EX",
      "mode": "render",            // "raw" | "render"
      "dpi": 203,                  // 203 | 300 | 600
      "default_label_mm": [100, 40]
    }
  ]
}
```

## 5. Stos technologiczny

- **Python 3.11+**
- **Pillow** — płótno i rasteryzacja
- **python-barcode** (Code128) + **qrcode** (QR)
- **pystray** — ikona w zasobniku (Win/Mac/Linux)
- **Tkinter** — okno ustawień (wbudowane, dobrze się pakuje)
- **platformdirs** — ścieżki configu i logów per system
- **pywin32** (Windows) / polecenia **CUPS** `lp`/`lpr` (macOS/Linux) — backend druku
- **PyInstaller** — budowa samodzielnych binarek

## 6. Zakres lokalnego renderera ZPL (MVP)

Świadomy podzbiór — pełny ZPL jest zbyt obszerny, a tryb jest offline:

- Struktura: `^XA`, `^XZ`, `^FS`
- Ustawienia: `^PW` (szerokość), `^LL` (długość), `^LH` (home), `^CI`; DPI z konfiguracji
- Pozycjonowanie: `^FO`, `^FT`
- Tekst: `^A` (fonty skalowalne → wbudowany font TrueType), `^FD`, `^FH`
- Grafika: `^GB` (ramki/linie/prostokąty), `^GF` (grafika bitmapowa), `^FR`
- Kody: `^BY`, `^BC` (Code128), `^BQ` (QR)
- **Nieobsługiwane polecenia** → pomijane z wpisem do logu (render best-effort,
  nie przerywa zadania).

Ograniczenie znane i zaakceptowane: bardziej egzotyczne polecenia ZPL mogą nie
renderować się idealnie. Ścieżka **raw** (dla drukarek natywnie ZPL) jest zawsze
w pełni wierna.

## 7. Obsługa błędów

Aplikacja nigdy się nie wywala; wszystko trafia do logu i okna:

- Port zajęty przy starcie → czytelny komunikat w GUI, możliwość zmiany portu.
- Brak wybranej / offline drukarki → zadanie oznaczone jako błędne w logu,
  aplikacja działa dalej.
- Klient rozłączył się w trakcie zadania (niepełne `^XA…^XZ`) → odrzucenie
  fragmentu z ostrzeżeniem.
- Nieobsługiwane polecenie ZPL (render) → pominięcie + log, reszta etykiety renderowana.
- Błąd backendu druku → log z treścią błędu; zadanie nie blokuje kolejnych.

## 8. Testy

- **Jednostkowe:** `jobs` (podział strumienia, sklejone/rozcięte pakiety TCP),
  `config` (zapis/odczyt, migracja), `printers` (backend zamockowany per OS).
- **Renderer:** testy „golden image" dla przykładowych etykiet (tekst, ramka,
  Code128, QR) — porównanie wymiarów i skrótu obrazu.
- **Integracyjne:** wysłanie przykładowego ZPL na lokalny socket → sprawdzenie,
  że router trafia do zamockowanego backendu w obu trybach.
- **Manualne:** prawdziwa Toshiba B-EX (render) + prawdziwa Zebra (raw).

## 9. Poza zakresem (YAGNI na teraz)

- Konwersja ZPL → TPCL / inne języki drukarek (rozwiązywane przez render do bitmapy).
- Wiele jednoczesnych wirtualnych drukarek w UI (architektura gotowa, UI później).
- Zaawansowany podgląd etykiety w GUI, kolejkowanie z ponawianiem, autentykacja.
