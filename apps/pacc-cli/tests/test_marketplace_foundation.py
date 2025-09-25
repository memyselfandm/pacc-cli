"""Comprehensive unit tests for marketplace foundation components.

Tests all major components including semantic versioning, dependency resolution,
caching system, and marketplace client functionality.
"""

import json
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from pacc.plugins.marketplace import (
    DependencyConstraint,
    DependencyResolver,
    MarketplaceClient,
    MetadataCache,
    PluginDependency,
    PluginMetadata,
    PluginReview,
    PluginVersion,
    RegistryConfig,
    RegistryType,
    SemanticVersion,
)


class TestSemanticVersion:
    """Test semantic version parsing and comparison."""

    def test_parse_valid_versions(self):
        """Test parsing valid semantic versions."""
        # Basic versions
        v1 = SemanticVersion.parse("1.0.0")
        assert v1.major == 1 and v1.minor == 0 and v1.patch == 0

        # With prerelease
        v2 = SemanticVersion.parse("2.1.3-alpha.1")
        assert v2.major == 2 and v2.minor == 1 and v2.patch == 3
        assert v2.prerelease == "alpha.1"

        # With build metadata
        v3 = SemanticVersion.parse("1.0.0+build.123")
        assert v3.build == "build.123"

        # With both
        v4 = SemanticVersion.parse("1.0.0-beta.2+build.456")
        assert v4.prerelease == "beta.2" and v4.build == "build.456"

        # Strip v prefix
        v5 = SemanticVersion.parse("v1.2.3")
        assert v5.major == 1 and v5.minor == 2 and v5.patch == 3

    def test_parse_invalid_versions(self):
        """Test parsing invalid semantic versions."""
        invalid_versions = [
            "1.0",  # Missing patch
            "1.0.0.0",  # Extra component
            "1.0.x",  # Non-numeric
            "invalid",  # Completely invalid
            "",  # Empty string
            "1.0.0-",  # Invalid prerelease
        ]

        for invalid in invalid_versions:
            with pytest.raises(ValueError):
                SemanticVersion.parse(invalid)

    def test_version_comparison(self):
        """Test version comparison operators."""
        v1_0_0 = SemanticVersion.parse("1.0.0")
        v1_0_1 = SemanticVersion.parse("1.0.1")
        v1_1_0 = SemanticVersion.parse("1.1.0")
        v2_0_0 = SemanticVersion.parse("2.0.0")
        v1_0_0_alpha = SemanticVersion.parse("1.0.0-alpha")
        v1_0_0_beta = SemanticVersion.parse("1.0.0-beta")

        # Basic comparison
        assert v1_0_0 < v1_0_1 < v1_1_0 < v2_0_0
        assert v2_0_0 > v1_1_0 > v1_0_1 > v1_0_0

        # Equality
        assert v1_0_0 == SemanticVersion.parse("1.0.0")
        assert v1_0_0 != v1_0_1

        # Prerelease comparison
        assert v1_0_0_alpha < v1_0_0_beta < v1_0_0
        assert v1_0_0_alpha < v1_0_0

    def test_version_compatibility(self):
        """Test version compatibility checking."""
        v1_0_0 = SemanticVersion.parse("1.0.0")
        v1_0_1 = SemanticVersion.parse("1.0.1")
        v1_1_0 = SemanticVersion.parse("1.1.0")
        v2_0_0 = SemanticVersion.parse("2.0.0")
        v0_1_0 = SemanticVersion.parse("0.1.0")
        v0_1_1 = SemanticVersion.parse("0.1.1")
        v0_2_0 = SemanticVersion.parse("0.2.0")

        # Major version 1+ compatibility - newer version is compatible with older
        assert v1_0_1.is_compatible_with(v1_0_0)
        assert v1_1_0.is_compatible_with(v1_0_0)
        assert not v2_0_0.is_compatible_with(v1_0_0)
        assert not v1_0_0.is_compatible_with(v1_0_1)  # Older not compatible with newer

        # 0.x.x compatibility (requires same minor version)
        assert v0_1_1.is_compatible_with(v0_1_0)
        assert not v0_2_0.is_compatible_with(v0_1_0)
        assert not v0_1_0.is_compatible_with(v0_1_1)  # Older not compatible

    def test_string_representation(self):
        """Test string conversion."""
        assert str(SemanticVersion.parse("1.0.0")) == "1.0.0"
        assert str(SemanticVersion.parse("1.0.0-alpha")) == "1.0.0-alpha"
        assert str(SemanticVersion.parse("1.0.0+build")) == "1.0.0+build"
        assert str(SemanticVersion.parse("1.0.0-alpha+build")) == "1.0.0-alpha+build"


