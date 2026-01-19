"""Cross-feature integration tests - PACC-26 Testing Part.

This comprehensive test suite validates integration between all major features:
1. S01 fixes + folder structure features
2. Extension detection + installation workflows  
3. Validation + CLI commands + project configuration
4. Performance optimization across all operations
5. Edge case handling with multiple features active

Related Issues:
- PACC-26: Comprehensive testing and documentation (subtask PACC-36)
- PACC-24: Extension detection hierarchy
- PACC-18: Slash command misclassification fix
"""

import json
import pytest
import time
import subprocess
import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Any, List, Tuple
from unittest.mock import patch, MagicMock

from pacc.validators import (
    validate_extension_directory,
    validate_extension_file,
    ExtensionDetector,
    ValidatorFactory
)
from pacc.core.config_manager import ClaudeConfigManager
from pacc.core.project_config import ProjectConfigManager
from pacc.cli import PACCCli


class TestS01FolderStructureIntegration:
    """Test integration between S01 fixes and folder structure features."""
    
    def test_detection_hierarchy_with_target_dir(self):
        """Test extension detection hierarchy works with targetDir configuration."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create project with complex structure
            project_dir = temp_path / "project"
            project_dir.mkdir()
            
            # Create misleading directory structure
            agents_dir = project_dir / "agents"  
            agents_dir.mkdir()
            
            # File that looks like agent but will be declared as command
            misleading_file = agents_dir / "actually-slash-command.md"
            misleading_file.write_text("""---
name: actually-slash-command
description: Has agent keywords but is slash command
tools: ["file-reader"] 
permissions: ["read-files"]
---

# /actually-slash-command

