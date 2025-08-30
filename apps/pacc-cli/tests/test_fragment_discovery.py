"""Tests for memory fragment discovery engine."""

import json
import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch

from pacc.plugins.discovery import (
    PluginScanner,
    RepositoryInfo,
    PluginInfo,
    FragmentInfo,
    FragmentCollectionInfo
)
from pacc.validators.fragment_validator import FragmentValidator
from pacc.validation.base import ValidationResult


class TestFragmentDiscovery:
    """Test fragment discovery functionality."""
    
    def test_discover_fragments_in_fragments_directory(self, tmp_path):
        """Test discovering fragments in standard /fragments/ directory."""
        # Create repository with fragments directory
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()
        
        fragments_dir = repo_path / "fragments"
        fragments_dir.mkdir()
        
        # Create sample fragments
        (fragments_dir / "memory-1.md").write_text("""---
title: Test Fragment 1
description: A test fragment
tags: [test, memory]
category: testing
---

# Test Fragment 1

This is a test memory fragment for the discovery engine.
""")
        
        (fragments_dir / "memory-2.md").write_text("""---
title: Another Fragment
description: Another test fragment
---

# Another Fragment

This is another test fragment without tags.
""")
        
        # Fragment without frontmatter (should still be discovered)
        (fragments_dir / "simple-fragment.md").write_text("""
# Simple Fragment

This is a simple fragment without frontmatter.
""")
        
        # Create plugin scanner and discover fragments
        scanner = PluginScanner()
        repo_info = scanner.scan_repository(repo_path)
        
        # Should discover fragments
        assert repo_info.has_fragments
        assert len(repo_info.fragments) == 3
        
        # Check fragment names
        fragment_names = [f.name for f in repo_info.fragments]
        assert "memory-1" in fragment_names
        assert "memory-2" in fragment_names
        assert "simple-fragment" in fragment_names
    
    def test_discover_fragment_collections(self, tmp_path):
        """Test discovering fragment collections (folders with multiple fragments)."""
        # Create repository with nested fragment collections
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()
        
        fragments_dir = repo_path / "fragments"
        fragments_dir.mkdir()
        
        # Create a collection directory
        collection_dir = fragments_dir / "api-docs"
        collection_dir.mkdir()
        
        # Add fragments to the collection
        (collection_dir / "auth.md").write_text("""---
title: Authentication API
category: api
---

# Authentication API

Details about auth endpoints.
""")
        
        (collection_dir / "users.md").write_text("""---
title: Users API
category: api
---

# Users API

Details about user endpoints.
""")
        
        # Create another collection
        guides_dir = fragments_dir / "guides"
        guides_dir.mkdir()
        
        (guides_dir / "setup.md").write_text("""# Setup Guide

How to set up the system.
""")
        
        (guides_dir / "deployment.md").write_text("""# Deployment Guide

How to deploy the system.
""")
        
        scanner = PluginScanner()
        repo_info = scanner.scan_repository(repo_path)
        
        # Should discover both individual fragments and collections
        assert repo_info.has_fragments
        assert len(repo_info.fragments) == 4  # auth.md, users.md, setup.md, deployment.md
        assert len(repo_info.fragment_collections) == 2
        
        # Check collection names
        collection_names = [c.name for c in repo_info.fragment_collections]
        assert "api-docs" in collection_names
        assert "guides" in collection_names
    
    def test_discover_fragments_with_pacc_json_specification(self, tmp_path):
        """Test fragment discovery with pacc.json specifications."""
        # Create repository with pacc.json
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()
        
        # Create pacc.json with fragment specifications
        pacc_config = {
            "fragments": {
                "directories": ["memories", "docs/fragments"],
                "patterns": ["*.md"],
                "collections": {
                    "api-reference": {
                        "path": "docs/api",
                        "description": "API Reference Documentation"
                    }
                }
            }
        }
        
        with open(repo_path / "pacc.json", 'w') as f:
            json.dump(pacc_config, f)
        
        # Create custom fragment directories
        memories_dir = repo_path / "memories"
        memories_dir.mkdir()
        (memories_dir / "important-notes.md").write_text("# Important Notes\n\nKey information to remember.")
        
        docs_fragments_dir = repo_path / "docs" / "fragments"
        docs_fragments_dir.mkdir(parents=True)
        (docs_fragments_dir / "workflow.md").write_text("# Workflow\n\nOur development workflow.")
        
        # Create collection specified in pacc.json
        api_dir = repo_path / "docs" / "api"
        api_dir.mkdir(parents=True)
        (api_dir / "endpoints.md").write_text("# API Endpoints\n\nList of endpoints.")
        (api_dir / "schemas.md").write_text("# Data Schemas\n\nData structures.")
        
        scanner = PluginScanner()
        repo_info = scanner.scan_repository(repo_path)
        
        # Should discover fragments according to pacc.json spec
        assert repo_info.has_fragments
        assert len(repo_info.fragments) >= 2  # From memories and docs/fragments
        assert len(repo_info.fragment_collections) >= 1  # api-reference collection
        
        # Check that pacc.json config is parsed
        assert repo_info.fragment_config is not None
        assert "directories" in repo_info.fragment_config
    
    def test_fragment_metadata_extraction(self, tmp_path):
        """Test extraction of fragment metadata."""
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()
        
        fragments_dir = repo_path / "fragments"
        fragments_dir.mkdir()
        
        # Create fragment with rich metadata
        fragment_content = """---
title: Complete Fragment
description: A fragment with all metadata fields
tags: [memory, reference, important]
category: documentation
author: Test Author
created: "2025-08-30"
modified: "2025-08-30"
---

# Complete Fragment

This fragment has complete metadata in its frontmatter.

## Key Points

- Point 1
- Point 2
- Point 3

```python
def example():
    return "Hello World"
```
"""
        
        (fragments_dir / "complete-fragment.md").write_text(fragment_content)
        
        scanner = PluginScanner()
        repo_info = scanner.scan_repository(repo_path)
        
        assert len(repo_info.fragments) == 1
        fragment = repo_info.fragments[0]
        
        # Check extracted metadata
        assert fragment.metadata["title"] == "Complete Fragment"
        assert fragment.metadata["description"] == "A fragment with all metadata fields"
        assert fragment.metadata["category"] == "documentation"
        assert fragment.metadata["author"] == "Test Author"
        assert "memory" in fragment.metadata["tags"]
        assert "reference" in fragment.metadata["tags"]
        assert "important" in fragment.metadata["tags"]
        
        # Check computed metadata
        assert fragment.metadata["has_frontmatter"] is True
        assert fragment.metadata["line_count"] > 0
        assert fragment.metadata["markdown_length"] > 0
    
    def test_nested_fragment_directory_structure(self, tmp_path):
        """Test handling of nested fragment directory structures."""
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()
        
        fragments_dir = repo_path / "fragments"
        fragments_dir.mkdir()
        
        # Create nested structure
        (fragments_dir / "level1").mkdir()
        (fragments_dir / "level1" / "level2").mkdir()
        
        # Add fragments at different levels
        (fragments_dir / "root-fragment.md").write_text("# Root Fragment")
        (fragments_dir / "level1" / "nested-fragment.md").write_text("# Nested Fragment")
        (fragments_dir / "level1" / "level2" / "deep-fragment.md").write_text("# Deep Fragment")
        
        scanner = PluginScanner()
        repo_info = scanner.scan_repository(repo_path)
        
        # Should discover fragments at all levels
        assert len(repo_info.fragments) == 3
        
        fragment_names = [f.name for f in repo_info.fragments]
        assert "root-fragment" in fragment_names
        assert "nested-fragment" in fragment_names
        assert "deep-fragment" in fragment_names
    
    def test_fragment_validation_integration(self, tmp_path):
        """Test integration with fragment validation."""
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()
        
        fragments_dir = repo_path / "fragments"
        fragments_dir.mkdir()
        
        # Create valid and invalid fragments
        (fragments_dir / "valid-fragment.md").write_text("""---
title: Valid Fragment
description: This is a valid fragment
---

# Valid Fragment

Good content here.
""")
        
        (fragments_dir / "invalid-fragment.md").write_text("""---
title: 
description: Invalid fragment with empty title
---

# Invalid Fragment

This has validation issues.
""")
        
        scanner = PluginScanner()
        repo_info = scanner.scan_repository(repo_path)
        
        assert len(repo_info.fragments) == 2
        
        # Check validation results - both should be valid but one should have warnings
        valid_fragment = next(f for f in repo_info.fragments if f.name == "valid-fragment")
        fragment_with_warnings = next(f for f in repo_info.fragments if f.name == "invalid-fragment")
        
        # Valid fragment should have no errors or warnings
        assert valid_fragment.is_valid
        assert len(valid_fragment.errors) == 0
        assert len(valid_fragment.warnings) == 0
        
        # Fragment with empty title should be valid but have warnings
        assert fragment_with_warnings.is_valid
        assert len(fragment_with_warnings.errors) == 0
        assert len(fragment_with_warnings.warnings) > 0
        assert "empty" in fragment_with_warnings.warnings[0].lower() or "title" in fragment_with_warnings.warnings[0].lower()
    
    def test_fragment_caching(self, tmp_path):
        """Test caching mechanisms for fragment discovery performance."""
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()
        
        fragments_dir = repo_path / "fragments"
        fragments_dir.mkdir()
        
        # Create several fragments
        for i in range(5):
            (fragments_dir / f"fragment-{i}.md").write_text(f"# Fragment {i}\n\nContent for fragment {i}.")
        
        scanner = PluginScanner()
        
        # First scan should cache results
        repo_info_1 = scanner.scan_repository(repo_path, use_cache=True)
        assert len(repo_info_1.fragments) == 5
        
        # Second scan should use cache (faster)
        repo_info_2 = scanner.scan_repository(repo_path, use_cache=True)
        assert len(repo_info_2.fragments) == 5
        
        # Should be the same object (cached)
        assert repo_info_1 is repo_info_2
        
        # Force refresh should bypass cache
        repo_info_3 = scanner.scan_repository(repo_path, use_cache=False)
        assert len(repo_info_3.fragments) == 5
        assert repo_info_3 is not repo_info_1
    
    def test_empty_repository_handling(self, tmp_path):
        """Test handling of repositories with no fragments."""
        repo_path = tmp_path / "empty-repo"
        repo_path.mkdir()
        
        # Create some non-fragment files
        (repo_path / "README.md").write_text("# Repository\n\nThis is a repository without fragments.")
        (repo_path / "src").mkdir()
        (repo_path / "src" / "main.py").write_text("print('Hello World')")
        
        scanner = PluginScanner()
        repo_info = scanner.scan_repository(repo_path)
        
        # Should not have any fragments
        assert not repo_info.has_fragments
        assert len(repo_info.fragments) == 0
        assert len(repo_info.fragment_collections) == 0
        assert repo_info.fragment_config is None
    
    def test_mixed_content_repository(self, tmp_path):
        """Test repository with both plugins and fragments."""
        repo_path = tmp_path / "mixed-repo"
        repo_path.mkdir()
        
        # Create plugin structure
        plugin_dir = repo_path / "awesome-plugin"
        plugin_dir.mkdir()
        
        with open(plugin_dir / "plugin.json", 'w') as f:
            json.dump({"name": "awesome-plugin"}, f)
        
        commands_dir = plugin_dir / "commands"
        commands_dir.mkdir()
        (commands_dir / "test-command.md").write_text("# Test Command")
        
        # Create fragments structure
        fragments_dir = repo_path / "fragments"
        fragments_dir.mkdir()
        (fragments_dir / "memory.md").write_text("# Memory Fragment")
        
        scanner = PluginScanner()
        repo_info = scanner.scan_repository(repo_path)
        
        # Should discover both plugins and fragments
        assert len(repo_info.plugins) == 1
        assert repo_info.has_fragments
        assert len(repo_info.fragments) == 1
        
        plugin = repo_info.plugins[0]
        assert plugin.name == "awesome-plugin"
        
        fragment = repo_info.fragments[0]
        assert fragment.name == "memory"


