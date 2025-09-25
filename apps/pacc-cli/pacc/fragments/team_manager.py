"""Team collaboration manager for Claude Code memory fragments.

This module provides team collaboration features for memory fragments,
including shared specifications and conflict resolution.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TeamMember:
    """Represents a team member in fragment collaboration."""

    name: str
    email: Optional[str] = None
    role: str = "member"  # 'owner', 'maintainer', 'member'
    joined_at: Optional[datetime] = None


@dataclass
class FragmentLock:
    """Represents a lock on a fragment for editing."""

    fragment_name: str
    locked_by: str
    locked_at: datetime
    reason: Optional[str] = None

    def is_expired(self, timeout_hours: int = 24) -> bool:
        """Check if lock has expired.

        Args:
            timeout_hours: Hours before lock expires

        Returns:
            True if lock is expired
        """
        elapsed = datetime.now() - self.locked_at
        return elapsed.total_seconds() > timeout_hours * 3600


@dataclass
class TeamConfig:
    """Team configuration for fragment collaboration."""

    team_name: str
    repository_url: Optional[str] = None
    members: List[TeamMember] = field(default_factory=list)
    fragment_locks: Dict[str, FragmentLock] = field(default_factory=dict)
    sync_strategy: str = "manual"  # 'manual', 'auto', 'on_commit'
    conflict_resolution: str = "interactive"  # 'interactive', 'local_first', 'remote_first'


class FragmentTeamManager:
    """Manages team collaboration for fragments."""

    TEAM_CONFIG_FILE = ".pacc/team_config.json"

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize team manager.

        Args:
            project_root: Project root directory
        """
        self.project_root = Path(project_root or Path.cwd()).resolve()
        self.config_file = self.project_root / self.TEAM_CONFIG_FILE
        self.team_config = self._load_team_config()

    def _load_team_config(self) -> Optional[TeamConfig]:
        """Load team configuration from file.

        Returns:
            Team configuration or None if not configured
        """
        if not self.config_file.exists():
            return None

        try:
            data = json.loads(self.config_file.read_text(encoding="utf-8"))

            # Parse members
            members = []
            for member_data in data.get("members", []):
                member = TeamMember(
                    name=member_data["name"],
                    email=member_data.get("email"),
                    role=member_data.get("role", "member"),
                    joined_at=datetime.fromisoformat(member_data["joined_at"])
                    if "joined_at" in member_data
                    else None,
                )
                members.append(member)

            # Parse locks
            locks = {}
            for lock_name, lock_data in data.get("fragment_locks", {}).items():
                lock = FragmentLock(
                    fragment_name=lock_name,
                    locked_by=lock_data["locked_by"],
                    locked_at=datetime.fromisoformat(lock_data["locked_at"]),
                    reason=lock_data.get("reason"),
                )
                locks[lock_name] = lock

            return TeamConfig(
                team_name=data["team_name"],
                repository_url=data.get("repository_url"),
                members=members,
                fragment_locks=locks,
                sync_strategy=data.get("sync_strategy", "manual"),
                conflict_resolution=data.get("conflict_resolution", "interactive"),
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to load team config: {e}")
            return None

    def _save_team_config(self) -> None:
        """Save team configuration to file."""
        if not self.team_config:
            return

        self.config_file.parent.mkdir(parents=True, exist_ok=True)

        # Convert to JSON-serializable format
        data = {
            "team_name": self.team_config.team_name,
            "repository_url": self.team_config.repository_url,
            "sync_strategy": self.team_config.sync_strategy,
            "conflict_resolution": self.team_config.conflict_resolution,
            "members": [
                {
                    "name": member.name,
                    "email": member.email,
                    "role": member.role,
                    "joined_at": member.joined_at.isoformat() if member.joined_at else None,
                }
                for member in self.team_config.members
            ],
            "fragment_locks": {
                lock_name: {
                    "locked_by": lock.locked_by,
                    "locked_at": lock.locked_at.isoformat(),
                    "reason": lock.reason,
                }
                for lock_name, lock in self.team_config.fragment_locks.items()
            },
        }

        self.config_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def initialize_team(
        self,
        team_name: str,
        repository_url: Optional[str] = None,
        sync_strategy: str = "manual",
        conflict_resolution: str = "interactive",
    ) -> TeamConfig:
        """Initialize team configuration.

        Args:
            team_name: Name of the team
            repository_url: Optional shared repository URL
            sync_strategy: Sync strategy to use
            conflict_resolution: Conflict resolution strategy

        Returns:
            Created team configuration
        """
        self.team_config = TeamConfig(
            team_name=team_name,
            repository_url=repository_url,
            sync_strategy=sync_strategy,
            conflict_resolution=conflict_resolution,
        )

        self._save_team_config()
        return self.team_config

    def add_team_member(self, name: str, email: Optional[str] = None, role: str = "member") -> bool:
        """Add a team member.

        Args:
            name: Member name
            email: Optional email
            role: Member role

        Returns:
            True if added successfully
        """
        if not self.team_config:
            logger.error("Team not initialized")
            return False

        # Check if member already exists
        if any(m.name == name for m in self.team_config.members):
            logger.warning(f"Member {name} already exists")
            return False

        member = TeamMember(name=name, email=email, role=role, joined_at=datetime.now())

        self.team_config.members.append(member)
        self._save_team_config()

        return True

    def remove_team_member(self, name: str) -> bool:
        """Remove a team member.

        Args:
            name: Member name to remove

        Returns:
            True if removed successfully
        """
        if not self.team_config:
            return False

        original_count = len(self.team_config.members)
        self.team_config.members = [m for m in self.team_config.members if m.name != name]

        if len(self.team_config.members) < original_count:
            self._save_team_config()
            return True

        return False

    def lock_fragment(
        self, fragment_name: str, locked_by: str, reason: Optional[str] = None
    ) -> bool:
        """Lock a fragment for exclusive editing.

        Args:
            fragment_name: Fragment to lock
            locked_by: Person locking the fragment
            reason: Optional reason for lock

        Returns:
            True if locked successfully
        """
        if not self.team_config:
            logger.error("Team not initialized")
            return False

        # Check if already locked
        if fragment_name in self.team_config.fragment_locks:
            existing_lock = self.team_config.fragment_locks[fragment_name]
            if not existing_lock.is_expired():
                logger.warning(
                    f"Fragment {fragment_name} already locked by {existing_lock.locked_by}"
                )
                return False

        lock = FragmentLock(
            fragment_name=fragment_name,
            locked_by=locked_by,
            locked_at=datetime.now(),
            reason=reason,
        )

        self.team_config.fragment_locks[fragment_name] = lock
        self._save_team_config()

        return True

    def unlock_fragment(self, fragment_name: str, unlocked_by: str) -> bool:
        """Unlock a fragment.

        Args:
            fragment_name: Fragment to unlock
            unlocked_by: Person unlocking (must match locker or be owner)

        Returns:
            True if unlocked successfully
        """
        if not self.team_config:
            return False

        if fragment_name not in self.team_config.fragment_locks:
            return False

        lock = self.team_config.fragment_locks[fragment_name]

        # Check permission to unlock
        unlocker_member = next((m for m in self.team_config.members if m.name == unlocked_by), None)
        can_unlock = (
            lock.locked_by == unlocked_by
            or lock.is_expired()
            or (unlocker_member and unlocker_member.role in ["owner", "maintainer"])
        )

        if not can_unlock:
            logger.warning(f"User {unlocked_by} cannot unlock fragment locked by {lock.locked_by}")
            return False

        del self.team_config.fragment_locks[fragment_name]
        self._save_team_config()

        return True

    def get_fragment_lock(self, fragment_name: str) -> Optional[FragmentLock]:
        """Get lock information for a fragment.

        Args:
            fragment_name: Fragment name

        Returns:
            Lock information or None if not locked
        """
        if not self.team_config:
            return None

        lock = self.team_config.fragment_locks.get(fragment_name)

        # Return None if lock is expired
        if lock and lock.is_expired():
            return None

        return lock

    def list_locked_fragments(self) -> List[FragmentLock]:
        """List all currently locked fragments.

        Returns:
            List of active locks
        """
        if not self.team_config:
            return []

        active_locks = []
        for lock in self.team_config.fragment_locks.values():
            if not lock.is_expired():
                active_locks.append(lock)

        return active_locks

    def cleanup_expired_locks(self) -> int:
        """Remove expired locks.

        Returns:
            Number of locks removed
        """
        if not self.team_config:
            return 0

        expired = []
        for fragment_name, lock in self.team_config.fragment_locks.items():
            if lock.is_expired():
                expired.append(fragment_name)

        for fragment_name in expired:
            del self.team_config.fragment_locks[fragment_name]

        if expired:
            self._save_team_config()

        return len(expired)
