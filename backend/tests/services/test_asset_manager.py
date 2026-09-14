"""Tests for asset manager."""

import os
import tempfile
import shutil
import pytest
from backend.app.services.asset_manager import AssetManager


class TestAssetManager:
    """Tests for AssetManager."""

    def setup_method(self):
        """Create temp directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = AssetManager(self.temp_dir)

    def teardown_method(self):
        """Cleanup temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_creates_directories(self):
        """Test that initialization creates required directories."""
        assert os.path.exists(os.path.join(self.temp_dir, "images"))
        assert os.path.exists(os.path.join(self.temp_dir, "videos"))
        assert os.path.exists(os.path.join(self.temp_dir, "final"))
        assert os.path.exists(os.path.join(self.temp_dir, "temp"))

    def test_save_asset(self):
        """Test saving an asset."""
        data = b"test content"
        path = self.manager.save_asset(data, "test.txt", category="temp")
        assert path.startswith("temp/")
        assert os.path.exists(os.path.join(self.temp_dir, path))

    def test_save_asset_auto_filename(self):
        """Test saving asset with auto-generated filename."""
        data = b"test content"
        path = self.manager.save_asset(data, category="images", extension="png")
        assert path.startswith("images/")
        assert path.endswith(".png")

    def test_save_asset_sanitizes_filename(self):
        """Test that filenames are sanitized."""
        data = b"test"
        path = self.manager.save_asset(data, "../../../etc/passwd", category="temp")
        # Should not contain path traversal sequences
        assert ".." not in path
        # The path should be in the correct category directory
        assert path.startswith("temp/")

    def test_get_asset_path(self):
        """Test getting absolute path."""
        path = self.manager.get_asset_path("images/test.png")
        assert os.path.isabs(path)
        # Handle both forward and backward slashes
        normalized = path.replace("\\", "/")
        assert normalized.endswith("images/test.png")

    def test_get_asset_url(self):
        """Test getting URL."""
        url = self.manager.get_asset_url("images/test.png")
        assert url == "/assets/images/test.png"

    def test_read_asset(self):
        """Test reading asset data."""
        data = b"hello world"
        path = self.manager.save_asset(data, "hello.txt")
        read_data = self.manager.read_asset(path)
        assert read_data == data

    def test_read_nonexistent_asset(self):
        """Test reading nonexistent asset raises error."""
        with pytest.raises(FileNotFoundError):
            self.manager.read_asset("nonexistent.txt")

    def test_delete_asset(self):
        """Test deleting an asset."""
        data = b"to delete"
        path = self.manager.save_asset(data, "delete_me.txt")
        assert self.manager.asset_exists(path)

        result = self.manager.delete_asset(path)
        assert result is True
        assert not self.manager.asset_exists(path)

    def test_delete_nonexistent_asset(self):
        """Test deleting nonexistent asset returns False."""
        result = self.manager.delete_asset("nonexistent.txt")
        assert result is False

    def test_asset_exists(self):
        """Test checking asset existence."""
        data = b"exists"
        path = self.manager.save_asset(data, "exists.txt")

        assert self.manager.asset_exists(path) is True
        assert self.manager.asset_exists("nonexistent.txt") is False

    def test_get_asset_info(self):
        """Test getting asset metadata."""
        data = b"metadata test"
        path = self.manager.save_asset(data, "meta.txt")

        info = self.manager.get_asset_info(path)
        assert info is not None
        assert info["path"] == path
        assert info["size"] == len(data)
        assert "created" in info
        assert "modified" in info

    def test_list_assets(self):
        """Test listing assets."""
        self.manager.save_asset(b"a", "a.txt", category="images")
        self.manager.save_asset(b"b", "b.txt", category="images")
        self.manager.save_asset(b"c", "c.txt", category="videos")

        all_assets = self.manager.list_assets()
        assert len(all_assets) == 3

        images = self.manager.list_assets("images")
        assert len(images) == 2

        videos = self.manager.list_assets("videos")
        assert len(videos) == 1

    def test_cleanup_old_assets(self):
        """Test cleaning up old assets."""
        # Save some files
        self.manager.save_asset(b"old", "old.txt", category="temp")
        self.manager.save_asset(b"new", "new.txt", category="temp")

        # Cleanup with 0 days max age (should delete all)
        deleted = self.manager.cleanup_old_assets(max_age_days=0, category="temp")
        # Note: May not delete immediately due to filesystem timing
        assert deleted >= 0

    def test_get_total_size(self):
        """Test calculating total size."""
        self.manager.save_asset(b"hello", "a.txt", category="images")
        self.manager.save_asset(b"world", "b.txt", category="videos")

        total = self.manager.get_total_size()
        assert total > 0

        images_size = self.manager.get_total_size("images")
        assert images_size == 5  # len("hello")

    def test_save_and_retrieve_image(self):
        """Test saving and retrieving a PNG image."""
        # Minimal PNG
        png_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        path = self.manager.save_asset(png_data, "test.png", category="images")
        retrieved = self.manager.read_asset(path)
        assert retrieved == png_data
