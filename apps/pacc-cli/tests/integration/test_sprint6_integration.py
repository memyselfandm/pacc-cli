"""Integration tests for Sprint 6 features: Plugin Creation Tools & Basic Discovery."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from pacc.cli import PACCCli
from pacc.plugins.creator import CreationMode, CreationPluginType, PluginCreator
from pacc.plugins.search import SearchPluginType, SearchResult, search_plugins


class TestSprintSixIntegration:
    """Integration tests for Sprint 6 plugin creation and search features."""

    def test_plugin_create_command_integration(self):
        """Test complete plugin create command workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cli = PACCCli()

            # Mock args for plugin create
            args = Mock()
            args.name = "test-plugin"
            args.type = "hooks"
            args.output_dir = temp_dir
            args.mode = "quick"
            args.init_git = True
            args.no_git = False

            # Mock user input for quick mode
            with patch("builtins.input") as mock_input:
                mock_input.side_effect = [
                    "Test Plugin",  # description
                    "Test Author",  # author
                    "1.0.0",  # version
                    "",  # accept defaults
                ]

                result = cli.handle_plugin_create(args)

                assert result == 0

                # Verify plugin was created
                plugin_dir = Path(temp_dir) / "test-plugin"
                assert plugin_dir.exists()
                assert (plugin_dir / "plugin.json").exists()
                assert (plugin_dir / "hooks").exists()

    def test_plugin_search_command_integration(self):
        """Test complete plugin search command workflow."""
        cli = PACCCli()

        # Mock args for plugin search
        args = Mock()
        args.query = "test"
        args.type = "all"
        args.sort = "relevance"
        args.limit = 10
        args.installed_only = False
        args.exclude_installed = False
        args.recommendations = False

        # Mock search results (search_plugins returns dicts)
        mock_results = [
            {
                "name": "test-plugin",
                "description": "A test plugin",
                "plugin_type": "hook",
                "repository_url": "https://github.com/test/test-plugin",
                "author": "Test Author",
                "installed": False,
                "enabled": False,
                "version": "latest",
                "popularity_score": 0,
                "last_updated": None,
                "tags": [],
                "namespace": None,
            }
        ]

        with patch("pacc.cli.search_plugins") as mock_search:
            mock_search.return_value = mock_results

            result = cli.handle_plugin_search(args)

            assert result == 0
            mock_search.assert_called_once_with(
                query="test",
                plugin_type="all",
                sort_by="relevance",
                include_installed=True,
                installed_only=False,
            )

    def test_plugin_search_recommendations_integration(self):
        """Test plugin search recommendations workflow."""
        cli = PACCCli()

        # Mock args for recommendations
        args = Mock()
        args.recommendations = True
        args.limit = 5

        # Mock recommendation results (get_plugin_recommendations returns dicts)
        mock_recommendations = [
            {
                "name": "python-helper",
                "description": "Python development helper",
                "plugin_type": "agent",
                "repository_url": "https://github.com/test/python-helper",
                "author": "Test Author",
                "installed": False,
                "enabled": False,
                "version": "latest",
                "popularity_score": 0,
                "last_updated": None,
                "tags": [],
                "namespace": None,
            }
        ]

        with patch("pacc.cli.get_plugin_recommendations") as mock_recs:
            mock_recs.return_value = mock_recommendations

            result = cli.handle_plugin_search(args)

            assert result == 0
            mock_recs.assert_called_once_with(limit=5)

    def test_create_and_search_workflow_integration(self):
        """Test creating a plugin and then finding it via search."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Step 1: Create a plugin
            creator = PluginCreator()

            with patch("builtins.input") as mock_input:
                mock_input.side_effect = [
                    "Test Integration Plugin",  # description
                    "Integration Tester",  # author
                    "1.0.0",  # version
                    "",  # accept defaults
                ]

                result = creator.create_plugin(
                    name="integration-test-plugin",
                    plugin_type=CreationPluginType.HOOKS,
                    output_dir=Path(temp_dir),
                    mode=CreationMode.QUICK,
                    init_git=False,
                )

                assert result.success
                plugin_path = result.plugin_path
                assert plugin_path.exists()

            # Step 2: Mock the plugin being discovered in search
            mock_local_plugin = {
                "name": "integration-test-plugin",
                "description": "Test Integration Plugin",
                "plugin_type": "hook",
                "repository_url": str(plugin_path),
                "author": "Integration Tester",
                "installed": True,
                "enabled": False,
                "namespace": "local",
                "version": "latest",
                "popularity_score": 0,
                "last_updated": None,
                "tags": [],
            }

            # Mock search finding our created plugin
            with patch(
                "pacc.plugins.search.LocalPluginIndex.get_installed_plugins"
            ) as mock_installed:
                mock_installed.return_value = [mock_local_plugin]

                results = search_plugins(query="integration-test", installed_only=True)

                assert len(results) == 1
                assert results[0]["name"] == "integration-test-plugin"
                assert results[0]["installed"] is True

    def test_plugin_creator_template_engine_integration(self):
        """Test template engine integration with all plugin types."""
        with tempfile.TemporaryDirectory() as temp_dir:
            creator = PluginCreator()

            # Test each plugin type (note: MCP plugins create "servers" directory)
            plugin_types = [
                (CreationPluginType.HOOKS, "hooks"),
                (CreationPluginType.AGENTS, "agents"),
                (CreationPluginType.COMMANDS, "commands"),
                (CreationPluginType.MCP, "servers"),
            ]

            for plugin_type, type_name in plugin_types:
                with patch("builtins.input") as mock_input:
                    mock_input.side_effect = [
                        f"Test {type_name.title()} Plugin",  # description
                        "Test Author",  # author
                        "1.0.0",  # version
                        "",  # accept defaults
                    ]

                    result = creator.create_plugin(
                        name=f"test-{type_name}-plugin",
                        plugin_type=plugin_type,
                        output_dir=Path(temp_dir),
                        mode=CreationMode.QUICK,
                        init_git=False,
                    )

                    assert result.success
                    plugin_dir = result.plugin_path
                    assert plugin_dir.exists()
                    assert (plugin_dir / "plugin.json").exists()
                    assert (plugin_dir / type_name).exists()

    def test_search_engine_with_created_plugins(self):
        """Test search engine finding various created plugin types."""
        # Mock multiple plugins of different types (as SearchResult objects for engine)
        hook_plugin = SearchResult(
            name="hook-plugin",
            description="A test hook plugin",
            plugin_type=SearchPluginType.HOOK,
            repository_url="https://github.com/test/hook-plugin",
            author="Test Author",
            installed=True,
            enabled=True,
        )
        agent_plugin = SearchResult(
            name="agent-plugin",
            description="A test agent plugin",
            plugin_type=SearchPluginType.AGENT,
            repository_url="https://github.com/test/agent-plugin",
            author="Test Author",
            installed=True,
            enabled=False,
        )
        command_plugin = SearchResult(
            name="command-plugin",
            description="A test command plugin",
            plugin_type=SearchPluginType.COMMAND,
            repository_url="https://github.com/test/command-plugin",
            author="Test Author",
            installed=False,
            enabled=False,
        )

        with patch("pacc.plugins.search.PluginRegistry.search_community_plugins") as mock_community:
            with patch("pacc.plugins.search.LocalPluginIndex.get_installed_plugins") as mock_local:
                mock_community.return_value = [command_plugin]  # Only command-plugin from community
                mock_local.return_value = [
                    hook_plugin,
                    agent_plugin,
                ]  # hook and agent plugins installed

                # Test searching by type
                hook_results = search_plugins(plugin_type="hook")
                agent_results = search_plugins(plugin_type="agent")
                command_results = search_plugins(plugin_type="command")

                assert len(hook_results) == 1
                assert hook_results[0]["name"] == "hook-plugin"

                assert len(agent_results) == 1
                assert agent_results[0]["name"] == "agent-plugin"

                assert len(command_results) == 1
                assert command_results[0]["name"] == "command-plugin"

    def test_error_handling_integration(self):
        """Test error handling across creation and search features."""
        cli = PACCCli()

        # Test create with invalid output directory
        args = Mock()
        args.name = "test-plugin"
        args.type = "hooks"
        args.output_dir = "/nonexistent/directory"
        args.mode = "quick"
        args.init_git = False
        args.no_git = False

        result = cli.handle_plugin_create(args)
        assert result == 1  # Should fail

        # Test search with conflicting flags
        args = Mock()
        args.query = "test"
        args.type = "all"
        args.sort = "relevance"
        args.limit = 10
        args.installed_only = True
        args.exclude_installed = True  # Conflicting with installed_only
        args.recommendations = False

        result = cli.handle_plugin_search(args)
        assert result == 1  # Should fail due to conflicting flags

    def test_cli_argument_parsing_integration(self):
        """Test CLI argument parsing for new Sprint 6 commands."""
        cli = PACCCli()

        # Test create command arguments
        create_args = [
            "plugin",
            "create",
            "my-plugin",
            "--type",
            "hooks",
            "--output-dir",
            "/tmp",
            "--mode",
            "guided",
            "--init-git",
        ]

        parser = cli.create_parser()
        parsed_args = parser.parse_args(create_args)

        assert parsed_args.command == "plugin"
        assert parsed_args.plugin_command == "create"
        assert parsed_args.name == "my-plugin"
        assert parsed_args.type == "hooks"
        assert parsed_args.output_dir == "/tmp"
        assert parsed_args.mode == "guided"
        assert parsed_args.init_git is True

        # Test search command arguments
        search_args = [
            "plugin",
            "search",
            "test-query",
            "--type",
            "agent",
            "--sort",
            "popularity",
            "--limit",
            "5",
            "--installed-only",
        ]

        parsed_args = parser.parse_args(search_args)

        assert parsed_args.command == "plugin"
        assert parsed_args.plugin_command == "search"
        assert parsed_args.query == "test-query"
        assert parsed_args.type == "agent"
        assert parsed_args.sort == "popularity"
        assert parsed_args.limit == 5
        assert parsed_args.installed_only is True

    def test_comprehensive_workflow_integration(self):
        """Test comprehensive workflow: create -> search -> enable workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cli = PACCCli()

            # Step 1: Create plugin using CLI
            create_args = Mock()
            create_args.name = "workflow-test-plugin"
            create_args.type = "agents"
            create_args.output_dir = temp_dir
            create_args.mode = "quick"
            create_args.init_git = False
            create_args.no_git = True

            with patch("builtins.input") as mock_input:
                mock_input.side_effect = [
                    "Workflow Test Plugin",  # description
                    "Workflow Tester",  # author
                    "1.0.0",  # version
                    "",  # accept defaults
                ]

                create_result = cli.handle_plugin_create(create_args)
                assert create_result == 0

                plugin_path = Path(temp_dir) / "workflow-test-plugin"
                assert plugin_path.exists()

            # Step 2: Search for the created plugin
            search_args = Mock()
            search_args.query = "workflow-test"
            search_args.type = "all"
            search_args.sort = "relevance"
            search_args.limit = 10
            search_args.installed_only = True
            search_args.exclude_installed = False
            search_args.recommendations = False

            # Mock the search finding our plugin
            mock_plugin_result = {
                "name": "workflow-test-plugin",
                "description": "Workflow Test Plugin",
                "plugin_type": "agent",
                "repository_url": str(plugin_path),
                "author": "Workflow Tester",
                "installed": True,
                "enabled": False,
                "version": "latest",
                "popularity_score": 0,
                "last_updated": None,
                "tags": [],
                "namespace": None,
            }

            with patch("pacc.plugins.search.search_plugins") as mock_search:
                mock_search.return_value = [mock_plugin_result]

                search_result = cli.handle_plugin_search(search_args)
                assert search_result == 0

                # Verify search was called with correct parameters
                mock_search.assert_called_once_with(
                    query="workflow-test",
                    plugin_type="all",
                    sort_by="relevance",
                    include_installed=True,
                    installed_only=True,
                )


