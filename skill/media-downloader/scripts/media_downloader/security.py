import ipaddress
import socket
from typing import Callable
from urllib.parse import urlsplit, urlunsplit


class UnsafeURLError(ValueError):
    pass


SYNTHETIC_PROXY_NETWORK = ipaddress.ip_network("198.18.0.0/15")


def _reject_non_global_address(address: str, *, allow_synthetic_proxy: bool = False) -> None:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return
    if allow_synthetic_proxy and ip in SYNTHETIC_PROXY_NETWORK:
        return
    if not ip.is_global:
        raise UnsafeURLError("URL resolves to a non-public network address")


def validate_public_http_url(
    url: str,
    *,
    resolve_dns: bool = True,
    resolver: Callable = socket.getaddrinfo,
) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in ("http", "https"):
        raise UnsafeURLError("only http and https URLs are allowed")
    if parts.username or parts.password:
        raise UnsafeURLError("credentials embedded in URLs are not allowed")
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        raise UnsafeURLError("URL has no hostname")
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise UnsafeURLError("local hostnames are not allowed")

    _reject_non_global_address(host)

    if resolve_dns:
        port = parts.port or (443 if parts.scheme.lower() == "https" else 80)
        try:
            records = resolver(host, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise UnsafeURLError("hostname could not be resolved: {}".format(exc)) from exc
        if not records:
            raise UnsafeURLError("hostname did not resolve")
        for record in records:
            _reject_non_global_address(record[4][0], allow_synthetic_proxy=True)

    return urlunsplit(parts)
