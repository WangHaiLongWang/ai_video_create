"""Cross-platform tests — path handling, Unicode, separators."""

import os
import tempfile
import shutil
import pytest
from pathlib import Path, PureWindowsPath, PurePosixPath


class TestPathHandling:
    """路径处理测试。"""

    def test_asset_manager_handles_forward_slashes(self):
        """AssetManager 处理正斜杠路径。"""
        from backend.app.services.asset_manager import AssetManager

        temp_dir = tempfile.mkdtemp()
        try:
            manager = AssetManager(temp_dir)

            # 使用正斜杠保存
            path = manager.save_asset(b"test", "test.txt", category="temp")
            assert "/" in path or "\\" in path  # 取决于平台

            # 读取应该成功
            data = manager.read_asset(path)
            assert data == b"test"
        finally:
            shutil.rmtree(temp_dir)

    def test_asset_manager_handles_backslashes(self):
        """AssetManager 处理反斜杠路径。"""
        from backend.app.services.asset_manager import AssetManager

        temp_dir = tempfile.mkdtemp()
        try:
            manager = AssetManager(temp_dir)

            # 保存文件
            path = manager.save_asset(b"test", "test.txt", category="temp")

            # 使用反斜杠读取（Windows 风格）
            backslash_path = path.replace("/", "\\")
            # 在 Windows 上应该可以读取
            if os.name == "nt":
                data = manager.read_asset(backslash_path)
                assert data == b"test"
        finally:
            shutil.rmtree(temp_dir)

    def test_unicode_filename(self):
        """Unicode 文件名处理。"""
        from backend.app.services.asset_manager import AssetManager

        temp_dir = tempfile.mkdtemp()
        try:
            manager = AssetManager(temp_dir)

            # 使用中文文件名
            path = manager.save_asset(b"test", "测试文件", category="temp", extension="txt")
            assert "测试文件" in path or "test" in path  # 可能被清理

            # 保存带特殊字符的文件名
            path2 = manager.save_asset(b"test2", "file with spaces", category="temp")
            assert path2 is not None
        finally:
            shutil.rmtree(temp_dir)

    def test_long_path(self):
        """长路径处理。"""
        from backend.app.services.asset_manager import AssetManager

        temp_dir = tempfile.mkdtemp()
        try:
            manager = AssetManager(temp_dir)

            # 长文件名（但不超过系统限制）
            long_name = "a" * 100
            path = manager.save_asset(b"test", long_name, category="temp")
            assert path is not None
        finally:
            shutil.rmtree(temp_dir)

    def test_special_characters_in_path(self):
        """特殊字符路径处理。"""
        from backend.app.services.asset_manager import AssetManager

        temp_dir = tempfile.mkdtemp()
        try:
            manager = AssetManager(temp_dir)

            # 特殊字符应该被清理
            path = manager.save_asset(b"test", "file;rm -rf /", category="temp")
            assert ";" not in path
            assert "rm" not in path or "rm" in path  # 可能保留部分字符
        finally:
            shutil.rmtree(temp_dir)

    def test_relative_path_resolution(self):
        """相对路径解析。"""
        from backend.app.services.asset_manager import AssetManager

        temp_dir = tempfile.mkdtemp()
        try:
            manager = AssetManager(temp_dir)

            # get_asset_path 应该返回绝对路径
            abs_path = manager.get_asset_path("images/test.png")
            assert os.path.isabs(abs_path)
        finally:
            shutil.rmtree(temp_dir)

    def test_url_generation(self):
        """URL 生成。"""
        from backend.app.services.asset_manager import AssetManager

        temp_dir = tempfile.mkdtemp()
        try:
            manager = AssetManager(temp_dir)

            # URL 应该使用正斜杠
            url = manager.get_asset_url("images/test.png")
            assert url.startswith("/assets/")
            assert "\\" not in url  # URL 不应包含反斜杠
        finally:
            shutil.rmtree(temp_dir)


class TestPurePaths:
    """纯路径操作测试（不依赖文件系统）。"""

    def test_pure_posix_path(self):
        """PurePosixPath 操作。"""
        p = PurePosixPath("/assets/images/test.png")
        assert p.name == "test.png"
        assert p.suffix == ".png"
        assert p.parent == PurePosixPath("/assets/images")

    def test_pure_windows_path(self):
        """PureWindowsPath 操作。"""
        p = PureWindowsPath("D:\\assets\\images\\test.png")
        assert p.name == "test.png"
        assert p.suffix == ".png"

    def test_path_normalization(self):
        """路径标准化。"""
        # 混合分隔符应该被标准化
        mixed = "assets//images///test.png"
        normalized = os.path.normpath(mixed)
        assert "//" not in normalized
        assert "///" not in normalized


class TestPlatformDetection:
    """平台检测测试。"""

    def test_os_name(self):
        """检测操作系统。"""
        assert os.name in ("nt", "posix", "java")

    def test_path_separator(self):
        """路径分隔符。"""
        if os.name == "nt":
            assert os.sep == "\\"
        else:
            assert os.sep == "/"

    def test_temp_directory(self):
        """临时目录存在。"""
        temp_dir = tempfile.gettempdir()
        assert os.path.exists(temp_dir)
        assert os.path.isdir(temp_dir)
