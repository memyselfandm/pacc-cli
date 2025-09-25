"""PACC memory fragments management."""

from .claude_md_manager import CLAUDEmdManager
from .installation_manager import FragmentInstallationManager, InstallationResult
from .repository_manager import (
    FragmentCloneSpec,
    FragmentDiscoveryResult,
    FragmentGitError,
    FragmentRepo,
    FragmentRepositoryError,
    FragmentRepositoryManager,
    FragmentUpdateResult,
)
from .storage_manager import FragmentStorageManager
from .sync_manager import FragmentSyncManager, FragmentSyncSpec, SyncResult
from .team_manager import FragmentLock, FragmentTeamManager, TeamConfig, TeamMember
from .update_manager import FragmentUpdateManager, UpdateResult
from .version_tracker import FragmentVersion, FragmentVersionTracker

__all__ = [
    "CLAUDEmdManager",
    "FragmentStorageManager",
    "FragmentInstallationManager",
    "InstallationResult",
    "FragmentUpdateManager",
    "UpdateResult",
    "FragmentVersionTracker",
    "FragmentVersion",
    "FragmentSyncManager",
    "SyncResult",
    "FragmentSyncSpec",
    "FragmentTeamManager",
    "TeamConfig",
    "TeamMember",
    "FragmentLock",
    "FragmentRepositoryManager",
    "FragmentRepo",
    "FragmentCloneSpec",
    "FragmentUpdateResult",
    "FragmentDiscoveryResult",
    "FragmentGitError",
    "FragmentRepositoryError",
]
