"""End-to-end tests for team collaboration scenarios with plugin management."""

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from pacc.plugins import (
    PluginConfigManager,
    PluginConverter,
    PluginRepositoryManager,
)


class TeamMember:
    """Simulates a team member with their own workspace."""

    def __init__(self, name: str, workspace_dir: Path):
        self.name = name
        self.workspace_dir = workspace_dir
        self.claude_dir = workspace_dir / ".claude"
        self.setup_workspace()

    def setup_workspace(self):
        """Setup individual team member workspace."""
        self.workspace_dir.mkdir(exist_ok=True)
        self.claude_dir.mkdir(exist_ok=True)

        # Create individual settings
        settings = {
            "modelId": "claude-3-5-sonnet-20241022",
            "maxTokens": 8192,
            "temperature": 0,
            "systemPrompt": f"Settings for team member: {self.name}",
            "plugins": {},
            "hooks": {},
            "agents": {},
            "commands": {},
            "mcp": {"servers": {}},
        }
        (self.claude_dir / "settings.json").write_text(json.dumps(settings, indent=2))

        # Create individual config
        config = {
            "version": "1.0.0",
            "team_member": self.name,
            "extensions": {"hooks": {}, "agents": {}, "commands": {}, "mcp": {"servers": {}}},
        }
        (self.claude_dir / "config.json").write_text(json.dumps(config, indent=2))

    def get_config_manager(self):
        """Get config manager for this team member."""
        return PluginConfigManager(self.claude_dir)

    def get_repo_manager(self):
        """Get repository manager for this team member."""
        return PluginRepositoryManager()


