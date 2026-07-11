"""Konfiguracja aplikacji: mapowania wirtualnych drukarek.

Konfiguracja to lista mapowań. Dziś UI obsługuje jedno, ale model jest listą,
żeby dodanie wielu wirtualnych drukarek nie wymagało zmian architektury.

Zapis/odczyt jako JSON w katalogu konfiguracji użytkownika (per system).
"""

from __future__ import annotations

import ipaddress
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from platformdirs import user_config_dir

APP_NAME = "zpl2usb"

# Dozwolone wartości
MODES = ("raw", "render")
DPIS = (203, 300, 600)

DEFAULT_PORT = 9100
DEFAULT_HOST = "0.0.0.0"
DEFAULT_MODE = "raw"
DEFAULT_DPI = 203
DEFAULT_LABEL_MM = (100.0, 40.0)


class ConfigError(ValueError):
    """Błąd walidacji konfiguracji."""


@dataclass
class Mapping:
    """Pojedyncze mapowanie: nasłuch na porcie -> drukarka systemowa."""

    listen_port: int = DEFAULT_PORT
    # Adres IP tego komputera, na którym nasłuchuje wirtualna drukarka.
    # "0.0.0.0" = wszystkie interfejsy; zwykle konkretny adres LAN (np. 192.168.1.50).
    listen_host: str = DEFAULT_HOST
    target_printer: str = ""
    mode: str = DEFAULT_MODE
    dpi: int = DEFAULT_DPI
    # Rozmiar etykiety w mm (szerokość, wysokość) — używany, gdy w ZPL brak ^PW/^LL.
    default_label_mm: tuple[float, float] = DEFAULT_LABEL_MM
    enabled: bool = True

    def validate(self) -> None:
        if not (1 <= self.listen_port <= 65535):
            raise ConfigError(f"Port poza zakresem 1-65535: {self.listen_port}")
        try:
            ipaddress.IPv4Address(self.listen_host)
        except ipaddress.AddressValueError as exc:
            raise ConfigError(f"Nieprawidłowy adres IPv4: {self.listen_host!r}") from exc
        if self.mode not in MODES:
            raise ConfigError(f"Nieznany tryb: {self.mode!r} (dozwolone: {MODES})")
        if self.dpi not in DPIS:
            raise ConfigError(f"Nieobsługiwane DPI: {self.dpi} (dozwolone: {DPIS})")
        w, h = self.default_label_mm
        if w <= 0 or h <= 0:
            raise ConfigError(f"Rozmiar etykiety musi być dodatni: {self.default_label_mm}")

    @classmethod
    def from_dict(cls, data: dict) -> Mapping:
        label = data.get("default_label_mm", DEFAULT_LABEL_MM)
        return cls(
            listen_port=int(data.get("listen_port", DEFAULT_PORT)),
            listen_host=str(data.get("listen_host", DEFAULT_HOST)),
            target_printer=str(data.get("target_printer", "")),
            mode=str(data.get("mode", DEFAULT_MODE)),
            dpi=int(data.get("dpi", DEFAULT_DPI)),
            default_label_mm=(float(label[0]), float(label[1])),
            enabled=bool(data.get("enabled", True)),
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        # asdict zamienia tuple na list — zostawiamy list (JSON-friendly).
        d["default_label_mm"] = [self.default_label_mm[0], self.default_label_mm[1]]
        return d


@dataclass
class Config:
    """Cała konfiguracja aplikacji."""

    mappings: list[Mapping] = field(default_factory=lambda: [Mapping()])
    # Uruchamiać aplikację przy starcie systemu (domyślnie włączone).
    autostart: bool = True

    def validate(self) -> None:
        if not self.mappings:
            raise ConfigError("Konfiguracja musi mieć przynajmniej jedno mapowanie.")
        # Nasłuchy nie mogą kolidować. Ten sam port jest dozwolony na różnych
        # konkretnych adresach, ale 0.0.0.0 zajmuje port na wszystkich interfejsach,
        # więc koliduje z każdym innym adresem na tym samym porcie.
        by_port: dict[int, list[str]] = {}
        for m in self.mappings:
            by_port.setdefault(m.listen_port, []).append(m.listen_host)
        for port, hosts in by_port.items():
            if len(hosts) != len(set(hosts)):
                raise ConfigError(f"Adres:port nasłuchu muszą być unikalne (port {port}).")
            if DEFAULT_HOST in hosts and len(hosts) > 1:
                raise ConfigError(
                    f"Port {port}: {DEFAULT_HOST} (wszystkie interfejsy) koliduje z "
                    f"innym adresem na tym samym porcie."
                )
        for m in self.mappings:
            m.validate()

    @classmethod
    def from_dict(cls, data: dict) -> Config:
        raw = data.get("mappings") or []
        mappings = [Mapping.from_dict(m) for m in raw]
        if not mappings:
            mappings = [Mapping()]
        return cls(mappings=mappings, autostart=bool(data.get("autostart", True)))

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "autostart": self.autostart,
            "mappings": [m.to_dict() for m in self.mappings],
        }


def config_path() -> Path:
    """Ścieżka pliku konfiguracji (per system, przez platformdirs)."""
    return Path(user_config_dir(APP_NAME, appauthor=False)) / "config.json"


def load(path: Path | None = None) -> Config:
    """Wczytaj konfigurację; przy braku pliku zwróć domyślną."""
    p = path or config_path()
    if not p.exists():
        return Config()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ConfigError(f"Nie można odczytać konfiguracji {p}: {exc}") from exc
    try:
        cfg = Config.from_dict(data)
        cfg.validate()
    except ConfigError:
        raise
    except (ValueError, TypeError, KeyError) as exc:
        # np. "listen_port": "abc" albo skalarny default_label_mm — zgłoś łagodnie.
        raise ConfigError(f"Nieprawidłowa konfiguracja {p}: {exc}") from exc
    return cfg


def save(cfg: Config, path: Path | None = None) -> Path:
    """Zapisz konfigurację (waliduje przed zapisem). Zwraca ścieżkę."""
    cfg.validate()
    p = path or config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(cfg.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)  # atomowy zapis
    return p
