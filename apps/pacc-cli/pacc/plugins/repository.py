"""Git repository management for Claude Code plugins.

This module handles all Git operations for plugin repositories including:
- Cloning repositories to ~/.claude/plugins/repos/owner/repo/
- Version tracking with commit SHA comparison
- Updates with conflict detection and rollback
- Repository structure validation
- Atomic operations for safe management
"""

import json
import logging
import re
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from urllib.parse import urlparse

from ..core.file_utils import FilePathValidator, PathNormalizer
from ..errors.exceptions import PACCError, ConfigurationError, ValidationError
from .config import PluginConfigManager


logger = logging.getLogger(__name__)


class GitError(PACCError):
    """Error raised when Git operations fail."""
    pass


class RepositoryStructureError(PACCError):
    """Error raised when repository structure is invalid."""
    pass


@dataclass
class PluginRepo:
    """Information about a plugin repository."""
    
    owner: str
    repo: str
    path: Path
    url: Optional[str] = None
    commit_sha: Optional[str] = None
    last_updated: Optional[datetime] = None
    plugins: List[str] = field(default_factory=list)
    
    @property
    def full_name(self) -> str:
        """Get full repository name in owner/repo format."""
        return f"{self.owner}/{self.repo}"


@dataclass 
class UpdateResult:
    """Result of a plugin repository update operation."""
    
    success: bool
    had_changes: bool = False
    old_sha: Optional[str] = None
    new_sha: Optional[str] = None
    message: Optional[str] = None
    error_message: Optional[str] = None
    conflicts: List[str] = field(default_factory=list)


@dataclass
class PluginInfo:
    """Information about plugins discovered in a repository."""
    
    owner: str
    repo: str
    plugins: List[str]
    path: Path
    commit_sha: Optional[str] = None
    
    @property
    def full_name(self) -> str:
        """Get full repository name."""
        return f"{self.owner}/{self.repo}"


@dataclass
class RepositoryValidationResult:
    """Result of repository structure validation."""
    
    is_valid: bool
    plugins_found: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


