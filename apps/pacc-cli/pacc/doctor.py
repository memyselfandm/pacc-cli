"""Doctor module for PACC - diagnostics and auto-fix for Claude Code environments.

Performs health checks on the Claude Code environment including configuration
files, MCP servers, hooks, plugins, fragments, and system dependencies.
Can automatically fix common issues when run with fix=True.
"""

import json
import logging
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from . import __version__

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticCheck:
    """Result of a single diagnostic check."""

    name: str
    description: str
    status: str  # "pass", "warn", "fail"
    message: str
    fixable: bool = False
    fix_description: Optional[str] = None


@dataclass
class DoctorReport:
    """Aggregated report from all diagnostic checks."""

    checks: List[DiagnosticCheck]
    passed: int
    warned: int
    failed: int
    timestamp: str
    auto_fixed: int = 0


class Doctor:
    """Performs diagnostics on the Claude Code environment and can auto-fix issues.

    Inspects configuration files, MCP servers, hooks, plugins, fragments,
    system dependencies, and permissions. Provides actionable feedback and
    optional automatic remediation for common problems.
    """

    # Claude Code configuration paths
    USER_CLAUDE_DIR = Path.home() / ".claude"
    USER_SETTINGS = USER_CLAUDE_DIR / "settings.json"
    USER_CLAUDE_MD = Path.home() / "CLAUDE.md"
    GLOBAL_CONFIG = Path.home() / ".claude.json"

    def __init__(self, project_dir: Optional[Path] = None):
        """Initialize the Doctor with an optional project directory.

        Args:
            project_dir: Path to the project root. Defaults to cwd.
        """
        self.project_dir = project_dir or Path.cwd()
        self.project_claude_dir = self.project_dir / ".claude"
        self.project_settings = self.project_claude_dir / "settings.json"
        self.project_claude_md = self.project_dir / "CLAUDE.md"
        self.pacc_json = self.project_dir / "pacc.json"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_diagnostics(
        self, fix: bool = False, verbose: bool = False
    ) -> DoctorReport:
        """Run all diagnostic checks and return a report.

        Args:
            fix: If True, attempt to auto-fix fixable issues.
            verbose: If True, include extra detail in check messages.

        Returns:
            A DoctorReport summarising every check.
        """
        check_methods = [
            self.check_claude_code_installed,
            self.check_config_files,
            self.check_mcp_servers,
            self.check_hooks_config,
            self.check_plugins_enabled,
            self.check_plugins_health,
            self.check_fragments_integrity,
            self.check_stacks_sync,
            self.check_permissions,
            self.check_git_available,
            self.check_python_version,
            self.check_pacc_version,
        ]

        checks: List[DiagnosticCheck] = []
        auto_fixed = 0

        for method in check_methods:
            try:
                check = method()
            except Exception as exc:
                logger.debug("Check %s raised: %s", method.__name__, exc)
                check = DiagnosticCheck(
                    name=method.__name__.replace("check_", ""),
                    description="Unexpected error during check",
                    status="fail",
                    message=str(exc),
                )

            # Attempt auto-fix when requested
            if fix and check.status == "fail" and check.fixable:
                fixed = self._attempt_fix(check)
                if fixed:
                    auto_fixed += 1
                    check.status = "pass"
                    check.message = (
                        f"Auto-fixed: {check.fix_description or 'issue resolved'}"
                    )

            checks.append(check)

        passed = sum(1 for c in checks if c.status == "pass")
        warned = sum(1 for c in checks if c.status == "warn")
        failed = sum(1 for c in checks if c.status == "fail")

        return DoctorReport(
            checks=checks,
            passed=passed,
            warned=warned,
            failed=failed,
            timestamp=datetime.utcnow().isoformat(),
            auto_fixed=auto_fixed,
        )

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def check_claude_code_installed(self) -> DiagnosticCheck:
        """Verify the ``claude`` CLI is available on PATH."""
        name = "claude_code_installed"
        description = "Check that the claude CLI is available"

        claude_path = shutil.which("claude")
        if claude_path:
            return DiagnosticCheck(
                name=name,
                description=description,
                status="pass",
                message=f"claude CLI found at {claude_path}",
            )
        return DiagnosticCheck(
            name=name,
            description=description,
            status="fail",
            message="claude CLI not found on PATH",
        )

    def check_config_files(self) -> DiagnosticCheck:
        """Verify config.json and settings.json are valid JSON."""
        name = "config_files"
        description = "Validate Claude Code configuration files"

        issues: List[str] = []
        warnings: List[str] = []

        config_paths: Dict[str, Path] = {
            "global config (~/.claude.json)": self.GLOBAL_CONFIG,
            "user settings (~/.claude/settings.json)": self.USER_SETTINGS,
            "project settings (.claude/settings.json)": self.project_settings,
        }

        for label, path in config_paths.items():
            if not path.exists():
                warnings.append(f"{label} does not exist")
                continue
            try:
                text = path.read_text(encoding="utf-8")
                json.loads(text)
            except json.JSONDecodeError as exc:
                issues.append(f"{label} has invalid JSON: {exc}")
            except OSError as exc:
                issues.append(f"{label} could not be read: {exc}")

        if issues:
            return DiagnosticCheck(
                name=name,
                description=description,
                status="fail",
                message="; ".join(issues),
                fixable=True,
                fix_description="Attempt to repair invalid JSON config files",
            )
        if warnings:
            return DiagnosticCheck(
                name=name,
                description=description,
                status="warn",
                message="; ".join(warnings),
            )
        return DiagnosticCheck(
            name=name,
            description=description,
            status="pass",
            message="All configuration files are valid JSON",
        )

    def check_mcp_servers(self) -> DiagnosticCheck:
        """Verify configured MCP servers have valid executables."""
        name = "mcp_servers"
        description = "Verify MCP server executables are available"

        settings_paths = [self.USER_SETTINGS, self.project_settings]
        servers_checked = 0
        missing: List[str] = []

        for settings_path in settings_paths:
            if not settings_path.exists():
                continue
            try:
                data = json.loads(settings_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            mcp_servers = data.get("mcpServers", {})
            for server_name, server_cfg in mcp_servers.items():
                if not isinstance(server_cfg, dict):
                    continue
                command = server_cfg.get("command")
                if not command:
                    continue
                servers_checked += 1
                if not shutil.which(command):
                    # The command may be a path
                    if not Path(command).is_file():
                        missing.append(
                            f"{server_name}: executable '{command}' not found"
                        )

        if missing:
            return DiagnosticCheck(
                name=name,
                description=description,
                status="fail",
                message="; ".join(missing),
            )
        if servers_checked == 0:
            return DiagnosticCheck(
                name=name,
                description=description,
                status="warn",
                message="No MCP servers configured",
            )
        return DiagnosticCheck(
            name=name,
            description=description,
            status="pass",
            message=f"All {servers_checked} MCP server executable(s) found",
        )

    def check_hooks_config(self) -> DiagnosticCheck:
        """Verify hooks configuration is valid."""
        name = "hooks_config"
        description = "Validate hooks configuration"

        valid_events = {"PreToolUse", "PostToolUse", "Notification", "Stop"}
        issues: List[str] = []
        hooks_found = 0

        settings_paths = [self.USER_SETTINGS, self.project_settings]
        for settings_path in settings_paths:
            if not settings_path.exists():
                continue
            try:
                data = json.loads(settings_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            hooks = data.get("hooks", {})
            if not isinstance(hooks, dict):
                issues.append(
                    f"{settings_path.name}: 'hooks' should be an object"
                )
                continue

            for event_type, hook_list in hooks.items():
                if event_type not in valid_events:
                    issues.append(
                        f"{settings_path.name}: unknown hook event '{event_type}'"
                    )
                if not isinstance(hook_list, list):
                    issues.append(
                        f"{settings_path.name}: hooks['{event_type}'] should be a list"
                    )
                    continue
                for idx, hook in enumerate(hook_list):
                    hooks_found += 1
                    if not isinstance(hook, dict):
                        issues.append(
                            f"{settings_path.name}: hooks['{event_type}'][{idx}] "
                            "should be an object"
                        )
                        continue
                    if "command" not in hook:
                        issues.append(
                            f"{settings_path.name}: hooks['{event_type}'][{idx}] "
                            "missing 'command'"
                        )

        if issues:
            return DiagnosticCheck(
                name=name,
                description=description,
                status="fail",
                message="; ".join(issues),
            )
        if hooks_found == 0:
            return DiagnosticCheck(
                name=name,
                description=description,
                status="warn",
                message="No hooks configured",
            )
        return DiagnosticCheck(
            name=name,
            description=description,
            status="pass",
            message=f"{hooks_found} hook(s) validated successfully",
        )

    def check_plugins_enabled(self) -> DiagnosticCheck:
        """Check whether the ENABLE_PLUGINS environment variable is set."""
        name = "plugins_enabled"
        description = "Check ENABLE_PLUGINS environment variable"

        value = os.environ.get("ENABLE_PLUGINS")
        if value and value.strip() not in ("0", "false", "no", ""):
            return DiagnosticCheck(
                name=name,
                description=description,
                status="pass",
                message=f"ENABLE_PLUGINS={value}",
            )
        return DiagnosticCheck(
            name=name,
            description=description,
            status="fail",
            message="ENABLE_PLUGINS is not set or is disabled",
            fixable=True,
            fix_description="Set ENABLE_PLUGINS=1 in the current environment",
        )

    def check_plugins_health(self) -> DiagnosticCheck:
        """Verify installed plugins are intact.

        Looks at pacc.json (if present) and checks each plugin directory
        exists and contains a manifest (plugin.json or pacc-plugin.json).
        """
        name = "plugins_health"
        description = "Verify installed plugins are intact"

        if not self.pacc_json.exists():
            return DiagnosticCheck(
                name=name,
                description=description,
                status="warn",
                message="No pacc.json found; skipping plugin health check",
            )

        try:
            pacc_data = json.loads(self.pacc_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return DiagnosticCheck(
                name=name,
                description=description,
                status="fail",
                message=f"Cannot read pacc.json: {exc}",
            )

        plugins = pacc_data.get("plugins", {})
        if not plugins:
            return DiagnosticCheck(
                name=name,
                description=description,
                status="pass",
                message="No plugins listed in pacc.json",
            )

        broken: List[str] = []
        healthy = 0
        plugins_dir = self.project_claude_dir / "pacc" / "plugins"

        for plugin_name, plugin_info in plugins.items():
            plugin_path = plugins_dir / plugin_name
            if not plugin_path.is_dir():
                broken.append(f"{plugin_name}: directory missing")
                continue
            manifest_found = (
                (plugin_path / "plugin.json").exists()
                or (plugin_path / "pacc-plugin.json").exists()
            )
            if not manifest_found:
                broken.append(f"{plugin_name}: manifest file missing")
                continue
            healthy += 1

        if broken:
            return DiagnosticCheck(
                name=name,
                description=description,
                status="fail",
                message=f"{len(broken)} plugin(s) broken: " + "; ".join(broken),
            )
        return DiagnosticCheck(
            name=name,
            description=description,
            status="pass",
            message=f"{healthy} plugin(s) healthy",
        )

    def check_fragments_integrity(self) -> DiagnosticCheck:
        """Verify CLAUDE.md fragment references match installed fragments."""
        name = "fragments_integrity"
        description = "Verify CLAUDE.md fragment references"

        claude_md_paths = [self.USER_CLAUDE_MD, self.project_claude_md]
        issues: List[str] = []
        refs_checked = 0

        fragment_ref_pattern = re.compile(
            r"^@(.+?)\s*-\s*.*$", re.MULTILINE
        )

        for md_path in claude_md_paths:
            if not md_path.exists():
                continue
            try:
                content = md_path.read_text(encoding="utf-8")
            except OSError:
                continue

            for match in fragment_ref_pattern.finditer(content):
                ref_path_str = match.group(1).strip()
                refs_checked += 1
                # Resolve relative to the directory containing CLAUDE.md
                ref_path = md_path.parent / ref_path_str
                if not ref_path.exists():
                    issues.append(
                        f"{md_path.name}: reference '{ref_path_str}' not found"
                    )

        if issues:
            return DiagnosticCheck(
                name=name,
                description=description,
                status="fail",
                message="; ".join(issues),
                fixable=True,
                fix_description=(
                    "Remove broken fragment references from CLAUDE.md"
                ),
            )
        if refs_checked == 0:
            return DiagnosticCheck(
                name=name,
                description=description,
                status="pass",
                message="No fragment references found",
            )
        return DiagnosticCheck(
            name=name,
            description=description,
            status="pass",
            message=f"{refs_checked} fragment reference(s) verified",
        )

    def check_stacks_sync(self) -> DiagnosticCheck:
        """Check if stacks are in sync with pacc.json."""
        name = "stacks_sync"
        description = "Check stack synchronisation with pacc.json"

        if not self.pacc_json.exists():
            return DiagnosticCheck(
                name=name,
                description=description,
                status="warn",
                message="No pacc.json found; nothing to sync",
            )

        try:
            pacc_data = json.loads(self.pacc_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return DiagnosticCheck(
                name=name,
                description=description,
                status="fail",
                message=f"Cannot read pacc.json: {exc}",
            )

        stacks = pacc_data.get("stacks", {})
        if not stacks:
            return DiagnosticCheck(
                name=name,
                description=description,
                status="pass",
                message="No stacks defined in pacc.json",
            )

        # Check that referenced plugin names in stacks actually exist
        plugins = pacc_data.get("plugins", {})
        missing: List[str] = []
        for stack_name, stack_info in stacks.items():
            stack_plugins = []
            if isinstance(stack_info, dict):
                stack_plugins = stack_info.get("plugins", [])
            elif isinstance(stack_info, list):
                stack_plugins = stack_info
            for pname in stack_plugins:
                if pname not in plugins:
                    missing.append(
                        f"stack '{stack_name}': plugin '{pname}' not in plugins"
                    )

        if missing:
            return DiagnosticCheck(
                name=name,
                description=description,
                status="fail",
                message="; ".join(missing),
            )
        return DiagnosticCheck(
            name=name,
            description=description,
            status="pass",
            message=f"{len(stacks)} stack(s) in sync",
        )

    def check_permissions(self) -> DiagnosticCheck:
        """Verify file permissions on the .claude directory."""
        name = "permissions"
        description = "Check .claude directory permissions"

        issues: List[str] = []

        for claude_dir in [self.USER_CLAUDE_DIR, self.project_claude_dir]:
            if not claude_dir.exists():
                continue

            # On non-Windows systems, check for overly permissive dirs
            if platform.system() != "Windows":
                try:
                    dir_stat = claude_dir.stat()
                    mode = dir_stat.st_mode
                    # Warn if world-writable
                    if mode & stat.S_IWOTH:
                        issues.append(
                            f"{claude_dir} is world-writable (mode "
                            f"{oct(mode & 0o777)})"
                        )
                except OSError as exc:
                    issues.append(f"Cannot stat {claude_dir}: {exc}")

            # Check that key files are readable
            for child_name in ["settings.json"]:
                child = claude_dir / child_name
                if child.exists() and not os.access(child, os.R_OK):
                    issues.append(f"{child} is not readable")

        if issues:
            return DiagnosticCheck(
                name=name,
                description=description,
                status="fail",
                message="; ".join(issues),
                fixable=True,
                fix_description="Fix permissions on .claude directory (chmod 700)",
            )
        return DiagnosticCheck(
            name=name,
            description=description,
            status="pass",
            message="Permissions look good",
        )

    def check_git_available(self) -> DiagnosticCheck:
        """Verify git is available for plugin operations."""
        name = "git_available"
        description = "Check that git is available"

        git_path = shutil.which("git")
        if not git_path:
            return DiagnosticCheck(
                name=name,
                description=description,
                status="fail",
                message="git not found on PATH; plugin operations require git",
            )

        # Optionally grab version
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            version_str = result.stdout.strip()
        except Exception:
            version_str = "unknown version"

        return DiagnosticCheck(
            name=name,
            description=description,
            status="pass",
            message=f"git available ({version_str})",
        )

    def check_python_version(self) -> DiagnosticCheck:
        """Verify Python version is 3.8+."""
        name = "python_version"
        description = "Check Python version compatibility"

        major, minor = sys.version_info[:2]
        version_str = platform.python_version()

        if (major, minor) < (3, 8):
            return DiagnosticCheck(
                name=name,
                description=description,
                status="fail",
                message=(
                    f"Python {version_str} detected; PACC requires Python 3.8+"
                ),
            )
        if (major, minor) < (3, 10):
            return DiagnosticCheck(
                name=name,
                description=description,
                status="warn",
                message=(
                    f"Python {version_str} is supported but 3.10+ is recommended"
                ),
            )
        return DiagnosticCheck(
            name=name,
            description=description,
            status="pass",
            message=f"Python {version_str}",
        )

    def check_pacc_version(self) -> DiagnosticCheck:
        """Report the current PACC version."""
        name = "pacc_version"
        description = "Check PACC version"

        return DiagnosticCheck(
            name=name,
            description=description,
            status="pass",
            message=f"PACC version {__version__}",
        )

    # ------------------------------------------------------------------
    # Auto-fix helpers
    # ------------------------------------------------------------------

    def _attempt_fix(self, check: DiagnosticCheck) -> bool:
        """Dispatch auto-fix for the given check.

        Returns True if the fix succeeded.
        """
        fix_dispatch: Dict[str, callable] = {
            "config_files": self._fix_config_files,
            "plugins_enabled": self._fix_plugins_enabled,
            "permissions": self._fix_permissions,
            "fragments_integrity": self._fix_fragments,
        }
        fixer = fix_dispatch.get(check.name)
        if fixer is None:
            return False
        try:
            return fixer()
        except Exception as exc:
            logger.warning("Auto-fix for %s failed: %s", check.name, exc)
            return False

    def _fix_config_files(self) -> bool:
        """Attempt to repair invalid JSON configuration files.

        Tries common fixes: stripping trailing commas, stripping BOM,
        and falling back to writing an empty JSON object if all else fails.
        """
        config_paths = [
            self.GLOBAL_CONFIG,
            self.USER_SETTINGS,
            self.project_settings,
        ]
        any_fixed = False

        for path in config_paths:
            if not path.exists():
                continue
            try:
                text = path.read_text(encoding="utf-8")
                json.loads(text)
                continue  # already valid
            except json.JSONDecodeError:
                pass
            except OSError:
                continue

            # Create backup before modifying
            backup_path = path.with_suffix(path.suffix + ".bak")
            try:
                shutil.copy2(str(path), str(backup_path))
            except OSError:
                continue

            fixed = False
            # Attempt 1: strip BOM and trailing commas
            cleaned = text.lstrip("\ufeff")
            # Remove trailing commas before } or ]
            cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
            try:
                json.loads(cleaned)
                path.write_text(cleaned, encoding="utf-8")
                fixed = True
            except (json.JSONDecodeError, OSError):
                pass

            # Attempt 2: write empty object as last resort
            if not fixed:
                try:
                    path.write_text("{}\n", encoding="utf-8")
                    fixed = True
                except OSError:
                    pass

            if fixed:
                any_fixed = True
                logger.info("Repaired %s (backup at %s)", path, backup_path)

        return any_fixed

    def _fix_plugins_enabled(self) -> bool:
        """Set ENABLE_PLUGINS=1 in the current process environment."""
        os.environ["ENABLE_PLUGINS"] = "1"
        return True

    def _fix_permissions(self) -> bool:
        """Fix permissions on .claude directories (Unix only)."""
        if platform.system() == "Windows":
            return False

        any_fixed = False
        for claude_dir in [self.USER_CLAUDE_DIR, self.project_claude_dir]:
            if not claude_dir.exists():
                continue
            try:
                current = claude_dir.stat().st_mode
                if current & stat.S_IWOTH:
                    claude_dir.chmod(0o700)
                    any_fixed = True
            except OSError:
                pass
        return any_fixed

    def _fix_fragments(self) -> bool:
        """Remove broken fragment references from CLAUDE.md files."""
        fragment_ref_pattern = re.compile(
            r"^@(.+?)\s*-\s*.*$", re.MULTILINE
        )
        any_fixed = False

        for md_path in [self.USER_CLAUDE_MD, self.project_claude_md]:
            if not md_path.exists():
                continue
            try:
                content = md_path.read_text(encoding="utf-8")
            except OSError:
                continue

            lines_to_remove: List[str] = []
            for match in fragment_ref_pattern.finditer(content):
                ref_path_str = match.group(1).strip()
                ref_path = md_path.parent / ref_path_str
                if not ref_path.exists():
                    lines_to_remove.append(match.group(0))

            if not lines_to_remove:
                continue

            # Backup
            backup_path = md_path.with_suffix(md_path.suffix + ".bak")
            try:
                shutil.copy2(str(md_path), str(backup_path))
            except OSError:
                continue

            new_content = content
            for line in lines_to_remove:
                new_content = new_content.replace(line + "\n", "")
                new_content = new_content.replace(line, "")

            try:
                md_path.write_text(new_content, encoding="utf-8")
                any_fixed = True
                logger.info(
                    "Removed %d broken reference(s) from %s",
                    len(lines_to_remove),
                    md_path,
                )
            except OSError:
                pass

        return any_fixed
