"""Version tracking for Claude Code memory fragments.

This module provides version tracking capabilities for fragments,
supporting Git commit tracking and content hashing for version comparison.
"""

import hashlib
import json
import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class FragmentVersion:
    """Represents version information for a fragment."""

    version_id: str  # Git SHA or content hash
    source_type: str  # 'git', 'url', 'local'
    timestamp: datetime
    source_url: Optional[str] = None
    commit_message: Optional[str] = None
    author: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version_id": self.version_id,
            "source_type": self.source_type,
            "timestamp": self.timestamp.isoformat(),
            "source_url": self.source_url,
            "commit_message": self.commit_message,
            "author": self.author,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FragmentVersion":
        """Create from dictionary."""
        return cls(
            version_id=data["version_id"],
            source_type=data["source_type"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source_url=data.get("source_url"),
            commit_message=data.get("commit_message"),
            author=data.get("author"),
        )


class FragmentVersionTracker:
    """Tracks versions of installed fragments."""

    VERSION_FILE = ".pacc/fragment_versions.json"

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize version tracker.

        Args:
            project_root: Project root directory
        """
        self.project_root = Path(project_root or Path.cwd()).resolve()
        self.version_file = self.project_root / self.VERSION_FILE
        self.versions = self._load_versions()

    def _load_versions(self) -> Dict[str, FragmentVersion]:
        """Load version information from storage.

        Returns:
            Dictionary of fragment names to version information
        """
        if not self.version_file.exists():
            return {}

        try:
            data = json.loads(self.version_file.read_text(encoding="utf-8"))
            return {
                name: FragmentVersion.from_dict(version_data) for name, version_data in data.items()
            }
        except (json.JSONDecodeError, UnicodeDecodeError, KeyError) as e:
            logger.warning(f"Could not load version file: {e}")
            return {}

    def _save_versions(self) -> None:
        """Save version information to storage."""
        self.version_file.parent.mkdir(parents=True, exist_ok=True)

        data = {name: version.to_dict() for name, version in self.versions.items()}

        self.version_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def track_installation(
        self, fragment_name: str, source_url: str, source_type: str, fragment_path: Path
    ) -> FragmentVersion:
        """Track a new fragment installation.

        Args:
            fragment_name: Name of the fragment
            source_url: Source URL or path
            source_type: Type of source ('git', 'url', 'local')
            fragment_path: Path to installed fragment file

        Returns:
            Version information for the fragment
        """
        version = None

        if source_type == "git":
            version = self._get_git_version(source_url, fragment_path)
        else:
            version = self._get_content_version(fragment_path, source_type, source_url)

        self.versions[fragment_name] = version
        self._save_versions()

        return version

    def _get_git_version(self, source_url: str, fragment_path: Path) -> FragmentVersion:
        """Get version information from Git source.

        Args:
            source_url: Git repository URL
            fragment_path: Path to fragment file

        Returns:
            Fragment version information
        """
        version_id = None
        commit_message = None
        author = None

        # Try to get Git information if we're in a Git repo
        try:
            # Get current commit SHA
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=fragment_path.parent,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                version_id = result.stdout.strip()[:8]  # Short SHA

                # Get commit message
                result = subprocess.run(
                    ["git", "log", "-1", "--pretty=%s"],
                    cwd=fragment_path.parent,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if result.returncode == 0:
                    commit_message = result.stdout.strip()

                # Get author
                result = subprocess.run(
                    ["git", "log", "-1", "--pretty=%an"],
                    cwd=fragment_path.parent,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if result.returncode == 0:
                    author = result.stdout.strip()

        except Exception as e:
            logger.warning(f"Could not get Git version info: {e}")

        # Fall back to content hash if Git info not available
        if not version_id:
            version_id = self._calculate_content_hash(fragment_path)

        return FragmentVersion(
            version_id=version_id,
            source_type="git",
            timestamp=datetime.now(),
            source_url=source_url,
            commit_message=commit_message,
            author=author,
        )

    def _get_content_version(
        self, fragment_path: Path, source_type: str, source_url: Optional[str]
    ) -> FragmentVersion:
        """Get version information based on content hash.

        Args:
            fragment_path: Path to fragment file
            source_type: Type of source
            source_url: Optional source URL

        Returns:
            Fragment version information
        """
        version_id = self._calculate_content_hash(fragment_path)

        return FragmentVersion(
            version_id=version_id,
            source_type=source_type,
            timestamp=datetime.now(),
            source_url=source_url,
        )

    def _calculate_content_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file content.

        Args:
            file_path: Path to file

        Returns:
            Hex digest of content hash (first 8 characters)
        """
        try:
            content = file_path.read_bytes()
            hash_obj = hashlib.sha256(content)
            return hash_obj.hexdigest()[:8]
        except Exception as e:
            logger.error(f"Could not calculate content hash: {e}")
            return "unknown"

    def get_version(self, fragment_name: str) -> Optional[FragmentVersion]:
        """Get version information for a fragment.

        Args:
            fragment_name: Name of the fragment

        Returns:
            Version information or None if not tracked
        """
        return self.versions.get(fragment_name)

    def has_update(self, fragment_name: str, latest_version: str) -> bool:
        """Check if a fragment has an available update.

        Args:
            fragment_name: Name of the fragment
            latest_version: Latest available version ID

        Returns:
            True if update is available
        """
        current = self.get_version(fragment_name)
        if not current:
            return False

        return current.version_id != latest_version

    def update_version(self, fragment_name: str, new_version: FragmentVersion) -> None:
        """Update version information for a fragment.

        Args:
            fragment_name: Name of the fragment
            new_version: New version information
        """
        self.versions[fragment_name] = new_version
        self._save_versions()

    def remove_version(self, fragment_name: str) -> None:
        """Remove version tracking for a fragment.

        Args:
            fragment_name: Name of the fragment
        """
        if fragment_name in self.versions:
            del self.versions[fragment_name]
            self._save_versions()
