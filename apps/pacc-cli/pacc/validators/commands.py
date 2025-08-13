"""Commands validator for Claude Code slash command extensions."""

import re
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from .base import BaseValidator, ValidationResult


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
    
    # Required fields in command YAML frontmatter (if using frontmatter format)
    REQUIRED_FRONTMATTER_FIELDS = ["name", "description"]
    
    # Optional fields with their expected types
    OPTIONAL_FRONTMATTER_FIELDS = {
        "usage": str,
        "examples": list,
        "parameters": dict,
        "category": str,
        "tags": list,
        "author": str,
        "version": str,
        "permissions": list,
        "aliases": list,
        "enabled": bool,
        "experimental": bool
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
        
        # Parse YAML frontmatter
        try:
            frontmatter = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            result.add_error(
                "INVALID_YAML",
                f"Invalid YAML in frontmatter: {e}",
                suggestion="Fix YAML syntax errors in the frontmatter"
            )
            return
        except Exception as e:
            result.add_error(
                "YAML_PARSE_ERROR",
                f"Error parsing YAML frontmatter: {e}",
                suggestion="Check YAML formatting and syntax"
            )
            return
        
        if frontmatter is None:
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
                "name": frontmatter.get("name", ""),
                "description": frontmatter.get("description", ""),
                "category": frontmatter.get("category", ""),
                "has_parameters": bool(frontmatter.get("parameters", {})),
                "has_examples": bool(frontmatter.get("examples", [])),
                "aliases": frontmatter.get("aliases", []),
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
        """Validate command YAML frontmatter structure."""
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
                    type_name = expected_type.__name__
                    result.add_error(
                        "INVALID_FIELD_TYPE",
                        f"Field '{field}' must be of type {type_name}, got {type(value).__name__}",
                        suggestion=f"Change '{field}' to the correct type"
                    )
        
        # Skip detailed validation if required fields are missing
        if not all(field in frontmatter for field in self.REQUIRED_FRONTMATTER_FIELDS):
            return
        
        # Validate specific fields
        self._validate_command_name(frontmatter["name"], result)
        self._validate_command_description(frontmatter["description"], result)
        
        if "usage" in frontmatter:
            self._validate_usage(frontmatter["usage"], result)
        
        if "examples" in frontmatter:
            self._validate_examples(frontmatter["examples"], result)
        
        if "parameters" in frontmatter:
            self._validate_parameters(frontmatter["parameters"], result)
        
        if "aliases" in frontmatter:
            self._validate_aliases(frontmatter["aliases"], result)
        
        if "tags" in frontmatter:
            self._validate_tags(frontmatter["tags"], result)
        
        if "permissions" in frontmatter:
            self._validate_permissions(frontmatter["permissions"], result)
    
    def _validate_command_name(self, name: str, result: ValidationResult) -> None:
        """Validate command name format."""
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
    
    def _validate_usage(self, usage: str, result: ValidationResult) -> None:
        """Validate command usage string."""
        if not isinstance(usage, str):
            result.add_error(
                "INVALID_USAGE_TYPE",
                "Usage must be a string",
                suggestion="Change usage to a string value"
            )
            return
        
        if not usage.strip():
            result.add_warning(
                "EMPTY_USAGE",
                "Usage field is empty",
                suggestion="Provide usage syntax for the command"
            )
            return
        
        # Check if usage starts with command syntax
        if not usage.strip().startswith('/'):
            result.add_warning(
                "USAGE_MISSING_SLASH",
                "Usage should start with / to show command syntax",
                suggestion="Start usage with /commandname to show proper syntax"
            )
        
        # Check for parameter placeholders
        placeholders = self._parameter_placeholder_pattern.findall(usage)
        if placeholders:
            result.metadata = result.metadata or {}
            result.metadata["usage_parameters"] = placeholders
    
    def _validate_examples(self, examples: List[Any], result: ValidationResult) -> None:
        """Validate command examples."""
        if not isinstance(examples, list):
            result.add_error(
                "INVALID_EXAMPLES_TYPE",
                "Examples must be an array",
                suggestion="Change examples to an array of example strings or objects"
            )
            return
        
        if not examples:
            result.add_warning(
                "NO_EXAMPLES",
                "No examples provided",
                suggestion="Add examples to show how to use the command"
            )
            return
        
        for i, example in enumerate(examples):
            if isinstance(example, str):
                if not example.strip():
                    result.add_error(
                        "EMPTY_EXAMPLE",
                        f"Example {i + 1} cannot be empty",
                        suggestion="Provide a meaningful example"
                    )
                elif not example.strip().startswith('/'):
                    result.add_warning(
                        "EXAMPLE_MISSING_SLASH",
                        f"Example {i + 1} should start with / to show command syntax",
                        suggestion="Start example with /commandname"
                    )
            elif isinstance(example, dict):
                if "command" not in example:
                    result.add_warning(
                        "EXAMPLE_MISSING_COMMAND",
                        f"Example {i + 1} should have 'command' field",
                        suggestion="Add a 'command' field to show the command usage"
                    )
                if "description" not in example:
                    result.add_warning(
                        "EXAMPLE_MISSING_DESCRIPTION", 
                        f"Example {i + 1} should have 'description' field",
                        suggestion="Add a 'description' field to explain the example"
                    )
            else:
                result.add_error(
                    "INVALID_EXAMPLE_FORMAT",
                    f"Example {i + 1} must be a string or object",
                    suggestion="Use either an example string or an example object"
                )
    
    def _validate_parameters(self, parameters: Dict[str, Any], result: ValidationResult) -> None:
        """Validate command parameters configuration."""
        if not isinstance(parameters, dict):
            result.add_error(
                "INVALID_PARAMETERS_TYPE",
                "Parameters must be an object",
                suggestion="Change parameters to an object with parameter definitions"
            )
            return
        
        for param_name, param_config in parameters.items():
            self._validate_single_parameter(param_name, param_config, result)
    
    def _validate_single_parameter(self, param_name: str, param_config: Any, 
                                   result: ValidationResult) -> None:
        """Validate a single parameter configuration."""
        param_prefix = f"Parameter '{param_name}'"
        
        # Validate parameter name
        if not self.COMMAND_NAME_PATTERN.match(param_name):
            result.add_error(
                "INVALID_PARAMETER_NAME",
                f"{param_prefix}: Parameter name contains invalid characters",
                suggestion="Use only alphanumeric characters, hyphens, and underscores"
            )
        
        if not isinstance(param_config, dict):
            result.add_error(
                "INVALID_PARAMETER_CONFIG_TYPE",
                f"{param_prefix}: Parameter configuration must be an object",
                suggestion="Use an object with type, description, and other fields"
            )
            return
        
        # Check required fields
        if "type" not in param_config:
            result.add_error(
                "MISSING_PARAMETER_TYPE",
                f"{param_prefix}: Missing required 'type' field",
                suggestion="Add a 'type' field to specify the parameter type"
            )
        
        if "description" not in param_config:
            result.add_warning(
                "MISSING_PARAMETER_DESCRIPTION",
                f"{param_prefix}: Missing 'description' field",
                suggestion="Add a 'description' field to document the parameter"
            )
        
        # Validate type field
        if "type" in param_config:
            param_type = param_config["type"]
            if param_type not in self.VALID_PARAMETER_TYPES:
                result.add_error(
                    "INVALID_PARAMETER_TYPE",
                    f"{param_prefix}: Invalid type '{param_type}'",
                    suggestion=f"Valid types are: {', '.join(self.VALID_PARAMETER_TYPES)}"
                )
        
        # Validate optional fields
        if "required" in param_config and not isinstance(param_config["required"], bool):
            result.add_error(
                "INVALID_PARAMETER_REQUIRED_TYPE",
                f"{param_prefix}: 'required' must be a boolean",
                suggestion="Set 'required' to true or false"
            )
        
        if "default" in param_config and "required" in param_config and param_config["required"]:
            result.add_warning(
                "REQUIRED_PARAMETER_HAS_DEFAULT",
                f"{param_prefix}: Required parameter should not have a default value",
                suggestion="Either make parameter optional or remove default value"
            )
        
        # Validate choice type parameters
        if param_config.get("type") == "choice":
            if "choices" not in param_config:
                result.add_error(
                    "MISSING_PARAMETER_CHOICES",
                    f"{param_prefix}: Choice type parameter must have 'choices' field",
                    suggestion="Add a 'choices' array with valid options"
                )
            elif not isinstance(param_config["choices"], list):
                result.add_error(
                    "INVALID_PARAMETER_CHOICES_TYPE",
                    f"{param_prefix}: 'choices' must be an array",
                    suggestion="Change 'choices' to an array of valid options"
                )
    
    def _validate_aliases(self, aliases: List[Any], result: ValidationResult) -> None:
        """Validate command aliases."""
        if not isinstance(aliases, list):
            result.add_error(
                "INVALID_ALIASES_TYPE",
                "Aliases must be an array",
                suggestion="Change aliases to an array of strings"
            )
            return
        
        for i, alias in enumerate(aliases):
            if not isinstance(alias, str):
                result.add_error(
                    "INVALID_ALIAS_TYPE",
                    f"Alias {i + 1} must be a string",
                    suggestion="Ensure all aliases are strings"
                )
            elif not alias.strip():
                result.add_error(
                    "EMPTY_ALIAS",
                    f"Alias {i + 1} cannot be empty",
                    suggestion="Remove empty aliases"
                )
            else:
                alias_name = alias.lstrip('/')
                if not self.COMMAND_NAME_PATTERN.match(alias_name):
                    result.add_error(
                        "INVALID_ALIAS_FORMAT",
                        f"Alias '{alias_name}' contains invalid characters",
                        suggestion="Use only alphanumeric characters, hyphens, and underscores"
                    )
                if alias_name.lower() in self.RESERVED_COMMAND_NAMES:
                    result.add_error(
                        "RESERVED_ALIAS_NAME",
                        f"Alias '{alias_name}' is reserved",
                        suggestion="Use a different alias name"
                    )
        
        # Check for duplicates
        if len(aliases) != len(set(aliases)):
            result.add_warning(
                "DUPLICATE_ALIASES",
                "Duplicate aliases found",
                suggestion="Remove duplicate aliases"
            )
    
    def _validate_tags(self, tags: List[Any], result: ValidationResult) -> None:
        """Validate command tags."""
        if not isinstance(tags, list):
            result.add_error(
                "INVALID_TAGS_TYPE",
                "Tags must be an array",
                suggestion="Change tags to an array of strings"
            )
            return
        
        for i, tag in enumerate(tags):
            if not isinstance(tag, str):
                result.add_error(
                    "INVALID_TAG_TYPE",
                    f"Tag {i + 1} must be a string",
                    suggestion="Ensure all tags are strings"
                )
            elif not tag.strip():
                result.add_error(
                    "EMPTY_TAG",
                    f"Tag {i + 1} cannot be empty",
                    suggestion="Remove empty tags"
                )
        
        # Check for duplicates
        if len(tags) != len(set(tags)):
            result.add_warning(
                "DUPLICATE_TAGS",
                "Duplicate tags found",
                suggestion="Remove duplicate tags"
            )
    
    def _validate_permissions(self, permissions: List[Any], result: ValidationResult) -> None:
        """Validate command permissions."""
        if not isinstance(permissions, list):
            result.add_error(
                "INVALID_PERMISSIONS_TYPE",
                "Permissions must be an array",
                suggestion="Change permissions to an array of strings"
            )
            return
        
        valid_permissions = {
            "read_files", "write_files", "execute_commands", "network_access",
            "user_confirmation_required", "admin_only"
        }
        
        for i, permission in enumerate(permissions):
            if not isinstance(permission, str):
                result.add_error(
                    "INVALID_PERMISSION_TYPE",
                    f"Permission {i + 1} must be a string",
                    suggestion="Ensure all permissions are strings"
                )
            elif permission not in valid_permissions:
                result.add_warning(
                    "UNKNOWN_PERMISSION",
                    f"Unknown permission '{permission}'",
                    suggestion=f"Valid permissions are: {', '.join(valid_permissions)}"
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
        
        # Check for command syntax examples
        if not self._command_syntax_pattern.search(content):
            result.add_info(
                "NO_COMMAND_SYNTAX_FOUND",
                "No command syntax examples found in content",
                suggestion="Include examples showing how to use the command"
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