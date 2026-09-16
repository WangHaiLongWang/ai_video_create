"""重试/退避机制 — 错误分类、指数退避、重试决策。"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.handlers.contracts import NodeError


class ErrorCategory(Enum):
    """错误分类枚举。"""
    TRANSIENT = "transient"      # 网络超时、429 限流 - 可重试
    PERMANENT = "permanent"      # 参数错误、认证失败 - 不可重试
    RESOURCE = "resource"        # 磁盘满、内存不足 - 可重试但需等待
    EXTERNAL = "external"        # 外部服务错误 - 可重试
    UNKNOWN = "unknown"          # 未知错误 - 不可重试


# 错误码 -> 错误分类映射
_ERROR_CODE_MAP: dict[str, ErrorCategory] = {
    # 瞬态错误 — 可重试
    "TIMEOUT": ErrorCategory.TRANSIENT,
    "NETWORK_ERROR": ErrorCategory.TRANSIENT,
    "RATE_LIMITED": ErrorCategory.TRANSIENT,
    "TOO_MANY_REQUESTS": ErrorCategory.TRANSIENT,
    "SERVICE_UNAVAILABLE": ErrorCategory.TRANSIENT,
    "CONNECTION_RESET": ErrorCategory.TRANSIENT,
    "DNS_RESOLUTION_FAILED": ErrorCategory.TRANSIENT,
    "SOCKET_TIMEOUT": ErrorCategory.TRANSIENT,

    # 永久错误 — 不可重试
    "INVALID_PARAMETER": ErrorCategory.PERMANENT,
    "AUTH_FAILED": ErrorCategory.PERMANENT,
    "UNAUTHORIZED": ErrorCategory.PERMANENT,
    "FORBIDDEN": ErrorCategory.PERMANENT,
    "NOT_FOUND": ErrorCategory.PERMANENT,
    "INVALID_PROMPT": ErrorCategory.PERMANENT,
    "CONTENT_POLICY": ErrorCategory.PERMANENT,
    "INVALID_MODEL": ErrorCategory.PERMANENT,

    # 资源错误 — 可重试但需等待
    "DISK_FULL": ErrorCategory.RESOURCE,
    "OUT_OF_MEMORY": ErrorCategory.RESOURCE,
    "QUOTA_EXCEEDED": ErrorCategory.RESOURCE,
    "STORAGE_LIMIT": ErrorCategory.RESOURCE,
    "GPU_BUSY": ErrorCategory.RESOURCE,

    # 外部服务错误 — 可重试
    "EXTERNAL_API_ERROR": ErrorCategory.EXTERNAL,
    "EXTERNAL_TIMEOUT": ErrorCategory.EXTERNAL,
    "EXTERNAL_RATE_LIMITED": ErrorCategory.EXTERNAL,
    "EXTERNAL_SERVICE_DOWN": ErrorCategory.EXTERNAL,
    "PROVIDER_ERROR": ErrorCategory.EXTERNAL,
    "TASK_FAILED": ErrorCategory.EXTERNAL,
}

# 429 状态码对应的已知瞬态错误码
_RATE_LIMIT_CODES: set[str] = {"RATE_LIMITED", "TOO_MANY_REQUESTS", "EXTERNAL_RATE_LIMITED"}


@dataclass
class RetryPolicy:
    """重试策略配置。"""
    max_attempts: int = 3
    base_delay: float = 1.0        # 基础延迟（秒）
    max_delay: float = 60.0        # 最大延迟（秒）
    exponential_base: float = 2.0  # 指数底数
    jitter: bool = True            # 是否添加随机抖动
    retryable_categories: set[ErrorCategory] = field(
        default_factory=lambda: {
            ErrorCategory.TRANSIENT,
            ErrorCategory.RESOURCE,
            ErrorCategory.EXTERNAL,
        }
    )


def classify_error(error: NodeError) -> ErrorCategory:
    """根据 NodeError 的 code 字段分类错误。

    规则：
    1. 如果 NodeError.retryable 为 True 且 code 未映射，返回 TRANSIENT
    2. 根据 code 字段查表分类
    3. code 未匹配时返回 UNKNOWN

    Args:
        error: 结构化错误信息

    Returns:
        错误分类枚举值
    """
    code = error.code.upper() if error.code else ""

    # 精确匹配
    if code in _ERROR_CODE_MAP:
        return _ERROR_CODE_MAP[code]

    # 前缀匹配：如 "TIMEOUT_500" 匹配 "TIMEOUT"
    for prefix, category in _ERROR_CODE_MAP.items():
        if code.startswith(prefix):
            return category

    # 如果 handler 标记了 retryable 但没有已知 code，默认为 TRANSIENT
    if error.retryable:
        return ErrorCategory.TRANSIENT

    return ErrorCategory.UNKNOWN


def should_retry(error: NodeError, attempt: int, policy: RetryPolicy | None = None) -> bool:
    """判断是否应该重试。

    规则：
    1. attempt >= max_attempts 时不重试
    2. 错误分类不在 retryable_categories 中时不重试
    3. 如果 error.retryable 为 True，即使分类为 UNKNOWN 也重试

    Args:
        error: 结构化错误信息
        attempt: 当前尝试次数（从 1 开始）
        policy: 重试策略，为 None 时使用默认策略

    Returns:
        True 表示应该重试
    """
    if policy is None:
        policy = RetryPolicy()

    # 超过最大尝试次数
    if attempt >= policy.max_attempts:
        return False

    category = classify_error(error)

    # 分类在可重试集合中
    if category in policy.retryable_categories:
        return True

    # handler 标记为 retryable，但分类为 UNKNOWN — 也允许重试
    if error.retryable and category == ErrorCategory.UNKNOWN:
        return True

    return False


def calculate_delay(attempt: int, policy: RetryPolicy | None = None) -> float:
    """计算指数退避延迟时间。

    公式：min(base_delay * exponential_base^(attempt-1), max_delay)
    可选添加 jitter: 实际延迟 * random(0.5, 1.0)

    Args:
        attempt: 当前尝试次数（从 1 开始）
        policy: 重试策略

    Returns:
        延迟秒数
    """
    if policy is None:
        policy = RetryPolicy()

    # 指数退避: base * base^(attempt-1)
    delay = policy.base_delay * (policy.exponential_base ** (attempt - 1))

    # 限制最大延迟
    delay = min(delay, policy.max_delay)

    # 添加随机抖动（±50%），避免惊群效应
    if policy.jitter:
        delay = delay * random.uniform(0.5, 1.0)

    return round(delay, 3)


def get_retry_after(error: NodeError) -> float | None:
    """从 NodeError 中提取 Retry-After 延迟（如 429 响应）。

    检查 error.details 中的 retry_after / Retry-After 字段。
    如果是数字，直接返回秒数；如果是日期字符串，返回相对秒数。

    Args:
        error: 结构化错误信息

    Returns:
        建议等待秒数，无信息时返回 None
    """
    details = error.details or {}

    # 尝试多种字段名
    for key in ("retry_after", "Retry-After", "retry-after", "retryAfter"):
        value = details.get(key)
        if value is not None:
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                try:
                    return float(value)
                except ValueError:
                    pass

    return None


def get_default_policy() -> RetryPolicy:
    """获取默认重试策略。"""
    return RetryPolicy()
