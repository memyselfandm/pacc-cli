"""Test utilities for PACC E2E and performance tests."""

from .fixtures import (
    ClaudeEnvironmentFactory,
    PluginRepositoryFactory,
    TeamWorkspaceFactory,
    create_test_manifest,
    create_test_plugin,
)
from .mocks import MockEnvironment, MockFileSystem, MockGitRepository, patch_claude_environment
from .performance import (
    BenchmarkReporter,
    MemoryMonitor,
    PerformanceProfiler,
    assert_performance,
    measure_throughput,
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
    "patch_claude_environment",
]
