"""SSRF 防护 — 阻止对内网地址和危险协议的请求。"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


# 允许的 URL scheme
ALLOWED_SCHEMES = frozenset({"http", "https"})

# 最大重定向次数
MAX_REDIRECTS = 3

# URL 验证超时（秒）
URL_VALIDATE_TIMEOUT = 5

# 私有 IP 范围 (RFC 1918 + link-local + loopback)
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),       # loopback
    ipaddress.ip_network("10.0.0.0/8"),         # Class A private
    ipaddress.ip_network("172.16.0.0/12"),      # Class B private
    ipaddress.ip_network("192.168.0.0/16"),     # Class C private
    ipaddress.ip_network("169.254.0.0/16"),     # link-local
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),           # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),          # IPv6 link-local
    ipaddress.ip_network("0.0.0.0/8"),          # "this" network
]


class SSRFError(Exception):
    """SSRF 防护拦截异常。"""

    def __init__(self, reason: str, url: str = "") -> None:
        self.reason = reason
        self.url = url
        super().__init__(f"SSRF blocked: {reason} (url={url})")


def _is_private_ip(ip_str: str) -> bool:
    """判断 IP 地址是否属于私有/保留网络。"""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        # 无法解析的 IP 视为危险
        return True

    return any(addr in network for network in _PRIVATE_NETWORKS)


def _resolve_hostname(hostname: str) -> str | None:
    """解析主机名到 IP 地址，返回 None 表示解析失败。"""
    try:
        result = socket.getaddrinfo(
            hostname,
            None,
            socket.AF_UNSPEC,
            socket.SOCK_STREAM,
        )
        if result:
            return result[0][4][0]  # 第一个解析结果的 IP
    except (socket.gaierror, OSError):
        pass
    return None


class URLPolicy:
    """URL 安全策略 — 检查 URL 是否允许访问。"""

    def __init__(
        self,
        allowed_schemes: frozenset[str] = ALLOWED_SCHEMES,
        max_redirects: int = MAX_REDIRECTS,
    ) -> None:
        self.allowed_schemes = allowed_schemes
        self.max_redirects = max_redirects

    def check_url(self, url: str) -> None:
        """检查 URL 是否安全，不安全则抛出 SSRFError。

        Args:
            url: 要检查的 URL

        Raises:
            SSRFError: 如果 URL 不安全
        """
        # 1. 检查 URL scheme
        parsed = urlparse(url)
        if parsed.scheme and parsed.scheme.lower() not in self.allowed_schemes:
            raise SSRFError(
                reason=f"不支持的协议: {parsed.scheme}",
                url=url,
            )

        # 2. 检查主机名
        hostname = parsed.hostname
        if not hostname:
            raise SSRFError(reason="缺少主机名", url=url)

        # 3. 检查是否为 IP 地址（直接检查）
        try:
            ipaddress.ip_address(hostname)
            if _is_private_ip(hostname):
                raise SSRFError(
                    reason=f"禁止访问私有 IP: {hostname}",
                    url=url,
                )
        except ValueError:
            # hostname 不是 IP 地址，需要 DNS 解析
            pass

        # 4. DNS 解析后检查
        resolved_ip = _resolve_hostname(hostname)
        if resolved_ip and _is_private_ip(resolved_ip):
            raise SSRFError(
                reason=f"主机名解析到私有 IP: {hostname} -> {resolved_ip}",
                url=url,
            )


def is_safe_url(url: str, **kwargs) -> bool:
    """便捷函数：检查 URL 是否安全。

    Args:
        url: 要检查的 URL
        **kwargs: 传递给 URLPolicy 构造函数的参数

    Returns:
        True 如果安全，否则 False
    """
    try:
        policy = URLPolicy(**kwargs)
        policy.check_url(url)
        return True
    except SSRFError:
        return False