class TestPluginDependency:
    """Test plugin dependency constraints and validation."""

    def test_dependency_creation(self):
        """Test creating plugin dependencies."""
        dep = PluginDependency(
            name="test-plugin",
            constraint_type=DependencyConstraint.MINIMUM,
            version="1.0.0",
            optional=True,
            namespace="test",
        )

        assert dep.name == "test-plugin"
        assert dep.constraint_type == DependencyConstraint.MINIMUM
        assert dep.version == "1.0.0"
        assert dep.optional
        assert dep.namespace == "test"
        assert dep.full_name == "test:test-plugin"

    def test_dependency_validation(self):
        """Test dependency version validation."""
        # Valid versions should work
        PluginDependency("test", DependencyConstraint.EXACT, "1.0.0")

        # Invalid versions should raise ValueError
        with pytest.raises(ValueError):
            PluginDependency("test", DependencyConstraint.EXACT, "invalid")

    def test_constraint_satisfaction(self):
        """Test dependency constraint satisfaction."""
        # Exact constraint
        exact_dep = PluginDependency("test", DependencyConstraint.EXACT, "1.0.0")
        assert exact_dep.is_satisfied_by("1.0.0")
        assert not exact_dep.is_satisfied_by("1.0.1")

        # Minimum constraint
        min_dep = PluginDependency("test", DependencyConstraint.MINIMUM, "1.0.0")
        assert min_dep.is_satisfied_by("1.0.0")
        assert min_dep.is_satisfied_by("1.0.1")
        assert min_dep.is_satisfied_by("2.0.0")
        assert not min_dep.is_satisfied_by("0.9.9")

        # Maximum constraint
        max_dep = PluginDependency("test", DependencyConstraint.MAXIMUM, "1.0.0")
        assert max_dep.is_satisfied_by("1.0.0")
        assert max_dep.is_satisfied_by("0.9.9")
        assert not max_dep.is_satisfied_by("1.0.1")

        # Compatible constraint (^1.0.0 means >=1.0.0 and <2.0.0)
        compat_dep = PluginDependency("test", DependencyConstraint.COMPATIBLE, "1.0.0")
        assert compat_dep.is_satisfied_by("1.0.0")  # Exact match should work
        assert compat_dep.is_satisfied_by("1.0.1")
        assert compat_dep.is_satisfied_by("1.9.9")
        assert not compat_dep.is_satisfied_by("2.0.0")
        assert not compat_dep.is_satisfied_by("0.9.9")

        # Range constraint
        range_dep = PluginDependency("test", DependencyConstraint.RANGE, ">=1.0.0,<2.0.0")
        assert range_dep.is_satisfied_by("1.0.0")
        assert range_dep.is_satisfied_by("1.9.9")
        assert not range_dep.is_satisfied_by("2.0.0")
        assert not range_dep.is_satisfied_by("0.9.9")