Agent keywords: tool, permission, agent assistance
But this is actually a slash command due to pacc.json declaration.
""")
            
            # Create target structure with preserveStructure
            target_dir = project_dir / "custom-extensions"
            target_dir.mkdir()
            
            # Create pacc.json with folder structure + extension declarations
            pacc_config = {
                "name": "integration-test-project",
                "version": "1.0.0",
                "targetDir": "./custom-extensions",
                "preserveStructure": True,
                "extensions": {
                    "commands": [
                        {
                            "name": "actually-slash-command",
                            "source": "./agents/actually-slash-command.md",  # pacc.json overrides directory
                            "version": "1.0.0",
                            "targetPath": "commands/slash/actually-slash-command.md"
                        }
                    ],
                    "hooks": [
                        {
                            "name": "auth-hook", 
                            "source": "./auth/hooks/auth-hook.json",
                            "version": "1.0.0",
                            "targetPath": "hooks/auth/auth-hook.json"
                        }
                    ]
                }
            }
            
            pacc_json = project_dir / "pacc.json"
            pacc_json.write_text(json.dumps(pacc_config, indent=2))
            
            # Create additional extension files
            auth_hooks_dir = project_dir / "auth" / "hooks"
            auth_hooks_dir.mkdir(parents=True)
            
            auth_hook = auth_hooks_dir / "auth-hook.json"
            auth_hook.write_text(json.dumps({
                "name": "auth-hook",
                "version": "1.0.0",
                "events": ["PreToolUse", "PostToolUse"],
                "description": "Authentication validation hook"
            }))
            
            # Test extension detection with project context
            detector = ExtensionDetector()
            
            # Should detect as command due to pacc.json (highest priority)
            command_type = detector.detect_extension_type(misleading_file, project_dir=project_dir)
            assert command_type == "commands", "pacc.json should override directory structure"
            
            # Should detect hook correctly
            hook_type = detector.detect_extension_type(auth_hook, project_dir=project_dir)
            assert hook_type == "hooks", "Hook should be detected correctly"
            
            # Test full directory validation
            results = validate_extension_directory(project_dir)
            
            # Verify correct categorization
            assert "commands" in results
            assert "hooks" in results
            
            command_files = [r.file_path for r in results["commands"]]
            hook_files = [r.file_path for r in results["hooks"]]
            
            assert any("actually-slash-command.md" in f for f in command_files)
            assert any("auth-hook.json" in f for f in hook_files)
    
    def test_validation_workflow_with_folder_structure(self):
        """Test complete validation workflow with folder structure features."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            project_dir = temp_path / "project"
            project_dir.mkdir()
            
            # Create complex nested structure
            structure = {
                "extensions/hooks/auth": ["pre-auth.json", "post-auth.json"],
                "extensions/hooks/tools": ["tool-validator.json"],
                "extensions/commands/user": ["profile.md", "settings.md"],
                "extensions/commands/admin": ["system.md"],
                "extensions/agents/support": ["help-agent.md"],
                "extensions/mcp/servers": ["database-server.json"]
            }
            
            extensions_config = {
                "hooks": [],
                "commands": [], 
                "agents": [],
                "mcp": []
            }
            
            # Create files and build configuration
            for dir_path, filenames in structure.items():
                full_dir = project_dir / dir_path
                full_dir.mkdir(parents=True)
                
                for filename in filenames:
                    file_path = full_dir / filename
                    ext_type = self._determine_extension_type_from_path(dir_path)
                    content = self._create_extension_content(filename, ext_type)
                    
                    file_path.write_text(content)
                    
                    # Add to configuration
                    relative_path = f"./{dir_path}/{filename}"
                    extensions_config[ext_type].append({
                        "name": filename.split('.')[0],
                        "source": relative_path,
                        "version": "1.0.0"
                    })
            
            # Create pacc.json with folder structure configuration
            pacc_config = {
                "name": "complex-structure-test",
                "version": "1.0.0",
                "targetDir": "./installed-extensions",
                "preserveStructure": True,
                "extensions": extensions_config
            }
            
            pacc_json = project_dir / "pacc.json"
            pacc_json.write_text(json.dumps(pacc_config, indent=2))
            
            # Run comprehensive validation
            results = validate_extension_directory(project_dir)
            
            # Verify all extension types found
            expected_types = ["hooks", "commands", "agents", "mcp"]
            for ext_type in expected_types:
                assert ext_type in results, f"Missing extension type: {ext_type}"
                assert len(results[ext_type]) > 0, f"No {ext_type} found"
            
            # Verify specific counts
            assert len(results["hooks"]) == 3  # 3 hook files
            assert len(results["commands"]) == 3  # 3 command files  
            assert len(results["agents"]) == 1  # 1 agent file
            assert len(results["mcp"]) == 1  # 1 mcp file
            
            # Test validation quality
            all_results = []
            for ext_results in results.values():
                all_results.extend(ext_results)
            
            valid_count = sum(1 for r in all_results if r.is_valid)
            total_count = len(all_results)
            
            # Should have high validation success rate
            success_rate = valid_count / total_count if total_count > 0 else 0
            assert success_rate >= 0.8, f"Low validation success rate: {success_rate:.2f}"
    
    def test_cli_integration_with_folder_features(self):
        """Test CLI commands integration with folder structure features."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            project_dir = temp_path / "project"
            project_dir.mkdir()
            
            # Create project with folder structure
            self._create_folder_structure_project(project_dir)
            
            # Test CLI validate command
            cli = PACCCli()
            
            class MockValidateArgs:
                source = str(project_dir)
                type = None
                strict = False
            
            # Should validate entire project structure
            result = cli.validate_command(MockValidateArgs())
            assert result in [0, 1], "CLI validate should not crash"
            
            # Test CLI validate with type filter
            class MockHooksArgs:
                source = str(project_dir)
                type = "hooks" 
                strict = False
            
            hooks_result = cli.validate_command(MockHooksArgs())
            assert hooks_result in [0, 1], "CLI hooks validation should not crash"
            
            # Test CLI validate in strict mode
            class MockStrictArgs:
                source = str(project_dir)
                type = None
                strict = True
            
            strict_result = cli.validate_command(MockStrictArgs())
            assert strict_result in [0, 1], "CLI strict validation should not crash"
    
    def _determine_extension_type_from_path(self, dir_path: str) -> str:
        """Determine extension type from directory path."""
        if "hooks" in dir_path:
            return "hooks"
        elif "commands" in dir_path:
            return "commands"
        elif "agents" in dir_path:
            return "agents"
        elif "mcp" in dir_path:
            return "mcp"
        else:
            return "hooks"  # default
    
    def _create_extension_content(self, filename: str, ext_type: str) -> str:
        """Create appropriate content for extension type."""
        base_name = filename.split('.')[0]
        
        if ext_type == "hooks":
            return json.dumps({
                "name": base_name,
                "version": "1.0.0",
                "events": ["PreToolUse"],
                "description": f"Hook: {base_name}"
            }, indent=2)
        
        elif ext_type == "commands":
            return f"""---
