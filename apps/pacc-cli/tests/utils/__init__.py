"""Test utilities for PACC E2E and performance tests."""

from .performance import (
    PerformanceProfiler,
    MemoryMonitor,
    BenchmarkReporter,
    assert_performance,
    measure_throughput
)

from .fixtures import (
    PluginRepositoryFactory,
    TeamWorkspaceFactory,
    ClaudeEnvironmentFactory,
    create_test_plugin,
    create_test_manifest
)

from .mocks import (
    MockGitRepository,
    MockFileSystem,
    MockEnvironment,
    patch_claude_environment
)

__all__ = [
    # Performance utilities
    "PerformanceProfiler",
    "MemoryMonitor", 
    "BenchmarkReporter",
    "assert_performance",
    "measure_throughput",
    
    # Test fixtures
    "PluginRepositoryFactory",
    "TeamWorkspaceFactory", 
    "ClaudeEnvironmentFactory",
    "create_test_plugin",
    "create_test_manifest",
    
    # Mock utilities
    "MockGitRepository",
    "MockFileSystem",
    "MockEnvironment",
    "patch_claude_environment"
]