class TestPluginReview:
    """Test plugin review functionality."""

    def test_review_creation(self):
        """Test creating plugin reviews."""
        review = PluginReview(
            user_id="user123",
            rating=5,
            title="Excellent plugin!",
            content="This plugin works great and saved me tons of time.",
            created_at=datetime.now(),
            helpful_count=10,
            version_reviewed="1.0.0",
            verified_user=True,
        )

        assert review.rating == 5
        assert review.title == "Excellent plugin!"
        assert review.verified_user

    def test_review_validation(self):
        """Test review rating validation."""
        # Valid ratings
        for rating in range(1, 6):
            PluginReview("user", rating, "Title", "Content", datetime.now())

        # Invalid ratings
        for invalid_rating in [0, 6, -1, 10]:
            with pytest.raises(ValueError):
                PluginReview("user", invalid_rating, "Title", "Content", datetime.now())

    def test_review_serialization(self):
        """Test review dictionary conversion."""
        review = PluginReview(
            user_id="user123",
            rating=4,
            title="Good plugin",
            content="Works well",
            created_at=datetime(2025, 1, 1, 12, 0, 0),
        )

        review_dict = review.to_dict()
        assert review_dict["user_id"] == "user123"
        assert review_dict["rating"] == 4
        assert review_dict["created_at"] == "2025-01-01T12:00:00"


class TestPluginVersion:
    """Test plugin version metadata."""

    def test_version_creation(self):
        """Test creating plugin versions."""
        dependencies = [
            PluginDependency("dep1", DependencyConstraint.MINIMUM, "1.0.0"),
            PluginDependency("dep2", DependencyConstraint.EXACT, "2.0.0", optional=True),
        ]

        version = PluginVersion(
            version="1.5.0",
            released_at=datetime.now(),
            changelog="Bug fixes and improvements",
            download_count=1000,
            dependencies=dependencies,
            platform_requirements=["linux", "darwin"],
        )

        assert version.version == "1.5.0"
        assert len(version.dependencies) == 2
        assert "linux" in version.platform_requirements

    def test_version_validation(self):
        """Test version string validation."""
        # Valid version
        PluginVersion("1.0.0", datetime.now())

        # Invalid version
        with pytest.raises(ValueError):
            PluginVersion("invalid", datetime.now())

    def test_platform_compatibility(self):
        """Test platform compatibility checking."""
        # Universal compatibility (no requirements)
        universal = PluginVersion("1.0.0", datetime.now())
        assert universal.is_compatible_with_platform("linux")
        assert universal.is_compatible_with_platform("darwin")
        assert universal.is_compatible_with_platform("win32")

        # Specific platform requirements
        linux_only = PluginVersion("1.0.0", datetime.now(), platform_requirements=["linux"])
        assert linux_only.is_compatible_with_platform("linux")
        assert not linux_only.is_compatible_with_platform("darwin")

    def test_semantic_version_property(self):
        """Test semantic version property."""
        version = PluginVersion("2.1.0-beta.1", datetime.now())
        sem_ver = version.semantic_version
        assert sem_ver.major == 2
        assert sem_ver.minor == 1
        assert sem_ver.patch == 0
        assert sem_ver.prerelease == "beta.1"


