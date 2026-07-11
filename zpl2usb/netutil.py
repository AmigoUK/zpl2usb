"""Wykrywanie lokalnych adresów IPv4 komputera.

Używane do listy „Adres nasłuchu (ten komputer)" w GUI. Preferujemy ``psutil``
(pewne, wieloplatformowe enumerowanie interfejsów, działa też offline).
Bez psutil działa fallback oparty na gnieździe UDP (adres interfejsu z trasą
domyślną) oraz nazwie hosta.
"""

from __future__ import annotations

import ipaddress
import socket


def _is_usable(addr: str) -> bool:
    """Pomiń loopback, link-local i nieprawidłowe adresy."""
    try:
        ip = ipaddress.IPv4Address(addr)
    except ipaddress.AddressValueError:
        return False
    return not (ip.is_loopback or ip.is_link_local or ip.is_unspecified)


def default_route_ip() -> str | None:
    """Adres IP interfejsu, którym poszłaby trasa domyślna (bez wysyłania danych).

    Działa offline, o ile istnieje trasa domyślna; w izolowanej sieci może zwrócić
    ``None``.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # nie wysyła pakietów — ustala tylko routing
        ip = s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()
    return ip if _is_usable(ip) else None


def _collect_via_psutil() -> list[str]:
    try:
        import psutil
    except ImportError:
        return []
    found = []
    for _iface, addrs in psutil.net_if_addrs().items():
        for a in addrs:
            if a.family == socket.AF_INET and _is_usable(a.address):
                found.append(a.address)
    return found


def _collect_via_socket() -> list[str]:
    found = []
    try:
        _host, _alias, ips = socket.gethostbyname_ex(socket.gethostname())
        found.extend(ip for ip in ips if _is_usable(ip))
    except OSError:
        pass
    return found


def order_addresses(addresses: list[str], primary: str | None) -> list[str]:
    """Usuń duplikaty, ustaw ``primary`` (adres trasy domyślnej) na początku."""
    seen: set[str] = set()
    ordered: list[str] = []
    if primary and _is_usable(primary):
        ordered.append(primary)
        seen.add(primary)
    for a in addresses:
        if a not in seen:
            ordered.append(a)
            seen.add(a)
    return ordered


def list_local_ipv4() -> list[str]:
    """Lista użytecznych adresów IPv4 tego komputera; adres LAN jako pierwszy.

    Zawsze zawiera ``0.0.0.0`` (wszystkie interfejsy) na końcu jako opcję awaryjną.
    """
    primary = default_route_ip()
    collected = _collect_via_psutil() or _collect_via_socket()
    ordered = order_addresses(collected, primary)
    ordered.append("0.0.0.0")
    return ordered
