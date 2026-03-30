"""Stack management for Claude Code - bundled extension environments.

Stacks bundle MCP servers, hooks, commands, agents, settings, and fragments
into one shareable, version-controlled unit. They are PACC's answer to
"tech packs" - a single git repo that fully configures a Claude Code environment.
"""

from .manager import (
    StackError,
    StackInfo,
    StackManifest,
    StackManager,
    StackResult,
    SyncResult,
)

__all__ = [
    "StackError",
    "StackInfo",
    "StackManifest",
    "StackManager",
    "StackResult",
    "SyncResult",
]