class TestPluginMetadata:
    """Test complete plugin metadata functionality."""

    def create_sample_plugin_metadata(self):
        """Create sample plugin metadata for testing."""
        versions = [
            PluginVersion("1.0.0", datetime(2025, 1, 1), is_prerelease=False),
            PluginVersion("1.1.0", datetime(2025, 1, 15), is_prerelease=False),
            PluginVersion("2.0.0-beta.1", datetime(2025, 2, 1), is_prerelease=True),
            PluginVersion(
                "0.9.0", datetime(2024, 12, 1), is_yanked=True, yank_reason="Security issue"
            ),
        ]

        reviews = [
            PluginReview("user1", 5, "Great!", "Love it", datetime(2025, 1, 10)),
            PluginReview("user2", 4, "Good", "Works well", datetime(2025, 1, 20)),
            PluginReview("user3", 3, "OK", "Could be better", datetime(2025, 1, 25)),
        ]

        return PluginMetadata(
            name="test-plugin",
            namespace="test",
            description="A test plugin",
            author="Test Author",
            author_email="test@example.com",
            repository_url="https://github.com/test/plugin",
            tags=["test", "utility"],
            plugin_type="command",
            versions=versions,
            reviews=reviews,
        )

    def test_full_name_property(self):
        """Test full name with namespace."""
        metadata = PluginMetadata("plugin", "test", "desc", "author")
        assert metadata.full_name == "test:plugin"

        metadata_no_ns = PluginMetadata("plugin", None, "desc", "author")
        assert metadata_no_ns.full_name == "plugin"

    def test_latest_version_property(self):
        """Test latest version detection."""
        metadata = self.create_sample_plugin_metadata()
        latest = metadata.latest_version

        assert latest is not None
        assert latest.version == "1.1.0"  # Should skip prerelease and yanked versions

    def test_get_specific_version(self):
        """Test getting specific version."""
        metadata = self.create_sample_plugin_metadata()

        # Existing version
        version = metadata.get_version("1.0.0")
        assert version is not None
        assert version.version == "1.0.0"

        # Non-existing version
        assert metadata.get_version("999.0.0") is None

    def test_rating_calculation(self):
        """Test rating statistics calculation."""
        metadata = self.create_sample_plugin_metadata()
        metadata.calculate_rating_stats()

        # Should calculate average of 5, 4, 3 = 4.0
        assert metadata.average_rating == 4.0
        assert metadata.review_count == 3

    def test_metadata_serialization(self):
        """Test metadata dictionary conversion."""
        metadata = self.create_sample_plugin_metadata()
        metadata_dict = metadata.to_dict()

        assert metadata_dict["name"] == "test-plugin"
        assert metadata_dict["namespace"] == "test"
        assert metadata_dict["status"] == "active"
        assert len(metadata_dict["versions"]) == 4
        assert len(metadata_dict["reviews"]) == 3


class TestRegistryConfig:
    """Test registry configuration."""

    def test_registry_creation(self):
        """Test creating registry configurations."""
        registry = RegistryConfig(
            name="test-registry",
            url="https://api.example.com",
            registry_type=RegistryType.PRIVATE,
            api_key="secret-key",
            timeout=60,
            verify_ssl=False,
        )

        assert registry.name == "test-registry"
        assert registry.url == "https://api.example.com/"  # Should add trailing slash
        assert registry.registry_type == RegistryType.PRIVATE
        assert not registry.verify_ssl

    def test_url_validation(self):
        """Test URL validation."""
        # Valid URLs
        RegistryConfig("test", "https://api.example.com", RegistryType.PUBLIC)
        RegistryConfig("test", "http://localhost:8080", RegistryType.LOCAL)

        # Invalid URLs
        with pytest.raises(ValueError):
            RegistryConfig("test", "invalid-url", RegistryType.PUBLIC)

        with pytest.raises(ValueError):
            RegistryConfig("test", "just-a-path", RegistryType.PUBLIC)

    def test_auth_headers(self):
        """Test authentication header generation."""
        # API key auth
        api_registry = RegistryConfig(
            "test", "https://api.example.com", RegistryType.PRIVATE, api_key="secret-token"
        )
        headers = api_registry.get_auth_headers()
        assert headers["Authorization"] == "Bearer secret-token"

        # Basic auth
        basic_registry = RegistryConfig(
            "test",
            "https://api.example.com",
            RegistryType.PRIVATE,
            username="user",
            password="pass",
        )
        headers = basic_registry.get_auth_headers()
        assert headers["Authorization"].startswith("Basic ")

        # No auth
        public_registry = RegistryConfig("test", "https://api.example.com", RegistryType.PUBLIC)
        headers = public_registry.get_auth_headers()
        assert "Authorization" not in headers

    def test_config_serialization(self):
        """Test configuration serialization."""
        registry = RegistryConfig(
            "test",
            "https://api.example.com",
            RegistryType.PRIVATE,
            api_key="secret",
            password="secret-pass",
        )

        config_dict = registry.to_dict()
        assert config_dict["name"] == "test"
        assert config_dict["registry_type"] == "private"
        # Sensitive data should be None
        assert config_dict["api_key"] is None
        assert config_dict["password"] is None


