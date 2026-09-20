"""SSRF protection — URL validation helpers and class-based validator."""

from __future__ import annotations

import ipaddress
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# IPv4 ranges that must never be the target of outbound requests
_BLOCKED_IPV4_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),     # loopback
    ipaddress.ip_network("10.0.0.0/8"),      # private Class A
    ipaddress.ip_network("172.16.0.0/12"),    # private Class B
    ipaddress.ip_network("192.168.0.0/16"),   # private Class C
    ipaddress.ip_network("169.254.0.0/16"),   # link-local
]

_BLOCKED_IPV6_NETWORKS = [
    ipaddress.ip_network("::1/128"),          # loopback
    ipaddress.ip_network("fc00::/7"),         # unique local
    ipaddress.ip_network("fe80::/10"),        # link-local
]


def _is_private_ip(ip_str: str) -> bool:
    """Return True if *ip_str* resolves to a private/loopback address."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    if isinstance(addr, ipaddress.IPv4Address):
        return any(addr in net for net in _BLOCKED_IPV4_NETWORKS)
    if isinstance(addr, ipaddress.IPv6Address):
        return any(addr in net for net in _BLOCKED_IPV6_NETWORKS)
    return False


def validate_url(url: str, *, resolve: bool = False) -> bool:
    """Validate that *url* does not point to a private / loopback address.

    Parameters
    ----------
    url:
        The URL to validate.
    resolve:
        If True, also resolve the hostname and check the resulting IP.
        Disabled by default to avoid DNS-rebinding attacks (use IP check
        instead).

    Returns
    -------
    bool
        ``True`` when the URL is safe, ``False`` when it should be blocked.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    # Direct numeric IP check
    if _is_private_ip(hostname):
        logger.warning("SSRF blocked: %s resolves to private IP %s", url, hostname)
        return False

    # Optional DNS resolution check
    if resolve:
        import socket

        try:
            infos = socket.getaddrinfo(hostname, None)
            for family, _, _, _, sockaddr in infos:
                if _is_private_ip(sockaddr[0]):
                    logger.warning(
                        "SSRF blocked: %s resolved to private IP %s", url, sockaddr[0]
                    )
                    return False
        except socket.gaierror:
            return False

    return True


class UrlValidator:
    """Reusable validator instance that can be shared across services."""

    def __init__(self, *, resolve: bool = False):
        self.resolve = resolve

    def __call__(self, url: str) -> bool:
        return validate_url(url, resolve=self.resolve)

    def assert_safe(self, url: str) -> None:
        """Raise ``ValueError`` if the URL is not safe."""
        if not self(url):
            raise ValueError(f"Blocked SSRF attempt: {url}")