@pytest.fixture
def team_plugin_repository(tmp_path):
    """Create a shared team plugin repository."""
    repo_dir = tmp_path / "team_plugins"
    repo_dir.mkdir()

    # Create team manifest
    manifest = {
        "name": "team-productivity-suite",
        "version": "1.0.0",
        "description": "Shared productivity plugins for the development team",
        "author": "Development Team",
        "team_config": {
            "required_plugins": ["code-reviewer", "task-manager"],
            "optional_plugins": ["time-tracker", "meeting-notes"],
            "environments": ["development", "staging", "production"],
        },
        "plugins": [
            {
                "name": "code-reviewer",
                "type": "agent",
                "path": "agents/code-reviewer.md",
                "description": "Automated code review assistant",
                "required": True,
                "environments": ["development", "staging", "production"],
            },
            {
                "name": "task-manager",
                "type": "agent",
                "path": "agents/task-manager.md",
                "description": "Project task management",
                "required": True,
                "environments": ["development", "staging", "production"],
            },
            {
                "name": "time-tracker",
                "type": "command",
                "path": "commands/time-tracker.md",
                "description": "Development time tracking",
                "required": False,
                "environments": ["development"],
            },
            {
                "name": "meeting-notes",
                "type": "agent",
                "path": "agents/meeting-notes.md",
                "description": "Meeting notes and action items",
                "required": False,
                "environments": ["development", "staging"],
            },
            {
                "name": "deployment-helper",
                "type": "command",
                "path": "commands/deployment-helper.md",
                "description": "Deployment automation commands",
                "required": True,
                "environments": ["staging", "production"],
            },
            {
                "name": "error-monitor",
                "type": "hook",
                "path": "hooks/error-monitor.json",
                "description": "Error monitoring and alerting",
                "required": True,
                "environments": ["production"],
            },
        ],
    }

    manifest_file = repo_dir / "pacc-manifest.yaml"
    manifest_file.write_text(yaml.dump(manifest, default_flow_style=False))

    # Create plugin directories
    (repo_dir / "agents").mkdir()
    (repo_dir / "commands").mkdir()
    (repo_dir / "hooks").mkdir()

    # Create code reviewer agent
    code_reviewer = """---
name: code-reviewer
version: 1.0.0
description: Automated code review assistant for team consistency
capabilities:
  - code_review
  - style_checking
  - security_analysis
  - team_standards
team_config:
  required: true
  standards_file: "team-standards.yaml"
---

# Code Reviewer Agent

Ensures code quality and consistency across the team.

## Team Standards

- Follow team coding conventions
- Perform security vulnerability scanning
- Check for performance antipatterns
- Verify documentation requirements

## Usage

Use this agent for all code reviews before merging to main branches.

## Team Integration

This agent uses shared team standards defined in `team-standards.yaml`.
"""
    (repo_dir / "agents" / "code-reviewer.md").write_text(code_reviewer)

    # Create task manager agent
    task_manager = """---
name: task-manager
version: 1.0.0
description: Centralized task management for team projects
capabilities:
  - task_tracking
  - sprint_planning
  - team_coordination
  - progress_reporting
team_config:
  required: true
  shared_board: true
---

# Task Manager Agent

Manages tasks and coordinates team activities.

## Features

- Shared task board across team members
- Sprint planning and tracking
- Automated progress reporting
- Integration with team workflows

## Team Coordination

- Sync tasks across team members
- Track individual and team progress
- Generate team reports
- Manage dependencies between team members
"""
    (repo_dir / "agents" / "task-manager.md").write_text(task_manager)

    # Create meeting notes agent
    meeting_notes = """---
name: meeting-notes
version: 1.0.0
description: Standardized meeting notes and action item tracking
capabilities:
  - meeting_documentation
  - action_tracking
  - team_communication
---

# Meeting Notes Agent

Standardizes meeting documentation and action item tracking.

## Features

- Template-based meeting notes
- Action item assignment and tracking
- Meeting summary generation
- Follow-up reminders
"""
    (repo_dir / "agents" / "meeting-notes.md").write_text(meeting_notes)

    # Create time tracker command
    time_tracker = """# Time Tracking Commands

Development time tracking for team productivity analysis.

## Commands

### `time-start`
Start tracking time for a task or project.

```bash
time-start --task "feature-development" --project "user-auth"
```

### `time-stop`
Stop current time tracking session.

```bash
time-stop --notes "Completed user login implementation"
```

### `time-report`
Generate time reports for team analysis.

```bash
time-report --period weekly --team --export csv
```

## Team Integration

- Shared time tracking database
- Team productivity metrics
- Project time allocation analysis
"""
    (repo_dir / "commands" / "time-tracker.md").write_text(time_tracker)

    # Create deployment helper command
    deployment_helper = """# Deployment Helper Commands

Standardized deployment procedures for team consistency.

## Commands

### `deploy-prepare`
Prepare application for deployment with team checks.

```bash
deploy-prepare --environment staging --run-tests --security-scan
```

### `deploy-execute`
Execute deployment with team notifications.

```bash
deploy-execute --environment production --notify-team --rollback-plan
```

### `deploy-verify`
Verify deployment success and notify team.

```bash
deploy-verify --environment production --health-check --team-notification
```

## Team Integration

- Standardized deployment procedures
- Team notifications and alerts
- Shared deployment logs
- Rollback coordination
"""
    (repo_dir / "commands" / "deployment-helper.md").write_text(deployment_helper)

    # Create error monitor hook
    error_monitor = {
        "name": "error-monitor",
        "version": "1.0.0",
        "description": "Team error monitoring and alerting system",
        "events": ["OnError", "OnException", "OnToolFailure"],
        "team_config": {
            "required": True,
            "alert_channels": ["#dev-alerts", "#team-notifications"],
            "escalation_rules": True,
        },
        "matchers": [
            {"pattern": "*", "severity": "error"},
            {"pattern": "*.py", "action": "log_and_alert"},
            {"pattern": "*.js", "action": "log_and_alert"},
        ],
        "actions": {
            "log_and_alert": {
                "command": "team-error-handler",
                "args": ["--error", "${error_message}", "--file", "${file_path}", "--team-alert"],
            }
        },
    }
    (repo_dir / "hooks" / "error-monitor.json").write_text(json.dumps(error_monitor, indent=2))

    return repo_dir


@pytest.fixture
def development_team(tmp_path):
    """Create a development team with multiple members."""
    team_workspace = tmp_path / "team_workspace"
    team_workspace.mkdir()

    team_members = {}
    for name in ["alice", "bob", "charlie", "diana"]:
        member_workspace = team_workspace / f"{name}_workspace"
        team_members[name] = TeamMember(name, member_workspace)

    return team_members


