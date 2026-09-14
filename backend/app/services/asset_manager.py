"""Asset manager — file storage, retrieval, and cleanup."""

from __future__ import annotations

import os
import shutil
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class AssetManager:
    """Manages file assets (images, videos) for the application.

    Assets are stored in a directory structure:
        {asset_dir}/{category}/{filename}.{ext}
    """

    def __init__(self, asset_dir: str = "data/assets"):
        """Initialize asset manager.

        Args:
            asset_dir: Base directory for storing assets
        """
        self.asset_dir = Path(asset_dir)
        self.asset_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (self.asset_dir / "images").mkdir(exist_ok=True)
        (self.asset_dir / "videos").mkdir(exist_ok=True)
        (self.asset_dir / "final").mkdir(exist_ok=True)
        (self.asset_dir / "temp").mkdir(exist_ok=True)

    def save_asset(
        self,
        data: bytes,
        filename: str | None = None,
        category: str = "temp",
        extension: str = "bin",
    ) -> str:
        """Save asset data to file.

        Args:
            data: File content as bytes
            filename: Optional filename (without extension). Generated if not provided.
            category: Asset category (images, videos, final, temp)
            extension: File extension (without dot)

        Returns:
            Relative path to the saved file
        """
        if filename is None:
            filename = f"{uuid.uuid4().hex[:12]}"

        # Sanitize filename
        safe_filename = "".join(c for c in filename if c.isalnum() or c in "-_").strip()
        if not safe_filename:
            safe_filename = uuid.uuid4().hex[:12]

        # Ensure category directory exists
        category_dir = self.asset_dir / category
        category_dir.mkdir(exist_ok=True)

        # Build full path
        ext = extension.lstrip(".")
        full_path = category_dir / f"{safe_filename}.{ext}"

        # Write file
        full_path.write_bytes(data)

        # Return relative path
        relative_path = f"{category}/{safe_filename}.{ext}"
        return relative_path

    def get_asset_path(self, relative_path: str) -> str:
        """Get absolute path for an asset.

        Args:
            relative_path: Relative path from asset_dir

        Returns:
            Absolute path to the asset file
        """
        return str(self.asset_dir / relative_path)

    def get_asset_url(self, relative_path: str) -> str:
        """Get URL for serving an asset.

        Args:
            relative_path: Relative path from asset_dir

        Returns:
            URL path for the asset (e.g., /assets/images/xxx.png)
        """
        # Normalize path separators
        normalized = relative_path.replace("\\", "/")
        return f"/assets/{normalized}"

    def read_asset(self, relative_path: str) -> bytes:
        """Read asset data.

        Args:
            relative_path: Relative path from asset_dir

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If asset doesn't exist
        """
        full_path = self.asset_dir / relative_path
        if not full_path.exists():
            raise FileNotFoundError(f"Asset not found: {relative_path}")
        return full_path.read_bytes()

    def delete_asset(self, relative_path: str) -> bool:
        """Delete an asset.

        Args:
            relative_path: Relative path from asset_dir

        Returns:
            True if deleted, False if not found
        """
        full_path = self.asset_dir / relative_path
        if full_path.exists():
            full_path.unlink()
            return True
        return False

    def asset_exists(self, relative_path: str) -> bool:
        """Check if an asset exists.

        Args:
            relative_path: Relative path from asset_dir

        Returns:
            True if exists
        """
        return (self.asset_dir / relative_path).exists()

    def get_asset_info(self, relative_path: str) -> dict[str, Any] | None:
        """Get metadata for an asset.

        Args:
            relative_path: Relative path from asset_dir

        Returns:
            Dictionary with file info, or None if not found
        """
        full_path = self.asset_dir / relative_path
        if not full_path.exists():
            return None

        stat = full_path.stat()
        return {
            "path": relative_path,
            "url": self.get_asset_url(relative_path),
            "size": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "extension": full_path.suffix,
        }

    def list_assets(self, category: str = "") -> list[dict[str, Any]]:
        """List all assets, optionally filtered by category.

        Args:
            category: Optional category to filter by (images, videos, final, temp)

        Returns:
            List of asset info dictionaries
        """
        assets = []

        if category:
            # List specific category
            category_dir = self.asset_dir / category
            if category_dir.exists():
                for file_path in category_dir.iterdir():
                    if file_path.is_file():
                        rel_path = f"{category}/{file_path.name}"
                        info = self.get_asset_info(rel_path)
                        if info:
                            assets.append(info)
        else:
            # List all categories
            for cat_dir in self.asset_dir.iterdir():
                if cat_dir.is_dir():
                    for file_path in cat_dir.iterdir():
                        if file_path.is_file():
                            rel_path = f"{cat_dir.name}/{file_path.name}"
                            info = self.get_asset_info(rel_path)
                            if info:
                                assets.append(info)

        return assets

    def cleanup_old_assets(self, max_age_days: int = 7, category: str = "temp") -> int:
        """Delete assets older than max_age_days.

        Args:
            max_age_days: Maximum age in days
            category: Category to clean (default: temp)

        Returns:
            Number of deleted files
        """
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        deleted_count = 0

        category_dir = self.asset_dir / category
        if not category_dir.exists():
            return 0

        for file_path in category_dir.iterdir():
            if file_path.is_file():
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    deleted_count += 1

        return deleted_count

    def get_total_size(self, category: str = "") -> int:
        """Get total size of all assets in bytes.

        Args:
            category: Optional category to filter by

        Returns:
            Total size in bytes
        """
        total_size = 0

        if category:
            category_dir = self.asset_dir / category
            if category_dir.exists():
                for file_path in category_dir.iterdir():
                    if file_path.is_file():
                        total_size += file_path.stat().st_size
        else:
            for cat_dir in self.asset_dir.iterdir():
                if cat_dir.is_dir():
                    for file_path in cat_dir.iterdir():
                        if file_path.is_file():
                            total_size += file_path.stat().st_size

        return total_size


# Global instance
_asset_manager: AssetManager | None = None


def get_asset_manager() -> AssetManager:
    """Get or create global asset manager instance."""
    global _asset_manager
    if _asset_manager is None:
        from backend.app.config import get_settings
        settings = get_settings()
        _asset_manager = AssetManager(settings.ASSET_DIR)
    return _asset_manager


def reset_asset_manager() -> None:
    """Reset asset manager (for testing)."""
    global _asset_manager
    _asset_manager = None