class TestSprintSixPerformance:
    """Performance tests for Sprint 6 features."""

    def test_plugin_creation_performance(self):
        """Test plugin creation performance under various conditions."""
        import time

        with tempfile.TemporaryDirectory() as temp_dir:
            creator = PluginCreator()

            # Test multiple plugin creation
            start_time = time.time()

            for i in range(5):
                with patch("builtins.input") as mock_input:
                    mock_input.side_effect = [
                        f"Performance Test Plugin {i}",  # description
                        "Performance Tester",  # author
                        "1.0.0",  # version
                        "",  # accept defaults
                    ]

                    result = creator.create_plugin(
                        name=f"perf-test-plugin-{i}",
                        plugin_type=CreationPluginType.HOOKS,
                        output_dir=Path(temp_dir),
                        mode=CreationMode.QUICK,
                        init_git=False,
                    )

                    assert result.success

            end_time = time.time()
            total_time = end_time - start_time

            # Should create 5 plugins in under 5 seconds
            assert total_time < 5.0

            # Verify all plugins were created
            plugin_dirs = list(Path(temp_dir).glob("perf-test-plugin-*"))
            assert len(plugin_dirs) == 5

    def test_search_performance_with_large_dataset(self):
        """Test search performance with larger mock datasets."""
        import time

        # Create mock dataset of 100 plugins as SearchResult objects
        mock_plugins = []
        for i in range(100):
            plugin_types = [
                SearchPluginType.HOOK,
                SearchPluginType.AGENT,
                SearchPluginType.COMMAND,
                SearchPluginType.MCP,
            ]
            mock_plugins.append(
                SearchResult(
                    name=f"plugin-{i:03d}",
                    description=f"Plugin number {i} for testing search performance",
                    plugin_type=plugin_types[i % 4],
                    repository_url=f"https://github.com/test/plugin-{i:03d}",
                    author=f"Author {i % 10}",
                    installed=i % 10 == 0,  # Every 10th plugin is installed
                    enabled=i % 20 == 0,  # Every 20th plugin is enabled
                )
            )

        with patch("pacc.plugins.search.PluginRegistry.search_community_plugins") as mock_registry:
            with patch("pacc.plugins.search.LocalPluginIndex.get_installed_plugins") as mock_local:
                mock_registry.return_value = mock_plugins
                mock_local.return_value = [p for p in mock_plugins if p.installed]

                start_time = time.time()

                # Perform various searches
                results_all = search_plugins()
                results_hooks = search_plugins(plugin_type="hook")
                results_query = search_plugins(query="plugin")
                results_installed = search_plugins(installed_only=True)

                end_time = time.time()
                search_time = end_time - start_time

                # All searches should complete in under 1 second
                assert search_time < 1.0

                # Verify correct filtering
                assert len(results_all) == 100
                assert all(p["plugin_type"] == "hook" for p in results_hooks)
                assert len(results_installed) == 10  # Every 10th plugin