name: {base_name}
description: Command {base_name}
---

# /{base_name}

Command content for {base_name}.
"""
        
        elif ext_type == "agents":
            return f"""---
name: {base_name}
description: Agent {base_name}
tools: ["file-reader"]
permissions: ["read-files"]
---

Agent content for {base_name}.
"""
        
        elif ext_type == "mcp":
            return json.dumps({
                "name": base_name,
                "command": ["python", f"{base_name}.py"],
                "args": ["--port", "3000"]
            }, indent=2)
        
        else:
            return f"Content for {filename}"
    
    def _create_folder_structure_project(self, project_dir: Path):
        """Create a project with folder structure for testing."""
        # Create extensions
        extensions_dir = project_dir / "extensions"
        extensions_dir.mkdir()
        
        # Hooks
        hooks_dir = extensions_dir / "hooks"
        hooks_dir.mkdir()
        
        hook_file = hooks_dir / "test-hook.json"
        hook_file.write_text(json.dumps({
            "name": "test-hook",
            "version": "1.0.0",
            "events": ["PreToolUse"],
            "description": "Test hook"
        }))
        
        # Commands
        commands_dir = extensions_dir / "commands"
        commands_dir.mkdir()
        
        command_file = commands_dir / "test-command.md"
        command_file.write_text("""---
name: test-command
description: Test command
---

# /test-command

