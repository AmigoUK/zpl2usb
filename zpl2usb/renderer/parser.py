"""Tokenizacja strumienia ZPL na listę poleceń.

Polecenia ZPL zaczynają się od prefiksu ``^`` (format) lub ``~`` (control),
po którym następuje 2-literowy mnemonik i parametry aż do kolejnego prefiksu.

Wyjątek: ``^A`` (wybór fontu) to jednoznakowy mnemonik — bezpośrednio po nim
występuje oznaczenie fontu (np. ``^A0N,30,30`` albo ``^A@N,...``).
Parametry polecenia ``^FD`` (dane pola) mogą zawierać dowolne znaki poza
prefiksami — kończą się na kolejnym ``^`` lub ``~``.
"""

from __future__ import annotations

from dataclasses import dataclass

PREFIXES = (b"^", b"~")


@dataclass(frozen=True)
class Command:
    """Pojedyncze polecenie ZPL."""

    name: str        # mnemonik bez prefiksu, wielkimi literami, np. "FO", "FD", "A"
    params: str      # surowe parametry (dla ^A zawiera oznaczenie fontu)
    prefix: str = "^"  # "^" lub "~"


def _decode(data: bytes | str) -> str:
    if isinstance(data, str):
        return data
    # latin-1 zachowuje bajty 1:1; ^CI/^FH i tak zwykle ASCII.
    return data.decode("latin-1")


def tokenize(zpl: bytes | str) -> list[Command]:
    """Zamień strumień ZPL na listę poleceń ``Command``.

    Tekst przed pierwszym prefiksem jest pomijany. Nieznane mnemoniki są
    zachowywane jako ``Command`` — interpreter zdecyduje, co z nimi zrobić.
    """
    text = _decode(zpl)
    commands: list[Command] = []
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]
        if ch not in ("^", "~"):
            i += 1
            continue
        prefix = ch
        i += 1
        if i >= n:
            break
        # Mnemonik: specjalny przypadek ^A (font) — jednoliterowy, gdy kolejny znak
        # nie jest wielką literą (jest cyfrą, '@', ',' itd.).
        first = text[i]
        if first == "A" and (i + 1 >= n or not text[i + 1].isalpha()):
            name = "A"
            i += 1
        else:
            name = text[i : i + 2].upper()
            i += 2

        # Parametry: do kolejnego prefiksu.
        j = i
        while j < n and text[j] not in ("^", "~"):
            j += 1
        params = text[i:j]
        i = j
        commands.append(Command(name=name, params=params, prefix=prefix))

    return commands
