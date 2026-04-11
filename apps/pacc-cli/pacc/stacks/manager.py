"""Stack management for Claude Code environments.

A stack is a Git repository containing a ``stack.yaml`` manifest that bundles
MCP servers, hooks, commands, agents, settings, and fragments into one
shareable, version-controlled unit.

Key design goals:
- **Idempotent**: ``sync_stacks()`` always converges to the desired state.
- **Safe**: timestamped backups before every config modification.
- **Lockable**: generates ``pacc.lock.yaml`` pinning exact git commits.
- **Clean**: removed stacks leave zero orphaned artefacts.
"""

import hashlib
import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# YAML helpers (optional dependency)
# ---------------------------------------------------------------------------

import yaml  # PyYAML is a required dependency (see pyproject.toml)


def _yaml_safe_load(text: str) -> Any:
    return yaml.safe_load(text)


def _yaml_safe_dump(data: Any) -> str:
    return yaml.safe_dump(data, default_flow_style=False, sort_keys=False)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class StackError(Exception):
    """Raised for stack-related errors."""


@dataclass
class StackManifest:
    """Parsed ``stack.yaml`` manifest."""

    name: str
    version: str
    description: str = ""
    author: str = ""
    mcp_servers: Dict[str, Any] = field(default_factory=dict)
    hooks: Dict[str, Any] = field(default_factory=dict)
    commands: List[Dict[str, str]] = field(default_factory=list)
    agents: List[Dict[str, str]] = field(default_factory=list)
    settings: Dict[str, Any] = field(default_factory=dict)
    fragments: List[Dict[str, str]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StackManifest":
        if "name" not in data:
            raise StackError("stack.yaml is missing required field 'name'")
        if "version" not in data:
            raise StackError("stack.yaml is missing required field 'version'")
        return cls(
            name=data["name"],
            version=str(data["version"]),
            description=data.get("description", ""),
            author=data.get("author", ""),
            mcp_servers=data.get("mcp_servers", {}),
            hooks=data.get("hooks", {}),
            commands=data.get("commands", []),
            agents=data.get("agents", []),
            settings=data.get("settings", {}),
            fragments=data.get("fragments", []),
        )

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"name": self.name, "version": self.version}
        if self.description:
            d["description"] = self.description
        if self.author:
            d["author"] = self.author
        if self.mcp_servers:
            d["mcp_servers"] = self.mcp_servers
        if self.hooks:
            d["hooks"] = self.hooks
        if self.commands:
            d["commands"] = self.commands
        if self.agents:
            d["agents"] = self.agents
        if self.settings:
            d["settings"] = self.settings
        if self.fragments:
            d["fragments"] = self.fragments
        return d


@dataclass
class StackInfo:
    """Metadata about an installed stack."""

    name: str
    version: str
    description: str
    author: str
    source: str  # Git URL or local path
    scope: str  # "project" or "user"
    commit: str = ""
    sha256: str = ""
    installed_at: str = ""
    manifest: Optional[StackManifest] = None
    components: Dict[str, int] = field(default_factory=dict)


@dataclass
class StackResult:
    """Result of a stack operation."""

    success: bool
    message: str
    stack_name: str = ""
    changes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    message: str
    added: int = 0
    removed: int = 0
    updated: int = 0
    unchanged: int = 0
    errors: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stack Manager
# ---------------------------------------------------------------------------


