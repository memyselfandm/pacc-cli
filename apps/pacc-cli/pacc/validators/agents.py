"""Agents validator for Claude Code agent extensions."""

import re
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .base import BaseValidator, ValidationResult
from .utils import parse_claude_frontmatter


class AgentsValidator(BaseValidator):
    """Validator for Claude Code agent extensions."""
    
    # Required fields in agent YAML frontmatter per Claude Code documentation
    REQUIRED_FRONTMATTER_FIELDS = ["name", "description"]
    
    # Optional fields per Claude Code documentation
    OPTIONAL_FRONTMATTER_FIELDS = {
        "tools": str,  # Comma-separated string like "Read, Write, Bash"
        "model": str,  # Optional model string like "claude-3-opus"
        "color": str   # Optional terminal color like "cyan", "red"
    }
    
    # Known Claude Code tools for validation
    # This is not exhaustive as MCP tools can be added dynamically
    COMMON_TOOLS = {
        "Read", "Write", "Edit", "MultiEdit", "Bash", "Grep", 
        "Glob", "WebFetch", "WebSearch", "TodoWrite", "Task",
        "NotebookEdit", "BashOutput", "KillBash", "ExitPlanMode",
        "LS"
    }
    
    def __init__(self, max_file_size: int = 10 * 1024 * 1024):
        """Initialize agents validator."""
        super().__init__(max_file_size)
        
        # Pre-compile regex patterns
        self._yaml_frontmatter_pattern = re.compile(
            r'^---\s*\n(.*?)\n---\s*\n(.*)', 
            re.DOTALL
        )
        self._name_pattern = re.compile(r'^[a-zA-Z0-9_-]+$')
    
    def get_extension_type(self) -> str:
        """Return the extension type this validator handles."""
        return "agents"
    
    def validate_single(self, file_path: Union[str, Path]) -> ValidationResult:
        """Validate a single agent file."""
        file_path = Path(file_path)
        result = ValidationResult(
            is_valid=True,
            file_path=str(file_path),
            extension_type=self.get_extension_type()
        )
        
        # Check file accessibility
        access_error = self._validate_file_accessibility(file_path)
        if access_error:
            result.add_error(
                access_error.code,
                access_error.message,
                suggestion=access_error.suggestion
            )
            return result
        
        # Read file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError as e:
            result.add_error(
                "ENCODING_ERROR",
                f"File encoding error: {e}",
                suggestion="Ensure file is saved with UTF-8 encoding"
            )
            return result
        except Exception as e:
            result.add_error(
                "FILE_READ_ERROR",
                f"Cannot read file: {e}",
                suggestion="Check file permissions and format"
            )
            return result
        
        # Parse YAML frontmatter and markdown content
        frontmatter_error, frontmatter, markdown_content = self._parse_agent_file(content, result)
        if frontmatter_error:
            return result
        
        # Validate frontmatter structure
        self._validate_frontmatter(frontmatter, result)
        
        # Validate markdown content
        self._validate_markdown_content(markdown_content, result)
        
        # Extract metadata for successful validations
        if result.is_valid and frontmatter:
            # Parse tools if present
            tools_str = frontmatter.get("tools", "")
            tools_list = [t.strip() for t in tools_str.split(",")] if tools_str else []
            
            result.metadata = {
                "name": frontmatter.get("name", ""),
                "description": frontmatter.get("description", ""),
                "tools": tools_list,
                "tools_raw": tools_str,
                "markdown_length": len(markdown_content.strip())
            }
        
        return result
    
    def _find_extension_files(self, directory: Path) -> List[Path]:
        """Find agent files in the given directory."""
        agent_files = []
        
        # Look for .md files (agents are typically markdown files)
        for md_file in directory.rglob("*.md"):
            # Quick check if this might be an agent file
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read(1024)  # Read first 1KB
                    if content.startswith("---") and "name:" in content:
                        agent_files.append(md_file)
            except Exception:
                # If we can't read it, let the full validation handle the error
                agent_files.append(md_file)
        
        return agent_files
    
    def _parse_agent_file(self, content: str, result: ValidationResult) -> tuple[Optional[bool], Optional[Dict[str, Any]], str]:
        """Parse agent file into frontmatter and markdown content."""
        # Check for YAML frontmatter
        match = self._yaml_frontmatter_pattern.match(content)
        if not match:
            # Check if file starts with --- but doesn't have closing ---
            if content.strip().startswith("---"):
                result.add_error(
                    "MALFORMED_FRONTMATTER",
                    "Agent file has opening --- but no closing --- for YAML frontmatter",
                    suggestion="Add closing --- to complete the YAML frontmatter section"
                )
                return True, None, ""
            else:
                result.add_error(
                    "MISSING_FRONTMATTER",
                    "Agent file must start with YAML frontmatter (---)",
                    suggestion="Add YAML frontmatter at the beginning of the file"
                )
                return True, None, ""
        
        yaml_content = match.group(1)
        markdown_content = match.group(2)
        
        # Parse YAML frontmatter using lenient Claude Code parser
        frontmatter = parse_claude_frontmatter(yaml_content)
        
        if frontmatter is None:
            # If lenient parser still failed, try strict YAML for better error message
            try:
                yaml.safe_load(yaml_content)
            except yaml.YAMLError as e:
                result.add_error(
                    "INVALID_YAML",
                    f"Invalid YAML in frontmatter: {e}",
                    suggestion="Fix YAML syntax errors in the frontmatter"
                )
            except Exception as e:
                result.add_error(
                    "YAML_PARSE_ERROR",
                    f"Error parsing YAML frontmatter: {e}",
                    suggestion="Check YAML formatting and syntax"
                )
            return True, None, ""
        
        if not frontmatter:
            result.add_error(
                "EMPTY_FRONTMATTER",
                "YAML frontmatter is empty",
                suggestion="Add required fields to the YAML frontmatter"
            )
            return True, None, ""
        
        if not isinstance(frontmatter, dict):
            result.add_error(
                "INVALID_FRONTMATTER_FORMAT",
                "YAML frontmatter must be a dictionary/object",
                suggestion="Ensure frontmatter contains key-value pairs"
            )
            return True, None, ""
        
        return None, frontmatter, markdown_content
    
    def _validate_frontmatter(self, frontmatter: Dict[str, Any], result: ValidationResult) -> None:
        """Validate agent YAML frontmatter structure and content."""
        file_path = result.file_path
        
        # Validate required fields
        for field in self.REQUIRED_FRONTMATTER_FIELDS:
            if field not in frontmatter:
                result.add_error(
                    "MISSING_REQUIRED_FIELD",
                    f"Missing required field '{field}' in frontmatter",
                    suggestion=f"Add the '{field}' field to the YAML frontmatter"
                )
            elif not frontmatter[field] or (isinstance(frontmatter[field], str) and not frontmatter[field].strip()):
                result.add_error(
                    "EMPTY_REQUIRED_FIELD",
                    f"Required field '{field}' cannot be empty",
                    suggestion=f"Provide a value for the '{field}' field"
                )
        
        # Validate field types
        for field, expected_type in self.OPTIONAL_FRONTMATTER_FIELDS.items():
            if field in frontmatter:
                value = frontmatter[field]
                if not isinstance(value, expected_type):
                    type_name = expected_type.__name__ if not isinstance(expected_type, tuple) else " or ".join(t.__name__ for t in expected_type)
                    result.add_error(
                        "INVALID_FIELD_TYPE",
                        f"Field '{field}' must be of type {type_name}, got {type(value).__name__}",
                        suggestion=f"Change '{field}' to the correct type"
                    )
        
        # Skip detailed validation if required fields are missing
        if not all(field in frontmatter for field in self.REQUIRED_FRONTMATTER_FIELDS):
            return
        
        # Validate specific fields
        self._validate_agent_name(frontmatter.get("name"), result)
        self._validate_agent_description(frontmatter.get("description"), result)
        
        if "tools" in frontmatter:
            self._validate_tools(frontmatter["tools"], result)
        
        # Check for unknown fields and warn about them
        known_fields = set(self.REQUIRED_FRONTMATTER_FIELDS) | set(self.OPTIONAL_FRONTMATTER_FIELDS.keys())
        for field in frontmatter:
            if field not in known_fields:
                result.add_warning(
                    "UNKNOWN_FRONTMATTER_FIELD",
                    f"Unknown field '{field}' in agent frontmatter",
                    suggestion=f"Valid fields are: {', '.join(sorted(known_fields))}"
                )
    
    def _validate_agent_name(self, name: str, result: ValidationResult) -> None:
        """Validate agent name format."""
        if not isinstance(name, str):
            result.add_error(
                "INVALID_NAME_TYPE",
                "Agent name must be a string",
                suggestion="Change name to a string value"
            )
            return
        
        if not name.strip():
            result.add_error(
                "EMPTY_NAME",
                "Agent name cannot be empty",
                suggestion="Provide a descriptive name for the agent"
            )
            return
        
        # Check name format (alphanumeric, hyphens, underscores, spaces allowed)
        if not re.match(r'^[a-zA-Z0-9_\s-]+$', name):
            result.add_error(
                "INVALID_NAME_FORMAT",
                f"Agent name '{name}' contains invalid characters",
                suggestion="Use only alphanumeric characters, spaces, hyphens, and underscores"
            )
        
        # Check name length
        if len(name) > 100:
            result.add_error(
                "NAME_TOO_LONG",
                f"Agent name is too long ({len(name)} characters, max 100)",
                suggestion="Use a shorter, more concise name"
            )
        
        # Check for reserved names
        reserved_names = {"system", "default", "internal", "claude", "anthropic", "assistant"}
        if name.lower() in reserved_names:
            result.add_warning(
                "RESERVED_NAME",
                f"Agent name '{name}' is reserved and may cause conflicts",
                suggestion="Consider using a different name"
            )
    
    def _validate_agent_description(self, description: str, result: ValidationResult) -> None:
        """Validate agent description."""
        if not isinstance(description, str):
            result.add_error(
                "INVALID_DESCRIPTION_TYPE",
                "Agent description must be a string",
                suggestion="Change description to a string value"
            )
            return
        
        if not description.strip():
            result.add_error(
                "EMPTY_DESCRIPTION",
                "Agent description cannot be empty",
                suggestion="Provide a description of what the agent does"
            )
            return
        
        if len(description) > 500:
            result.add_warning(
                "DESCRIPTION_TOO_LONG",
                f"Agent description is very long ({len(description)} characters)",
                suggestion="Consider using a more concise description"
            )
        
        if len(description) < 10:
            result.add_warning(
                "DESCRIPTION_TOO_SHORT",
                "Agent description is very short",
                suggestion="Provide a more detailed description of the agent's purpose"
            )
    
    def _validate_tools(self, tools: Any, result: ValidationResult) -> None:
        """Validate agent tools configuration.
        
        Per Claude Code docs, tools should be a comma-separated string.
        """
        if not isinstance(tools, str):
            result.add_error(
                "INVALID_TOOLS_TYPE",
                f"Tools must be a comma-separated string, got {type(tools).__name__}",
                suggestion='Use format like: "Read, Write, Bash"'
            )
            return
        
        if not tools.strip():
            # Empty tools string is valid - inherits all tools
            return
        
        # Parse and validate individual tools
        tool_list = [t.strip() for t in tools.split(",")]
        
        for tool in tool_list:
            if not tool:
                result.add_warning(
                    "EMPTY_TOOL_NAME",
                    "Empty tool name in tools list",
                    suggestion="Remove extra commas from tools list"
                )
            elif tool not in self.COMMON_TOOLS and not tool.startswith("mcp__"):
                # Only warn for unknown tools since MCP and custom tools exist
                result.add_info(
                    "UNKNOWN_TOOL",
                    f"Tool '{tool}' is not a known Claude Code tool",
                    suggestion="Verify this tool name is correct (could be an MCP tool)"
                )
    
    # Removed invalid validation methods for fields not in Claude Code spec
    
    def _validate_markdown_content(self, markdown_content: str, result: ValidationResult) -> None:
        """Validate the markdown content of the agent."""
        if not markdown_content.strip():
            result.add_warning(
                "EMPTY_MARKDOWN_CONTENT",
                "Agent file has no markdown content after frontmatter",
                suggestion="Add markdown content describing the agent's behavior and instructions"
            )
            return
        
        # Check for common markdown issues
        lines = markdown_content.split('\n')
        
        # Check for very short content
        if len(markdown_content.strip()) < 50:
            result.add_warning(
                "VERY_SHORT_CONTENT",
                "Agent markdown content is very short",
                suggestion="Provide more detailed instructions and examples"
            )
        
        # Check for headers (good practice)
        has_headers = any(line.strip().startswith('#') for line in lines)
        if not has_headers and len(markdown_content.strip()) > 200:
            result.add_info(
                "NO_HEADERS_FOUND",
                "Consider using headers to organize the agent content",
                suggestion="Add headers (# ## ###) to structure the content"
            )
        
        # Check for code blocks (often useful in agents)
        has_code_blocks = '```' in markdown_content
        if not has_code_blocks and len(markdown_content.strip()) > 500:
            result.add_info(
                "NO_CODE_BLOCKS_FOUND",
                "Consider using code blocks to show examples",
                suggestion="Use ```language ... ``` blocks for code examples"
            )