class TestSprintSixEdgeCases:
    """Edge case tests for Sprint 6 features."""

    def test_plugin_creation_with_special_characters(self):
        """Test plugin creation with special characters in names."""
        with tempfile.TemporaryDirectory() as temp_dir:
            creator = PluginCreator()

            # Test plugin name normalization
            with patch("builtins.input") as mock_input:
                mock_input.side_effect = [
                    "Special Characters Plugin",  # description
                    "Special Author",  # author
                    "1.0.0",  # version
                    "",  # accept defaults
                ]

                # The creator should handle and normalize special characters
                result = creator.create_plugin(
                    name="my-special-plugin!@#",  # Contains special chars
                    plugin_type=CreationPluginType.HOOKS,
                    output_dir=Path(temp_dir),
                    mode=CreationMode.QUICK,
                    init_git=False,
                )

                # Should succeed and normalize the name
                assert result.success
                # The actual directory name should be normalized
                normalized_dirs = list(Path(temp_dir).glob("my-special-plugin*"))
                assert len(normalized_dirs) == 1

    def test_search_with_empty_results(self):
        """Test search behavior with no results."""
        cli = PACCCli()

        args = Mock()
        args.query = "nonexistent-plugin-query"
        args.type = "all"
        args.sort = "relevance"
        args.limit = 10
        args.installed_only = False
        args.exclude_installed = False
        args.recommendations = False

        with patch("pacc.plugins.search.search_plugins") as mock_search:
            mock_search.return_value = []  # No results

            result = cli.handle_plugin_search(args)

            # Should complete successfully even with no results
            assert result == 0

    def test_plugin_creation_in_existing_directory(self):
        """Test plugin creation when target directory already exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a directory with the same name first
            existing_dir = Path(temp_dir) / "existing-plugin"
            existing_dir.mkdir()

            creator = PluginCreator()

            with patch("builtins.input") as mock_input:
                mock_input.side_effect = [
                    "Existing Directory Plugin",  # description
                    "Test Author",  # author
                    "1.0.0",  # version
                    "",  # accept defaults
                ]

                result = creator.create_plugin(
                    name="existing-plugin",
                    plugin_type=CreationPluginType.HOOKS,
                    output_dir=Path(temp_dir),
                    mode=CreationMode.QUICK,
                    init_git=False,
                )

                # Should fail because directory already exists
                assert not result.success
                assert "already exists" in result.error_message.lower()