@pytest.mark.e2e
@pytest.mark.team_collaboration
class TestTeamPluginSync:
    """Test team plugin synchronization scenarios."""

    def test_initial_team_setup_sync(self, team_plugin_repository, development_team, tmp_path):
        """Test initial team setup where all members sync to shared plugin configuration."""
        repo_dir = team_plugin_repository
        team = development_team

        with patch("os.getcwd", return_value=str(tmp_path)):
            # Step 1: Team lead (Alice) sets up initial configuration
            alice = team["alice"]

            with patch(
                "pacc.core.project_config.ProjectConfigValidator._find_claude_dir",
                return_value=alice.claude_dir,
            ):
                alice_repo_manager = alice.get_repo_manager()
                alice_config_manager = alice.get_config_manager()

                # Discover and install all required plugins
                plugins = alice_repo_manager.discover_plugins(repo_dir)
                required_plugins = [p for p in plugins if getattr(p, "required", True)]

                start_time = time.perf_counter()
                result = alice_config_manager.install_plugins(required_plugins, repo_dir)
                setup_time = time.perf_counter() - start_time

                assert setup_time < 3.0, f"Initial setup took {setup_time:.3f}s (should be < 3s)"
                assert result["success"] is True
                assert result["installed_count"] >= 3  # At least required plugins

            # Step 2: Other team members sync to Alice's configuration
            sync_times = []

            for member_name in ["bob", "charlie", "diana"]:
                member = team[member_name]

                with patch(
                    "pacc.core.project_config.ProjectConfigValidator._find_claude_dir",
                    return_value=member.claude_dir,
                ):
                    member_repo_manager = member.get_repo_manager()
                    member_config_manager = member.get_config_manager()

                    # Sync from shared repository
                    start_time = time.perf_counter()
                    sync_result = member_config_manager.sync_with_repository(
                        repo_dir, strategy="team_sync"
                    )
                    sync_time = time.perf_counter() - start_time

                    sync_times.append(sync_time)

                    assert (
                        sync_time < 2.0
                    ), f"{member_name} sync took {sync_time:.3f}s (should be < 2s)"
                    assert sync_result["success"] is True

                    # Verify team member has required plugins
                    member_settings = json.loads((member.claude_dir / "settings.json").read_text())
                    assert "code-reviewer" in member_settings["agents"]
                    assert "task-manager" in member_settings["agents"]

            # Step 3: Verify team consistency
            team_configs = {}
            for name, member in team.items():
                settings = json.loads((member.claude_dir / "settings.json").read_text())
                team_configs[name] = {
                    "agents": list(settings["agents"].keys()),
                    "commands": list(settings["commands"].keys()),
                    "hooks": list(settings["hooks"].keys()),
                }

            # All team members should have consistent required plugins
            required_agents = {"code-reviewer", "task-manager"}
            for name, config in team_configs.items():
                member_agents = set(config["agents"])
                assert required_agents.issubset(member_agents), f"{name} missing required agents"

            avg_sync_time = sum(sync_times) / len(sync_times)
            print(f"Team sync completed - Average sync time: {avg_sync_time:.3f}s")

    def test_plugin_conflict_resolution_across_team(
        self, team_plugin_repository, development_team, tmp_path
    ):
        """Test handling plugin conflicts when team members have different configurations."""
        repo_dir = team_plugin_repository
        team = development_team

        with patch("os.getcwd", return_value=str(tmp_path)):
            # Step 1: Set up different configurations for team members
            alice = team["alice"]
            bob = team["bob"]

            # Alice installs standard team plugins
            with patch(
                "pacc.core.project_config.ProjectConfigValidator._find_claude_dir",
                return_value=alice.claude_dir,
            ):
                alice_repo_manager = alice.get_repo_manager()
                alice_config_manager = alice.get_config_manager()

                plugins = alice_repo_manager.discover_plugins(repo_dir)
                alice_config_manager.install_plugins(plugins, repo_dir)

            # Bob has a different version of one plugin (simulate local changes)
            with patch(
                "pacc.core.project_config.ProjectConfigValidator._find_claude_dir",
                return_value=bob.claude_dir,
            ):
                bob_config_manager = bob.get_config_manager()

                # Bob manually adds a conflicting plugin configuration
                bob_settings = json.loads((bob.claude_dir / "settings.json").read_text())
                bob_settings["agents"]["code-reviewer"] = {
                    "path": "/custom/path/code-reviewer-custom.md",
                    "enabled": True,
                    "version": "2.0.0-custom",
                }
                (bob.claude_dir / "settings.json").write_text(json.dumps(bob_settings, indent=2))

                # Step 2: Bob tries to sync with team repository (should detect conflict)
                start_time = time.perf_counter()
                conflict_result = bob_config_manager.sync_with_repository(
                    repo_dir, strategy="detect_conflicts"
                )
                conflict_time = time.perf_counter() - start_time

                assert (
                    conflict_time < 1.0
                ), f"Conflict detection took {conflict_time:.3f}s (should be < 1s)"
                assert conflict_result["success"] is False
                assert "conflicts" in conflict_result
                assert len(conflict_result["conflicts"]) > 0

                # Verify specific conflict details
                conflicts = conflict_result["conflicts"]
                code_reviewer_conflict = next(
                    (c for c in conflicts if c["plugin_name"] == "code-reviewer"), None
                )
                assert code_reviewer_conflict is not None
                assert code_reviewer_conflict["type"] == "version_mismatch"

            # Step 3: Test conflict resolution strategies
            with patch(
                "pacc.core.project_config.ProjectConfigValidator._find_claude_dir",
                return_value=bob.claude_dir,
            ):
                # Strategy 1: Override with team version
                start_time = time.perf_counter()
                override_result = bob_config_manager.sync_with_repository(
                    repo_dir, strategy="team_override", conflict_resolution="use_team_version"
                )
                override_time = time.perf_counter() - start_time

                assert (
                    override_time < 1.0
                ), f"Conflict resolution took {override_time:.3f}s (should be < 1s)"
                assert override_result["success"] is True
                assert override_result["conflicts_resolved"] > 0

                # Verify Bob now has team version
                updated_settings = json.loads((bob.claude_dir / "settings.json").read_text())
                code_reviewer_config = updated_settings["agents"]["code-reviewer"]
                assert "custom" not in code_reviewer_config["path"]
                assert str(repo_dir) in code_reviewer_config["path"]

    def test_collaborative_plugin_development(
        self, team_plugin_repository, development_team, tmp_path
    ):
        """Test collaborative plugin development workflow."""
        repo_dir = team_plugin_repository
        team = development_team

        with patch("os.getcwd", return_value=str(tmp_path)):
            # Step 1: Alice develops a new plugin
            alice = team["alice"]

            with patch(
                "pacc.core.project_config.ProjectConfigValidator._find_claude_dir",
                return_value=alice.claude_dir,
            ):
                alice_config_manager = alice.get_config_manager()

                # Create new plugin in development
                dev_plugin_dir = tmp_path / "alice_dev_plugins"
                dev_plugin_dir.mkdir()
                (dev_plugin_dir / "agents").mkdir()

                new_plugin_content = """---
name: performance-analyzer
version: 0.1.0-dev
description: Performance analysis tool (in development)
capabilities:
  - performance_monitoring
  - bottleneck_detection
  - optimization_suggestions
team_config:
  status: "development"
  developer: "alice"
---

# Performance Analyzer Agent

**Status: In Development**

A tool for analyzing application performance and identifying optimization opportunities.

## Development Notes

- Initial implementation complete
- Needs testing and validation
- Ready for team review
"""
                (dev_plugin_dir / "agents" / "performance-analyzer.md").write_text(
                    new_plugin_content
                )

                # Alice installs her development plugin locally
                start_time = time.perf_counter()
                dev_result = alice_config_manager.install_local_plugin(
                    dev_plugin_dir / "agents" / "performance-analyzer.md", plugin_type="agent"
                )
                dev_time = time.perf_counter() - start_time

                assert dev_time < 0.5, f"Dev plugin install took {dev_time:.3f}s (should be < 0.5s)"
                assert dev_result["success"] is True

            # Step 2: Alice shares plugin for team review
            with patch(
                "pacc.core.project_config.ProjectConfigValidator._find_claude_dir",
                return_value=alice.claude_dir,
            ):
                # Create plugin package for sharing
                plugin_converter = PluginConverter()

                start_time = time.perf_counter()
                package_result = plugin_converter.create_team_review_package(
                    dev_plugin_dir / "agents" / "performance-analyzer.md",
                    output_dir=tmp_path / "shared_review",
                )
                package_time = time.perf_counter() - start_time

                assert (
                    package_time < 1.0
                ), f"Package creation took {package_time:.3f}s (should be < 1s)"
                assert package_result["success"] is True

            # Step 3: Team members review and test the plugin
            review_results = {}

            for member_name in ["bob", "charlie"]:
                member = team[member_name]

                with patch(
                    "pacc.core.project_config.ProjectConfigValidator._find_claude_dir",
                    return_value=member.claude_dir,
                ):
                    member_config_manager = member.get_config_manager()

                    # Install plugin for review
                    start_time = time.perf_counter()
                    review_result = member_config_manager.install_review_plugin(
                        package_result["package_path"], reviewer=member_name
                    )
                    review_time = time.perf_counter() - start_time

                    review_results[member_name] = {
                        "install_time": review_time,
                        "success": review_result["success"],
                    }

                    assert (
                        review_time < 1.0
                    ), f"{member_name} review install took {review_time:.3f}s"
                    assert review_result["success"] is True

            # Step 4: Collect feedback and finalize plugin
            with patch(
                "pacc.core.project_config.ProjectConfigValidator._find_claude_dir",
                return_value=alice.claude_dir,
            ):
                # Simulate positive team feedback and finalization
                final_plugin_content = (
                    new_plugin_content.replace("version: 0.1.0-dev", "version: 1.0.0")
                    .replace('status: "development"', 'status: "stable"')
                    .replace("**Status: In Development**", "**Status: Team Approved**")
                )

                # Add to team repository
                (repo_dir / "agents" / "performance-analyzer.md").write_text(final_plugin_content)

                # Update manifest
                manifest_file = repo_dir / "pacc-manifest.yaml"
                manifest_data = yaml.safe_load(manifest_file.read_text())
                manifest_data["plugins"].append(
                    {
                        "name": "performance-analyzer",
                        "type": "agent",
                        "path": "agents/performance-analyzer.md",
                        "description": "Performance analysis tool",
                        "required": False,
                        "environments": ["development"],
                    }
                )
                manifest_file.write_text(yaml.dump(manifest_data, default_flow_style=False))

            # Step 5: Team synchronizes with new plugin
            sync_results = {}

            for member_name, member in team.items():
                with patch(
                    "pacc.core.project_config.ProjectConfigValidator._find_claude_dir",
                    return_value=member.claude_dir,
                ):
                    member_config_manager = member.get_config_manager()

                    start_time = time.perf_counter()
                    sync_result = member_config_manager.sync_with_repository(repo_dir)
                    sync_time = time.perf_counter() - start_time

                    sync_results[member_name] = {
                        "sync_time": sync_time,
                        "success": sync_result["success"],
                    }

                    assert sync_time < 1.5, f"{member_name} final sync took {sync_time:.3f}s"
                    assert sync_result["success"] is True

                    # Verify new plugin is available
                    settings = json.loads((member.claude_dir / "settings.json").read_text())
                    assert "performance-analyzer" in settings["agents"]

            avg_sync_time = sum(r["sync_time"] for r in sync_results.values()) / len(sync_results)
            print(f"Collaborative development completed - Average final sync: {avg_sync_time:.3f}s")

    def test_team_plugin_rollback_scenario(
        self, team_plugin_repository, development_team, tmp_path
    ):
        """Test team-wide plugin rollback when issues are discovered."""
        repo_dir = team_plugin_repository
        team = development_team

        with patch("os.getcwd", return_value=str(tmp_path)):
            # Step 1: Team has stable configuration
            for member_name, member in team.items():
                with patch(
                    "pacc.core.project_config.ProjectConfigValidator._find_claude_dir",
                    return_value=member.claude_dir,
                ):
                    member_repo_manager = member.get_repo_manager()
                    member_config_manager = member.get_config_manager()

                    plugins = member_repo_manager.discover_plugins(repo_dir)
                    member_config_manager.install_plugins(plugins, repo_dir)

            # Step 2: Problematic plugin update is released
            # Simulate breaking change in code-reviewer plugin
            original_plugin = (repo_dir / "agents" / "code-reviewer.md").read_text()

            broken_plugin = original_plugin.replace("version: 1.0.0", "version: 1.1.0").replace(
                "# Code Reviewer Agent",
                "# Code Reviewer Agent\n\n**WARNING: This version has known issues**",
            )

            (repo_dir / "agents" / "code-reviewer.md").write_text(broken_plugin)

            # Update manifest version
            manifest_file = repo_dir / "pacc-manifest.yaml"
            manifest_data = yaml.safe_load(manifest_file.read_text())
            manifest_data["version"] = "1.1.0"
            for plugin in manifest_data["plugins"]:
                if plugin["name"] == "code-reviewer":
                    plugin["version"] = "1.1.0"
            manifest_file.write_text(yaml.dump(manifest_data, default_flow_style=False))

            # Step 3: Team members update and discover issues
            update_times = []

            for member_name, member in team.items():
                with patch(
                    "pacc.core.project_config.ProjectConfigValidator._find_claude_dir",
                    return_value=member.claude_dir,
                ):
                    member_config_manager = member.get_config_manager()

                    start_time = time.perf_counter()
                    update_result = member_config_manager.update_plugins_from_repository(repo_dir)
                    update_time = time.perf_counter() - start_time

                    update_times.append(update_time)

                    assert update_time < 2.0, f"{member_name} update took {update_time:.3f}s"
                    assert update_result["success"] is True

            # Step 4: Issues discovered - initiate team rollback
            alice = team["alice"]  # Alice coordinates the rollback

            with patch(
                "pacc.core.project_config.ProjectConfigValidator._find_claude_dir",
                return_value=alice.claude_dir,
            ):
                alice_config_manager = alice.get_config_manager()

                # Create rollback configuration
                start_time = time.perf_counter()
                rollback_plan = alice_config_manager.create_team_rollback_plan(
                    target_version="1.0.0", affected_plugins=["code-reviewer"]
                )
                rollback_plan_time = time.perf_counter() - start_time

                assert (
                    rollback_plan_time < 1.0
                ), f"Rollback plan creation took {rollback_plan_time:.3f}s"
                assert rollback_plan["success"] is True
                assert len(rollback_plan["affected_members"]) == len(team)

            # Step 5: Execute team-wide rollback
            # First, restore the repository to previous state
            (repo_dir / "agents" / "code-reviewer.md").write_text(original_plugin)

            manifest_data["version"] = "1.0.0"
            for plugin in manifest_data["plugins"]:
                if plugin["name"] == "code-reviewer":
                    plugin["version"] = "1.0.0"
            manifest_file.write_text(yaml.dump(manifest_data, default_flow_style=False))

            # Execute rollback for each team member
            rollback_times = []

            for member_name, member in team.items():
                with patch(
                    "pacc.core.project_config.ProjectConfigValidator._find_claude_dir",
                    return_value=member.claude_dir,
                ):
                    member_config_manager = member.get_config_manager()

                    start_time = time.perf_counter()
                    rollback_result = member_config_manager.execute_rollback(
                        rollback_plan["plan_id"]
                    )
                    rollback_time = time.perf_counter() - start_time

                    rollback_times.append(rollback_time)

                    assert rollback_time < 1.5, f"{member_name} rollback took {rollback_time:.3f}s"
                    assert rollback_result["success"] is True

                    # Verify rollback was successful
                    settings = json.loads((member.claude_dir / "settings.json").read_text())
                    code_reviewer_path = settings["agents"]["code-reviewer"]["path"]
                    plugin_content = Path(code_reviewer_path).read_text()
                    assert "version: 1.0.0" in plugin_content
                    assert "WARNING" not in plugin_content

            avg_rollback_time = sum(rollback_times) / len(rollback_times)
            print(f"Team rollback completed - Average rollback time: {avg_rollback_time:.3f}s")