class PluginRepositoryManager:
    """Manages Git repositories containing Claude Code plugins.
    
    This class handles all repository operations for the Claude Code plugin system:
    - Cloning repositories to ~/.claude/plugins/repos/owner/repo/
    - Tracking commit SHAs for version control
    - Updating repositories with conflict detection
    - Rolling back failed updates
    - Validating repository structure for plugins
    
    The manager ensures atomic operations and provides rollback capabilities
    for all repository changes.
    """
    
    def __init__(
        self,
        plugins_dir: Optional[Path] = None,
        config_manager: Optional[PluginConfigManager] = None
    ):
        """Initialize plugin repository manager.
        
        Args:
            plugins_dir: Directory for plugin storage (default: ~/.claude/plugins)
            config_manager: Configuration manager instance
        """
        if plugins_dir is None:
            plugins_dir = Path.home() / ".claude" / "plugins"
        
        self.plugins_dir = plugins_dir
        self.repos_dir = plugins_dir / "repos"
        self.config_manager = config_manager or PluginConfigManager(plugins_dir=plugins_dir)
        
        self.path_validator = FilePathValidator()
        self._lock = threading.RLock()
        
        # Ensure directories exist
        self.repos_dir.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"PluginRepositoryManager initialized with repos_dir: {self.repos_dir}")
    
    def clone_plugin(self, repo_url: str, target_dir: Optional[Path] = None) -> PluginRepo:
        """Clone a plugin repository from Git URL.
        
        Args:
            repo_url: Git repository URL (HTTPS or SSH)
            target_dir: Optional target directory (auto-determined if None)
            
        Returns:
            PluginRepo object with repository information
            
        Raises:
            GitError: If git clone fails
            RepositoryStructureError: If repository doesn't contain valid plugins
        """
        with self._lock:
            try:
                # Parse repository URL to get owner/repo
                owner, repo = self._parse_repo_url(repo_url)
                
                # Determine target directory
                if target_dir is None:
                    target_dir = self.repos_dir / owner / repo
                
                # Create parent directory
                target_dir.parent.mkdir(parents=True, exist_ok=True)
                
                # Clone repository
                logger.info(f"Cloning repository {owner}/{repo} to {target_dir}")
                
                cmd = ["git", "clone", repo_url, str(target_dir)]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
                
                if result.returncode != 0:
                    raise GitError(
                        f"Git clone failed for {repo_url}: {result.stderr}",
                        error_code="CLONE_FAILED",
                        context={"repo_url": repo_url, "stderr": result.stderr}
                    )
                
                # Get current commit SHA
                commit_sha = self._get_current_commit_sha(target_dir)
                
                # Validate repository structure
                validation_result = self.validate_repository_structure(target_dir)
                if not validation_result.is_valid:
                    # Clean up cloned directory on validation failure
                    import shutil
                    shutil.rmtree(target_dir, ignore_errors=True)
                    raise RepositoryStructureError(
                        f"Repository {owner}/{repo} does not contain valid plugins: {validation_result.error_message}"
                    )
                
                # Create PluginRepo object
                plugin_repo = PluginRepo(
                    owner=owner,
                    repo=repo,
                    path=target_dir,
                    url=repo_url,
                    commit_sha=commit_sha,
                    last_updated=datetime.now(),
                    plugins=validation_result.plugins_found
                )
                
                # Add to configuration
                metadata = {
                    "lastUpdated": plugin_repo.last_updated.isoformat(),
                    "commitSha": commit_sha,
                    "plugins": validation_result.plugins_found,
                    "url": repo_url
                }
                
                if not self.config_manager.add_repository(owner, repo, metadata):
                    logger.warning(f"Failed to add repository {owner}/{repo} to config")
                
                logger.info(f"Successfully cloned {owner}/{repo} with {len(validation_result.plugins_found)} plugins")
                return plugin_repo
                
            except subprocess.TimeoutExpired:
                raise GitError(f"Git clone timed out for {repo_url}", error_code="CLONE_TIMEOUT")
            except Exception as e:
                if isinstance(e, (GitError, RepositoryStructureError)):
                    raise
                raise GitError(f"Failed to clone repository {repo_url}: {e}", error_code="CLONE_ERROR")
    
    def update_plugin(self, repo_path: Path) -> UpdateResult:
        """Update a plugin repository with git pull --ff-only.
        
        Args:
            repo_path: Path to plugin repository
            
        Returns:
            UpdateResult with update status and details
        """
        with self._lock:
            try:
                if not repo_path.exists():
                    return UpdateResult(
                        success=False,
                        error_message=f"Repository path does not exist: {repo_path}"
                    )
                
                # Check working tree is clean
                if not self._is_working_tree_clean(repo_path):
                    return UpdateResult(
                        success=False,
                        error_message="Cannot update repository with dirty working tree. Please commit or stash changes."
                    )
                
                # Get current commit SHA before update
                old_sha = self._get_current_commit_sha(repo_path)
                
                # Perform git pull --ff-only
                cmd = ["git", "pull", "--ff-only"]
                result = subprocess.run(
                    cmd,
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                
                if result.returncode != 0:
                    # Handle merge conflict or other errors
                    error_msg = result.stderr.lower()
                    if "not possible to fast-forward" in error_msg:
                        return UpdateResult(
                            success=False,
                            error_message="Update failed due to merge conflict. Repository requires manual merge or rollback.",
                            old_sha=old_sha
                        )
                    else:
                        return UpdateResult(
                            success=False,
                            error_message=f"Git pull failed: {result.stderr}",
                            old_sha=old_sha
                        )
                
                # Get new commit SHA after update
                new_sha = self._get_current_commit_sha(repo_path)
                
                # Determine if there were changes
                had_changes = old_sha != new_sha
                
                # Validate repository structure after update
                validation_result = self.validate_repository_structure(repo_path)
                if not validation_result.is_valid:
                    logger.warning(f"Repository structure validation failed after update: {validation_result.error_message}")
                
                return UpdateResult(
                    success=True,
                    had_changes=had_changes,
                    old_sha=old_sha,
                    new_sha=new_sha,
                    message=result.stdout.strip()
                )
                
            except subprocess.TimeoutExpired:
                return UpdateResult(
                    success=False,
                    error_message="Git pull timed out"
                )
            except Exception as e:
                logger.error(f"Update failed for {repo_path}: {e}")
                return UpdateResult(
                    success=False,
                    error_message=f"Update failed: {e}"
                )
    
    def rollback_plugin(self, repo_path: Path, commit_sha: str) -> bool:
        """Rollback plugin repository to specific commit.
        
        Args:
            repo_path: Path to plugin repository
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
    
    def get_plugin_info(self, repo_path: Path) -> PluginInfo:
        """Get information about plugins in a repository.
        
        Args:
            repo_path: Path to plugin repository
            
        Returns:
            PluginInfo with repository and plugin details
            
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
            
            # Discover plugins
            plugins = self._discover_plugins_in_repo(repo_path)
            
            # Get current commit SHA
            commit_sha = None
            try:
                commit_sha = self._get_current_commit_sha(repo_path)
            except Exception as e:
                logger.warning(f"Could not get commit SHA for {repo_path}: {e}")
            
            return PluginInfo(
                owner=owner,
                repo=repo,
                plugins=plugins,
                path=repo_path,
                commit_sha=commit_sha
            )
            
        except Exception as e:
            logger.error(f"Failed to get plugin info for {repo_path}: {e}")
            raise PACCError(f"Failed to get plugin information: {e}")
    
    def validate_repository_structure(self, repo_path: Path) -> RepositoryValidationResult:
        """Validate repository contains valid plugin structure.
        
        Args:
            repo_path: Path to repository to validate
            
        Returns:
            RepositoryValidationResult with validation details
        """
        if not repo_path.exists():
            return RepositoryValidationResult(
                is_valid=False,
                error_message=f"Repository path does not exist: {repo_path}"
            )
        
        try:
            # Discover plugins in repository
            plugins = self._discover_plugins_in_repo(repo_path)
            
            if not plugins:
                return RepositoryValidationResult(
                    is_valid=False,
                    plugins_found=[],
                    error_message="No plugins found in repository. Repository must contain at least one directory with plugin.json."
                )
            
            warnings = []
            
            # Validate each plugin structure
            for plugin_path in plugins:
                full_plugin_path = repo_path / plugin_path
                
                # Check for plugin.json
                plugin_json_path = full_plugin_path / "plugin.json"
                if not plugin_json_path.exists():
                    warnings.append(f"Plugin {plugin_path} missing plugin.json manifest")
                    continue
                
                # Validate plugin.json structure
                try:
                    with open(plugin_json_path, 'r', encoding='utf-8') as f:
                        plugin_data = json.load(f)
                    
                    # Check required fields
                    if "name" not in plugin_data:
                        warnings.append(f"Plugin {plugin_path} missing required 'name' field in plugin.json")
                    
                except (json.JSONDecodeError, IOError) as e:
                    warnings.append(f"Plugin {plugin_path} has invalid plugin.json: {e}")
                
                # Check for at least one component type
                has_components = any([
                    (full_plugin_path / "commands").exists(),
                    (full_plugin_path / "agents").exists(), 
                    (full_plugin_path / "hooks" / "hooks.json").exists()
                ])
                
                if not has_components:
                    warnings.append(f"Plugin {plugin_path} has no commands, agents, or hooks")
            
            return RepositoryValidationResult(
                is_valid=True,
                plugins_found=plugins,
                warnings=warnings
            )
            
        except Exception as e:
            logger.error(f"Repository validation failed for {repo_path}: {e}")
            return RepositoryValidationResult(
                is_valid=False,
                error_message=f"Validation failed: {e}"
            )
    
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
            GitError: If unable to get commit SHA
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
                raise GitError(f"Failed to get commit SHA: {result.stderr}")
            
            return result.stdout.strip()
            
        except subprocess.TimeoutExpired:
            raise GitError("Timeout getting commit SHA")
        except Exception as e:
            raise GitError(f"Failed to get commit SHA: {e}")
    
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
    
    def _discover_plugins_in_repo(self, repo_path: Path) -> List[str]:
        """Discover all plugins in a repository.
        
        Plugins are identified by the presence of plugin.json files or
        by directory structure containing commands/, agents/, or hooks/
        subdirectories.
        
        Args:
            repo_path: Path to repository
            
        Returns:
            List of plugin directory paths relative to repo root
        """
        plugins = []
        
        try:
            # Search for plugin.json files
            for plugin_json in repo_path.rglob("plugin.json"):
                # Get plugin directory relative to repo root
                plugin_dir = plugin_json.parent
                relative_path = plugin_dir.relative_to(repo_path)
                
                # Skip if in .git directory
                if ".git" in relative_path.parts:
                    continue
                
                plugins.append(str(relative_path))
            
            # If no plugin.json files found, look for plugin-like structures
            if not plugins:
                for subdir in repo_path.iterdir():
                    if subdir.is_dir() and subdir.name != ".git":
                        # Check if directory has plugin components
                        has_components = any([
                            (subdir / "commands").exists(),
                            (subdir / "agents").exists(),
                            (subdir / "hooks").exists()
                        ])
                        
                        if has_components:
                            relative_path = subdir.relative_to(repo_path)
                            plugins.append(str(relative_path))
            
            # Remove duplicates and sort
            plugins = sorted(list(set(plugins)))
            
            logger.debug(f"Discovered {len(plugins)} plugins in {repo_path}: {plugins}")
            return plugins
            
        except Exception as e:
            logger.error(f"Failed to discover plugins in {repo_path}: {e}")
            return []
    
    def create_plugin_repository(
        self, 
        plugin_dir: Path, 
        plugin_metadata: Dict[str, Any],
        init_git: bool = True
    ) -> bool:
        """Create a new Git repository for a plugin directory.
        
        This method initializes a Git repository in the given plugin directory,
        generates appropriate README.md and .gitignore files, and creates an
        initial commit. This is typically used when converting existing
        extensions to shareable plugins.
        
        Args:
            plugin_dir: Path to plugin directory to initialize
            plugin_metadata: Plugin metadata from plugin.json
            init_git: Whether to initialize Git repository (default: True)
            
        Returns:
            True if repository was created successfully, False otherwise
            
        Raises:
            GitError: If Git operations fail
            ValidationError: If plugin directory structure is invalid
        """
        with self._lock:
            try:
                if not plugin_dir.exists():
                    raise ValidationError(f"Plugin directory does not exist: {plugin_dir}")
                
                # Validate plugin structure before creating repository
                if not self._validate_plugin_structure(plugin_dir):
                    raise ValidationError(f"Invalid plugin structure in {plugin_dir}")
                
                if init_git:
                    # Initialize Git repository
                    logger.info(f"Initializing Git repository in {plugin_dir}")
                    cmd = ["git", "init"]
                    result = subprocess.run(
                        cmd,
                        cwd=plugin_dir,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if result.returncode != 0:
                        raise GitError(f"Failed to initialize Git repository: {result.stderr}")
                
                # Generate README.md
                readme_path = plugin_dir / "README.md"
                if not readme_path.exists():
                    readme_content = self.generate_readme(plugin_metadata, plugin_dir)
                    with open(readme_path, 'w', encoding='utf-8') as f:
                        f.write(readme_content)
                    logger.info(f"Generated README.md for plugin {plugin_metadata.get('name', 'unknown')}")
                
                # Create .gitignore
                gitignore_path = plugin_dir / ".gitignore"
                if not gitignore_path.exists():
                    gitignore_content = self.create_gitignore()
                    with open(gitignore_path, 'w', encoding='utf-8') as f:
                        f.write(gitignore_content)
                    logger.info(f"Created .gitignore for plugin")
                
                logger.info(f"Successfully set up plugin repository structure in {plugin_dir}")
                return True
                
            except subprocess.TimeoutExpired:
                raise GitError("Git init timed out")
            except Exception as e:
                if isinstance(e, (GitError, ValidationError)):
                    raise
                logger.error(f"Failed to create plugin repository: {e}")
                raise GitError(f"Repository creation failed: {e}")
    
    def generate_readme(self, plugin_metadata: Dict[str, Any], plugin_dir: Path) -> str:
        """Generate comprehensive README.md content from plugin metadata.
        
        Creates a well-formatted README that includes plugin description,
        component inventory, installation instructions, and usage examples.
        
        Args:
            plugin_metadata: Plugin metadata from plugin.json
            plugin_dir: Path to plugin directory for component analysis
            
        Returns:
            README.md content as string
        """
        plugin_name = plugin_metadata.get('name', 'Unnamed Plugin')
        description = plugin_metadata.get('description', 'A Claude Code plugin')
        version = plugin_metadata.get('version', '1.0.0')
        author = plugin_metadata.get('author', {})
        
        # Analyze plugin components
        components = self._analyze_plugin_components(plugin_dir)
        
        readme_content = f"""# {plugin_name}

{description}

**Version:** {version}
"""
        
        # Add author information if available
        if author:
            author_name = author.get('name', '')
            author_email = author.get('email', '')
            author_url = author.get('url', '')
            
            if author_name or author_email:
                readme_content += f"\n**Author:** "
                if author_name:
                    readme_content += author_name
                if author_email:
                    readme_content += f" <{author_email}>"
                if author_url:
                    readme_content += f" ([Website]({author_url}))"
                readme_content += "\n"
        
        # Add components section
        readme_content += "\n## Components\n\n"
        
        if components['commands']:
            readme_content += f"**Commands:** {len(components['commands'])} custom commands\n"
            for cmd in components['commands'][:5]:  # Show first 5
                readme_content += f"- `{cmd}`\n"
            if len(components['commands']) > 5:
                readme_content += f"- ... and {len(components['commands']) - 5} more\n"
            readme_content += "\n"
        
        if components['agents']:
            readme_content += f"**Agents:** {len(components['agents'])} specialized agents\n"
            for agent in components['agents'][:5]:  # Show first 5
                readme_content += f"- `{agent}`\n"
            if len(components['agents']) > 5:
                readme_content += f"- ... and {len(components['agents']) - 5} more\n"
            readme_content += "\n"
        
        if components['hooks']:
            readme_content += f"**Hooks:** {len(components['hooks'])} event hooks\n"
            for hook in components['hooks'][:5]:  # Show first 5
                readme_content += f"- `{hook}`\n"
            if len(components['hooks']) > 5:
                readme_content += f"- ... and {len(components['hooks']) - 5} more\n"
            readme_content += "\n"
        
        if not any([components['commands'], components['agents'], components['hooks']]):
            readme_content += "No components detected in this plugin.\n\n"
        
        # Add installation section
        readme_content += """## Installation

This plugin can be installed using PACC (Package manager for Claude Code):

```bash
pacc plugin install <owner>/<repo>
```

Or manually by cloning this repository to your Claude Code plugins directory:

```bash
git clone <repo-url> ~/.claude/plugins/repos/<owner>/<repo>
```

After installation, enable the plugin in your Claude Code settings.

## Usage

"""
        
        # Add usage examples based on components
        if components['commands']:
            readme_content += "### Commands\n\n"
            readme_content += "This plugin provides the following custom commands:\n\n"
            for cmd in components['commands'][:3]:  # Show examples for first 3
                readme_content += f"- `/{cmd}` - Custom command functionality\n"
            readme_content += "\n"
        
        if components['agents']:
            readme_content += "### Agents\n\n"
            readme_content += "This plugin includes specialized agents for enhanced AI assistance:\n\n"
            for agent in components['agents'][:3]:  # Show examples for first 3
                readme_content += f"- **{agent}** - Specialized agent functionality\n"
            readme_content += "\n"
        
        if components['hooks']:
            readme_content += "### Hooks\n\n"
            readme_content += "This plugin provides event-driven functionality through hooks:\n\n"
            for hook in components['hooks'][:3]:  # Show examples for first 3
                readme_content += f"- **{hook}** - Automated event handling\n"
            readme_content += "\n"
        
        # Add requirements section
        readme_content += """## Requirements

- Claude Code v1.0.81 or later with plugin support
- `ENABLE_PLUGINS=1` environment variable set
- Git for installation and updates

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## License

This plugin is provided as-is for use with Claude Code.
"""
        
        return readme_content
    
    def create_gitignore(self) -> str:
        """Create appropriate .gitignore content for Claude Code plugins.
        
        Returns:
            .gitignore content as string
        """
        return """\
# OS-specific files
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/

# IDE files
.vscode/
.idea/
*.swp
*.swo
*~

# Logs
*.log
logs/

# Environment variables
.env
.env.local
.env.*.local

# Temporary files
tmp/
temp/
*.tmp
*.temp

# Node.js (if any JavaScript tools)
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Claude Code specific
.claude/local/
"""
    
    def commit_plugin(self, plugin_dir: Path, message: Optional[str] = None) -> bool:
        """Create initial commit for plugin repository.
        
        Args:
            plugin_dir: Path to plugin directory
            message: Optional commit message (auto-generated if None)
            
        Returns:
            True if commit succeeded, False otherwise
        """
        with self._lock:
            try:
                if not plugin_dir.exists():
                    logger.error(f"Plugin directory does not exist: {plugin_dir}")
                    return False
                
                # Check if this is a Git repository
                git_dir = plugin_dir / ".git"
                if not git_dir.exists():
                    logger.error(f"Not a Git repository: {plugin_dir}")
                    return False
                
                # Add all files
                cmd = ["git", "add", "."]
                result = subprocess.run(
                    cmd,
                    cwd=plugin_dir,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode != 0:
                    logger.error(f"Git add failed: {result.stderr}")
                    return False
                
                # Generate commit message if not provided
                if message is None:
                    # Try to get plugin name from plugin.json
                    plugin_json_path = plugin_dir / "plugin.json"
                    plugin_name = "plugin"
                    if plugin_json_path.exists():
                        try:
                            with open(plugin_json_path, 'r', encoding='utf-8') as f:
                                plugin_data = json.load(f)
                                plugin_name = plugin_data.get('name', 'plugin')
                        except (json.JSONDecodeError, IOError):
                            pass
                    
                    message = f"Initial commit for {plugin_name}\n\nGenerated by PACC plugin converter"
                
                # Create commit
                cmd = ["git", "commit", "-m", message]
                result = subprocess.run(
                    cmd,
                    cwd=plugin_dir,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode != 0:
                    # Check if there were no changes to commit
                    if "nothing to commit" in result.stdout.lower():
                        logger.info("No changes to commit")
                        return True
                    else:
                        logger.error(f"Git commit failed: {result.stderr}")
                        return False
                
                logger.info(f"Successfully created initial commit for plugin in {plugin_dir}")
                return True
                
            except subprocess.TimeoutExpired:
                logger.error("Git commit timed out")
                return False
            except Exception as e:
                logger.error(f"Commit failed for {plugin_dir}: {e}")
                return False
    
    def push_plugin(
        self, 
        plugin_dir: Path, 
        repo_url: str, 
        auth: Optional[Dict[str, str]] = None,
        branch: str = "main"
    ) -> bool:
        """Push plugin repository to remote Git repository.
        
        Supports authentication via SSH keys (default) or HTTPS with tokens.
        Handles GitHub, GitLab, and Bitbucket repositories.
        
        Args:
            plugin_dir: Path to plugin directory
            repo_url: Remote repository URL (HTTPS or SSH)
            auth: Optional authentication dict with 'token' or 'username'/'password'
            branch: Branch to push to (default: 'main')
            
        Returns:
            True if push succeeded, False otherwise
        """
        with self._lock:
            try:
                if not plugin_dir.exists():
                    logger.error(f"Plugin directory does not exist: {plugin_dir}")
                    return False
                
                # Check if this is a Git repository
                git_dir = plugin_dir / ".git"
                if not git_dir.exists():
                    logger.error(f"Not a Git repository: {plugin_dir}")
                    return False
                
                # Prepare remote URL with authentication if needed
                push_url = self._prepare_authenticated_url(repo_url, auth)
                
                # Add remote origin if it doesn't exist
                cmd = ["git", "remote", "get-url", "origin"]
                result = subprocess.run(
                    cmd,
                    cwd=plugin_dir,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    # Add remote origin
                    cmd = ["git", "remote", "add", "origin", push_url]
                    result = subprocess.run(
                        cmd,
                        cwd=plugin_dir,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if result.returncode != 0:
                        logger.error(f"Failed to add remote origin: {result.stderr}")
                        return False
                else:
                    # Update existing remote URL
                    cmd = ["git", "remote", "set-url", "origin", push_url]
                    result = subprocess.run(
                        cmd,
                        cwd=plugin_dir,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if result.returncode != 0:
                        logger.error(f"Failed to update remote URL: {result.stderr}")
                        return False
                
                # Push to remote
                logger.info(f"Pushing plugin to {repo_url} (branch: {branch})")
                cmd = ["git", "push", "-u", "origin", branch]
                result = subprocess.run(
                    cmd,
                    cwd=plugin_dir,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout for push
                )
                
                if result.returncode != 0:
                    error_message = result.stderr.lower()
                    
                    # Provide specific error messages for common issues
                    if "authentication failed" in error_message or "access denied" in error_message:
                        logger.error("Authentication failed. Please check your credentials or SSH keys.")
                        return False
                    elif "repository not found" in error_message:
                        logger.error("Repository not found. Please check the repository URL and permissions.")
                        return False
                    elif "permission denied" in error_message:
                        logger.error("Permission denied. Please check repository permissions.")
                        return False
                    else:
                        logger.error(f"Git push failed: {result.stderr}")
                        return False
                
                logger.info(f"Successfully pushed plugin to {repo_url}")
                return True
                
            except subprocess.TimeoutExpired:
                logger.error("Git push timed out")
                return False
            except Exception as e:
                logger.error(f"Push failed for {plugin_dir}: {e}")
                return False
    
    def _validate_plugin_structure(self, plugin_dir: Path) -> bool:
        """Validate that plugin directory has required structure.
        
        Args:
            plugin_dir: Path to plugin directory
            
        Returns:
            True if structure is valid, False otherwise
        """
        try:
            # Check for plugin.json
            plugin_json_path = plugin_dir / "plugin.json"
            if not plugin_json_path.exists():
                logger.warning(f"No plugin.json found in {plugin_dir}")
                return False
            
            # Validate plugin.json content
            with open(plugin_json_path, 'r', encoding='utf-8') as f:
                plugin_data = json.load(f)
            
            if "name" not in plugin_data:
                logger.warning(f"Plugin manifest missing required 'name' field")
                return False
            
            # Check for at least one component type
            has_components = any([
                (plugin_dir / "commands").exists(),
                (plugin_dir / "agents").exists(),
                (plugin_dir / "hooks").exists()
            ])
            
            if not has_components:
                logger.warning(f"Plugin has no commands, agents, or hooks directories")
            
            return True
            
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Invalid plugin.json in {plugin_dir}: {e}")
            return False
        except Exception as e:
            logger.error(f"Plugin validation failed for {plugin_dir}: {e}")
            return False
    
    def _analyze_plugin_components(self, plugin_dir: Path) -> Dict[str, List[str]]:
        """Analyze plugin directory to identify components.
        
        Args:
            plugin_dir: Path to plugin directory
            
        Returns:
            Dict with lists of commands, agents, and hooks
        """
        components = {
            'commands': [],
            'agents': [],
            'hooks': []
        }
        
        try:
            # Analyze commands
            commands_dir = plugin_dir / "commands"
            if commands_dir.exists():
                for cmd_file in commands_dir.rglob("*.md"):
                    # Get command name from filename (without .md extension)
                    cmd_name = cmd_file.stem
                    # Add namespace if in subdirectory
                    relative_path = cmd_file.relative_to(commands_dir)
                    if len(relative_path.parts) > 1:
                        namespace = "/".join(relative_path.parts[:-1])
                        cmd_name = f"{namespace}/{cmd_name}"
                    components['commands'].append(cmd_name)
            
            # Analyze agents
            agents_dir = plugin_dir / "agents"
            if agents_dir.exists():
                for agent_file in agents_dir.rglob("*.md"):
                    # Get agent name from filename (without .md extension)
                    agent_name = agent_file.stem
                    # Add namespace if in subdirectory
                    relative_path = agent_file.relative_to(agents_dir)
                    if len(relative_path.parts) > 1:
                        namespace = "/".join(relative_path.parts[:-1])
                        agent_name = f"{namespace}/{agent_name}"
                    components['agents'].append(agent_name)
            
            # Analyze hooks
            hooks_file = plugin_dir / "hooks" / "hooks.json"
            if hooks_file.exists():
                try:
                    with open(hooks_file, 'r', encoding='utf-8') as f:
                        hooks_data = json.load(f)
                    
                    if isinstance(hooks_data, dict):
                        components['hooks'] = list(hooks_data.keys())
                    elif isinstance(hooks_data, list):
                        # If hooks.json is a list, extract hook names
                        for hook in hooks_data:
                            if isinstance(hook, dict) and 'name' in hook:
                                components['hooks'].append(hook['name'])
                            
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Could not parse hooks.json: {e}")
            
        except Exception as e:
            logger.error(f"Failed to analyze plugin components: {e}")
        
        return components
    
    def _prepare_authenticated_url(self, repo_url: str, auth: Optional[Dict[str, str]]) -> str:
        """Prepare repository URL with authentication if needed.
        
        Args:
            repo_url: Repository URL
            auth: Authentication dictionary
            
        Returns:
            URL prepared for authenticated access
        """
        if not auth:
            return repo_url
        
        # For SSH URLs, return as-is (assume SSH keys are configured)
        if repo_url.startswith("git@"):
            return repo_url
        
        # For HTTPS URLs, inject token if provided
        if repo_url.startswith("https://") and "token" in auth:
            token = auth["token"]
            
            # Handle GitHub URLs
            if "github.com" in repo_url:
                return repo_url.replace("https://", f"https://{token}@")
            
            # Handle GitLab URLs
            elif "gitlab.com" in repo_url:
                return repo_url.replace("https://", f"https://oauth2:{token}@")
            
            # Handle Bitbucket URLs
            elif "bitbucket.org" in repo_url:
                return repo_url.replace("https://", f"https://x-token-auth:{token}@")
            
            # Generic token auth
            else:
                return repo_url.replace("https://", f"https://{token}@")
        
        # Handle username/password auth
        elif repo_url.startswith("https://") and "username" in auth and "password" in auth:
            username = auth["username"]
            password = auth["password"]
            return repo_url.replace("https://", f"https://{username}:{password}@")
        
        return repo_url