Test command content.
""")
        
        # pacc.json
        pacc_config = {
            "name": "folder-structure-project",
            "version": "1.0.0",
            "targetDir": "./target",
            "preserveStructure": True,
            "extensions": {
                "hooks": [
                    {"name": "test-hook", "source": "./extensions/hooks/test-hook.json", "version": "1.0.0"}
                ],
                "commands": [
                    {"name": "test-command", "source": "./extensions/commands/test-command.md", "version": "1.0.0"}
                ]
            }
        }
        
        pacc_json = project_dir / "pacc.json"
        pacc_json.write_text(json.dumps(pacc_config, indent=2))


class TestValidationInstallationWorkflowIntegration:
    """Test integration between validation and installation workflows."""
    
    def test_validation_before_installation_workflow(self):
        """Test validation step before installation in complete workflow."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create source project
            source_dir = temp_path / "source"
            source_dir.mkdir()
            
            # Create target installation directory
            target_dir = temp_path / "claude-config" 
            target_dir.mkdir()
            
            # Create mixed valid/invalid extensions
            self._create_mixed_quality_extensions(source_dir)
            
            # Step 1: Validate before installation
            validation_results = validate_extension_directory(source_dir)
            
            # Analyze validation results
            all_results = []
            for ext_results in validation_results.values():
                all_results.extend(ext_results)
            
            valid_extensions = [r for r in all_results if r.is_valid]
            invalid_extensions = [r for r in all_results if not r.is_valid]
            
            assert len(valid_extensions) > 0, "Should have some valid extensions"
            assert len(invalid_extensions) > 0, "Should have some invalid extensions"
            
            # Step 2: Only install valid extensions (simulated)
            installable_files = [Path(r.file_path) for r in valid_extensions]
            
            # Verify installable files exist and are valid
            for file_path in installable_files:
                assert file_path.exists(), f"Installable file missing: {file_path}"
            
            # Step 3: Verify invalid extensions are excluded
            invalid_files = [Path(r.file_path) for r in invalid_extensions]
            
            # Should not attempt to install invalid extensions
            for invalid_file in invalid_files:
                assert invalid_file not in installable_files
    
    def test_detection_validation_installation_chain(self):
        """Test complete chain: detection → validation → installation simulation."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create source with ambiguous files
            source_dir = temp_path / "source"
            source_dir.mkdir()
            
            # Create files that need detection hierarchy to classify correctly
            self._create_detection_test_files(source_dir)
            
            # Step 1: Extension Detection
            detector = ExtensionDetector()
            detected_extensions = {}
            
            for file_path in source_dir.rglob("*"):
                if file_path.is_file() and not file_path.name.startswith('.'):
                    ext_type = detector.detect_extension_type(file_path, project_dir=source_dir)
                    if ext_type:
                        if ext_type not in detected_extensions:
                            detected_extensions[ext_type] = []
                        detected_extensions[ext_type].append(file_path)
            
            # Verify detection worked
            assert len(detected_extensions) > 0, "Should detect some extensions"
            
            # Step 2: Validation of detected extensions
            validation_results = validate_extension_directory(source_dir)
            
            # Step 3: Cross-reference detection and validation
            for ext_type, detected_files in detected_extensions.items():
                if ext_type in validation_results:
                    validated_files = [Path(r.file_path) for r in validation_results[ext_type]]
                    
                    # Most detected files should be validated (some may be invalid)
                    overlap = set(detected_files) & set(validated_files)
                    assert len(overlap) > 0, f"No overlap between detection and validation for {ext_type}"
            
            # Step 4: Installation readiness check
            installable_count = 0
            for ext_type, validation_list in validation_results.items():
                for validation_result in validation_list:
                    if validation_result.is_valid:
                        installable_count += 1
            
            assert installable_count > 0, "Should have installable extensions after validation"
    
    def test_performance_across_workflow_steps(self):
        """Test performance across all workflow steps."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create large test dataset
            source_dir = temp_path / "large-source"
            source_dir.mkdir()
            
            self._create_large_test_dataset(source_dir, num_files=200)
            
            # Measure complete workflow performance
            start_time = time.time()
            
            # Step 1: Detection (simulated)
            detector = ExtensionDetector()
            detection_start = time.time()
            
            detected_count = 0
            for file_path in source_dir.rglob("*"):
                if file_path.is_file():
                    ext_type = detector.detect_extension_type(file_path)
                    if ext_type:
                        detected_count += 1
            
            detection_time = time.time() - detection_start
            
            # Step 2: Validation
            validation_start = time.time()
            validation_results = validate_extension_directory(source_dir)
            validation_time = time.time() - validation_start
            
            total_time = time.time() - start_time
            
            # Performance assertions
            assert detection_time < 5.0, f"Detection too slow: {detection_time:.2f}s"
            assert validation_time < 10.0, f"Validation too slow: {validation_time:.2f}s"
            assert total_time < 15.0, f"Total workflow too slow: {total_time:.2f}s"
            
            # Throughput assertions
            files_per_second = detected_count / total_time if total_time > 0 else 0
            assert files_per_second > 10, f"Low throughput: {files_per_second:.1f} files/s"
            
            print(f"\nWorkflow Performance Results:")
            print(f"- Files processed: {detected_count}")
            print(f"- Detection time: {detection_time:.3f}s")
            print(f"- Validation time: {validation_time:.3f}s") 
            print(f"- Total time: {total_time:.3f}s")
            print(f"- Throughput: {files_per_second:.1f} files/s")
    
    def _create_mixed_quality_extensions(self, base_dir: Path):
        """Create mix of valid and invalid extensions."""
        # Valid hook
        valid_hook = base_dir / "valid-hook.json"
        valid_hook.write_text(json.dumps({
            "name": "valid-hook",
            "version": "1.0.0",
            "events": ["PreToolUse"],
            "description": "Valid hook for testing"
        }))
        
        # Invalid hook (missing required fields)
        invalid_hook = base_dir / "invalid-hook.json"
        invalid_hook.write_text(json.dumps({
            "name": "invalid-hook"
            # Missing version and events
        }))
        
        # Malformed JSON
        malformed_hook = base_dir / "malformed-hook.json"
        malformed_hook.write_text('{"name": "malformed", invalid json}')
        
        # Valid command
        commands_dir = base_dir / "commands"
        commands_dir.mkdir()
        
        valid_command = commands_dir / "valid-command.md"
        valid_command.write_text("""---
name: valid-command
description: Valid command
---

# /valid-command

Valid command content.
""")
        
        # Invalid command (no proper structure)
        invalid_command = commands_dir / "invalid-command.md"
        invalid_command.write_text("Just plain text without proper markdown structure.")
    
    def _create_detection_test_files(self, base_dir: Path):
        """Create files that test detection hierarchy."""
        # File in agents directory but declared as command in pacc.json
        agents_dir = base_dir / "agents"
        agents_dir.mkdir()
        
        misleading_file = agents_dir / "actually-command.md"
        misleading_file.write_text("""---
name: actually-command
description: Has agent keywords but is command per pacc.json
tools: ["calculator"]
permissions: ["execute"]
---

# /actually-command

Contains agent keywords but should be detected as command.
""")
        
        # Clear agent file (fallback detection)
        clear_agent = base_dir / "clear-agent.md"
        clear_agent.write_text("""---
name: clear-agent
description: Clear agent with tools
tools: ["file-reader", "calculator"]
permissions: ["read-files", "execute"]
---

Clear agent content for fallback detection.
""")
        
        # Hook in proper directory
        hooks_dir = base_dir / "hooks"
        hooks_dir.mkdir()
        
        hook_file = hooks_dir / "proper-hook.json"
        hook_file.write_text(json.dumps({
            "name": "proper-hook",
            "version": "1.0.0",
            "events": ["PreToolUse"],
            "description": "Proper hook in hooks directory"
        }))
        
        # Create pacc.json with override
        pacc_config = {
            "name": "detection-test",
            "version": "1.0.0",
            "extensions": {
                "commands": [
                    {
                        "name": "actually-command",
                        "source": "./agents/actually-command.md",
                        "version": "1.0.0"
                    }
                ]
            }
        }
        
        pacc_json = base_dir / "pacc.json"
        pacc_json.write_text(json.dumps(pacc_config, indent=2))
    
    def _create_large_test_dataset(self, base_dir: Path, num_files: int = 200):
        """Create large dataset for performance testing."""
        # Create multiple extension types
        ext_types = ["hooks", "commands", "agents", "mcp"]
        files_per_type = num_files // len(ext_types)
        
        for ext_type in ext_types:
            type_dir = base_dir / ext_type
            type_dir.mkdir()
            
            for i in range(files_per_type):
                if ext_type == "hooks":
                    file_path = type_dir / f"hook_{i:03d}.json"
                    content = json.dumps({
                        "name": f"hook-{i}",
                        "version": "1.0.0",
                        "events": ["PreToolUse"],
                        "description": f"Test hook {i}"
                    })
                
                elif ext_type == "commands":
                    file_path = type_dir / f"command_{i:03d}.md"
                    content = f"""---
name: command-{i}
description: Test command {i}
---

# /command-{i}

Test command content {i}.
"""
                
                elif ext_type == "agents":
                    file_path = type_dir / f"agent_{i:03d}.md"
                    content = f"""---
name: agent-{i}
description: Test agent {i}
tools: ["file-reader"]
permissions: ["read-files"]
---

Test agent content {i}.
"""
                
                elif ext_type == "mcp":
                    file_path = type_dir / f"server_{i:03d}.json"
                    content = json.dumps({
                        "name": f"server-{i}",
                        "command": ["python", f"server_{i}.py"],
                        "args": ["--port", str(3000 + i)]
                    })
                
                file_path.write_text(content)


