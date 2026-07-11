"""Podział strumienia bajtów ZPL na pojedyncze zadania (etykiety).

Zadanie ZPL zaczyna się od ``^XA`` i kończy ``^XZ`` (dopuszczamy też wariant
z ``~`` jako prefiksem sterującym w niektórych implementacjach, ale znaczniki
formatu to ``^XA``/``^XZ``).

Dane z TCP przychodzą w dowolnie pociętych porcjach: jeden pakiet może zawierać
kilka etykiet, a jedna etykieta może być rozbita na wiele pakietów. ``JobSplitter``
buforuje bajty między wywołaniami i wydaje kompletne zadania.
"""

from __future__ import annotations

START = b"^XA"
END = b"^XZ"


class JobSplitter:
    """Buforuje strumień bajtów i wydaje kompletne zadania ZPL (^XA..^XZ)."""

    def __init__(self, max_buffer: int = 8 * 1024 * 1024) -> None:
        self._buf = bytearray()
        self._max_buffer = max_buffer

    def feed(self, chunk: bytes) -> list[bytes]:
        """Dodaj porcję danych; zwróć listę kompletnych zadań (może być pusta).

        Każde zwrócone zadanie zawiera znaczniki ``^XA``..``^XZ`` włącznie.
        Bajty przed pierwszym ``^XA`` (śmieci/puste linie) są pomijane.
        """
        self._buf.extend(chunk)
        jobs: list[bytes] = []

        while True:
            start = self._buf.find(START)
            if start == -1:
                # Brak początku zadania. Zachowaj ewentualny ogon, który może być
                # niepełnym "^X" na styku pakietów; resztę odrzuć.
                self._trim_leading_noise()
                break
            # Odrzuć śmieci przed ^XA.
            if start > 0:
                del self._buf[:start]
            end = self._buf.find(END)
            if end == -1:
                break  # zadanie jeszcze niekompletne — czekamy na dalsze dane
            end_full = end + len(END)
            jobs.append(bytes(self._buf[:end_full]))
            del self._buf[:end_full]

        if len(self._buf) > self._max_buffer:
            # Zabezpieczenie przed nieograniczonym buforem przy zepsutym strumieniu.
            raise BufferError(f"Bufor zadania przekroczył {self._max_buffer} B bez znacznika ^XZ")
        return jobs

    def _trim_leading_noise(self) -> None:
        """Zostaw w buforze tylko możliwy niepełny prefiks znacznika ^XA.

        Gdy w buforze nie ma ``^XA``, jedyne co warto zachować to końcówka, która
        może być początkiem ``^XA`` rozbitego między pakietami (np. ``^`` lub ``^X``).
        """
        keep = len(START) - 1
        if len(self._buf) > keep:
            del self._buf[: len(self._buf) - keep]

    @property
    def pending(self) -> bytes:
        """Bajty aktualnie w buforze (niekompletne zadanie)."""
        return bytes(self._buf)

    def reset(self) -> None:
        """Wyczyść bufor (np. po rozłączeniu klienta)."""
        self._buf.clear()


def split_jobs(data: bytes) -> list[bytes]:
    """Wygodna funkcja: podziel kompletny bufor na zadania (bez stanu)."""
    return JobSplitter().feed(data)
