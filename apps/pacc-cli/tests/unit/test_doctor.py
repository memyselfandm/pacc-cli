"""Unit tests for pacc.doctor module."""

import json
import os
import platform
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pacc.doctor import DiagnosticCheck, Doctor, DoctorReport


class TestDiagnosticCheck:
    """Test DiagnosticCheck dataclass."""

    def test_basic_creation(self):
        check = DiagnosticCheck(
            name="test_check",
            description="A test check",
            status="pass",
            message="All good",
        )
        assert check.name == "test_check"
        assert check.status == "pass"
        assert check.fixable is False

    def test_fixable_check(self):
        check = DiagnosticCheck(
            name="fixable",
            description="A fixable issue",
            status="fail",
            message="Something broke",
            fixable=True,
            fix_description="Run the fix command",
        )
        assert check.fixable is True
        assert check.fix_description == "Run the fix command"


class TestDoctorReport:
    """Test DoctorReport dataclass."""

    def test_report_creation(self):
        checks = [
            DiagnosticCheck(name="a", description="a", status="pass", message="ok"),
            DiagnosticCheck(name="b", description="b", status="warn", message="meh"),
            DiagnosticCheck(name="c", description="c", status="fail", message="bad"),
        ]
        report = DoctorReport(
            checks=checks, passed=1, warned=1, failed=1, timestamp="2026-01-01T00:00:00"
        )
        assert report.passed == 1
        assert report.warned == 1
        assert report.failed == 1
        assert report.auto_fixed == 0
        assert len(report.checks) == 3


class TestDoctorChecks:
    """Test individual Doctor diagnostic checks."""

    @pytest.fixture
    def doctor(self, temp_dir):
        """Create a Doctor instance pointed at a temp project directory."""
        return Doctor(project_dir=temp_dir)

    def test_check_git_available(self, doctor):
        """git should be available in test environments."""
        result = doctor.check_git_available()
        assert result.status == "pass"
        assert "git" in result.message.lower()

    def test_check_git_not_available(self, doctor):
        with patch("shutil.which", return_value=None):
            result = doctor.check_git_available()
            assert result.status == "fail"

    def test_check_python_version(self, doctor):
        result = doctor.check_python_version()
        # We're running on 3.8+ so this should pass or warn
        assert result.status in ("pass", "warn")

    def test_check_pacc_version(self, doctor):
        result = doctor.check_pacc_version()
        assert result.status == "pass"
        assert "1.2.0" in result.message

    def test_check_config_files_no_files(self, doctor):
        """No config files = warnings, not failures."""
        result = doctor.check_config_files()
        # With fresh temp dir, no config files exist -> warnings
        assert result.status in ("pass", "warn")

    def test_check_config_files_valid_json(self, doctor, temp_dir):
        """Valid JSON files pass."""
        settings_dir = temp_dir / ".claude"
        settings_dir.mkdir(parents=True)
        (settings_dir / "settings.json").write_text('{"model": "sonnet"}')
        result = doctor.check_config_files()
        # Project settings now valid, others may warn
        assert result.status in ("pass", "warn")

    def test_check_config_files_invalid_json(self, doctor, temp_dir):
        """Invalid JSON files should fail."""
        settings_dir = temp_dir / ".claude"
        settings_dir.mkdir(parents=True)
        (settings_dir / "settings.json").write_text("{invalid json")
        result = doctor.check_config_files()
        assert result.status == "fail"
        assert result.fixable is True

    def test_check_hooks_config_no_hooks(self, doctor, temp_dir):
        """No hooks configured = warning (when user settings also empty)."""
        settings_dir = temp_dir / ".claude"
        settings_dir.mkdir(parents=True)
        (settings_dir / "settings.json").write_text("{}")
        # Mock away user-level settings so only project settings are checked
        with patch.object(doctor, "USER_SETTINGS", temp_dir / ".nonexistent" / "settings.json"):
            result = doctor.check_hooks_config()
            assert result.status == "warn"

    def test_check_hooks_config_valid(self, doctor, temp_dir):
        """Valid hooks pass (doctor expects 'command' key on each hook entry)."""
        settings_dir = temp_dir / ".claude"
        settings_dir.mkdir(parents=True)
        hooks = {
            "hooks": {
                "PreToolUse": [{"command": "echo test"}]
            }
        }
        (settings_dir / "settings.json").write_text(json.dumps(hooks))
        with patch.object(doctor, "USER_SETTINGS", temp_dir / ".nonexistent" / "settings.json"):
            result = doctor.check_hooks_config()
            assert result.status == "pass"

    def test_check_hooks_config_invalid_event(self, doctor, temp_dir):
        """Unknown hook event should fail."""
        settings_dir = temp_dir / ".claude"
        settings_dir.mkdir(parents=True)
        hooks = {"hooks": {"InvalidEvent": [{"command": "echo test"}]}}
        (settings_dir / "settings.json").write_text(json.dumps(hooks))
        with patch.object(doctor, "USER_SETTINGS", temp_dir / ".nonexistent" / "settings.json"):
            result = doctor.check_hooks_config()
            assert result.status == "fail"

    def test_check_plugins_enabled_set(self, doctor):
        with patch.dict(os.environ, {"ENABLE_PLUGINS": "1"}):
            result = doctor.check_plugins_enabled()
            assert result.status == "pass"

    def test_check_plugins_enabled_not_set(self, doctor):
        env = os.environ.copy()
        env.pop("ENABLE_PLUGINS", None)
        with patch.dict(os.environ, env, clear=True):
            result = doctor.check_plugins_enabled()
            assert result.status == "fail"
            assert result.fixable is True

    def test_check_plugins_health_no_pacc_json(self, doctor):
        result = doctor.check_plugins_health()
        assert result.status == "warn"

    def test_check_plugins_health_empty(self, doctor, temp_dir):
        (temp_dir / "pacc.json").write_text('{"plugins": {}}')
        result = doctor.check_plugins_health()
        assert result.status == "pass"

    def test_check_mcp_servers_no_config(self, doctor, temp_dir):
        """No MCP servers configured = warning."""
        settings_dir = temp_dir / ".claude"
        settings_dir.mkdir(parents=True)
        (settings_dir / "settings.json").write_text("{}")
        result = doctor.check_mcp_servers()
        assert result.status == "warn"

    def test_check_fragments_no_refs(self, doctor, temp_dir):
        """No fragment references = pass."""
        result = doctor.check_fragments_integrity()
        assert result.status == "pass"

    def test_check_fragments_broken_ref(self, doctor, temp_dir):
        """Broken fragment reference = fail."""
        (temp_dir / "CLAUDE.md").write_text("@.claude/fragments/missing.md - Missing Fragment\n")
        result = doctor.check_fragments_integrity()
        assert result.status == "fail"
        assert result.fixable is True

    def test_check_stacks_sync_no_pacc_json(self, doctor):
        result = doctor.check_stacks_sync()
        assert result.status == "warn"

    def test_check_stacks_sync_no_stacks(self, doctor, temp_dir):
        (temp_dir / "pacc.json").write_text("{}")
        result = doctor.check_stacks_sync()
        assert result.status == "pass"

    def test_check_permissions(self, doctor, temp_dir):
        """Permissions check should pass in normal conditions."""
        claude_dir = temp_dir / ".claude"
        claude_dir.mkdir()
        result = doctor.check_permissions()
        assert result.status == "pass"

    def test_check_claude_code_installed_found(self, doctor):
        with patch("shutil.which", return_value="/usr/bin/claude"):
            result = doctor.check_claude_code_installed()
            assert result.status == "pass"

    def test_check_claude_code_installed_not_found(self, doctor):
        with patch("shutil.which", return_value=None):
            result = doctor.check_claude_code_installed()
            assert result.status == "fail"