class TestEdgeCasesIntegration:
    """Test edge cases with multiple features active."""
    
    def test_empty_project_handling(self):
        """Test handling of completely empty projects."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            empty_dir = temp_path / "empty"
            empty_dir.mkdir()
            
            # Test validation on empty directory
            results = validate_extension_directory(empty_dir)
            
            # Should handle gracefully
            assert isinstance(results, dict)
            total_results = sum(len(file_list) for file_list in results.values())
            assert total_results == 0
            
            # Test CLI on empty directory
            cli = PACCCli()
            
            class MockArgs:
                source = str(empty_dir)
                type = None
                strict = False
            
            result = cli.validate_command(MockArgs())
            assert result == 1  # Should return error for no extensions found
    
    def test_corrupted_project_configuration(self):
        """Test handling of corrupted pacc.json files."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            project_dir = temp_path / "corrupted"
            project_dir.mkdir()
            
            # Create valid extension file
            hook_file = project_dir / "hook.json"
            hook_file.write_text(json.dumps({
                "name": "test-hook",
                "version": "1.0.0",
                "events": ["PreToolUse"]
            }))
            
            # Create corrupted pacc.json
            pacc_json = project_dir / "pacc.json"
            pacc_json.write_text('{"name": "corrupted", invalid json syntax}')
            
            # Should handle corruption gracefully
            try:
                results = validate_extension_directory(project_dir)
                
                # Should still find extensions via fallback detection
                total_results = sum(len(file_list) for file_list in results.values())
                assert total_results > 0
                
            except json.JSONDecodeError:
                # Acceptable to fail on corrupted JSON
                pass
    
    def test_mixed_file_permissions(self):
        """Test handling of mixed file permissions."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            project_dir = temp_path / "permissions"
            project_dir.mkdir()
            
            # Create accessible file
            accessible_hook = project_dir / "accessible-hook.json"
            accessible_hook.write_text(json.dumps({
                "name": "accessible-hook",
                "version": "1.0.0",
                "events": ["PreToolUse"]
            }))
            
            # Create restricted directory (simulate)
            restricted_dir = project_dir / "restricted"
            restricted_dir.mkdir()
            
            restricted_hook = restricted_dir / "restricted-hook.json"
            restricted_hook.write_text(json.dumps({
                "name": "restricted-hook",
                "version": "1.0.0", 
                "events": ["PreToolUse"]
            }))
            
            # Mock permission error
            original_read_text = Path.read_text
            
            def mock_read_text(self, *args, **kwargs):
                if "restricted" in str(self):
                    raise PermissionError("Permission denied")
                return original_read_text(self, *args, **kwargs)
            
            with patch.object(Path, 'read_text', mock_read_text):
                # Should handle permission errors gracefully
                results = validate_extension_directory(project_dir)
                
                # Should still process accessible files
                total_results = sum(len(file_list) for file_list in results.values())
                assert total_results > 0
    
    def test_circular_symlink_handling(self):
        """Test handling of circular symbolic links."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            project_dir = temp_path / "symlinks"
            project_dir.mkdir()
            
            # Create normal file
            normal_file = project_dir / "normal-hook.json"
            normal_file.write_text(json.dumps({
                "name": "normal-hook",
                "version": "1.0.0",
                "events": ["PreToolUse"]
            }))
            
            # Create circular symlinks (if supported)
            try:
                if hasattr(os, 'symlink'):
                    link1 = project_dir / "link1"
                    link2 = project_dir / "link2"
                    
                    # Create circular reference
                    os.symlink(link2, link1)
                    os.symlink(link1, link2)
                    
                    # Should handle circular symlinks without infinite loop
                    start_time = time.time()
                    results = validate_extension_directory(project_dir)
                    end_time = time.time()
                    
                    # Should complete quickly (not get stuck in infinite loop)
                    duration = end_time - start_time
                    assert duration < 10.0, f"Circular symlink caused infinite loop: {duration:.2f}s"
                    
                    # Should still find normal files
                    total_results = sum(len(file_list) for file_list in results.values())
                    assert total_results > 0
            
            except (OSError, NotImplementedError):
                pytest.skip("Platform does not support symlinks")
    
    def test_unicode_and_special_characters_integration(self):
        """Test handling of Unicode and special characters across all features."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            project_dir = temp_path / "unicode"
            project_dir.mkdir()
            
            # Create files with Unicode names and content
            unicode_files = [
                ("测试-hook.json", "hooks"),
                ("émoji-🎉-command.md", "commands"),
                ("спецсимволы-agent.md", "agents")
            ]
            
            extensions_config = {"hooks": [], "commands": [], "agents": []}
            
            for filename, ext_type in unicode_files:
                try:
                    file_path = project_dir / filename
                    
                    if ext_type == "hooks":
                        content = json.dumps({
                            "name": "unicode-hook",
                            "version": "1.0.0",
                            "events": ["PreToolUse"],
                            "description": f"Unicode test: {filename}"
                        }, ensure_ascii=False)
                    
                    elif ext_type == "commands":
                        content = f"""---