class StackManager:
    """Manages stack lifecycle: install, sync, remove, export."""

    STACKS_DIR_NAME = "pacc/stacks"
    LOCK_FILE = "pacc.lock.yaml"
    MANIFEST_FILE = "stack.yaml"

    def __init__(self, project_dir: Optional[Path] = None):
        self.project_dir = project_dir or Path.cwd()
        self.user_claude_dir = Path.home() / ".claude"

    # ----- path helpers ----------------------------------------------------

    def _stacks_dir(self, scope: str) -> Path:
        base = self.user_claude_dir if scope == "user" else (self.project_dir / ".claude")
        return base / self.STACKS_DIR_NAME

    def _settings_path(self, scope: str) -> Path:
        base = self.user_claude_dir if scope == "user" else (self.project_dir / ".claude")
        return base / "settings.json"

    def _pacc_json_path(self) -> Path:
        return self.project_dir / "pacc.json"

    def _lock_path(self) -> Path:
        return self.project_dir / self.LOCK_FILE

    # ----- public API -------------------------------------------------------

    def install_stack(
        self,
        source: str,
        scope: str = "project",
        dry_run: bool = False,
    ) -> StackResult:
        """Install a stack from a Git repository or local path.

        Args:
            source: Git URL or local directory path containing stack.yaml.
            scope: ``"project"`` or ``"user"``.
            dry_run: If True, preview changes without applying.

        Returns:
            StackResult describing what happened.
        """
        changes: List[str] = []
        warnings: List[str] = []

        # 1. Resolve source -------------------------------------------------
        source_dir, commit_sha, is_temp = self._resolve_source(source)
        try:
            manifest = self._load_manifest(source_dir)
        except StackError as exc:
            return StackResult(success=False, message=str(exc))

        stack_name = manifest.name
        dest = self._stacks_dir(scope) / stack_name

        if dry_run:
            return self._dry_run_report(manifest, scope)

        # 2. Create destination directory -----------------------------------
        dest.mkdir(parents=True, exist_ok=True)

        # 3. Backup existing settings before modifying ----------------------
        settings_path = self._settings_path(scope)
        self._backup(settings_path)

        # 4. Apply each section of the manifest -----------------------------
        settings = self._read_json(settings_path)

        # MCP servers
        if manifest.mcp_servers:
            mcp = settings.setdefault("mcpServers", {})
            for name, cfg in manifest.mcp_servers.items():
                mcp[name] = cfg
                changes.append(f"Added MCP server: {name}")

        # Hooks
        if manifest.hooks:
            hooks = settings.setdefault("hooks", {})
            for event, hook_list in manifest.hooks.items():
                existing = hooks.setdefault(event, [])
                if isinstance(hook_list, list):
                    existing.extend(hook_list)
                else:
                    existing.append(hook_list)
                changes.append(f"Added hooks for event: {event}")

        # Settings (merge)
        if manifest.settings:
            for key, value in manifest.settings.items():
                if key not in ("mcpServers", "hooks"):
                    settings[key] = value
                    changes.append(f"Set setting: {key}")

        # Write updated settings
        self._write_json(settings_path, settings)

        # Commands - copy to .claude/commands/
        base = self.user_claude_dir if scope == "user" else (self.project_dir / ".claude")
        if manifest.commands:
            cmds_dir = base / "commands"
            cmds_dir.mkdir(parents=True, exist_ok=True)
            for cmd in manifest.commands:
                src_file = source_dir / cmd.get("source", "")
                cmd_name = cmd.get("name", src_file.stem)
                if src_file.exists():
                    dst = cmds_dir / src_file.name
                    shutil.copy2(str(src_file), str(dst))
                    changes.append(f"Installed command: {cmd_name}")
                else:
                    warnings.append(f"Command source not found: {cmd.get('source')}")

        # Agents - copy to .claude/agents/
        if manifest.agents:
            agents_dir = base / "agents"
            agents_dir.mkdir(parents=True, exist_ok=True)
            for agent in manifest.agents:
                src_file = source_dir / agent.get("source", "")
                agent_name = agent.get("name", src_file.stem)
                if src_file.exists():
                    dst = agents_dir / src_file.name
                    shutil.copy2(str(src_file), str(dst))
                    changes.append(f"Installed agent: {agent_name}")
                else:
                    warnings.append(f"Agent source not found: {agent.get('source')}")

        # Fragments - copy to .claude/pacc/fragments/
        if manifest.fragments:
            frags_dir = base / "pacc" / "fragments"
            frags_dir.mkdir(parents=True, exist_ok=True)
            for frag in manifest.fragments:
                src_file = source_dir / frag.get("source", "")
                frag_name = frag.get("name", src_file.stem)
                if src_file.exists():
                    dst = frags_dir / src_file.name
                    shutil.copy2(str(src_file), str(dst))
                    changes.append(f"Installed fragment: {frag_name}")
                else:
                    warnings.append(f"Fragment source not found: {frag.get('source')}")

        # 5. Save stack metadata ---------------------------------------------
        sha = self._compute_sha256(source_dir)
        info = StackInfo(
            name=stack_name,
            version=manifest.version,
            description=manifest.description,
            author=manifest.author,
            source=source,
            scope=scope,
            commit=commit_sha,
            sha256=sha,
            installed_at=datetime.now(timezone.utc).isoformat(),
            components={
                "mcp_servers": len(manifest.mcp_servers),
                "hooks": sum(
                    len(v) if isinstance(v, list) else 1
                    for v in manifest.hooks.values()
                ),
                "commands": len(manifest.commands),
                "agents": len(manifest.agents),
                "settings": len(manifest.settings),
                "fragments": len(manifest.fragments),
            },
        )
        self._save_stack_info(dest, info, manifest)

        # 6. Update lockfile --------------------------------------------------
        self._update_lockfile(stack_name, source, commit_sha, sha)

        # 7. Update pacc.json ------------------------------------------------
        self._update_pacc_json(stack_name, source, manifest.version, scope)

        # Cleanup temp
        if is_temp and source_dir.exists():
            shutil.rmtree(str(source_dir), ignore_errors=True)

        return StackResult(
            success=True,
            message=f"Stack '{stack_name}' installed successfully ({len(changes)} changes)",
            stack_name=stack_name,
            changes=changes,
            warnings=warnings,
        )

    def list_stacks(self, scope: Optional[str] = None) -> List[StackInfo]:
        """List installed stacks.

        Args:
            scope: Filter by ``"project"`` or ``"user"``. None returns both.

        Returns:
            List of StackInfo objects.
        """
        stacks: List[StackInfo] = []
        scopes = [scope] if scope else ["project", "user"]

        for s in scopes:
            stacks_dir = self._stacks_dir(s)
            if not stacks_dir.exists():
                continue
            for child in sorted(stacks_dir.iterdir()):
                if not child.is_dir():
                    continue
                info = self._load_stack_info(child, s)
                if info:
                    stacks.append(info)

        return stacks

    def info_stack(self, name: str) -> Optional[StackInfo]:
        """Get detailed information about an installed stack."""
        for scope in ("project", "user"):
            stack_dir = self._stacks_dir(scope) / name
            if stack_dir.is_dir():
                return self._load_stack_info(stack_dir, scope)
        return None

    def remove_stack(
        self,
        name: str,
        scope: str = "project",
        dry_run: bool = False,
    ) -> StackResult:
        """Remove a stack and all its installed components.

        Args:
            name: Stack name to remove.
            scope: ``"project"`` or ``"user"``.
            dry_run: Preview-only mode.

        Returns:
            StackResult.
        """
        stack_dir = self._stacks_dir(scope) / name
        if not stack_dir.is_dir():
            return StackResult(
                success=False,
                message=f"Stack '{name}' not found in {scope} scope",
                stack_name=name,
            )

        info = self._load_stack_info(stack_dir, scope)
        changes: List[str] = []

        if dry_run:
            changes.append(f"Would remove stack directory: {stack_dir}")
            if info and info.manifest:
                m = info.manifest
                for srv in m.mcp_servers:
                    changes.append(f"Would remove MCP server: {srv}")
                for event in m.hooks:
                    changes.append(f"Would remove hooks for: {event}")
            return StackResult(
                success=True,
                message=f"Dry run: would remove stack '{name}'",
                stack_name=name,
                changes=changes,
            )

        # Backup settings before touching
        settings_path = self._settings_path(scope)
        self._backup(settings_path)

        # Remove stack components from settings
        if info and info.manifest:
            settings = self._read_json(settings_path)
            m = info.manifest

            # Remove MCP servers
            mcp = settings.get("mcpServers", {})
            for srv_name in m.mcp_servers:
                if srv_name in mcp:
                    del mcp[srv_name]
                    changes.append(f"Removed MCP server: {srv_name}")

            # Remove hooks (best-effort)
            hooks = settings.get("hooks", {})
            for event in m.hooks:
                if event in hooks:
                    del hooks[event]
                    changes.append(f"Removed hooks for: {event}")

            # Remove settings keys
            for key in m.settings:
                if key in settings and key not in ("mcpServers", "hooks"):
                    del settings[key]
                    changes.append(f"Removed setting: {key}")

            self._write_json(settings_path, settings)

        # Remove stack directory
        shutil.rmtree(str(stack_dir), ignore_errors=True)
        changes.append(f"Removed stack directory")

        # Remove from lockfile
        self._remove_from_lockfile(name)

        # Remove from pacc.json
        self._remove_from_pacc_json(name)

        return StackResult(
            success=True,
            message=f"Stack '{name}' removed ({len(changes)} changes)",
            stack_name=name,
            changes=changes,
        )

    def sync_stacks(self, dry_run: bool = False) -> SyncResult:
        """Idempotent sync — converge to desired state from pacc.json.

        Installs missing stacks, removes stale ones, updates outdated ones.

        Args:
            dry_run: Preview-only mode.

        Returns:
            SyncResult.
        """
        pacc_json_path = self._pacc_json_path()
        if not pacc_json_path.exists():
            return SyncResult(
                success=True,
                message="No pacc.json found; nothing to sync",
            )

        try:
            pacc_data = json.loads(pacc_json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return SyncResult(success=False, message=f"Cannot read pacc.json: {exc}")

        desired_stacks = pacc_data.get("stacks", {})
        installed = {s.name: s for s in self.list_stacks()}

        added = 0
        removed = 0
        updated = 0
        unchanged = 0
        errors: List[str] = []

        # Install or update desired stacks
        for stack_key, stack_cfg in desired_stacks.items():
            if not isinstance(stack_cfg, dict):
                continue
            source = stack_cfg.get("source", stack_key)
            version = stack_cfg.get("version", "")
            scope = stack_cfg.get("scope", "project")
            stack_name = stack_key.split("/")[-1] if "/" in stack_key else stack_key

            if stack_name in installed:
                existing = installed[stack_name]
                if version and existing.version != version:
                    result = self.install_stack(source, scope, dry_run=dry_run)
                    if result.success:
                        updated += 1
                    else:
                        errors.append(f"Update {stack_name}: {result.message}")
                else:
                    unchanged += 1
            else:
                result = self.install_stack(source, scope, dry_run=dry_run)
                if result.success:
                    added += 1
                else:
                    errors.append(f"Install {stack_name}: {result.message}")

        # Remove stacks not in desired state
        desired_names = set()
        for stack_key in desired_stacks:
            desired_names.add(stack_key.split("/")[-1] if "/" in stack_key else stack_key)

        for name, info in installed.items():
            if name not in desired_names:
                result = self.remove_stack(name, info.scope, dry_run=dry_run)
                if result.success:
                    removed += 1
                else:
                    errors.append(f"Remove {name}: {result.message}")

        total = added + removed + updated
        msg = (
            f"Sync complete: {added} added, {updated} updated, "
            f"{removed} removed, {unchanged} unchanged"
        )
        if dry_run:
            msg = f"Dry run: {msg}"

        return SyncResult(
            success=len(errors) == 0,
            message=msg,
            added=added,
            removed=removed,
            updated=updated,
            unchanged=unchanged,
            errors=errors,
        )

    def export_stack(
        self,
        name: str,
        output_dir: str,
        include_settings: bool = True,
    ) -> StackResult:
        """Export the current Claude Code configuration as a reusable stack.

        Reads the current settings.json and generates a ``stack.yaml`` manifest
        in *output_dir*.

        Args:
            name: Name for the exported stack.
            output_dir: Destination directory for the stack files.
            include_settings: Whether to include non-MCP/hook settings.

        Returns:
            StackResult.
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        changes: List[str] = []

        # Read current settings
        settings = {}
        for scope in ("project", "user"):
            sp = self._settings_path(scope)
            if sp.exists():
                settings = self._read_json(sp)
                break

        manifest_data: Dict[str, Any] = {
            "name": name,
            "version": "1.0.0",
            "description": f"Exported from current Claude Code environment",
            "author": "",
        }

        # MCP servers
        mcp = settings.get("mcpServers", {})
        if mcp:
            manifest_data["mcp_servers"] = dict(mcp)
            changes.append(f"Exported {len(mcp)} MCP server(s)")

        # Hooks
        hooks = settings.get("hooks", {})
        if hooks:
            manifest_data["hooks"] = dict(hooks)
            changes.append(f"Exported hooks for {len(hooks)} event(s)")

        # Other settings
        if include_settings:
            other = {}
            for k, v in settings.items():
                if k not in ("mcpServers", "hooks"):
                    other[k] = v
            if other:
                manifest_data["settings"] = other
                changes.append(f"Exported {len(other)} setting(s)")

        # Commands - check for .claude/commands/
        for scope in ("project", "user"):
            base = self.user_claude_dir if scope == "user" else (self.project_dir / ".claude")
            cmds_dir = base / "commands"
            if cmds_dir.exists():
                exported_cmds_dir = out / "commands"
                exported_cmds_dir.mkdir(exist_ok=True)
                cmds = []
                for f in sorted(cmds_dir.iterdir()):
                    if f.is_file() and f.suffix == ".md":
                        shutil.copy2(str(f), str(exported_cmds_dir / f.name))
                        cmds.append({"source": f"./commands/{f.name}", "name": f.stem})
                if cmds:
                    manifest_data["commands"] = cmds
                    changes.append(f"Exported {len(cmds)} command(s)")
                break

        # Agents
        for scope in ("project", "user"):
            base = self.user_claude_dir if scope == "user" else (self.project_dir / ".claude")
            agents_dir = base / "agents"
            if agents_dir.exists():
                exported_agents_dir = out / "agents"
                exported_agents_dir.mkdir(exist_ok=True)
                agents = []
                for f in sorted(agents_dir.iterdir()):
                    if f.is_file() and f.suffix == ".md":
                        shutil.copy2(str(f), str(exported_agents_dir / f.name))
                        agents.append({"source": f"./agents/{f.name}", "name": f.stem})
                if agents:
                    manifest_data["agents"] = agents
                    changes.append(f"Exported {len(agents)} agent(s)")
                break

        # Write stack.yaml
        manifest_yaml = _yaml_safe_dump(manifest_data)
        (out / self.MANIFEST_FILE).write_text(manifest_yaml, encoding="utf-8")
        changes.append(f"Written {self.MANIFEST_FILE}")

        # Generate README.md
        readme = self._generate_stack_readme(manifest_data)
        (out / "README.md").write_text(readme, encoding="utf-8")
        changes.append("Generated README.md")

        return StackResult(
            success=True,
            message=f"Stack '{name}' exported to {out}",
            stack_name=name,
            changes=changes,
        )

    # ----- internal helpers ------------------------------------------------

    @staticmethod
    def _validate_source(source: str) -> None:
        """Validate a git URL or local path to prevent command injection.

        Raises:
            StackError: If the source looks malicious or invalid.
        """
        import re

        # Reject obviously dangerous input
        dangerous_chars = set(";|&$`\n\r")
        if dangerous_chars.intersection(source):
            raise StackError(
                f"Invalid source: contains shell metacharacters"
            )

        # Allow local paths
        if Path(source).is_dir():
            return

        # Validate as a git URL (HTTPS, SSH, or GitHub shorthand)
        git_url_patterns = [
            # HTTPS URLs
            r"^https?://[\w.\-]+/[\w.\-]+/[\w.\-]+(?:\.git)?/?$",
            # SSH URLs
            r"^git@[\w.\-]+:[\w.\-]+/[\w.\-]+(?:\.git)?$",
            # GitHub shorthand (owner/repo)
            r"^[\w.\-]+/[\w.\-]+$",
        ]
        if not any(re.match(p, source) for p in git_url_patterns):
            raise StackError(
                f"Invalid source URL: '{source}'. "
                "Expected HTTPS URL, SSH URL, or owner/repo shorthand."
            )

    def _resolve_source(self, source: str) -> Tuple[Path, str, bool]:
        """Resolve source to a local directory, commit SHA, and temp flag."""
        source_path = Path(source)
        if source_path.is_dir():
            commit = self._get_git_commit(source_path)
            return source_path, commit, False

        # Validate URL before passing to git
        self._validate_source(source)

        # Treat as Git URL
        import tempfile

        tmp = Path(tempfile.mkdtemp(prefix="pacc-stack-"))
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", source, str(tmp)],
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            shutil.rmtree(str(tmp), ignore_errors=True)
            raise StackError(f"Failed to clone '{source}': {exc.stderr.strip()}")
        except FileNotFoundError:
            shutil.rmtree(str(tmp), ignore_errors=True)
            raise StackError("git is not installed; cannot clone stack repository")

        commit = self._get_git_commit(tmp)
        return tmp, commit, True

    def _get_git_commit(self, repo_dir: Path) -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=str(repo_dir),
                timeout=10,
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            return ""

    def _load_manifest(self, source_dir: Path) -> StackManifest:
        manifest_path = source_dir / self.MANIFEST_FILE
        if not manifest_path.exists():
            raise StackError(f"No {self.MANIFEST_FILE} found in {source_dir}")
        text = manifest_path.read_text(encoding="utf-8")
        data = _yaml_safe_load(text)
        if not isinstance(data, dict):
            raise StackError(f"{self.MANIFEST_FILE} must be a YAML mapping")
        return StackManifest.from_dict(data)

    def _compute_sha256(self, directory: Path) -> str:
        h = hashlib.sha256()
        for f in sorted(directory.rglob("*")):
            if f.is_file() and ".git" not in f.parts:
                h.update(f.read_bytes())
        return h.hexdigest()

    def _backup(self, path: Path) -> Optional[Path]:
        if not path.exists():
            return None
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = path.with_suffix(f".{ts}.bak")
        try:
            shutil.copy2(str(path), str(backup))
            logger.debug("Backed up %s -> %s", path, backup)
            return backup
        except OSError as exc:
            logger.warning("Failed to backup %s: %s", path, exc)
            return None

    def _read_json(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_json(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )

    def _save_stack_info(
        self, dest: Path, info: StackInfo, manifest: StackManifest
    ) -> None:
        meta = {
            "name": info.name,
            "version": info.version,
            "description": info.description,
            "author": info.author,
            "source": info.source,
            "scope": info.scope,
            "commit": info.commit,
            "sha256": info.sha256,
            "installed_at": info.installed_at,
            "components": info.components,
        }
        self._write_json(dest / "stack.meta.json", meta)
        # Also save the original manifest
        manifest_yaml = _yaml_safe_dump(manifest.to_dict())
        (dest / self.MANIFEST_FILE).write_text(manifest_yaml, encoding="utf-8")

    def _load_stack_info(self, stack_dir: Path, scope: str) -> Optional[StackInfo]:
        meta_path = stack_dir / "stack.meta.json"
        if not meta_path.exists():
            return StackInfo(
                name=stack_dir.name,
                version="unknown",
                description="",
                author="",
                source="",
                scope=scope,
            )
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

        # Load manifest if available
        manifest = None
        manifest_path = stack_dir / self.MANIFEST_FILE
        if manifest_path.exists():
            try:
                mdata = _yaml_safe_load(manifest_path.read_text(encoding="utf-8"))
                manifest = StackManifest.from_dict(mdata)
            except Exception:
                pass

        return StackInfo(
            name=data.get("name", stack_dir.name),
            version=data.get("version", "unknown"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            source=data.get("source", ""),
            scope=scope,
            commit=data.get("commit", ""),
            sha256=data.get("sha256", ""),
            installed_at=data.get("installed_at", ""),
            manifest=manifest,
            components=data.get("components", {}),
        )

    # ----- lockfile management ----------------------------------------------

    def _update_lockfile(
        self, name: str, source: str, commit: str, sha256: str
    ) -> None:
        lock_path = self._lock_path()
        lock_data: Dict[str, Any] = {}
        if lock_path.exists():
            try:
                lock_data = _yaml_safe_load(lock_path.read_text(encoding="utf-8")) or {}
            except Exception:
                lock_data = {}

        stacks = lock_data.setdefault("stacks", {})
        stacks[name] = {
            "source": source,
            "commit": commit,
            "sha256": sha256,
            "locked_at": datetime.now(timezone.utc).isoformat(),
        }

        lock_path.write_text(_yaml_safe_dump(lock_data), encoding="utf-8")

    def _remove_from_lockfile(self, name: str) -> None:
        lock_path = self._lock_path()
        if not lock_path.exists():
            return
        try:
            lock_data = _yaml_safe_load(lock_path.read_text(encoding="utf-8")) or {}
        except Exception:
            return

        stacks = lock_data.get("stacks", {})
        if name in stacks:
            del stacks[name]
            lock_path.write_text(_yaml_safe_dump(lock_data), encoding="utf-8")

    # ----- pacc.json management ---------------------------------------------

    def _update_pacc_json(
        self, name: str, source: str, version: str, scope: str
    ) -> None:
        path = self._pacc_json_path()
        data = self._read_json(path)
        stacks = data.setdefault("stacks", {})
        stacks[name] = {
            "source": source,
            "version": version,
            "scope": scope,
        }
        self._write_json(path, data)

    def _remove_from_pacc_json(self, name: str) -> None:
        path = self._pacc_json_path()
        if not path.exists():
            return
        data = self._read_json(path)
        stacks = data.get("stacks", {})
        if name in stacks:
            del stacks[name]
            self._write_json(path, data)

    # ----- dry run ----------------------------------------------------------

    def _dry_run_report(self, manifest: StackManifest, scope: str) -> StackResult:
        changes: List[str] = []
        for name in manifest.mcp_servers:
            changes.append(f"Would add MCP server: {name}")
        for event in manifest.hooks:
            changes.append(f"Would add hooks for: {event}")
        for cmd in manifest.commands:
            changes.append(f"Would install command: {cmd.get('name', '?')}")
        for agent in manifest.agents:
            changes.append(f"Would install agent: {agent.get('name', '?')}")
        for frag in manifest.fragments:
            changes.append(f"Would install fragment: {frag.get('name', '?')}")
        for key in manifest.settings:
            if key not in ("mcpServers", "hooks"):
                changes.append(f"Would set setting: {key}")
        return StackResult(
            success=True,
            message=f"Dry run: stack '{manifest.name}' would install {len(changes)} components",
            stack_name=manifest.name,
            changes=changes,
        )

    # ----- README generation ------------------------------------------------

    def _generate_stack_readme(self, manifest_data: Dict[str, Any]) -> str:
        name = manifest_data.get("name", "my-stack")
        desc = manifest_data.get("description", "")
        lines = [
            f"# {name}",
            "",
            desc,
            "",
            "## Installation",
            "",
            "```bash",
            "pacc stack install <this-repo-url>",
            "```",
            "",
            "## Contents",
            "",
        ]
        if manifest_data.get("mcp_servers"):
            lines.append(f"- **MCP Servers**: {', '.join(manifest_data['mcp_servers'].keys())}")
        if manifest_data.get("hooks"):
            lines.append(f"- **Hooks**: {', '.join(manifest_data['hooks'].keys())}")
        if manifest_data.get("commands"):
            names = [c.get("name", "?") for c in manifest_data["commands"]]
            lines.append(f"- **Commands**: {', '.join(names)}")
        if manifest_data.get("agents"):
            names = [a.get("name", "?") for a in manifest_data["agents"]]
            lines.append(f"- **Agents**: {', '.join(names)}")
        if manifest_data.get("fragments"):
            names = [f.get("name", "?") for f in manifest_data["fragments"]]
            lines.append(f"- **Fragments**: {', '.join(names)}")
        if manifest_data.get("settings"):
            lines.append(f"- **Settings**: {len(manifest_data['settings'])} configured")
        lines.extend([
            "",
            "## Requirements",
            "",
            "- [PACC CLI](https://github.com/memyselfandm/pacc-cli) (`pip install pacc-cli`)",
            "- Claude Code",
            "",
            "---",
            f"*Generated by PACC v{self._get_pacc_version()}*",
        ])
        return "\n".join(lines) + "\n"

    def _get_pacc_version(self) -> str:
        try:
            from pacc import __version__
            return __version__
        except ImportError:
            return "unknown"