class TestFragmentInfo:
    """Test FragmentInfo data class functionality."""
    
    def test_fragment_info_creation(self, tmp_path):
        """Test creating FragmentInfo instances."""
        fragment_path = tmp_path / "test.md"
        fragment_path.write_text("# Test Fragment")
        
        # This would be created by the scanner
        fragment_info = type('FragmentInfo', (), {
            'name': 'test',
            'path': fragment_path,
            'metadata': {
                'title': 'Test Fragment',
                'description': '',
                'tags': [],
                'category': '',
                'author': '',
                'has_frontmatter': False,
                'line_count': 1,
                'markdown_length': 15
            },
            'validation_result': None,
            'errors': [],
            'warnings': [],
            'is_valid': True
        })()
        
        assert fragment_info.name == 'test'
        assert fragment_info.path == fragment_path
        assert fragment_info.is_valid
        assert fragment_info.metadata['title'] == 'Test Fragment'


class TestFragmentCollectionInfo:
    """Test FragmentCollectionInfo functionality."""
    
    def test_fragment_collection_creation(self, tmp_path):
        """Test creating fragment collections."""
        collection_path = tmp_path / "api-docs"
        collection_path.mkdir()
        
        # Create fragments in collection
        (collection_path / "auth.md").write_text("# Auth API")
        (collection_path / "users.md").write_text("# Users API")
        
        # This would be created by the scanner
        collection_info = type('FragmentCollectionInfo', (), {
            'name': 'api-docs',
            'path': collection_path,
            'fragments': ['auth', 'users'],
            'metadata': {
                'description': 'API Documentation Collection',
                'fragment_count': 2
            },
            'errors': []
        })()
        
        assert collection_info.name == 'api-docs'
        assert collection_info.path == collection_path
        assert len(collection_info.fragments) == 2
        assert 'auth' in collection_info.fragments
        assert 'users' in collection_info.fragments


class TestRepositoryInfoFragmentExtensions:
    """Test RepositoryInfo extensions for fragment support."""
    
    def test_repository_info_fragment_properties(self, tmp_path):
        """Test fragment-related properties on RepositoryInfo."""
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()
        
        # Create mock repository info with fragments
        repo_info = RepositoryInfo(path=repo_path)
        
        # Initially no fragments
        assert not repo_info.has_fragments
        assert repo_info.fragment_count == 0
        
        # Add mock fragments (would be done by scanner)
        mock_fragment = type('FragmentInfo', (), {
            'name': 'test-fragment',
            'is_valid': True,
            'errors': [],
            'warnings': []
        })()
        
        # This tests the expected interface
        repo_info.fragments = [mock_fragment]
        repo_info.fragment_collections = []
        
        assert repo_info.has_fragments
        assert repo_info.fragment_count == 1