"""Version management for deployments."""

from datetime import datetime
from pathlib import Path
from typing import Optional, Dict
import json


class VersionManager:
    """Manage scoring model versions."""

    def __init__(self, version_dir: str = "models/"):
        """
        Initialize version manager.

        Args:
            version_dir: Directory to store version info
        """
        self.version_dir = Path(version_dir)
        self.version_dir.mkdir(parents=True, exist_ok=True)
        self.current_version = self._load_current_version()

    def create_version(
        self,
        version_tag: str,
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Create a new version.

        Args:
            version_tag: Version tag (e.g., v1.0.0-prod-20260728)
            metadata: Optional metadata dict

        Returns:
            Version ID
        """
        version_data = {
            'version': version_tag,
            'created_at': datetime.utcnow().isoformat(),
            'status': 'active',
            'metadata': metadata or {},
        }

        version_file = self.version_dir / f"{version_tag}.json"
        with open(version_file, 'w') as f:
            json.dump(version_data, f, indent=2)

        self.current_version = version_tag
        self._save_current_version()

        return version_tag

    def get_current_version(self) -> str:
        """Get currently active version."""
        return self.current_version

    def rollback_version(self, target_version: str) -> bool:
        """
        Rollback to a previous version.

        Args:
            target_version: Version to rollback to

        Returns:
            True if rollback successful
        """
        version_file = self.version_dir / f"{target_version}.json"
        if not version_file.exists():
            return False

        self.current_version = target_version
        self._save_current_version()

        return True

    def list_versions(self):
        """List all versions."""
        versions = []
        for f in self.version_dir.glob("*.json"):
            with open(f, 'r') as fp:
                data = json.load(fp)
            versions.append(data)

        return sorted(versions, key=lambda x: x['created_at'], reverse=True)

    def _load_current_version(self) -> str:
        """Load current version from file."""
        current_file = self.version_dir / "CURRENT.txt"
        if current_file.exists():
            return current_file.read_text().strip()
        return "1.0.0"

    def _save_current_version(self):
        """Save current version to file."""
        current_file = self.version_dir / "CURRENT.txt"
        current_file.write_text(self.current_version)
