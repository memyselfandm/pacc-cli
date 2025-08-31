"""Git repository management for Claude Code memory fragments.

This module adapts the PluginRepositoryManager for fragment use, providing:
- Repository cloning to ~/.claude/pacc/fragments/repos/owner/repo/
- Branch and tag support for fragments
- Version pinning with commit SHA comparison
- Shallow cloning optimization for performance
- Repository cache management
- Basic error handling and recovery
"""

import json
import logging
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from urllib.parse import urlparse

from ..core.file_utils import FilePathValidator, PathNormalizer
from ..errors.exceptions import PACCError, ConfigurationError, ValidationError

logger = logging.getLogger(__name__)


class FragmentGitError(PACCError):
    """Error raised when Git operations fail for fragments."""
    pass


class FragmentRepositoryError(PACCError):
    """Error raised when fragment repository structure is invalid."""
    pass


@dataclass
class FragmentRepo:
    """Information about a fragment repository."""
    
    owner: str
    repo: str
    path: Path
    url: Optional[str] = None
    commit_sha: Optional[str] = None
    branch: Optional[str] = None
    tag: Optional[str] = None
    last_updated: Optional[datetime] = None
    fragments: List[str] = field(default_factory=list)
    is_shallow: bool = False
    
    @property
    def full_name(self) -> str:
        """Get full repository name in owner/repo format."""
        return f"{self.owner}/{self.repo}"
    
    @property
    def version_ref(self) -> str:
        """Get version reference (branch, tag, or SHA)."""
        if self.tag:
            return f"tag:{self.tag}"
        elif self.branch:
            return f"branch:{self.branch}"
        elif self.commit_sha:
            return f"sha:{self.commit_sha[:8]}"
        return "unknown"


@dataclass 
class FragmentUpdateResult:
    """Result of a fragment repository update operation."""
    
    success: bool
    had_changes: bool = False
    old_sha: Optional[str] = None
    new_sha: Optional[str] = None
    message: Optional[str] = None
    error_message: Optional[str] = None
    conflicts: List[str] = field(default_factory=list)


@dataclass
class FragmentCloneSpec:
    """Specification for cloning a fragment repository."""
    
    repo_url: str
    branch: Optional[str] = None
    tag: Optional[str] = None
    commit_sha: Optional[str] = None
    shallow: bool = True
    target_dir: Optional[Path] = None
    
    def __post_init__(self):
        """Validate clone specification."""
        ref_count = sum(1 for ref in [self.branch, self.tag, self.commit_sha] if ref is not None)
        if ref_count > 1:
            raise ValidationError("Can only specify one of: branch, tag, or commit_sha")


@dataclass
class FragmentDiscoveryResult:
    """Result of fragment discovery in a repository."""
    
    is_valid: bool
    fragments_found: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


