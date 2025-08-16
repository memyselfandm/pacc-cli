"""Git repository source handling for PACC."""

import re
import json
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse, parse_qs
from dataclasses import dataclass

from ..errors import SourceError
from ..validators import ExtensionDetector
from .base import SourceHandler, Source


@dataclass
class GitRepositoryInfo:
    """Information about a Git repository."""
    
    provider: str  # github, gitlab, bitbucket, etc.
    owner: str
    repo: str
    protocol: str  # https, ssh
    branch: Optional[str] = None
    tag: Optional[str] = None
    commit: Optional[str] = None
    path: Optional[str] = None  # subdirectory path
    

class GitUrlParser:
    """Parser for Git repository URLs."""
    
    # Supported Git providers and their patterns
    PROVIDER_PATTERNS = {
        'github': {
            'https': r'https://github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/(.+?))?(?:[#@](.+))?/?$',
            'ssh': r'git@github\.com:([^/]+)/([^/]+?)(?:\.git)?(?:/(.+?))?(?:[#@](.+))?/?$'
        },
        'gitlab': {
            'https': r'https://gitlab\.com/(.*)/([^/]+?)(?:\.git)?(?:/(.+?))?(?:[#@](.+))?/?$',
            'ssh': r'git@gitlab\.com:(.*)/([^/]+?)(?:\.git)?(?:/(.+?))?(?:[#@](.+))?/?$'
        },
        'bitbucket': {
            'https': r'https://bitbucket\.org/([^/]+)/([^/]+?)(?:\.git)?(?:/(.+?))?(?:[#@](.+))?/?$',
            'ssh': r'git@bitbucket\.org:([^/]+)/([^/]+?)(?:\.git)?(?:/(.+?))?(?:[#@](.+))?/?$'
        },
        'local': {
            'file': r'file://(.+?)(?:[#@](.+))?/?$'
        }
    }
    
    def parse(self, url: str) -> Dict[str, Any]:
        """Parse a Git URL and extract repository information.
        
        Args:
            url: Git repository URL
            
        Returns:
            Dictionary with parsed URL components
            
        Raises:
            SourceError: If URL cannot be parsed or provider is unsupported
        """
        # Try to match against known providers
        for provider, protocols in self.PROVIDER_PATTERNS.items():
            for protocol, pattern in protocols.items():
                match = re.match(pattern, url, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    
                    # Handle local file URLs differently
                    if provider == 'local':
                        full_path = groups[0]
                        path_parts = full_path.strip('/').split('/')
                        
                        # Check if the last part looks like a common extension directory
                        common_extension_dirs = ['hooks', 'agents', 'commands', 'mcp', 'servers']
                        subpath = None
                        repo_parts = path_parts
                        
                        if path_parts and path_parts[-1] in common_extension_dirs:
                            # Last part looks like an extension directory - treat it as subpath
                            subpath = path_parts[-1]
                            repo_parts = path_parts[:-1]
                        
                        repo_name = repo_parts[-1] if repo_parts else 'unknown'
                        owner_path = '/'.join(repo_parts[:-1]) if len(repo_parts) > 1 else ''
                        
                        result = {
                            'provider': provider,
                            'protocol': protocol,
                            'owner': owner_path,
                            'repo': repo_name,
                            'path': subpath,
                            'branch': None,
                            'tag': None,
                            'commit': None,
                            'full_path': '/'.join(repo_parts) if repo_parts else full_path  # Store repo path for local URLs
                        }
                        
                        # Parse branch/tag/commit specification for local URLs
                        if len(groups) > 1 and groups[1]:
                            ref_spec = groups[1]
                            if ref_spec.startswith('v') or '.' in ref_spec:
                                result['tag'] = ref_spec
                            elif len(ref_spec) >= 7 and all(c in '0123456789abcdef' for c in ref_spec.lower()):
                                result['commit'] = ref_spec
                            else:
                                result['branch'] = ref_spec
                    else:
                        # Handle remote URLs (GitHub, GitLab, etc.)
                        result = {
                            'provider': provider,
                            'protocol': protocol,
                            'owner': groups[0],
                            'repo': groups[1],
                            'path': groups[2] if len(groups) > 2 and groups[2] else None,
                            'branch': None,
                            'tag': None,
                            'commit': None
                        }
                        
                        # Parse branch/tag/commit specification for remote URLs
                        if len(groups) > 3 and groups[3]:
                            ref_spec = groups[3]
                            if ref_spec.startswith('v') or '.' in ref_spec:
                                # Looks like a version tag
                                result['tag'] = ref_spec
                            elif len(ref_spec) >= 7 and all(c in '0123456789abcdef' for c in ref_spec.lower()):
                                # Looks like a commit hash
                                result['commit'] = ref_spec
                            else:
                                # Assume it's a branch
                                result['branch'] = ref_spec
                    
                    return result
        
        raise SourceError(f"Unsupported or invalid Git URL: {url}")
    
    def validate(self, url: str) -> bool:
        """Validate that a URL is a supported Git repository URL.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is valid and supported
        """
        try:
            result = self.parse(url)
            # For local file URLs, be more restrictive
            if result['provider'] == 'local':
                path = result.get('full_path', '')
                filename = path.split('/')[-1]
                
                # Accept if it explicitly ends with .git
                if filename.endswith('.git'):
                    return True
                    
                # For directories, only accept if they look like repo names
                # Common repo naming patterns
                repo_like_patterns = ['repo', 'project', 'extension', 'plugin', 'tool']
                if '.' not in filename and any(pattern in filename.lower() for pattern in repo_like_patterns):
                    return True
                    
                # Be more restrictive - only accept obvious repo-like paths
                return False
            return True
        except SourceError:
            return False
    
    def normalize(self, url: str) -> str:
        """Normalize a Git URL to its canonical form.
        
        Args:
            url: Git URL to normalize
            
        Returns:
            Normalized URL with .git suffix
        """
        try:
            info = self.parse(url)
            
            # Handle local file URLs
            if info['provider'] == 'local':
                base_url = url.split('#')[0].split('@')[0]  # Remove ref specifications for base
            elif info['protocol'] == 'https':
                base_url = f"https://{info['provider']}.com/{info['owner']}/{info['repo']}"
                if not base_url.endswith('.git'):
                    base_url += '.git'
            else:  # ssh
                base_url = f"git@{info['provider']}.com:{info['owner']}/{info['repo']}.git"
            
            # Add path if specified (not for local URLs)
            if info['path'] and info['provider'] != 'local':
                base_url += f"/{info['path']}"
            
            # Add ref specification
            if info['branch']:
                base_url += f"#{info['branch']}"
            elif info['tag']:
                base_url += f"@{info['tag']}"
            elif info['commit']:
                base_url += f"@{info['commit']}"
            
            return base_url
            
        except SourceError:
            # If we can't parse it, return as-is
            return url


class GitCloner:
    """Handles cloning Git repositories."""
    
    def __init__(self, temp_dir: Optional[str] = None):
        """Initialize Git cloner.
        
        Args:
            temp_dir: Base temporary directory for clones
        """
        self.temp_dir = temp_dir or tempfile.gettempdir()
        self.parser = GitUrlParser()
    
    def clone(self, url: str, branch: Optional[str] = None, tag: Optional[str] = None,
              commit: Optional[str] = None, shallow: bool = True, 
              depth: int = 1) -> Path:
        """Clone a Git repository.
        
        Args:
            url: Git repository URL
            branch: Specific branch to clone
            tag: Specific tag to clone
            commit: Specific commit to clone
            shallow: Whether to do a shallow clone
            depth: Depth for shallow clone
            
        Returns:
            Path to cloned repository
            
        Raises:
            SourceError: If cloning fails
        """
        # Parse URL to get repository info
        repo_info = self.parser.parse(url)
        clone_name = f"{repo_info['owner']}-{repo_info['repo']}"
        clone_path = Path(self.temp_dir) / f"pacc-git-{clone_name}"
        
        # Remove existing clone if it exists
        if clone_path.exists():
            shutil.rmtree(clone_path)
        
        # Build git clone command
        git_cmd = ['git', 'clone']
        
        # Add shallow clone options
        if shallow:
            git_cmd.extend(['--depth', str(depth)])
        
        # Add branch/tag specification
        ref_to_clone = branch or tag or commit
        if ref_to_clone:
            git_cmd.extend(['--branch', ref_to_clone])
        
        # Add URL and destination
        clone_url = self._get_clone_url(url, repo_info)
        git_cmd.extend([clone_url, str(clone_path)])
        
        try:
            # Execute clone command
            result = subprocess.run(
                git_cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=300  # 5 minute timeout
            )
            
            # Also check return code explicitly (for test compatibility)
            if result.returncode != 0:
                error_msg = f"Git clone failed: {result.stderr or result.stdout or 'Unknown error'}"
                raise SourceError(error_msg, source_type="git", source_path=Path(url))
            
            # If we need to checkout a specific commit after cloning
            if commit and not tag:
                checkout_result = subprocess.run(
                    ['git', 'checkout', commit],
                    cwd=clone_path,
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                if checkout_result.returncode != 0:
                    error_msg = f"Git checkout failed: {checkout_result.stderr or checkout_result.stdout or 'Unknown error'}"
                    raise SourceError(error_msg, source_type="git", source_path=Path(url))
            
            return clone_path
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Git clone failed: {e.stderr or e.stdout or str(e)}"
            raise SourceError(error_msg, source_type="git", source_path=Path(url))
        except subprocess.TimeoutExpired:
            raise SourceError("Git clone timed out", source_type="git", source_path=Path(url))
        except Exception as e:
            raise SourceError(f"Unexpected error during clone: {str(e)}", 
                            source_type="git", source_path=Path(url))
    
    def _get_clone_url(self, original_url: str, repo_info: Dict[str, Any]) -> str:
        """Get the actual URL to use for cloning.
        
        Args:
            original_url: Original URL provided
            repo_info: Parsed repository information
            
        Returns:
            URL suitable for git clone command
        """
        # Handle local file URLs
        if repo_info['provider'] == 'local':
            # For local URLs, use the repository path (without subpath)
            if 'full_path' in repo_info:
                return f"file:///{repo_info['full_path']}"
            else:
                return original_url.split('#')[0].split('@')[0]  # Remove ref specifications
        
        # Remove any path/ref specifications for cloning
        if repo_info['protocol'] == 'https':
            return f"https://{repo_info['provider']}.com/{repo_info['owner']}/{repo_info['repo']}.git"
        else:  # ssh
            return f"git@{repo_info['provider']}.com:{repo_info['owner']}/{repo_info['repo']}.git"
    
    def _parse_auth_info(self, url: str) -> Dict[str, str]:
        """Parse authentication information from URL.
        
        Args:
            url: Git repository URL
            
        Returns:
            Dictionary with auth information
        """
        if url.startswith('git@'):
            return {'auth_type': 'ssh'}
        elif url.startswith('https://'):
            return {'auth_type': 'https'}
        else:
            return {'auth_type': 'unknown'}
    
    def cleanup(self, clone_path: Path) -> None:
        """Clean up a cloned repository.
        
        Args:
            clone_path: Path to repository clone to clean up
        """
        try:
            if clone_path.exists():
                shutil.rmtree(clone_path)
        except Exception:
            # Best effort cleanup - don't fail if we can't clean up
            pass


class GitRepositorySource(Source):
    """Represents a Git repository as an extension source."""
    
    def __init__(self, url: str):
        """Initialize Git repository source.
        
        Args:
            url: Git repository URL
        """
        super().__init__(url, "git")
        self.parser = GitUrlParser()
        self.repo_info = self.parser.parse(url)
        self._cloner = GitCloner()
        self._clone_path: Optional[Path] = None
    
    def scan_extensions(self) -> List:
        """Scan the repository for extensions.
        
        Returns:
            List of Extension objects found in repository
        """
        from ..cli import Extension  # Import here to avoid circular imports
        
        # Clone the repository if not already done
        if not self._clone_path:
            self._clone_path = self._cloner.clone(
                self.url,
                branch=self.repo_info.get('branch'),
                tag=self.repo_info.get('tag'),
                commit=self.repo_info.get('commit')
            )
        
        # Determine scan directory (full repo or subdirectory)
        scan_dir = self._clone_path
        if self.repo_info.get('path'):
            scan_dir = self._clone_path / self.repo_info['path']
            if not scan_dir.exists():
                return []
        
        # Use existing extension detector to find extensions, but filter out Git-related files
        detected_files = ExtensionDetector.scan_directory(scan_dir)
        extensions = []
        
        for ext_type, file_paths in detected_files.items():
            for file_path in file_paths:
                # Skip files in .git directories
                if '.git' in file_path.parts:
                    continue
                    
                # Skip system files
                if file_path.name.startswith('.'):
                    continue
                
                # Skip common non-extension files
                if self._should_skip_file(file_path, ext_type):
                    continue
                    
                extension = Extension(
                    name=file_path.stem,
                    file_path=file_path,
                    extension_type=ext_type,
                    description=self._extract_description(file_path, ext_type)
                )
                extensions.append(extension)
        
        return extensions
    
    def _should_skip_file(self, file_path: Path, ext_type: str) -> bool:
        """Check if a file should be skipped during extension scanning.
        
        Args:
            file_path: Path to the file
            ext_type: Detected extension type
            
        Returns:
            True if file should be skipped
        """
        filename = file_path.name.lower()
        
        # Skip common documentation and metadata files
        if filename in ['readme.md', 'readme.txt', 'readme.rst', 'readme', 
                       'changelog.md', 'changelog.txt', 'changelog',
                       'license.md', 'license.txt', 'license', 'license.mit',
                       'contributing.md', 'contributing.txt',
                       'package.json', 'setup.py', 'setup.cfg',
                       'pacc.json', 'pyproject.toml', 'requirements.txt']:
            return True
        
        # Skip Python scripts that aren't explicitly extensions
        if filename.endswith('.py') and ext_type == 'mcp':
            # Allow .py files only if they're clearly MCP servers (have specific naming)
            if not any(keyword in filename for keyword in ['server', 'mcp', 'service']):
                return True
        
        # Skip test files
        if any(pattern in filename for pattern in ['test_', '_test', 'spec_', '_spec']):
            return True
        
        # Skip backup and temp files
        if filename.endswith(('.bak', '.tmp', '.temp', '~')):
            return True
            
        return False
    
    def _extract_description(self, file_path: Path, ext_type: str) -> Optional[str]:
        """Extract description from extension file.
        
        Args:
            file_path: Path to extension file
            ext_type: Type of extension
            
        Returns:
            Description string if found
        """
        try:
            if ext_type in ['hooks', 'mcp']:
                # JSON files
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return data.get('description')
            elif ext_type == 'agents':
                # Markdown with YAML frontmatter
                import yaml
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 2:
                        frontmatter = yaml.safe_load(parts[1])
                        return frontmatter.get('description')
            elif ext_type == 'commands':
                # Markdown file - extract first line after title
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                for i, line in enumerate(lines):
                    line = line.strip()
                    if line and not line.startswith('#') and i > 0:
                        return line
        except Exception:
            pass
        
        return None
    
    def extract_extension(self, name: str, ext_type: str) -> Optional[Dict[str, Any]]:
        """Extract specific extension data from repository.
        
        Args:
            name: Name of extension
            ext_type: Type of extension
            
        Returns:
            Extension data dictionary or None if not found
        """
        extensions = self.scan_extensions()
        for ext in extensions:
            if ext.name == name and ext.extension_type == ext_type:
                try:
                    if ext_type in ['hooks', 'mcp']:
                        with open(ext.file_path, 'r', encoding='utf-8') as f:
                            return json.load(f)
                    # For other types, could implement more extraction logic
                except Exception:
                    pass
        return None
    
    def get_repository_metadata(self) -> Dict[str, Any]:
        """Extract metadata from the repository.
        
        Returns:
            Repository metadata dictionary
        """
        if not self._clone_path:
            self._clone_path = self._cloner.clone(self.url)
        
        metadata = {
            'url': self.url,
            'provider': self.repo_info['provider'],
            'owner': self.repo_info['owner'],
            'repo': self.repo_info['repo']
        }
        
        # Look for package metadata files
        for metadata_file in ['pacc.json', 'package.json', 'setup.json']:
            meta_path = self._clone_path / metadata_file
            if meta_path.exists():
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        file_metadata = json.load(f)
                    metadata.update(file_metadata)
                    break
                except Exception:
                    continue
        
        # Look for README
        for readme_file in ['README.md', 'README.rst', 'README.txt', 'README']:
            readme_path = self._clone_path / readme_file
            if readme_path.exists():
                try:
                    with open(readme_path, 'r', encoding='utf-8') as f:
                        readme_content = f.read()
                    metadata['readme'] = readme_content[:1000]  # First 1000 chars
                    break
                except Exception:
                    continue
        
        return metadata
    
    def cleanup(self) -> None:
        """Clean up temporary repository clone."""
        if self._clone_path:
            self._cloner.cleanup(self._clone_path)
            self._clone_path = None


class GitSourceHandler(SourceHandler):
    """Handler for Git repository sources."""
    
    def __init__(self):
        """Initialize Git source handler."""
        self.parser = GitUrlParser()
    
    def can_handle(self, source: str) -> bool:
        """Check if source is a Git repository URL.
        
        Args:
            source: Source URL or path
            
        Returns:
            True if source is a supported Git URL
        """
        return self.parser.validate(source)
    
    def process_source(self, source: str, extension_type: Optional[str] = None, 
                      **kwargs) -> List:
        """Process Git repository source and return extensions.
        
        Args:
            source: Git repository URL
            extension_type: Filter by specific extension type
            **kwargs: Additional options
            
        Returns:
            List of Extension objects from repository
        """
        git_source = GitRepositorySource(source)
        
        try:
            extensions = git_source.scan_extensions()
            
            # Filter by extension type if specified
            if extension_type:
                extensions = [ext for ext in extensions if ext.extension_type == extension_type]
            
            return extensions
            
        finally:
            git_source.cleanup()
    
    def get_source_info(self, source: str) -> Dict[str, Any]:
        """Get information about Git repository source.
        
        Args:
            source: Git repository URL
            
        Returns:
            Dictionary with source information
        """
        repo_info = self.parser.parse(source)
        
        info = {
            'type': 'git',
            'provider': repo_info['provider'],
            'owner': repo_info['owner'],
            'repo': repo_info['repo'],
            'protocol': repo_info['protocol'],
            'url': source
        }
        
        # Add branch/tag/commit if specified
        for ref_type in ['branch', 'tag', 'commit']:
            if repo_info.get(ref_type):
                info[ref_type] = repo_info[ref_type]
        
        # Add path if specified
        if repo_info.get('path'):
            info['path'] = repo_info['path']
        
        return info