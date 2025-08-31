"""PACC memory fragments management."""

from .claude_md_manager import CLAUDEmdManager
from .storage_manager import FragmentStorageManager
from .installation_manager import FragmentInstallationManager, InstallationResult
from .update_manager import FragmentUpdateManager, UpdateResult
from .version_tracker import FragmentVersionTracker, FragmentVersion
from .sync_manager import FragmentSyncManager, SyncResult, FragmentSyncSpec
from .team_manager import FragmentTeamManager, TeamConfig, TeamMember, FragmentLock
from .repository_manager import (
    FragmentRepositoryManager,
    FragmentRepo,
    FragmentCloneSpec,
    FragmentUpdateResult,
    FragmentDiscoveryResult,
    FragmentGitError,
    FragmentRepositoryError
)

__all__ = [
    'CLAUDEmdManager',
    'FragmentStorageManager', 
    'FragmentInstallationManager',
    'InstallationResult',
    'FragmentUpdateManager',
    'UpdateResult',
    'FragmentVersionTracker',
    'FragmentVersion',
    'FragmentSyncManager',
    'SyncResult',
    'FragmentSyncSpec',
    'FragmentTeamManager',
    'TeamConfig',
    'TeamMember',
    'FragmentLock',
    'FragmentRepositoryManager',
    'FragmentRepo',
    'FragmentCloneSpec',
    'FragmentUpdateResult',
    'FragmentDiscoveryResult',
    'FragmentGitError',
    'FragmentRepositoryError'
]