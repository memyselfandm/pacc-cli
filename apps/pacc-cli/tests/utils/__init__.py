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
    "BenchmarkReporter",
    "ClaudeEnvironmentFactory",
    "MemoryMonitor",
    "MockEnvironment",
    "MockFileSystem",
    # Mock utilities
    "MockGitRepository",
    # Performance utilities
    "PerformanceProfiler",
    # Test fixtures
    "PluginRepositoryFactory",
    "TeamWorkspaceFactory",
    "assert_performance",
    "create_test_manifest",
    "create_test_plugin",
    "measure_throughput",
    "patch_claude_environment",
]
