"""路径安全 — 防止路径遍历和符号链接逃逸。"""

from __future__ import annotations

import os
import re
from pathlib import Path


class PathTraversalError(Exception):
    """路径遍历防护拦截异常。"""

    def __init__(self, reason: str, path: str = "") -> None:
        self.reason = reason
        self.path = path
        super().__init__(f"Path traversal blocked: {reason} (path={path})")


# 危险路径模式
_DANGEROUS_PATH_PATTERNS = [
    re.compile(r"\.\."),               # ..
    re.compile(r"~"),                   # 家目录展开
    re.compile(r"\$\{"),                # 变量展开
    re.compile(r"%[0-9a-fA-F]{2}"),    # URL 编码
]


def _sanitize_filename(filename: str) -> str:
    """清理文件名，移除危险字符。

    Args:
        filename: 原始文件名

    Returns:
        清理后的安全文件名
    """
    # 移除路径分隔符
    safe = filename.replace("/", "_").replace("\\", "_")
    # 只保留字母、数字、下划线（不允许点，防止 .. 路径）
    safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", safe)
    # 合并连续下划线
    safe = re.sub(r"_+", "_", safe)
    # 去除首尾下划线
    safe = safe.strip("_")
    # 防止过长
    if len(safe) > 255:
        safe = safe[:255]
    return safe or "unnamed"


def _is_symlink(path: Path) -> bool:
    """检查路径是否为符号链接。"""
    try:
        return path.is_symlink()
    except OSError:
        return False


def _follows_symlink_outside(path: Path, root: Path) -> bool:
    """检查路径中的任何组件是否为指向根目录外部的符号链接。"""
    try:
        resolved = path.resolve()
    except (OSError, ValueError):
        return True

    # 检查解析后的路径是否在根目录内
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return True

    return False


class PathSafety:
    """路径安全检查器 — 确保路径在允许的根目录内。"""

    def __init__(self, root_dirs: list[str | Path] | None = None) -> None:
        """初始化路径安全检查器。

        Args:
            root_dirs: 允许的根目录列表。如果为 None，则不检查根目录限制。
        """
        self.root_dirs: list[Path] = []
        if root_dirs:
            for d in root_dirs:
                self.root_dirs.append(Path(d).resolve())

    def validate_path(self, path: str | Path) -> Path:
        """验证路径是否安全。

        Args:
            path: 要验证的路径

        Returns:
            解析后的安全路径

        Raises:
            PathTraversalError: 如果路径不安全
        """
        path = Path(path)

        # 1. 检查危险模式
        path_str = str(path)
        for pattern in _DANGEROUS_PATH_PATTERNS:
            if pattern.search(path_str):
                raise PathTraversalError(
                    reason=f"路径包含危险模式: {pattern.pattern}",
                    path=path_str,
                )

        # 2. 检查绝对路径（如果不在允许的根目录内）
        if path.is_absolute() and not self.root_dirs:
            raise PathTraversalError(
                reason="不允许使用绝对路径",
                path=path_str,
            )

        # 3. 解析路径并检查是否在根目录内
        if self.root_dirs:
            # 对于相对路径，需要基于每个根目录解析
            in_root = False
            resolved_target = None
            matched_root = None

            for root in self.root_dirs:
                try:
                    # 将相对路径与根目录拼接后解析
                    if path.is_absolute():
                        resolved_target = path.resolve()
                    else:
                        resolved_target = (root / path).resolve()
                    resolved_target.relative_to(root.resolve())
                    in_root = True
                    matched_root = root
                    break
                except (ValueError, OSError):
                    continue

            if not in_root:
                raise PathTraversalError(
                    reason=f"路径在允许的根目录之外",
                    path=path_str,
                )

            # 4. 检查符号链接逃逸（对原始路径的每个组件检查）
            if matched_root:
                # 检查路径是否存在，如果存在则检查符号链接
                full_check_path = matched_root / path
                if full_check_path.exists() and _is_symlink(full_check_path):
                    raise PathTraversalError(
                        reason="路径包含指向根目录外部的符号链接",
                        path=path_str,
                    )

        return path

    def sanitize_filename(self, filename: str) -> str:
        """清理文件名。

        Args:
            filename: 原始文件名

        Returns:
            清理后的安全文件名
        """
        return _sanitize_filename(filename)

    def is_safe_relative(self, relative_path: str, base_dir: str | Path) -> bool:
        """检查相对路径是否安全（不逃逸基础目录）。

        Args:
            relative_path: 相对路径
            base_dir: 基础目录

        Returns:
            True 如果安全
        """
        try:
            base = Path(base_dir).resolve()
            target = (base / relative_path).resolve()
            target.relative_to(base)
            return True
        except (ValueError, OSError):
            return False


def validate_asset_path(
    relative_path: str,
    asset_dir: str | Path,
) -> Path:
    """便捷函数：验证资产路径安全性。

    Args:
        relative_path: 资产相对路径
        asset_dir: 资产根目录

    Returns:
        验证后的安全路径

    Raises:
        PathTraversalError: 如果路径不安全
    """
    safety = PathSafety(root_dirs=[asset_dir])
    return safety.validate_path(Path(asset_dir) / relative_path)
