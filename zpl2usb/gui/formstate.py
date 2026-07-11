"""Czysta logika mapowania między formularzem GUI a modelem konfiguracji.

Wydzielone z widoku Tkinter, żeby dało się testować bez ekranu.
"""

from __future__ import annotations

from ..config import DPIS, MODES, Mapping


def mapping_to_form(m: Mapping) -> dict:
    """Model -> wartości pól formularza (stringi, wygodne dla widgetów)."""
    return {
        "listen_port": str(m.listen_port),
        "target_printer": m.target_printer,
        "mode": m.mode,
        "dpi": str(m.dpi),
        "label_w": _fmt(m.default_label_mm[0]),
        "label_h": _fmt(m.default_label_mm[1]),
        "enabled": m.enabled,
    }


def form_to_mapping(form: dict) -> Mapping:
    """Wartości pól formularza -> model (z konwersją typów).

    Rzuca ``ValueError`` przy niepoprawnych wartościach — komunikat nadaje się
    do pokazania użytkownikowi.
    """
    port = _to_int(form.get("listen_port"), "Port")
    dpi = _to_int(form.get("dpi"), "DPI")
    lw = _to_float(form.get("label_w"), "Szerokość etykiety")
    lh = _to_float(form.get("label_h"), "Wysokość etykiety")
    mode = (form.get("mode") or "").strip()

    if mode not in MODES:
        raise ValueError(f"Nieprawidłowy tryb: {mode!r}")
    if dpi not in DPIS:
        raise ValueError(f"Nieobsługiwane DPI: {dpi} (dozwolone: {', '.join(map(str, DPIS))})")

    m = Mapping(
        listen_port=port,
        target_printer=(form.get("target_printer") or "").strip(),
        mode=mode,
        dpi=dpi,
        default_label_mm=(lw, lh),
        enabled=bool(form.get("enabled", True)),
    )
    m.validate()  # dodatkowa walidacja zakresów
    return m


def _fmt(value: float) -> str:
    # 100.0 -> "100", 40.5 -> "40.5"
    return f"{value:g}"


def _to_int(value, label: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(f"{label}: podaj liczbę całkowitą (otrzymano {value!r})")


def _to_float(value, label: str) -> float:
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError(f"{label}: podaj liczbę (otrzymano {value!r})")