class TestDoctorRunDiagnostics:
    """Test the full diagnostics run."""

    @pytest.fixture
    def doctor(self, temp_dir):
        return Doctor(project_dir=temp_dir)

    def test_run_returns_report(self, doctor):
        report = doctor.run_diagnostics()
        assert isinstance(report, DoctorReport)
        assert len(report.checks) == 12
        assert report.passed + report.warned + report.failed == 12

    def test_run_with_fix(self, doctor):
        report = doctor.run_diagnostics(fix=True)
        assert isinstance(report, DoctorReport)


class TestDoctorAutoFix:
    """Test auto-fix capabilities."""

    @pytest.fixture
    def doctor(self, temp_dir):
        return Doctor(project_dir=temp_dir)

    def test_fix_plugins_enabled(self, doctor):
        env = os.environ.copy()
        env.pop("ENABLE_PLUGINS", None)
        with patch.dict(os.environ, env, clear=True):
            result = doctor._fix_plugins_enabled()
            assert result is True
            assert os.environ.get("ENABLE_PLUGINS") == "1"

    def test_fix_config_files_invalid_json(self, doctor, temp_dir):
        """Should fix invalid JSON by cleaning trailing commas."""
        settings_dir = temp_dir / ".claude"
        settings_dir.mkdir(parents=True)
        settings_file = settings_dir / "settings.json"
        settings_file.write_text('{"key": "value",}')

        result = doctor._fix_config_files()
        assert result is True
        # Verify the file is now valid JSON
        data = json.loads(settings_file.read_text())
        assert data == {"key": "value"}

    def test_fix_fragments_removes_broken_refs(self, doctor, temp_dir):
        """Should remove broken fragment references."""
        claude_md = temp_dir / "CLAUDE.md"
        claude_md.write_text(
            "# Project\n\n"
            "@.claude/fragments/missing.md - Missing Fragment\n"
            "Some other content\n"
        )
        result = doctor._fix_fragments()
        assert result is True
        content = claude_md.read_text()
        assert "missing.md" not in content
        assert "Some other content" in content