@pytest.mark.e2e
@pytest.mark.team_performance
class TestTeamCollaborationPerformance:
    """Performance tests for team collaboration scenarios."""

    def test_large_team_sync_performance(self, team_plugin_repository, tmp_path):
        """Test plugin sync performance with larger teams."""
        repo_dir = team_plugin_repository

        # Create larger team (10 members)
        large_team = {}
        team_workspace = tmp_path / "large_team_workspace"
        team_workspace.mkdir()

        for i in range(10):
            member_name = f"member_{i:02d}"
            member_workspace = team_workspace / f"{member_name}_workspace"
            large_team[member_name] = TeamMember(member_name, member_workspace)

        with patch("os.getcwd", return_value=str(tmp_path)):
            # Measure concurrent sync performance
            sync_times = []

            for member_name, member in large_team.items():
                with patch(
                    "pacc.core.project_config.ProjectConfigValidator._find_claude_dir",
                    return_value=member.claude_dir,
                ):
                    member_repo_manager = member.get_repo_manager()
                    member_config_manager = member.get_config_manager()

                    start_time = time.perf_counter()
                    plugins = member_repo_manager.discover_plugins(repo_dir)
                    sync_result = member_config_manager.install_plugins(plugins, repo_dir)
                    sync_time = time.perf_counter() - start_time

                    sync_times.append(sync_time)

                    assert (
                        sync_time < 5.0
                    ), f"{member_name} sync took {sync_time:.3f}s (should be < 5s)"
                    assert sync_result["success"] is True

            # Performance analysis
            avg_sync_time = sum(sync_times) / len(sync_times)
            max_sync_time = max(sync_times)
            min_sync_time = min(sync_times)

            assert avg_sync_time < 3.0, f"Average sync time: {avg_sync_time:.3f}s (should be < 3s)"
            assert max_sync_time < 5.0, f"Max sync time: {max_sync_time:.3f}s (should be < 5s)"

            print("Large team sync performance:")
            print(f"  Team size: {len(large_team)} members")
            print(f"  Average sync time: {avg_sync_time:.3f}s")
            print(f"  Range: {min_sync_time:.3f}s - {max_sync_time:.3f}s")

    def test_concurrent_team_operations(self, team_plugin_repository, development_team, tmp_path):
        """Test concurrent team operations for thread safety."""
        import concurrent.futures

        repo_dir = team_plugin_repository
        team = development_team

        with patch("os.getcwd", return_value=str(tmp_path)):

            def member_operations(member_info):
                """Perform various operations for a team member."""
                member_name, member = member_info
                results = []

                with patch(
                    "pacc.core.project_config.ProjectConfigValidator._find_claude_dir",
                    return_value=member.claude_dir,
                ):
                    member_config_manager = member.get_config_manager()
                    member_repo_manager = member.get_repo_manager()

                    try:
                        # Operation 1: Discover plugins
                        start_time = time.perf_counter()
                        plugins = member_repo_manager.discover_plugins(repo_dir)
                        discover_time = time.perf_counter() - start_time
                        results.append(("discover", discover_time, True))

                        # Operation 2: Install plugins
                        start_time = time.perf_counter()
                        install_result = member_config_manager.install_plugins(plugins, repo_dir)
                        install_time = time.perf_counter() - start_time
                        results.append(("install", install_time, install_result["success"]))

                        # Operation 3: Update plugins
                        start_time = time.perf_counter()
                        update_result = member_config_manager.sync_with_repository(repo_dir)
                        update_time = time.perf_counter() - start_time
                        results.append(("update", update_time, update_result["success"]))

                    except Exception as e:
                        results.append(("error", 0, str(e)))

                return member_name, results

            # Execute concurrent operations
            start_time = time.perf_counter()

            with concurrent.futures.ThreadPoolExecutor(max_workers=len(team)) as executor:
                futures = [
                    executor.submit(member_operations, (name, member))
                    for name, member in team.items()
                ]

                all_results = {}
                for future in concurrent.futures.as_completed(futures):
                    member_name, results = future.result()
                    all_results[member_name] = results

            total_time = time.perf_counter() - start_time

            # Verify concurrent operations completed successfully
            assert (
                total_time < 10.0
            ), f"Concurrent operations took {total_time:.3f}s (should be < 10s)"

            # Check for errors
            errors = []
            for member_name, results in all_results.items():
                for operation, duration, success in results:
                    if operation == "error" or not success:
                        errors.append(f"{member_name}: {operation} failed")

            assert len(errors) == 0, f"Concurrent operation errors: {errors}"

            # Performance analysis
            operation_times = {"discover": [], "install": [], "update": []}
            for member_name, results in all_results.items():
                for operation, duration, success in results:
                    if operation in operation_times and success:
                        operation_times[operation].append(duration)

            for operation, times in operation_times.items():
                if times:
                    avg_time = sum(times) / len(times)
                    max_time = max(times)
                    print(f"Concurrent {operation}: avg={avg_time:.3f}s, max={max_time:.3f}s")

    def test_team_repository_stress_test(self, tmp_path):
        """Test team collaboration with large plugin repositories."""
        # Create large team repository
        large_repo = tmp_path / "large_team_repo"
        large_repo.mkdir()

        # Create large manifest with many team plugins
        plugins_list = []
        categories = ["agents", "commands", "mcp", "hooks"]

        for i in range(50):  # 50 plugins total
            category = categories[i % len(categories)]
            extension = (
                "md"
                if category in ["agents", "commands"]
                else ("yaml" if category == "mcp" else "json")
            )

            plugins_list.append(
                {
                    "name": f"team-{category}-{i:02d}",
                    "type": category.rstrip("s"),
                    "path": f"{category}/team-{category}-{i:02d}.{extension}",
                    "description": f"Team plugin {i} for {category}",
                    "required": i < 5,  # First 5 are required
                    "team_config": {
                        "environments": ["development", "staging"] if i < 25 else ["production"]
                    },
                }
            )

        manifest = {
            "name": "large-team-plugin-suite",
            "version": "1.0.0",
            "description": "Large team plugin collection for stress testing",
            "plugins": plugins_list,
        }

        (large_repo / "pacc-manifest.yaml").write_text(
            yaml.dump(manifest, default_flow_style=False)
        )

        # Create directories and plugin files
        for category in categories:
            (large_repo / category).mkdir()

            for i in range(13):  # ~13 plugins per category
                plugin_index = (categories.index(category) * 13) + i
                if plugin_index >= 50:
                    break

                filename = f"team-{category}-{plugin_index:02d}"

                if category in ["agents", "commands"]:
                    content = f"""---
name: {filename}
version: 1.0.0
description: Team plugin {plugin_index} for stress testing
team_config:
  required: {plugin_index < 5}
---

# Team Plugin {plugin_index}

Large team stress test plugin for {category}.
"""
                    (large_repo / category / f"{filename}.md").write_text(content)

                elif category == "mcp":
                    content = {
                        "name": filename,
                        "command": "python",
                        "args": ["-m", filename],
                        "team_config": {"stress_test": True},
                    }
                    (large_repo / category / f"{filename}.yaml").write_text(yaml.dump(content))

                elif category == "hooks":
                    content = {
                        "name": filename,
                        "version": "1.0.0",
                        "events": ["PreToolUse"],
                        "description": f"Team stress test hook {plugin_index}",
                        "team_config": {"stress_test": True},
                    }
                    (large_repo / category / f"{filename}.json").write_text(
                        json.dumps(content, indent=2)
                    )

        # Create stress test team
        stress_team = {}
        stress_workspace = tmp_path / "stress_team_workspace"
        stress_workspace.mkdir()

        for i in range(8):  # 8 team members
            member_name = f"stress_member_{i}"
            member_workspace = stress_workspace / f"{member_name}_workspace"
            stress_team[member_name] = TeamMember(member_name, member_workspace)

        # Test team sync with large repository
        with patch("os.getcwd", return_value=str(tmp_path)):
            sync_results = {}

            for member_name, member in stress_team.items():
                with patch(
                    "pacc.core.project_config.ProjectConfigValidator._find_claude_dir",
                    return_value=member.claude_dir,
                ):
                    member_repo_manager = member.get_repo_manager()
                    member_config_manager = member.get_config_manager()

                    # Full repository sync
                    start_time = time.perf_counter()
                    plugins = member_repo_manager.discover_plugins(large_repo)
                    discovery_time = time.perf_counter() - start_time

                    start_time = time.perf_counter()
                    sync_result = member_config_manager.install_plugins(plugins, large_repo)
                    install_time = time.perf_counter() - start_time

                    sync_results[member_name] = {
                        "discovery_time": discovery_time,
                        "install_time": install_time,
                        "total_time": discovery_time + install_time,
                        "plugins_count": len(plugins),
                        "success": sync_result["success"],
                    }

                    # Performance assertions
                    assert (
                        discovery_time < 3.0
                    ), f"{member_name} discovery took {discovery_time:.3f}s"
                    assert install_time < 8.0, f"{member_name} install took {install_time:.3f}s"
                    assert sync_result["success"] is True

            # Analyze stress test results
            total_times = [r["total_time"] for r in sync_results.values()]
            avg_total_time = sum(total_times) / len(total_times)
            max_total_time = max(total_times)

            assert avg_total_time < 8.0, f"Average stress test time: {avg_total_time:.3f}s"
            assert max_total_time < 12.0, f"Max stress test time: {max_total_time:.3f}s"

            plugin_counts = [r["plugins_count"] for r in sync_results.values()]
            assert all(
                count == 50 for count in plugin_counts
            ), "All members should process 50 plugins"

            print("Stress test completed:")
            print(f"  Team size: {len(stress_team)} members")
            print("  Plugin count: 50 plugins")
            print(f"  Average total time: {avg_total_time:.3f}s")
            print(f"  Max total time: {max_total_time:.3f}s")
            print(f"  All syncs successful: {all(r['success'] for r in sync_results.values())}")