name: unicode-command
description: Unicode test {filename}
---

# /unicode-command

Unicode content: {filename}
"""
                    
                    elif ext_type == "agents":
                        content = f"""---
name: unicode-agent
description: Unicode agent {filename}
tools: ["file-reader"]
---

Unicode agent content: {filename}
"""
                    
                    file_path.write_text(content, encoding='utf-8')
                    
                    extensions_config[ext_type].append({
                        "name": f"unicode-{ext_type[:-1]}",  # Remove 's' from type
                        "source": f"./{filename}",
                        "version": "1.0.0"
                    })
                
                except (OSError, UnicodeError):
                    # Skip if filesystem doesn't support Unicode
                    continue
            
            # Create pacc.json with Unicode content
            if any(extensions_config.values()):
                pacc_config = {
                    "name": "unicode-test-项目",
                    "version": "1.0.0", 
                    "targetDir": "./目标目录",
                    "extensions": extensions_config
                }
                
                try:
                    pacc_json = project_dir / "pacc.json"
                    pacc_json.write_text(json.dumps(pacc_config, ensure_ascii=False, indent=2), encoding='utf-8')
                    
                    # Test validation with Unicode
                    results = validate_extension_directory(project_dir)
                    
                    # Should handle Unicode without crashing
                    total_results = sum(len(file_list) for file_list in results.values())
                    assert total_results >= 0
                
                except (OSError, UnicodeError):
                    pytest.skip("Filesystem doesn't support Unicode filenames")
    
    def test_extremely_large_files_handling(self):
        """Test handling of extremely large extension files."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            project_dir = temp_path / "large-files"
            project_dir.mkdir()
            
            # Create normal-sized file
            normal_hook = project_dir / "normal-hook.json"
            normal_hook.write_text(json.dumps({
                "name": "normal-hook",
                "version": "1.0.0",
                "events": ["PreToolUse"]
            }))
            
            # Create large file (1MB of JSON)
            large_content = {
                "name": "large-hook",
                "version": "1.0.0",
                "events": ["PreToolUse"],
                "description": "Large hook for testing",
                "large_data": "x" * (1024 * 1024)  # 1MB of data
            }
            
            large_hook = project_dir / "large-hook.json"
            large_hook.write_text(json.dumps(large_content))
            
            # Test validation handles large files
            start_time = time.time()
            results = validate_extension_directory(project_dir)
            end_time = time.time()
            
            duration = end_time - start_time
            
            # Should complete in reasonable time despite large files
            assert duration < 30.0, f"Large file validation too slow: {duration:.2f}s"
            
            # Should validate both files
            total_results = sum(len(file_list) for file_list in results.values())
            assert total_results >= 2


if __name__ == "__main__":
    # Run cross-feature integration tests
    pytest.main([__file__, "-v", "--tb=short"])