class FragmentRepositoryManager:
    """Manages Git repositories containing Claude Code memory fragments.
    
    This class adapts the PluginRepositoryManager patterns for fragments:
    - Cloning repositories to ~/.claude/pacc/fragments/repos/owner/repo/
    - Branch and tag selection support
    - Commit SHA version pinning
    - Shallow clone optimization
    - Repository cache management
    - Basic error handling and recovery
    
    The manager ensures atomic operations and provides rollback capabilities
    for all repository changes.
    """
    
    def __init__(self, fragments_dir: Optional[Path] = None):
        """Initialize fragment repository manager.
        
        Args:
            fragments_dir: Directory for fragment storage (default: ~/.claude/pacc/fragments)
        """
        if fragments_dir is None:
            fragments_dir = Path.home() / ".claude" / "pacc" / "fragments"
        
        self.fragments_dir = fragments_dir
        self.repos_dir = fragments_dir / "repos"
        self.cache_dir = fragments_dir / "cache"
        
        self.path_validator = FilePathValidator()
        self._lock = threading.RLock()
        
        # Ensure directories exist
        self.repos_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"FragmentRepositoryManager initialized with repos_dir: {self.repos_dir}")
    
    def clone_fragment_repo(self, clone_spec: FragmentCloneSpec) -> FragmentRepo:
        """Clone a fragment repository from Git URL.
        
        Args:
            clone_spec: Specification for the clone operation
            
        Returns:
            FragmentRepo object with repository information
            
        Raises:
            FragmentGitError: If git clone fails
            FragmentRepositoryError: If repository doesn't contain valid fragments
        """
        with self._lock:
            try:
                # Parse repository URL to get owner/repo
                owner, repo = self._parse_repo_url(clone_spec.repo_url)
                
                # Determine target directory
                if clone_spec.target_dir is None:
                    target_dir = self.repos_dir / owner / repo
                else:
                    target_dir = clone_spec.target_dir
                
                # Create parent directory
                target_dir.parent.mkdir(parents=True, exist_ok=True)
                
                # Build git clone command
                cmd = ["git", "clone"]
                
                # Add shallow clone option for performance
                if clone_spec.shallow:
                    cmd.extend(["--depth", "1"])
                
                # Add branch or tag specification
                if clone_spec.branch:
                    cmd.extend(["--branch", clone_spec.branch])
                elif clone_spec.tag:
                    cmd.extend(["--branch", clone_spec.tag])
                
                cmd.extend([clone_spec.repo_url, str(target_dir)])
                
                logger.info(f"Cloning fragment repository {owner}/{repo} to {target_dir}")
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
                
                if result.returncode != 0:
                    raise FragmentGitError(
                        f"Git clone failed for {clone_spec.repo_url}: {result.stderr}",
                        error_code="CLONE_FAILED",
                        context={"repo_url": clone_spec.repo_url, "stderr": result.stderr}
                    )
                
                # Handle specific commit SHA checkout if requested
                if clone_spec.commit_sha:
                    self._checkout_commit(target_dir, clone_spec.commit_sha)
                
                # Get current commit SHA
                commit_sha = self._get_current_commit_sha(target_dir)
                
                # Get current branch (if any)
                current_branch = self._get_current_branch(target_dir) if not clone_spec.commit_sha else None
                
                # Validate repository structure
                discovery_result = self.discover_fragments(target_dir)
                if not discovery_result.is_valid:
                    # Clean up cloned directory on validation failure
                    import shutil
                    shutil.rmtree(target_dir, ignore_errors=True)
                    raise FragmentRepositoryError(
                        f"Repository {owner}/{repo} does not contain valid fragments: {discovery_result.error_message}"
                    )
                
                # Create FragmentRepo object
                fragment_repo = FragmentRepo(
                    owner=owner,
                    repo=repo,
                    path=target_dir,
                    url=clone_spec.repo_url,
                    commit_sha=commit_sha,
                    branch=clone_spec.branch or current_branch,
                    tag=clone_spec.tag,
                    last_updated=datetime.now(),
                    fragments=discovery_result.fragments_found,
                    is_shallow=clone_spec.shallow
                )
                
                logger.info(f"Successfully cloned {owner}/{repo} with {len(discovery_result.fragments_found)} fragments")
                return fragment_repo
                
            except subprocess.TimeoutExpired:
                raise FragmentGitError(f"Git clone timed out for {clone_spec.repo_url}", error_code="CLONE_TIMEOUT")
            except Exception as e:
                if isinstance(e, (FragmentGitError, FragmentRepositoryError)):
                    raise
                raise FragmentGitError(f"Failed to clone repository {clone_spec.repo_url}: {e}", error_code="CLONE_ERROR")
    
    def update_fragment_repo(self, repo_path: Path, target_ref: Optional[str] = None) -> FragmentUpdateResult:
        """Update a fragment repository with git pull or checkout.
        
        Args:
            repo_path: Path to fragment repository
            target_ref: Optional target reference (branch, tag, or SHA)
            
        Returns:
            FragmentUpdateResult with update status and details
        """
        with self._lock:
            try:
                if not repo_path.exists():
                    return FragmentUpdateResult(
                        success=False,
                        error_message=f"Repository path does not exist: {repo_path}"
                    )
                
                # Get current commit SHA before update
                old_sha = self._get_current_commit_sha(repo_path)
                
                # Handle different update scenarios
                if target_ref:
                    # Checkout specific reference
                    success = self._checkout_reference(repo_path, target_ref)
                    if not success:
                        return FragmentUpdateResult(
                            success=False,
                            error_message=f"Failed to checkout reference: {target_ref}",
                            old_sha=old_sha
                        )
                else:
                    # Check if working tree is clean
                    if not self._is_working_tree_clean(repo_path):
                        return FragmentUpdateResult(
                            success=False,
                            error_message="Cannot update repository with dirty working tree. Please commit or stash changes."
                        )
                    
                    # Try git pull if on a branch
                    current_branch = self._get_current_branch(repo_path)
                    if current_branch:
                        cmd = ["git", "pull", "--ff-only"]
                        result = subprocess.run(
                            cmd,
                            cwd=repo_path,
                            capture_output=True,
                            text=True,
                            timeout=120
                        )
                        
                        if result.returncode != 0:
                            error_msg = result.stderr.lower()
                            if "not possible to fast-forward" in error_msg:
                                return FragmentUpdateResult(
                                    success=False,
                                    error_message="Update failed due to merge conflict. Repository requires manual merge or rollback.",
                                    old_sha=old_sha
                                )
                            else:
                                return FragmentUpdateResult(
                                    success=False,
                                    error_message=f"Git pull failed: {result.stderr}",
                                    old_sha=old_sha
                                )
                
                # Get new commit SHA after update
                new_sha = self._get_current_commit_sha(repo_path)
                
                # Determine if there were changes
                had_changes = old_sha != new_sha
                
                # Validate repository structure after update
                discovery_result = self.discover_fragments(repo_path)
                if not discovery_result.is_valid:
                    logger.warning(f"Fragment discovery failed after update: {discovery_result.error_message}")
                
                return FragmentUpdateResult(
                    success=True,
                    had_changes=had_changes,
                    old_sha=old_sha,
                    new_sha=new_sha,
                    message=f"Updated to {new_sha[:8]}"
                )
                
            except subprocess.TimeoutExpired:
                return FragmentUpdateResult(
                    success=False,
                    error_message="Git pull timed out"
                )
            except Exception as e:
                logger.error(f"Update failed for {repo_path}: {e}")
                return FragmentUpdateResult(
                    success=False,
                    error_message=f"Update failed: {e}"
                )
    
    def rollback_fragment_repo(self, repo_path: Path, commit_sha: str) -> bool:
        """Rollback fragment repository to specific commit.
        
        Args:
            repo_path: Path to fragment repository
            commit_sha: Target commit SHA to rollback to
            
        Returns:
            True if rollback succeeded, False otherwise
        """
        with self._lock:
            try:
                if not repo_path.exists():
                    logger.error(f"Repository path does not exist: {repo_path}")
                    return False
                
                # Validate commit SHA exists
                cmd = ["git", "rev-parse", "--verify", commit_sha]
                result = subprocess.run(
                    cmd,
                    cwd=repo_path,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    logger.error(f"Invalid commit SHA {commit_sha}: {result.stderr}")
                    return False
                
                # Perform hard reset to target commit
                cmd = ["git", "reset", "--hard", commit_sha]
                result = subprocess.run(
                    cmd,
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode != 0:
                    logger.error(f"Git reset failed: {result.stderr}")
                    return False
                
                logger.info(f"Successfully rolled back {repo_path} to {commit_sha}")
                return True
                
            except subprocess.TimeoutExpired:
                logger.error("Git reset timed out")
                return False
            except Exception as e:
                logger.error(f"Rollback failed for {repo_path}: {e}")
                return False
    
    def discover_fragments(self, repo_path: Path) -> FragmentDiscoveryResult:
        """Discover memory fragments in a repository.
        
        Args:
            repo_path: Path to repository to scan
            
        Returns:
            FragmentDiscoveryResult with discovery details
        """
        if not repo_path.exists():
            return FragmentDiscoveryResult(
                is_valid=False,
                error_message=f"Repository path does not exist: {repo_path}"
            )
        
        try:
            fragments = self._discover_fragments_in_repo(repo_path)
            
            if not fragments:
                return FragmentDiscoveryResult(
                    is_valid=False,
                    fragments_found=[],
                    error_message="No fragments found in repository. Repository must contain .md files."
                )
            
            warnings = []
            
            # Basic validation of found fragments
            for fragment_path in fragments:
                full_fragment_path = repo_path / fragment_path
                
                if not full_fragment_path.exists():
                    warnings.append(f"Fragment file not found: {fragment_path}")
                    continue
                
                # Check file size (warn if very large)
                try:
                    file_size = full_fragment_path.stat().st_size
                    if file_size > 1024 * 1024:  # 1MB
                        warnings.append(f"Fragment {fragment_path} is very large ({file_size // 1024}KB)")
                except OSError:
                    warnings.append(f"Could not check size of fragment: {fragment_path}")
            
            return FragmentDiscoveryResult(
                is_valid=True,
                fragments_found=fragments,
                warnings=warnings
            )
            
        except Exception as e:
            logger.error(f"Fragment discovery failed for {repo_path}: {e}")
            return FragmentDiscoveryResult(
                is_valid=False,
                error_message=f"Discovery failed: {e}"
            )
    
    def get_repo_info(self, repo_path: Path) -> Dict[str, Any]:
        """Get information about a fragment repository.
        
        Args:
            repo_path: Path to fragment repository
            
        Returns:
            Dictionary with repository information
            
        Raises:
            PACCError: If repository path is invalid
        """
        if not repo_path.exists():
            raise PACCError(f"Repository path does not exist: {repo_path}")
        
        try:
            # Parse owner/repo from path
            path_parts = repo_path.parts
            if len(path_parts) < 2:
                raise PACCError(f"Invalid repository path structure: {repo_path}")
            
            repo = path_parts[-1]
            owner = path_parts[-2]
            
            # Get Git information
            commit_sha = None
            branch = None
            remote_url = None
            
            try:
                commit_sha = self._get_current_commit_sha(repo_path)
                branch = self._get_current_branch(repo_path)
                remote_url = self._get_remote_url(repo_path)
            except Exception as e:
                logger.warning(f"Could not get Git info for {repo_path}: {e}")
            
            # Discover fragments
            discovery_result = self.discover_fragments(repo_path)
            
            return {
                'owner': owner,
                'repo': repo,
                'full_name': f"{owner}/{repo}",
                'path': str(repo_path),
                'commit_sha': commit_sha,
                'branch': branch,
                'remote_url': remote_url,
                'fragments': discovery_result.fragments_found,
                'fragment_count': len(discovery_result.fragments_found),
                'is_valid': discovery_result.is_valid,
                'warnings': discovery_result.warnings
            }
            
        except Exception as e:
            logger.error(f"Failed to get repo info for {repo_path}: {e}")
            raise PACCError(f"Failed to get repository information: {e}")
    
    def cleanup_cache(self, max_age_days: int = 30) -> int:
        """Clean up old cache entries.
        
        Args:
            max_age_days: Maximum age in days for cache entries
            
        Returns:
            Number of cache entries removed
        """
        removed_count = 0
        
        if not self.cache_dir.exists():
            return 0
        
        try:
            import time
            current_time = time.time()
            max_age_seconds = max_age_days * 24 * 60 * 60
            
            for cache_file in self.cache_dir.rglob("*"):
                if cache_file.is_file():
                    try:
                        file_age = current_time - cache_file.stat().st_mtime
                        if file_age > max_age_seconds:
                            cache_file.unlink()
                            removed_count += 1
                    except OSError:
                        # Skip files we can't access
                        continue
            
            # Remove empty directories
            for cache_dir in self.cache_dir.rglob("*"):
                if cache_dir.is_dir():
                    try:
                        cache_dir.rmdir()  # Only removes if empty
                    except OSError:
                        continue
                        
        except Exception as e:
            logger.warning(f"Cache cleanup failed: {e}")
        
        logger.info(f"Cleaned up {removed_count} cache entries")
        return removed_count
    
    def _parse_repo_url(self, repo_url: str) -> Tuple[str, str]:
        """Parse Git repository URL to extract owner and repo name.
        
        Args:
            repo_url: Git repository URL
            
        Returns:
            Tuple of (owner, repo)
            
        Raises:
            ValueError: If URL format is invalid
        """
        # Handle GitHub HTTPS URLs
        if repo_url.startswith("https://github.com/"):
            path = repo_url.replace("https://github.com/", "")
            if path.endswith(".git"):
                path = path[:-4]
            parts = path.split("/")
            if len(parts) >= 2:
                return parts[0], parts[1]
        
        # Handle GitHub SSH URLs  
        elif repo_url.startswith("git@github.com:"):
            path = repo_url.replace("git@github.com:", "")
            if path.endswith(".git"):
                path = path[:-4]
            parts = path.split("/")
            if len(parts) >= 2:
                return parts[0], parts[1]
        
        # Handle other Git URLs
        else:
            try:
                parsed = urlparse(repo_url)
                if parsed.path:
                    path = parsed.path.lstrip("/")
                    if path.endswith(".git"):
                        path = path[:-4]
                    parts = path.split("/")
                    if len(parts) >= 2:
                        return parts[0], parts[1]
            except Exception:
                pass
        
        raise ValueError(f"Unable to parse repository URL: {repo_url}")
    
    def _get_current_commit_sha(self, repo_path: Path) -> str:
        """Get current commit SHA for repository.
        
        Args:
            repo_path: Path to Git repository
            
        Returns:
            Current commit SHA string
            
        Raises:
            FragmentGitError: If unable to get commit SHA
        """
        try:
            cmd = ["git", "log", "-1", "--format=%H"]
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                raise FragmentGitError(f"Failed to get commit SHA: {result.stderr}")
            
            return result.stdout.strip()
            
        except subprocess.TimeoutExpired:
            raise FragmentGitError("Timeout getting commit SHA")
        except Exception as e:
            raise FragmentGitError(f"Failed to get commit SHA: {e}")
    
    def _get_current_branch(self, repo_path: Path) -> Optional[str]:
        """Get current branch name."""
        try:
            cmd = ["git", "rev-parse", "--abbrev-ref", "HEAD"]
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                branch = result.stdout.strip()
                return branch if branch != "HEAD" else None
            
        except Exception as e:
            logger.debug(f"Could not get current branch: {e}")
        
        return None
    
    def _get_remote_url(self, repo_path: Path) -> Optional[str]:
        """Get remote origin URL."""
        try:
            cmd = ["git", "remote", "get-url", "origin"]
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            
        except Exception as e:
            logger.debug(f"Could not get remote URL: {e}")
        
        return None
    
    def _is_working_tree_clean(self, repo_path: Path) -> bool:
        """Check if Git working tree is clean (no uncommitted changes).
        
        Args:
            repo_path: Path to Git repository
            
        Returns:
            True if working tree is clean, False otherwise
        """
        try:
            cmd = ["git", "status", "--porcelain"]
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.warning(f"Failed to check git status: {result.stderr}")
                return False
            
            # If output is empty, working tree is clean
            return len(result.stdout.strip()) == 0
            
        except Exception as e:
            logger.warning(f"Failed to check working tree status: {e}")
            return False
    
    def _checkout_commit(self, repo_path: Path, commit_sha: str) -> bool:
        """Checkout a specific commit."""
        try:
            cmd = ["git", "checkout", commit_sha]
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Failed to checkout commit {commit_sha}: {e}")
            return False
    
    def _checkout_reference(self, repo_path: Path, reference: str) -> bool:
        """Checkout a branch, tag, or commit."""
        try:
            cmd = ["git", "checkout", reference]
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Failed to checkout reference {reference}: {e}")
            return False
    
    def _discover_fragments_in_repo(self, repo_path: Path) -> List[str]:
        """Discover all fragment files in a repository.
        
        Fragments are identified as .md files anywhere in the repository.
        
        Args:
            repo_path: Path to repository
            
        Returns:
            List of fragment file paths relative to repo root
        """
        fragments = []
        
        try:
            # Search for .md files (fragments)
            for md_file in repo_path.rglob("*.md"):
                # Skip files in .git directory
                if ".git" in md_file.parts:
                    continue
                
                # Skip README files
                if md_file.name.lower() in ["readme.md", "readme"]:
                    continue
                
                # Get file path relative to repo root
                relative_path = md_file.relative_to(repo_path)
                fragments.append(str(relative_path))
            
            # Remove duplicates and sort
            fragments = sorted(list(set(fragments)))
            
            logger.debug(f"Discovered {len(fragments)} fragments in {repo_path}: {fragments}")
            return fragments
            
        except Exception as e:
            logger.error(f"Failed to discover fragments in {repo_path}: {e}")
            return []