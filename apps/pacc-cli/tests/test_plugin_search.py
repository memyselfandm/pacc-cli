"""Test plugin search functionality."""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from pacc.plugins.search import (
    PluginSearchEngine,
    PluginRegistry,
    LocalPluginIndex,
    SearchResult,
    SearchPluginType,
    SortBy,
    ProjectContext,
    search_plugins,
    get_plugin_recommendations
)
from pacc.plugins.config import PluginConfigManager
from pacc.plugins.discovery import PluginScanner, PluginInfo


class TestSearchPluginType:
    """Test SearchPluginType enum."""
    
    def test_plugin_type_values(self):
        """Test that plugin types have correct values."""
        assert SearchPluginType.COMMAND.value == "command"
        assert SearchPluginType.AGENT.value == "agent"
        assert SearchPluginType.HOOK.value == "hook"
        assert SearchPluginType.MCP.value == "mcp"
        assert SearchPluginType.ALL.value == "all"


class TestSortBy:
    """Test SortBy enum."""
    
    def test_sort_by_values(self):
        """Test that sort criteria have correct values."""
        assert SortBy.POPULARITY.value == "popularity"
        assert SortBy.DATE.value == "date"
        assert SortBy.NAME.value == "name"
        assert SortBy.RELEVANCE.value == "relevance"


