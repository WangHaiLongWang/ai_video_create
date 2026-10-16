"""密钥脱敏 — 在日志和导出中掩码敏感信息。"""

from __future__ import annotations

import re


# 常见密钥模式
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # OpenAI API Key
    ("OPENAI_API_KEY", re.compile(r"sk-[a-zA-Z0-9]{20,}")),
    # DashScope API Key
    ("DASHSCOPE_API_KEY", re.compile(r"sk-[a-zA-Z0-9]{20,}")),
    # 通用 Bearer Token
    ("BEARER_TOKEN", re.compile(r"(Bearer\s+)[a-zA-Z0-9._\-]{20,}", re.IGNORECASE)),
    # 通用 API Key 模式 (key=xxx 或 api_key=xxx)
    ("API_KEY_ASSIGN", re.compile(
        r"((?:api[_\-]?key|apikey|secret[_\-]?key|token|password|passwd|pwd)"
        r"\s*[=:]\s*['\"]?)([a-zA-Z0-9._\-]{8,})(['\"]?)",
        re.IGNORECASE,
    )),
    # AWS Access Key
    ("AWS_ACCESS_KEY", re.compile(r"(AKIA[0-9A-Z]{16})")),
    # GitHub Token
    ("GITHUB_TOKEN", re.compile(r"(gh[pousr]_[A-Za-z0-9_]{36,})")),
    # 通用 Hex Token (32+ 位)
    ("HEX_TOKEN", re.compile(r"\b([0-9a-fA-F]{32,})\b")),
]


def _mask_value(value: str, keep_start: int = 4, keep_end: int = 4) -> str:
    """掩码敏感值，保留首尾字符。

    Args:
        value: 要掩码的值
        keep_start: 保留开头字符数
        keep_end: 保留结尾字符数

    Returns:
        掩码后的值
    """
    if len(value) <= keep_start + keep_end:
        return "*" * len(value)
    return value[:keep_start] + "*" * (len(value) - keep_start - keep_end) + value[-keep_end:]


def mask_secrets(text: str) -> str:
    """对文本中的敏感信息进行脱敏处理。

    Args:
        text: 包含潜在密钥的文本

    Returns:
        脱敏后的文本
    """
    if not text:
        return text

    result = text

    for name, pattern in _SECRET_PATTERNS:
        if name == "API_KEY_ASSIGN":
            # 特殊处理：捕获组模式
            def _replace_key_assign(match: re.Match) -> str:
                prefix = match.group(1)
                secret = match.group(2)
                suffix = match.group(3)
                masked = _mask_value(secret)
                return f"{prefix}{masked}{suffix}"

            result = pattern.sub(_replace_key_assign, result)
        else:
            # 简单替换模式
            def _replace_secret(match: re.Match) -> str:
                full = match.group(0)
                if name == "BEARER_TOKEN":
                    prefix = match.group(1)
                    token = full[len(prefix):]
                    return prefix + _mask_value(token)
                return _mask_value(full)

            result = pattern.sub(_replace_secret, result)

    return result


class SecretsMask:
    """密钥脱敏器 — 可配置的脱敏工具。"""

    def __init__(self, extra_patterns: list[tuple[str, re.Pattern[str]]] | None = None) -> None:
        """初始化脱敏器。

        Args:
            extra_patterns: 额外的正则模式列表 [(名称, 模式), ...]
        """
        self.patterns = list(_SECRET_PATTERNS)
        if extra_patterns:
            self.patterns.extend(extra_patterns)

    def mask(self, text: str) -> str:
        """对文本进行脱敏。

        Args:
            text: 要脱敏的文本

        Returns:
            脱敏后的文本
        """
        if not text:
            return text

        result = text
        for name, pattern in self.patterns:
            if name == "API_KEY_ASSIGN":
                def _replace_key_assign(match: re.Match, _n: str = name) -> str:
                    prefix = match.group(1)
                    secret = match.group(2)
                    suffix = match.group(3)
                    masked = _mask_value(secret)
                    return f"{prefix}{masked}{suffix}"

                result = pattern.sub(_replace_key_assign, result)
            else:
                def _replace_secret(match: re.Match, _n: str = name) -> str:
                    full = match.group(0)
                    if _n == "BEARER_TOKEN":
                        prefix = match.group(1)
                        token = full[len(prefix):]
                        return prefix + _mask_value(token)
                    return _mask_value(full)

                result = pattern.sub(_replace_secret, result)

        return result
