"""Router: decyduje, jak wysłać zadanie ZPL do drukarki (raw vs render)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import Mapping
from .printers import PrinterBackend, PrintError
from .renderer import render


@dataclass
class RouteResult:
    ok: bool
    mode: str
    printer: str
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


class Router:
    """Kieruje pojedyncze zadania ZPL na backend druku wg konfiguracji mapowania."""

    def __init__(self, backend: PrinterBackend) -> None:
        self.backend = backend

    def handle_job(self, mapping: Mapping, job: bytes) -> RouteResult:
        printer = mapping.target_printer
        if not printer:
            return RouteResult(False, mapping.mode, printer,
                               error="Nie wybrano drukarki docelowej.")
        try:
            if mapping.mode == "raw":
                self.backend.print_raw(printer, job)
                return RouteResult(True, "raw", printer)

            result = render(job, dpi=mapping.dpi,
                            default_label_mm=mapping.default_label_mm)
            self.backend.print_image(printer, result.image, dpi=mapping.dpi)
            warns = list(result.warnings)
            if result.unsupported:
                warns.append("Pominięte polecenia ZPL: " + ", ".join(result.unsupported))
            return RouteResult(True, "render", printer, warnings=warns)
        except PrintError as exc:
            return RouteResult(False, mapping.mode, printer, error=str(exc))
        except Exception as exc:  # renderer/inne — nie wywalamy serwera
            return RouteResult(False, mapping.mode, printer,
                               error=f"Błąd przetwarzania zadania: {exc}")