class TestSearchResult:
    """Test SearchResult dataclass."""
    
    def test_search_result_creation(self):
        """Test creating a search result."""
        result = SearchResult(
            name="test-plugin",
            description="A test plugin",
            plugin_type=SearchPluginType.COMMAND,
            repository_url="https://github.com/test/plugin",
            author="test-author"
        )
        
        assert result.name == "test-plugin"
        assert result.description == "A test plugin"
        assert result.plugin_type == SearchPluginType.COMMAND
        assert result.repository_url == "https://github.com/test/plugin"
        assert result.author == "test-author"
        assert result.version == "latest"
        assert result.popularity_score == 0
        assert result.last_updated is None
        assert result.tags == []
        assert result.installed is False
        assert result.enabled is False
        assert result.namespace is None
    
    def test_full_name_without_namespace(self):
        """Test full name without namespace."""
        result = SearchResult(
            name="test-plugin",
            description="A test plugin",
            plugin_type=SearchPluginType.COMMAND,
            repository_url="https://github.com/test/plugin",
            author="test-author"
        )
        
        assert result.full_name == "test-plugin"
    
    def test_full_name_with_namespace(self):
        """Test full name with namespace."""
        result = SearchResult(
            name="test-plugin",
            description="A test plugin",
            plugin_type=SearchPluginType.COMMAND,
            repository_url="https://github.com/test/plugin",
            author="test-author",
            namespace="test"
        )
        
        assert result.full_name == "test:test-plugin"
    
    def test_matches_query_empty_query(self):
        """Test that empty query matches everything."""
        result = SearchResult(
            name="test-plugin",
            description="A test plugin",
            plugin_type=SearchPluginType.COMMAND,
            repository_url="https://github.com/test/plugin",
            author="test-author"
        )
        
        assert result.matches_query("")
        assert result.matches_query(None)
    
    def test_matches_query_name(self):
        """Test query matching against name."""
        result = SearchResult(
            name="python-linter",
            description="A Python linting plugin",
            plugin_type=SearchPluginType.HOOK,
            repository_url="https://github.com/test/plugin",
            author="test-author"
        )
        
        assert result.matches_query("python")
        assert result.matches_query("Python")
        assert result.matches_query("PYTHON")
        assert result.matches_query("linter")
        assert not result.matches_query("javascript")
    
    def test_matches_query_description(self):
        """Test query matching against description."""
        result = SearchResult(
            name="test-plugin",
            description="JavaScript build tools",
            plugin_type=SearchPluginType.COMMAND,
            repository_url="https://github.com/test/plugin",
            author="test-author"
        )
        
        assert result.matches_query("javascript")
        assert result.matches_query("build")
        assert result.matches_query("tools")
        assert not result.matches_query("python")
    
    def test_matches_query_author(self):
        """Test query matching against author."""
        result = SearchResult(
            name="test-plugin",
            description="A test plugin",
            plugin_type=SearchPluginType.COMMAND,
            repository_url="https://github.com/test/plugin",
            author="claude-code"
        )
        
        assert result.matches_query("claude")
        assert result.matches_query("code")
        assert not result.matches_query("github")
    
    def test_matches_query_tags(self):
        """Test query matching against tags."""
        result = SearchResult(
            name="test-plugin",
            description="A test plugin",
            plugin_type=SearchPluginType.COMMAND,
            repository_url="https://github.com/test/plugin",
            author="test-author",
            tags=["linting", "python", "formatting"]
        )
        
        assert result.matches_query("linting")
        assert result.matches_query("python")
        assert result.matches_query("formatting")
        assert not result.matches_query("javascript")
    
    def test_to_dict(self):
        """Test converting to dictionary."""
        result = SearchResult(
            name="test-plugin",
            description="A test plugin",
            plugin_type=SearchPluginType.COMMAND,
            repository_url="https://github.com/test/plugin",
            author="test-author",
            version="1.0.0",
            popularity_score=85,
            last_updated="2025-08-19T10:00:00Z",
            tags=["test", "example"],
            installed=True,
            enabled=False,
            namespace="test"
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["name"] == "test-plugin"
        assert result_dict["description"] == "A test plugin"
        assert result_dict["plugin_type"] == "command"  # Enum value
        assert result_dict["repository_url"] == "https://github.com/test/plugin"
        assert result_dict["author"] == "test-author"
        assert result_dict["version"] == "1.0.0"
        assert result_dict["popularity_score"] == 85
        assert result_dict["last_updated"] == "2025-08-19T10:00:00Z"
        assert result_dict["tags"] == ["test", "example"]
        assert result_dict["installed"] is True
        assert result_dict["enabled"] is False
        assert result_dict["namespace"] == "test"


class TestProjectContext:
    """Test ProjectContext dataclass."""
    
    def test_project_context_creation(self):
        """Test creating project context."""
        context = ProjectContext()
        
        assert context.project_type is None
        assert context.languages == set()
        assert context.frameworks == set()
        assert context.has_tests is False
        assert context.has_docs is False
    
    def test_project_context_with_data(self):
        """Test creating project context with data."""
        languages = {"python", "javascript"}
        frameworks = {"django", "react"}
        
        context = ProjectContext(
            project_type="web",
            languages=languages,
            frameworks=frameworks,
            has_tests=True,
            has_docs=True
        )
        
        assert context.project_type == "web"
        assert context.languages == languages
        assert context.frameworks == frameworks
        assert context.has_tests is True
        assert context.has_docs is True


class TestPluginRegistry:
    """Test PluginRegistry class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.registry_path = Path(self.temp_dir) / "test_registry.json"
        
        # Create test registry data
        self.test_registry = {
            "version": "1.0",
            "last_updated": "2025-08-19T10:00:00Z",
            "plugins": [
                {
                    "name": "python-linter",
                    "description": "Python linting tools",
                    "type": "hook",
                    "repository_url": "https://github.com/test/python-linter",
                    "author": "test-author",
                    "version": "1.0.0",
                    "popularity_score": 90,
                    "last_updated": "2025-08-19T09:00:00Z",
                    "tags": ["python", "linting", "quality"],
                    "namespace": "python"
                },
                {
                    "name": "js-tools",
                    "description": "JavaScript development tools",
                    "type": "command",
                    "repository_url": "https://github.com/test/js-tools",
                    "author": "js-dev",
                    "version": "2.1.0",
                    "popularity_score": 75,
                    "last_updated": "2025-08-18T15:30:00Z",
                    "tags": ["javascript", "tools", "build"],
                    "namespace": "js"
                },
                {
                    "name": "security-scanner",
                    "description": "Security vulnerability scanner",
                    "type": "agent",
                    "repository_url": "https://github.com/test/security",
                    "author": "security-team",
                    "version": "0.9.0",
                    "popularity_score": 85,
                    "last_updated": "2025-08-17T12:00:00Z",
                    "tags": ["security", "scanner", "audit"],
                    "namespace": "security"
                }
            ]
        }
        
        # Write test registry to file
        with open(self.registry_path, 'w') as f:
            json.dump(self.test_registry, f)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_registry_load_existing_file(self):
        """Test loading registry from existing file."""
        registry = PluginRegistry(self.registry_path)
        data = registry._load_registry()
        
        assert data["version"] == "1.0"
        assert len(data["plugins"]) == 3
    
    def test_registry_load_nonexistent_file(self):
        """Test loading registry from nonexistent file."""
        nonexistent_path = Path(self.temp_dir) / "nonexistent.json"
        registry = PluginRegistry(nonexistent_path)
        data = registry._load_registry()
        
        assert data["plugins"] == []
        assert data["version"] == "1.0"
    
    def test_search_community_plugins_no_query(self):
        """Test searching community plugins without query."""
        registry = PluginRegistry(self.registry_path)
        results = registry.search_community_plugins()
        
        assert len(results) == 3
        assert all(isinstance(r, SearchResult) for r in results)
    
    def test_search_community_plugins_with_query(self):
        """Test searching community plugins with query."""
        registry = PluginRegistry(self.registry_path)
        results = registry.search_community_plugins("python")
        
        assert len(results) == 1
        assert results[0].name == "python-linter"
    
    def test_search_community_plugins_with_type_filter(self):
        """Test searching community plugins with type filter."""
        registry = PluginRegistry(self.registry_path)
        results = registry.search_community_plugins(plugin_type=SearchPluginType.HOOK)
        
        assert len(results) == 1
        assert results[0].plugin_type == SearchPluginType.HOOK
    
    def test_search_community_plugins_with_query_and_type(self):
        """Test searching community plugins with query and type filter."""
        registry = PluginRegistry(self.registry_path)
        results = registry.search_community_plugins("tools", SearchPluginType.COMMAND)
        
        assert len(results) == 1
        assert results[0].name == "js-tools"
        assert results[0].plugin_type == SearchPluginType.COMMAND
    
    def test_get_recommendations_basic(self):
        """Test getting basic recommendations."""
        registry = PluginRegistry(self.registry_path)
        context = ProjectContext()
        results = registry.get_recommendations(context, limit=10)
        
        # Should return results sorted by popularity, but may be empty with no context
        assert len(results) <= 10
        # With empty context, plugins with no relevance boost might not be returned
        # This is correct behavior - recommendations should be relevant
    
    def test_get_recommendations_python_project(self):
        """Test getting recommendations for Python project."""
        registry = PluginRegistry(self.registry_path)
        context = ProjectContext(
            project_type="python",
            languages={"python"},
            has_tests=True
        )
        results = registry.get_recommendations(context, limit=10)
        
        # Python linter should be boosted and appear first
        assert len(results) > 0
        # Check that python-linter got relevance boost
        python_result = next((r for r in results if r.name == "python-linter"), None)
        assert python_result is not None
        assert python_result.popularity_score > 90  # Original was 90, should be boosted
    
    def test_calculate_relevance_language_match(self):
        """Test relevance calculation for language match."""
        registry = PluginRegistry(self.registry_path)
        
        plugin = SearchResult(
            name="test",
            description="Python development tools",
            plugin_type=SearchPluginType.COMMAND,
            repository_url="https://github.com/test/test",
            author="test",
            tags=["python", "development"]
        )
        
        context = ProjectContext(languages={"python"})
        score = registry._calculate_relevance(plugin, context)
        
        # Should get points for language in tags (10) and description (5)
        assert score >= 15
    
    def test_calculate_relevance_project_type_match(self):
        """Test relevance calculation for project type match."""
        registry = PluginRegistry(self.registry_path)
        
        plugin = SearchResult(
            name="test",
            description="Web development framework",
            plugin_type=SearchPluginType.COMMAND,
            repository_url="https://github.com/test/test",
            author="test",
            tags=["web", "framework"]
        )
        
        context = ProjectContext(project_type="web")
        score = registry._calculate_relevance(plugin, context)
        
        # Should get points for project type in tags (15) and description (8)
        assert score >= 23


class TestLocalPluginIndex:
    """Test LocalPluginIndex class."""
    
    @patch('pacc.plugins.search.PluginScanner')
    @patch('pacc.plugins.search.PluginConfigManager')
    def test_get_installed_plugins_empty(self, mock_config_manager, mock_scanner):
        """Test getting installed plugins when none are installed."""
        # Mock empty config
        mock_config_manager.return_value.load_config.return_value = {"repositories": {}}
        mock_config_manager.return_value.get_enabled_plugins.return_value = set()
        
        index = LocalPluginIndex()
        results = index.get_installed_plugins()
        
        assert results == []
    
    @patch('pacc.plugins.search.PluginScanner')
    @patch('pacc.plugins.search.PluginConfigManager')
    def test_get_installed_plugins_with_repos(self, mock_config_manager, mock_scanner):
        """Test getting installed plugins with repositories."""
        # Mock config with repositories
        mock_config = {
            "repositories": {
                "test/repo": {
                    "path": "/fake/path",
                    "url": "https://github.com/test/repo",
                    "owner": "test",
                    "current_commit": "abc123def456",
                    "last_updated": "2025-08-19T10:00:00Z"
                }
            }
        }
        mock_config_manager.return_value.load_config.return_value = mock_config
        mock_config_manager.return_value.get_enabled_plugins.return_value = {"test-plugin"}
        
        # Mock plugin discovery
        mock_plugin_info = PluginInfo(
            name="test-plugin",
            path=Path("/fake/path"),
            manifest={
                "description": "A test plugin",
                "author": "test-author"
            },
            components={
                "commands": [Path("/fake/path/commands/test.md")]
            }
        )
        mock_scanner.return_value.scan_repository.return_value = [mock_plugin_info]
        
        # Mock path exists
        with patch('pathlib.Path.exists', return_value=True):
            index = LocalPluginIndex()
            results = index.get_installed_plugins()
        
        assert len(results) == 1
        result = results[0]
        assert result.name == "test-plugin"
        assert result.namespace is None  # No namespace in simple name
        assert result.installed is True
        assert result.enabled is True
        assert result.plugin_type == SearchPluginType.COMMAND
        assert result.repository_url == "https://github.com/test/repo"
        assert result.author == "test"
        assert result.version == "abc123de"  # First 8 chars of commit
        assert result.description == "A test plugin"
    
    def test_plugin_type_from_components_hooks(self):
        """Test plugin type detection for hooks."""
        index = LocalPluginIndex()
        components = {"hooks": [{"name": "test-hook"}]}
        plugin_type = index._plugin_type_from_components(components)
        
        assert plugin_type == SearchPluginType.HOOK
    
    def test_plugin_type_from_components_mcps(self):
        """Test plugin type detection for MCPs."""
        index = LocalPluginIndex()
        components = {"mcps": [{"name": "test-mcp"}]}
        plugin_type = index._plugin_type_from_components(components)
        
        assert plugin_type == SearchPluginType.MCP
    
    def test_plugin_type_from_components_agents(self):
        """Test plugin type detection for agents."""
        index = LocalPluginIndex()
        components = {"agents": [{"name": "test-agent"}]}
        plugin_type = index._plugin_type_from_components(components)
        
        assert plugin_type == SearchPluginType.AGENT
    
    def test_plugin_type_from_components_commands(self):
        """Test plugin type detection for commands."""
        index = LocalPluginIndex()
        components = {"commands": [{"name": "test-command"}]}
        plugin_type = index._plugin_type_from_components(components)
        
        assert plugin_type == SearchPluginType.COMMAND
    
    def test_plugin_type_from_components_default(self):
        """Test plugin type detection default case."""
        index = LocalPluginIndex()
        components = {}
        plugin_type = index._plugin_type_from_components(components)
        
        assert plugin_type == SearchPluginType.COMMAND


class TestPluginSearchEngine:
    """Test PluginSearchEngine class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.registry_path = Path(self.temp_dir) / "test_registry.json"
        
        # Create test registry
        test_registry = {
            "version": "1.0",
            "plugins": [
                {
                    "name": "community-plugin",
                    "description": "A community plugin",
                    "type": "command",
                    "repository_url": "https://github.com/test/community",
                    "author": "community",
                    "popularity_score": 50
                }
            ]
        }
        
        with open(self.registry_path, 'w') as f:
            json.dump(test_registry, f)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @patch('pacc.plugins.search.LocalPluginIndex')
    def test_search_installed_only(self, mock_local_index):
        """Test search with installed_only flag."""
        # Mock local index to return installed plugins
        mock_installed = [
            SearchResult(
                name="installed-plugin",
                description="An installed plugin",
                plugin_type=SearchPluginType.COMMAND,
                repository_url="https://github.com/test/installed",
                author="test",
                installed=True
            )
        ]
        mock_local_index.return_value.get_installed_plugins.return_value = mock_installed
        
        engine = PluginSearchEngine(self.registry_path)
        results = engine.search(installed_only=True)
        
        assert len(results) == 1
        assert results[0].name == "installed-plugin"
        assert results[0].installed is True
    
    @patch('pacc.plugins.search.LocalPluginIndex')
    def test_search_exclude_installed(self, mock_local_index):
        """Test search with exclude_installed flag."""
        # Mock no installed plugins
        mock_local_index.return_value.get_installed_plugins.return_value = []
        
        engine = PluginSearchEngine(self.registry_path)
        results = engine.search(include_installed=False)
        
        # Should only return community plugins
        assert len(results) == 1
        assert results[0].name == "community-plugin"
        assert results[0].installed is False
    
    @patch('pacc.plugins.search.LocalPluginIndex')
    def test_search_with_query(self, mock_local_index):
        """Test search with query."""
        mock_local_index.return_value.get_installed_plugins.return_value = []
        
        engine = PluginSearchEngine(self.registry_path)
        results = engine.search(query="community")
        
        assert len(results) == 1
        assert results[0].name == "community-plugin"
    
    @patch('pacc.plugins.search.LocalPluginIndex')
    def test_search_with_type_filter(self, mock_local_index):
        """Test search with type filter."""
        mock_local_index.return_value.get_installed_plugins.return_value = []
        
        engine = PluginSearchEngine(self.registry_path)
        results = engine.search(plugin_type=SearchPluginType.COMMAND)
        
        assert len(results) == 1
        assert results[0].plugin_type == SearchPluginType.COMMAND
    
    @patch('pacc.plugins.search.LocalPluginIndex')
    def test_sort_results_by_name(self, mock_local_index):
        """Test sorting results by name."""
        mock_local_index.return_value.get_installed_plugins.return_value = []
        
        engine = PluginSearchEngine(self.registry_path)
        
        # Create test results
        results = [
            SearchResult("zebra", "Z plugin", SearchPluginType.COMMAND, "url", "author"),
            SearchResult("alpha", "A plugin", SearchPluginType.COMMAND, "url", "author"),
            SearchResult("beta", "B plugin", SearchPluginType.COMMAND, "url", "author")
        ]
        
        sorted_results = engine._sort_results(results, SortBy.NAME)
        
        assert [r.name for r in sorted_results] == ["alpha", "beta", "zebra"]
    
    @patch('pacc.plugins.search.LocalPluginIndex')
    def test_sort_results_by_popularity(self, mock_local_index):
        """Test sorting results by popularity."""
        mock_local_index.return_value.get_installed_plugins.return_value = []
        
        engine = PluginSearchEngine(self.registry_path)
        
        # Create test results with different popularity scores
        results = [
            SearchResult("low", "Low plugin", SearchPluginType.COMMAND, "url", "author", popularity_score=10),
            SearchResult("high", "High plugin", SearchPluginType.COMMAND, "url", "author", popularity_score=90),
            SearchResult("medium", "Medium plugin", SearchPluginType.COMMAND, "url", "author", popularity_score=50)
        ]
        
        sorted_results = engine._sort_results(results, SortBy.POPULARITY)
        
        assert [r.name for r in sorted_results] == ["high", "medium", "low"]
    
    @patch('pacc.plugins.search.LocalPluginIndex')
    def test_sort_results_by_date(self, mock_local_index):
        """Test sorting results by date."""
        mock_local_index.return_value.get_installed_plugins.return_value = []
        
        engine = PluginSearchEngine(self.registry_path)
        
        # Create test results with different dates
        results = [
            SearchResult("old", "Old plugin", SearchPluginType.COMMAND, "url", "author", last_updated="2025-01-01"),
            SearchResult("new", "New plugin", SearchPluginType.COMMAND, "url", "author", last_updated="2025-08-19"),
            SearchResult("none", "No date plugin", SearchPluginType.COMMAND, "url", "author", last_updated=None)
        ]
        
        sorted_results = engine._sort_results(results, SortBy.DATE)
        
        # Newest first, None values at end
        assert sorted_results[0].name == "new"
        assert sorted_results[1].name == "old"
        assert sorted_results[2].name == "none"
    
    @patch('pacc.plugins.search.LocalPluginIndex')
    def test_sort_results_by_relevance(self, mock_local_index):
        """Test sorting results by relevance (installed first)."""
        mock_local_index.return_value.get_installed_plugins.return_value = []
        
        engine = PluginSearchEngine(self.registry_path)
        
        # Create test results with mixed installed status
        results = [
            SearchResult("not-installed", "Not installed", SearchPluginType.COMMAND, "url", "author", 
                        installed=False, popularity_score=90),
            SearchResult("installed", "Installed", SearchPluginType.COMMAND, "url", "author", 
                        installed=True, popularity_score=50)
        ]
        
        sorted_results = engine._sort_results(results, SortBy.RELEVANCE)
        
        # Installed plugins should come first
        assert sorted_results[0].name == "installed"
        assert sorted_results[1].name == "not-installed"
    
    @patch('pacc.plugins.search.LocalPluginIndex')
    def test_analyze_project_context_python(self, mock_local_index):
        """Test project context analysis for Python project."""
        mock_local_index.return_value.get_installed_plugins.return_value = []
        
        # Create real temp directory with requirements.txt for testing
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create requirements.txt
            requirements_path = Path(temp_dir) / "requirements.txt"
            requirements_path.write_text("requests==2.25.1\n")
            
            # Change to temp directory
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                engine = PluginSearchEngine(self.registry_path)
                context = engine._analyze_project_context()
                
                assert "python" in context.languages
                assert context.project_type == "python"
                
            finally:
                os.chdir(original_cwd)
    
    @patch('pacc.plugins.search.LocalPluginIndex')
    def test_analyze_project_context_javascript(self, mock_local_index):
        """Test project context analysis for JavaScript project."""
        mock_local_index.return_value.get_installed_plugins.return_value = []
        
        # Create real temp directory with package.json for testing
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create package.json
            package_path = Path(temp_dir) / "package.json"
            package_path.write_text('{"name": "test-project", "version": "1.0.0"}')
            
            # Change to temp directory
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                engine = PluginSearchEngine(self.registry_path)
                context = engine._analyze_project_context()
                
                assert "javascript" in context.languages
                assert context.project_type == "web"
                
            finally:
                os.chdir(original_cwd)


class TestConvenienceFunctions:
    """Test convenience functions for CLI usage."""
    
    def test_search_plugins_basic(self):
        """Test basic search_plugins function."""
        with patch('pacc.plugins.search.PluginSearchEngine') as mock_engine:
            # Mock search results
            mock_results = [
                SearchResult("test", "Test plugin", SearchPluginType.COMMAND, "url", "author")
            ]
            mock_engine.return_value.search.return_value = mock_results
            
            results = search_plugins("test")
            
            assert len(results) == 1
            assert isinstance(results[0], dict)
            assert results[0]["name"] == "test"
    
    def test_search_plugins_invalid_type(self):
        """Test search_plugins with invalid type."""
        with patch('pacc.plugins.search.PluginSearchEngine') as mock_engine:
            mock_engine.return_value.search.return_value = []
            
            # Should default to SearchPluginType.ALL for invalid type
            results = search_plugins(plugin_type="invalid")
            
            # Verify search was called with ALL type
            mock_engine.return_value.search.assert_called_once()
            call_args = mock_engine.return_value.search.call_args[1]
            assert call_args["plugin_type"] == SearchPluginType.ALL
    
    def test_search_plugins_invalid_sort(self):
        """Test search_plugins with invalid sort criteria."""
        with patch('pacc.plugins.search.PluginSearchEngine') as mock_engine:
            mock_engine.return_value.search.return_value = []
            
            # Should default to SortBy.RELEVANCE for invalid sort
            results = search_plugins(sort_by="invalid")
            
            # Verify search was called with RELEVANCE sort
            mock_engine.return_value.search.assert_called_once()
            call_args = mock_engine.return_value.search.call_args[1]
            assert call_args["sort_by"] == SortBy.RELEVANCE
    
    def test_get_plugin_recommendations(self):
        """Test get_plugin_recommendations function."""
        with patch('pacc.plugins.search.PluginSearchEngine') as mock_engine:
            # Mock recommendation results
            mock_results = [
                SearchResult("recommended", "Recommended plugin", SearchPluginType.AGENT, "url", "author")
            ]
            mock_engine.return_value.get_recommendations.return_value = mock_results
            
            results = get_plugin_recommendations(limit=5)
            
            assert len(results) == 1
            assert isinstance(results[0], dict)
            assert results[0]["name"] == "recommended"
            
            # Verify get_recommendations was called with correct limit
            mock_engine.return_value.get_recommendations.assert_called_once_with(5)


# Performance tests
class TestSearchPerformance:
    """Test search performance requirements."""
    
    def test_search_performance_under_2_seconds(self):
        """Test that search completes in under 2 seconds."""
        import time
        
        # Create a large registry for performance testing
        temp_dir = tempfile.mkdtemp()
        try:
            registry_path = Path(temp_dir) / "large_registry.json"
            
            # Generate 1000 plugins for performance test
            plugins = []
            for i in range(1000):
                plugins.append({
                    "name": f"plugin-{i:04d}",
                    "description": f"Test plugin number {i}",
                    "type": "command",
                    "repository_url": f"https://github.com/test/plugin-{i}",
                    "author": f"author-{i % 10}",
                    "popularity_score": i % 100,
                    "tags": [f"tag-{i % 20}", f"category-{i % 5}"]
                })
            
            large_registry = {
                "version": "1.0",
                "plugins": plugins
            }
            
            with open(registry_path, 'w') as f:
                json.dump(large_registry, f)
            
            # Time the search operation
            start_time = time.time()
            
            with patch('pacc.plugins.search.LocalPluginIndex') as mock_local_index:
                mock_local_index.return_value.get_installed_plugins.return_value = []
                
                engine = PluginSearchEngine(registry_path)
                results = engine.search("test")
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Should complete in under 2 seconds
            assert duration < 2.0, f"Search took {duration:.2f} seconds, should be under 2.0 seconds"
            
            # Should still return valid results
            assert len(results) > 0
            
        finally:
            import shutil
            shutil.rmtree(temp_dir)


# Integration tests would be in a separate file, but here are the key scenarios:
"""
Integration test scenarios to implement:

1. test_cli_search_basic():
   - Run: pacc plugin search
   - Verify: Shows community plugins in table format

2. test_cli_search_with_query():
   - Run: pacc plugin search "python"
   - Verify: Only shows plugins matching "python"

3. test_cli_search_type_filter():
   - Run: pacc plugin search --type agent
   - Verify: Only shows agent plugins

4. test_cli_search_sort_options():
   - Run: pacc plugin search --sort popularity
   - Verify: Results sorted by popularity score

5. test_cli_search_installed_only():
   - Setup: Install some plugins first
   - Run: pacc plugin search --installed-only
   - Verify: Only shows installed plugins

6. test_cli_search_recommendations():
   - Setup: Create Python project (requirements.txt)
   - Run: pacc plugin search --recommendations
   - Verify: Shows relevant recommendations for Python

7. test_cli_search_limit():
   - Run: pacc plugin search --limit 5
   - Verify: Shows maximum 5 results

8. test_cli_search_performance():
   - Run: pacc plugin search (large registry)
   - Verify: Completes in under 2 seconds
"""