"""Commands validator for Claude Code slash command extensions."""

import re
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from .base import BaseValidator, ValidationResult
from .utils import parse_claude_frontmatter


class CommandsValidator(BaseValidator):
    """Validator for Claude Code slash command extensions."""
    
    # Valid naming patterns for slash commands
    COMMAND_NAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]*$')
    
    # Reserved command names that shouldn't be used
    RESERVED_COMMAND_NAMES = {
        "help", "exit", "quit", "clear", "reset", "restart", "stop",
        "system", "admin", "config", "settings", "debug", "test",
        "claude", "anthropic", "ai", "assistant"
    }
    
    # Frontmatter is completely optional for slash commands
    # Valid frontmatter fields per Claude Code documentation
    VALID_FRONTMATTER_FIELDS = {
        "allowed-tools": (str, list),  # Can be string or list
        "argument-hint": str,
        "description": str,
        "model": str
    }
    
    # Valid parameter types for command parameters
    VALID_PARAMETER_TYPES = {
        "string", "number", "integer", "boolean", "file", "directory", "choice"
    }
    
    def __init__(self, max_file_size: int = 10 * 1024 * 1024):
        """Initialize commands validator."""
        super().__init__(max_file_size)
        
        # Pre-compile regex patterns
        self._yaml_frontmatter_pattern = re.compile(
            r'^---\s*\n(.*?)\n---\s*\n(.*)', 
            re.DOTALL
        )
        self._parameter_placeholder_pattern = re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}')
        self._command_syntax_pattern = re.compile(r'^/[a-zA-Z][a-zA-Z0-9_-]*')
    
    def get_extension_type(self) -> str:
        """Return the extension type this validator handles."""
        return "commands"
    
    def validate_single(self, file_path: Union[str, Path]) -> ValidationResult:
        """Validate a single command file."""
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
        
        # Validate file naming convention
        self._validate_file_naming(file_path, result)
        
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
        
        # Determine command format and validate accordingly
        if content.strip().startswith("---"):
            # YAML frontmatter format
            self._validate_frontmatter_format(content, result)
        else:
            # Simple markdown format
            self._validate_simple_format(content, result)
        
        return result
    
    def _find_extension_files(self, directory: Path) -> List[Path]:
        """Find command files in the given directory."""
        command_files = []
        
        # Look for .md files in commands directory or with command naming pattern
        for md_file in directory.rglob("*.md"):
            # Check if file is in a commands directory
            if any(part == "commands" for part in md_file.parts):
                command_files.append(md_file)
                continue
            
            # Check if filename suggests it's a command
            filename = md_file.stem
            if filename.startswith("command-") or filename.startswith("cmd-"):
                command_files.append(md_file)
                continue
            
            # Quick content check for command-like structure
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read(1024)  # Read first 1KB
                    if self._command_syntax_pattern.search(content) or "slash command" in content.lower():
                        command_files.append(md_file)
            except Exception:
                # If we can't read it, let the full validation handle the error
                pass
        
        return command_files
    
    def _validate_file_naming(self, file_path: Path, result: ValidationResult) -> None:
        """Validate command file naming conventions."""
        filename = file_path.stem  # filename without extension
        
        # Check file extension
        if file_path.suffix.lower() != '.md':
            result.add_warning(
                "NON_MARKDOWN_EXTENSION",
                f"Command file should have .md extension, found {file_path.suffix}",
                suggestion="Rename file to use .md extension"
            )
        
        # Check filename format
        if not self.COMMAND_NAME_PATTERN.match(filename):
            result.add_error(
                "INVALID_FILENAME_FORMAT",
                f"Command filename '{filename}' contains invalid characters",
                suggestion="Use only alphanumeric characters, hyphens, and underscores, starting with a letter"
            )
        
        # Check for reserved names
        if filename.lower() in self.RESERVED_COMMAND_NAMES:
            result.add_error(
                "RESERVED_COMMAND_NAME",
                f"Command filename '{filename}' is reserved",
                suggestion="Use a different name for the command"
            )
        
        # Check filename length
        if len(filename) > 50:
            result.add_warning(
                "FILENAME_TOO_LONG",
                f"Command filename is very long ({len(filename)} characters)",
                suggestion="Use a shorter, more concise filename"
            )
        
        # Check for good naming practices
        if len(filename) < 3:
            result.add_warning(
                "FILENAME_TOO_SHORT",
                "Command filename is very short",
                suggestion="Use a more descriptive filename"
            )
    
    def _validate_frontmatter_format(self, content: str, result: ValidationResult) -> None:
        """Validate command file with YAML frontmatter format."""
        # Parse frontmatter and content
        match = self._yaml_frontmatter_pattern.match(content)
        if not match:
            result.add_error(
                "MALFORMED_FRONTMATTER",
                "Command file has opening --- but no closing --- for YAML frontmatter",
                suggestion="Add closing --- to complete the YAML frontmatter section"
            )
            return
        
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
            return
        
        if not frontmatter:
            result.add_error(
                "EMPTY_FRONTMATTER",
                "YAML frontmatter is empty",
                suggestion="Add required fields to the YAML frontmatter"
            )
            return
        
        if not isinstance(frontmatter, dict):
            result.add_error(
                "INVALID_FRONTMATTER_FORMAT",
                "YAML frontmatter must be a dictionary/object",
                suggestion="Ensure frontmatter contains key-value pairs"
            )
            return
        
        # Validate frontmatter structure
        self._validate_frontmatter_structure(frontmatter, result)
        
        # Validate markdown content
        self._validate_command_content(markdown_content, result)
        
        # Extract metadata
        if result.is_valid and frontmatter:
            result.metadata = {
                "description": frontmatter.get("description", ""),
                "argument_hint": frontmatter.get("argument-hint", ""),
                "allowed_tools": frontmatter.get("allowed-tools", ""),
                "model": frontmatter.get("model", ""),
                "content_length": len(markdown_content.strip())
            }
    
    def _validate_simple_format(self, content: str, result: ValidationResult) -> None:
        """Validate command file with simple markdown format."""
        # Validate content structure
        self._validate_command_content(content, result)
        
        # Try to extract command information from content
        lines = content.split('\n')
        command_name = None
        description = None
        
        # Look for command definition patterns
        for line in lines:
            line = line.strip()
            if line.startswith('#'):
                # Potential command name from header
                header_text = line.lstrip('#').strip()
                if self._command_syntax_pattern.match(header_text):
                    command_name = header_text
                elif not command_name and header_text:
                    command_name = header_text
            elif line.startswith('/') and self._command_syntax_pattern.match(line):
                # Direct command syntax
                command_name = line.split()[0]
            elif not description and len(line) > 20 and not line.startswith('#'):
                # Potential description
                description = line
        
        # Validate extracted information
        if command_name:
            self._validate_command_name(command_name, result)
        else:
            result.add_warning(
                "NO_COMMAND_NAME_FOUND",
                "Could not identify command name in file",
                suggestion="Add a clear command name as a header or in the content"
            )
        
        # Extract metadata
        result.metadata = {
            "name": command_name or "",
            "description": description or "",
            "format": "simple",
            "content_length": len(content.strip())
        }
    
    def _validate_frontmatter_structure(self, frontmatter: Dict[str, Any], result: ValidationResult) -> None:
        """Validate command YAML frontmatter structure.
        
        Per Claude Code documentation:
        - Frontmatter is completely optional
        - Valid fields: allowed-tools, argument-hint, description, model
        - Command name comes from filename, not frontmatter
        """
        # Check for unknown fields and warn about them
        for field in frontmatter:
            if field not in self.VALID_FRONTMATTER_FIELDS:
                # Map common misunderstandings
                if field == "name":
                    result.add_warning(
                        "INVALID_FRONTMATTER_FIELD",
                        f"Field '{field}' is not valid in slash command frontmatter",
                        suggestion="Command name is derived from the filename, not frontmatter. Remove this field."
                    )
                else:
                    result.add_warning(
                        "UNKNOWN_FRONTMATTER_FIELD",
                        f"Unknown field '{field}' in frontmatter",
                        suggestion=f"Valid fields are: {', '.join(self.VALID_FRONTMATTER_FIELDS.keys())}"
                    )
        
        # Validate field types for known fields
        for field, expected_types in self.VALID_FRONTMATTER_FIELDS.items():
            if field in frontmatter:
                value = frontmatter[field]
                # Handle fields that can have multiple types
                if isinstance(expected_types, tuple):
                    if not any(isinstance(value, t) for t in expected_types):
                        type_names = ' or '.join(t.__name__ for t in expected_types)
                        result.add_error(
                            "INVALID_FIELD_TYPE",
                            f"Field '{field}' must be of type {type_names}, got {type(value).__name__}",
                            suggestion=f"Change '{field}' to the correct type"
                        )
                else:
                    if not isinstance(value, expected_types):
                        result.add_error(
                            "INVALID_FIELD_TYPE",
                            f"Field '{field}' must be of type {expected_types.__name__}, got {type(value).__name__}",
                            suggestion=f"Change '{field}' to the correct type"
                        )
        
        # Validate specific field values
        if "description" in frontmatter:
            self._validate_command_description(frontmatter["description"], result)
        
        if "argument-hint" in frontmatter:
            self._validate_argument_hint(frontmatter["argument-hint"], result)
        
        if "allowed-tools" in frontmatter:
            self._validate_allowed_tools(frontmatter["allowed-tools"], result)
        
        if "model" in frontmatter:
            self._validate_model(frontmatter["model"], result)
    
    def _validate_argument_hint(self, hint: str, result: ValidationResult) -> None:
        """Validate argument-hint field."""
        if not isinstance(hint, str):
            result.add_error(
                "INVALID_ARGUMENT_HINT_TYPE",
                "argument-hint must be a string",
                suggestion="Change argument-hint to a string value"
            )
            return
        
        if not hint.strip():
            result.add_warning(
                "EMPTY_ARGUMENT_HINT",
                "argument-hint is empty",
                suggestion="Provide a hint about expected arguments like '[message]' or '[tagId]'"
            )
    
    def _validate_allowed_tools(self, tools: Union[str, List[str]], result: ValidationResult) -> None:
        """Validate allowed-tools field."""
        if isinstance(tools, str):
            # Single tool as string is valid
            if not tools.strip():
                result.add_warning(
                    "EMPTY_ALLOWED_TOOLS",
                    "allowed-tools is empty",
                    suggestion="Specify tools like 'Bash(git status:*)' or remove this field"
                )
        elif isinstance(tools, list):
            # List of tools is valid
            for i, tool in enumerate(tools):
                if not isinstance(tool, str):
                    result.add_error(
                        "INVALID_TOOL_TYPE",
                        f"Tool {i + 1} in allowed-tools must be a string",
                        suggestion="Ensure all tools are strings"
                    )
                elif not tool.strip():
                    result.add_warning(
                        "EMPTY_TOOL",
                        f"Tool {i + 1} in allowed-tools is empty",
                        suggestion="Remove empty tool entries"
                    )
        else:
            result.add_error(
                "INVALID_ALLOWED_TOOLS_TYPE",
                "allowed-tools must be a string or list of strings",
                suggestion="Use a string like 'Bash(git:*)' or a list of such strings"
            )
    
    def _validate_model(self, model: str, result: ValidationResult) -> None:
        """Validate model field."""
        if not isinstance(model, str):
            result.add_error(
                "INVALID_MODEL_TYPE",
                "model must be a string",
                suggestion="Change model to a string value"
            )
            return
        
        if not model.strip():
            result.add_warning(
                "EMPTY_MODEL",
                "model field is empty",
                suggestion="Specify a model like 'claude-3-5-sonnet-20241022' or remove this field"
            )
    
    def _validate_command_description(self, description: str, result: ValidationResult) -> None:
        """Validate command description."""
        if not isinstance(description, str):
            result.add_error(
                "INVALID_DESCRIPTION_TYPE",
                "Command description must be a string",
                suggestion="Change description to a string value"
            )
            return
        
        if not description.strip():
            result.add_error(
                "EMPTY_DESCRIPTION",
                "Command description cannot be empty",
                suggestion="Provide a description of what the command does"
            )
            return
        
        if len(description) > 200:
            result.add_warning(
                "DESCRIPTION_TOO_LONG",
                f"Command description is very long ({len(description)} characters)",
                suggestion="Use a more concise description"
            )
        
        if len(description) < 10:
            result.add_warning(
                "DESCRIPTION_TOO_SHORT",
                "Command description is very short",
                suggestion="Provide a more detailed description"
            )
    
    def _validate_command_name(self, name: str, result: ValidationResult) -> None:
        """Validate command name format (used for simple format validation)."""
        if not isinstance(name, str):
            result.add_error(
                "INVALID_NAME_TYPE",
                "Command name must be a string",
                suggestion="Change name to a string value"
            )
            return
        
        # Remove leading slash if present
        command_name = name.lstrip('/')
        
        if not command_name:
            result.add_error(
                "EMPTY_COMMAND_NAME",
                "Command name cannot be empty",
                suggestion="Provide a descriptive name for the command"
            )
            return
        
        # Check name format
        if not self.COMMAND_NAME_PATTERN.match(command_name):
            result.add_error(
                "INVALID_COMMAND_NAME_FORMAT",
                f"Command name '{command_name}' contains invalid characters",
                suggestion="Use only alphanumeric characters, hyphens, and underscores, starting with a letter"
            )
        
        # Check for reserved names
        if command_name.lower() in self.RESERVED_COMMAND_NAMES:
            result.add_error(
                "RESERVED_COMMAND_NAME",
                f"Command name '{command_name}' is reserved",
                suggestion="Use a different name for the command"
            )
        
        # Check name length
        if len(command_name) > 30:
            result.add_warning(
                "COMMAND_NAME_TOO_LONG",
                f"Command name is very long ({len(command_name)} characters)",
                suggestion="Use a shorter, more concise name"
            )
        
        if len(command_name) < 3:
            result.add_warning(
                "COMMAND_NAME_TOO_SHORT",
                "Command name is very short",
                suggestion="Use a more descriptive name"
            )
    
    
    def _validate_command_content(self, content: str, result: ValidationResult) -> None:
        """Validate the markdown content of the command."""
        if not content.strip():
            result.add_warning(
                "EMPTY_CONTENT",
                "Command file has no content",
                suggestion="Add markdown content describing the command's behavior"
            )
            return
        
        # Check for very short content
        if len(content.strip()) < 50:
            result.add_warning(
                "VERY_SHORT_CONTENT",
                "Command content is very short",
                suggestion="Provide more detailed information about the command"
            )
        
        # Check for command syntax examples (optional)
        if not self._command_syntax_pattern.search(content):
            result.add_info(
                "NO_COMMAND_SYNTAX_FOUND",
                "No command syntax examples found in content",
                suggestion="Consider including examples showing how to use the command (optional)"
            )
        
        # Check for headers (good practice)
        lines = content.split('\n')
        has_headers = any(line.strip().startswith('#') for line in lines)
        if not has_headers and len(content.strip()) > 200:
            result.add_info(
                "NO_HEADERS_FOUND",
                "Consider using headers to organize the command documentation",
                suggestion="Add headers (# ## ###) to structure the content"
            )