class TestMetadataCache:
    """Test metadata caching system."""

    def test_cache_initialization(self):
        """Test cache initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache = MetadataCache(cache_dir, default_ttl=1800)

            assert cache.cache_dir == cache_dir
            assert cache.default_ttl == 1800
            assert cache_dir.exists()

    def test_cache_operations(self):
        """Test basic cache get/set operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache = MetadataCache(cache_dir, default_ttl=3600)

            # Cache miss
            result = cache.get("test-registry", "plugins/test-plugin")
            assert result is None

            # Cache set and hit
            test_data = {"name": "test-plugin", "version": "1.0.0"}
            cache.set("test-registry", "plugins/test-plugin", test_data)

            result = cache.get("test-registry", "plugins/test-plugin")
            assert result == test_data

    def test_cache_ttl_expiration(self):
        """Test cache TTL expiration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache = MetadataCache(cache_dir, default_ttl=1)  # 1 second TTL

            # Cache data
            test_data = {"name": "test-plugin"}
            cache.set("test-registry", "plugins/test-plugin", test_data)

            # Should be available immediately
            result = cache.get("test-registry", "plugins/test-plugin")
            assert result == test_data

            # Wait for expiration
            time.sleep(1.1)

            # Should be expired
            result = cache.get("test-registry", "plugins/test-plugin", ttl=1)
            assert result is None

    def test_cache_invalidation(self):
        """Test cache invalidation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache = MetadataCache(cache_dir)

            # Cache multiple entries
            cache.set("registry1", "endpoint1", {"data": "1"})
            cache.set("registry1", "endpoint2", {"data": "2"})
            cache.set("registry2", "endpoint1", {"data": "3"})

            # Verify all cached
            assert cache.get("registry1", "endpoint1") == {"data": "1"}
            assert cache.get("registry1", "endpoint2") == {"data": "2"}
            assert cache.get("registry2", "endpoint1") == {"data": "3"}

            # Invalidate specific endpoint
            cache.invalidate("registry1", "endpoint1")
            assert cache.get("registry1", "endpoint1") is None
            assert cache.get("registry1", "endpoint2") == {"data": "2"}
            assert cache.get("registry2", "endpoint1") == {"data": "3"}

            # Invalidate entire registry
            cache.invalidate("registry1")
            assert cache.get("registry1", "endpoint2") is None
            assert cache.get("registry2", "endpoint1") == {"data": "3"}

    def test_cache_key_generation(self):
        """Test cache key generation for complex queries."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache = MetadataCache(cache_dir)

            # Cache with parameters
            params = {"query": "test", "type": "command", "limit": "10"}
            cache.set("registry", "search", {"results": []}, params)

            # Should retrieve with same parameters
            result = cache.get("registry", "search", params)
            assert result == {"results": []}

            # Should miss with different parameters
            different_params = {"query": "test", "type": "agent", "limit": "10"}
            result = cache.get("registry", "search", different_params)
            assert result is None


class TestDependencyResolver:
    """Test dependency resolution algorithm."""

    def setup_method(self):
        """Set up test dependencies."""
        self.mock_client = Mock()
        self.resolver = DependencyResolver(self.mock_client)

    def test_dependency_resolution_success(self):
        """Test successful dependency resolution."""
        # Mock plugin metadata
        plugin_metadata = PluginMetadata(
            name="test-plugin",
            namespace=None,
            description="Test plugin",
            author="Test Author",
            versions=[
                PluginVersion(
                    version="1.0.0",
                    released_at=datetime.now(),
                    dependencies=[
                        PluginDependency("dep1", DependencyConstraint.MINIMUM, "1.0.0"),
                        PluginDependency(
                            "dep2", DependencyConstraint.EXACT, "2.0.0", optional=True
                        ),
                    ],
                )
            ],
        )

        dep1_metadata = PluginMetadata(
            name="dep1",
            namespace=None,
            description="Dependency 1",
            author="Dep Author",
            versions=[PluginVersion("1.2.0", datetime.now())],
        )

        dep2_metadata = PluginMetadata(
            name="dep2",
            namespace=None,
            description="Dependency 2",
            author="Dep Author",
            versions=[PluginVersion("2.0.0", datetime.now())],
        )

        # Mock client responses
        def mock_get_metadata(name):
            if name == "test-plugin":
                return plugin_metadata
            elif name == "dep1":
                return dep1_metadata
            elif name == "dep2":
                return dep2_metadata
            return None

        self.mock_client.get_plugin_metadata = mock_get_metadata

        # Resolve dependencies
        result = self.resolver.resolve_dependencies("test-plugin", "1.0.0")

        assert result["success"]
        assert len(result["dependencies"]) == 2
        assert len(result["conflicts"]) == 0

        # Check dependency details
        dep_names = [dep["name"] for dep in result["dependencies"]]
        assert "dep1" in dep_names
        assert "dep2" in dep_names

    def test_dependency_conflict_detection(self):
        """Test dependency conflict detection."""
        # Mock plugin with conflicting dependency
        plugin_metadata = PluginMetadata(
            name="test-plugin",
            namespace=None,
            description="Test plugin",
            author="Test Author",
            versions=[
                PluginVersion(
                    version="1.0.0",
                    released_at=datetime.now(),
                    dependencies=[
                        PluginDependency("conflict-dep", DependencyConstraint.EXACT, "2.0.0")
                    ],
                )
            ],
        )

        self.mock_client.get_plugin_metadata.return_value = plugin_metadata

        # Plugin already installed with different version
        installed_plugins = {"conflict-dep": "1.0.0"}

        result = self.resolver.resolve_dependencies("test-plugin", "1.0.0", installed_plugins)

        assert not result["success"]
        assert len(result["conflicts"]) == 1
        assert result["conflicts"][0]["dependency"] == "conflict-dep"

    def test_circular_dependency_detection(self):
        """Test circular dependency detection."""
        # Create circular dependency: A -> B -> A
        plugin_a = PluginMetadata(
            name="plugin-a",
            namespace=None,
            description="Plugin A",
            author="Author",
            versions=[
                PluginVersion(
                    version="1.0.0",
                    released_at=datetime.now(),
                    dependencies=[
                        PluginDependency("plugin-b", DependencyConstraint.MINIMUM, "1.0.0")
                    ],
                )
            ],
        )

        plugin_b = PluginMetadata(
            name="plugin-b",
            namespace=None,
            description="Plugin B",
            author="Author",
            versions=[
                PluginVersion(
                    version="1.0.0",
                    released_at=datetime.now(),
                    dependencies=[
                        PluginDependency("plugin-a", DependencyConstraint.MINIMUM, "1.0.0")
                    ],
                )
            ],
        )

        def mock_get_metadata(name):
            if name == "plugin-a":
                return plugin_a
            elif name == "plugin-b":
                return plugin_b
            return None

        self.mock_client.get_plugin_metadata = mock_get_metadata

        result = self.resolver.check_circular_dependencies("plugin-a", "1.0.0")

        assert result["has_circular"]
        assert "plugin-a" in result["chain"]
        assert "plugin-b" in result["chain"]


class TestMarketplaceClient:
    """Test marketplace client functionality."""

    def setup_method(self):
        """Set up test client."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "marketplace.json"
        self.client = MarketplaceClient(self.config_path)

    def teardown_method(self):
        """Clean up test files."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_client_initialization(self):
        """Test client initialization and default config creation."""
        assert self.config_path.exists()
        assert "community" in self.client.registries

        registry = self.client.registries["community"]
        assert registry.name == "community"
        assert registry.registry_type == RegistryType.PUBLIC

    def test_registry_management(self):
        """Test adding and removing registries."""
        # Add new registry
        new_registry = RegistryConfig(
            name="private-registry",
            url="https://private.example.com/api/",
            registry_type=RegistryType.PRIVATE,
            api_key="secret-key",
        )

        assert self.client.add_registry(new_registry)
        assert "private-registry" in self.client.registries

        # Remove registry
        assert self.client.remove_registry("private-registry")
        assert "private-registry" not in self.client.registries

    def test_config_persistence(self):
        """Test configuration saving and loading."""
        # Add registry
        registry = RegistryConfig("test-registry", "https://test.com", RegistryType.PUBLIC)
        self.client.add_registry(registry)

        # Create new client instance
        new_client = MarketplaceClient(self.config_path)

        # Should load saved configuration
        assert "test-registry" in new_client.registries
        assert new_client.registries["test-registry"].url == "https://test.com/"

    @patch("pacc.plugins.marketplace.Path")
    def test_mock_plugin_metadata_retrieval(self, mock_path):
        """Test mock plugin metadata retrieval."""
        # Mock registry.json file
        mock_registry_data = {
            "plugins": [
                {
                    "name": "test-plugin",
                    "description": "A test plugin",
                    "type": "command",
                    "author": "Test Author",
                    "version": "1.0.0",
                    "repository_url": "https://github.com/test/plugin",
                    "tags": ["test", "utility"],
                    "popularity_score": 85,
                    "last_updated": "2025-01-01T00:00:00Z",
                }
            ]
        }

        # Mock Path behavior
        mock_registry_file = MagicMock()
        mock_registry_file.exists.return_value = True
        mock_registry_file.open.return_value.__enter__.return_value.read.return_value = json.dumps(
            mock_registry_data
        )
        mock_path.return_value = mock_registry_file

        # Get plugin metadata - this should use cached data instead
        # For this test, let's test the cache directly
        cached_data = {
            "name": "test-plugin",
            "namespace": None,
            "description": "A test plugin",
            "author": "Test Author",
            "plugin_type": "command",
            "status": "active",
            "versions": [
                {"version": "1.0.0", "released_at": "2025-01-01T00:00:00", "dependencies": []}
            ],
            "reviews": [],
            "created_at": None,
            "updated_at": None,
        }

        self.client.cache.set("community", "plugins/test-plugin", cached_data)
        metadata = self.client.get_plugin_metadata("test-plugin")

        assert metadata is not None
        assert metadata.name == "test-plugin"
        assert metadata.description == "A test plugin"
        assert metadata.plugin_type == "command"

    def test_cache_integration(self):
        """Test cache integration with client."""
        # Mock successful cache hit
        test_metadata = {
            "name": "cached-plugin",
            "description": "Cached plugin",
            "author": "Author",
            "versions": [],
            "reviews": [],
        }

        self.client.cache.set("community", "plugins/cached-plugin", test_metadata)

        # Should return cached data without hitting mock API
        result = self.client.get_plugin_metadata("cached-plugin")
        assert result.name == "cached-plugin"

    def test_cache_invalidation(self):
        """Test cache invalidation."""
        # Cache some data
        self.client.cache.set("test-registry", "plugins/test", {"data": "test"})

        # Verify cached
        assert self.client.cache.get("test-registry", "plugins/test") is not None

        # Invalidate
        self.client.invalidate_cache("test-registry")

        # Should be cleared
        assert self.client.cache.get("test-registry", "plugins/test") is None


class TestIntegrationScenarios:
    """Test complex integration scenarios."""

    def test_complete_dependency_resolution_workflow(self):
        """Test complete dependency resolution workflow."""
        # This would test a realistic scenario with multiple plugins,
        # dependencies, version constraints, and conflict resolution
        pass

    def test_marketplace_search_and_install_workflow(self):
        """Test searching and installing plugins from marketplace."""
        # This would test the complete workflow from search to installation
        pass

    def test_private_registry_authentication_workflow(self):
        """Test private registry authentication."""
        # This would test authentication flows for private registries
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
