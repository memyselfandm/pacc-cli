"""Agents validator for Claude Code agent extensions."""

import re
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .base import BaseValidator, ValidationResult


class AgentsValidator(BaseValidator):
    """Validator for Claude Code agent extensions."""
    
    # Required fields in agent YAML frontmatter
    REQUIRED_FRONTMATTER_FIELDS = ["name", "description"]
    
    # Optional fields with their expected types
    OPTIONAL_FRONTMATTER_FIELDS = {
        "version": str,
        "author": str,
        "tags": list,
        "tools": list,
        "permissions": list,
        "parameters": dict,
        "examples": list,
        "model": str,
        "temperature": (int, float),
        "max_tokens": int,
        "timeout": (int, float),
        "enabled": bool
    }
    
    # Valid permission types for agents
    VALID_PERMISSIONS = {
        "read_files",
        "write_files",
        "execute_commands",
        "network_access",
        "filesystem_access",
        "tool_use",
        "user_confirmation_required"
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
            result.metadata = {
                "name": frontmatter.get("name", ""),
                "description": frontmatter.get("description", ""),
                "version": frontmatter.get("version", "1.0.0"),
                "author": frontmatter.get("author", ""),
                "model": frontmatter.get("model", ""),
                "tools": frontmatter.get("tools", []),
                "permissions": frontmatter.get("permissions", []),
                "has_examples": bool(frontmatter.get("examples", [])),
                "markdown_length": len(markdown_content.strip()),
                "has_parameters": bool(frontmatter.get("parameters", {})),
                "temperature": frontmatter.get("temperature"),
                "max_tokens": frontmatter.get("max_tokens")
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
        
        # Parse YAML frontmatter
        try:
            frontmatter = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            result.add_error(
                "INVALID_YAML",
                f"Invalid YAML in frontmatter: {e}",
                suggestion="Fix YAML syntax errors in the frontmatter"
            )
            return True, None, ""
        except Exception as e:
            result.add_error(
                "YAML_PARSE_ERROR",
                f"Error parsing YAML frontmatter: {e}",
                suggestion="Check YAML formatting and syntax"
            )
            return True, None, ""
        
        if frontmatter is None:
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
        
        if "version" in frontmatter:
            self._validate_version(frontmatter["version"], result)
        
        if "tags" in frontmatter:
            self._validate_tags(frontmatter["tags"], result)
        
        if "tools" in frontmatter:
            self._validate_tools(frontmatter["tools"], result)
        
        if "permissions" in frontmatter:
            self._validate_permissions(frontmatter["permissions"], result)
        
        if "parameters" in frontmatter:
            self._validate_parameters(frontmatter["parameters"], result)
        
        if "examples" in frontmatter:
            self._validate_examples(frontmatter["examples"], result)
        
        if "temperature" in frontmatter:
            self._validate_temperature(frontmatter["temperature"], result)
        
        if "max_tokens" in frontmatter:
            self._validate_max_tokens(frontmatter["max_tokens"], result)
        
        if "timeout" in frontmatter:
            self._validate_timeout(frontmatter["timeout"], result)
    
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
    
    def _validate_version(self, version: str, result: ValidationResult) -> None:
        """Validate version format (semantic versioning)."""
        if not isinstance(version, str):
            result.add_error(
                "INVALID_VERSION_TYPE",
                "Version must be a string",
                suggestion="Set version to a string value like '1.0.0'"
            )
            return
        
        # Basic semantic versioning check
        semver_pattern = r'^\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?(?:\+[a-zA-Z0-9.-]+)?$'
        if not re.match(semver_pattern, version):
            result.add_warning(
                "INVALID_VERSION_FORMAT",
                f"Version '{version}' does not follow semantic versioning",
                suggestion="Use semantic versioning format like '1.0.0'"
            )
    
    def _validate_tags(self, tags: List[Any], result: ValidationResult) -> None:
        """Validate agent tags."""
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
                    suggestion="Remove empty tags or provide meaningful tag names"
                )
        
        # Check for duplicates
        if len(tags) != len(set(tags)):
            result.add_warning(
                "DUPLICATE_TAGS",
                "Duplicate tags found",
                suggestion="Remove duplicate tags"
            )
    
    def _validate_tools(self, tools: List[Any], result: ValidationResult) -> None:
        """Validate agent tools configuration."""
        if not isinstance(tools, list):
            result.add_error(
                "INVALID_TOOLS_TYPE",
                "Tools must be an array",
                suggestion="Change tools to an array of tool names or configurations"
            )
            return
        
        for i, tool in enumerate(tools):
            if isinstance(tool, str):
                # Simple tool name
                if not tool.strip():
                    result.add_error(
                        "EMPTY_TOOL_NAME",
                        f"Tool {i + 1} name cannot be empty",
                        suggestion="Provide a valid tool name"
                    )
            elif isinstance(tool, dict):
                # Tool configuration object
                if "name" not in tool:
                    result.add_error(
                        "MISSING_TOOL_NAME",
                        f"Tool {i + 1} configuration must have 'name' field",
                        suggestion="Add a 'name' field to the tool configuration"
                    )
                elif not isinstance(tool["name"], str) or not tool["name"].strip():
                    result.add_error(
                        "INVALID_TOOL_NAME",
                        f"Tool {i + 1} name must be a non-empty string",
                        suggestion="Provide a valid tool name"
                    )
            else:
                result.add_error(
                    "INVALID_TOOL_FORMAT",
                    f"Tool {i + 1} must be a string name or configuration object",
                    suggestion="Use either a tool name string or a tool configuration object"
                )
    
    def _validate_permissions(self, permissions: List[Any], result: ValidationResult) -> None:
        """Validate agent permissions."""
        if not isinstance(permissions, list):
            result.add_error(
                "INVALID_PERMISSIONS_TYPE",
                "Permissions must be an array",
                suggestion="Change permissions to an array of permission strings"
            )
            return
        
        invalid_permissions = []
        for i, permission in enumerate(permissions):
            if not isinstance(permission, str):
                result.add_error(
                    "INVALID_PERMISSION_TYPE",
                    f"Permission {i + 1} must be a string",
                    suggestion="Ensure all permissions are strings"
                )
            elif permission not in self.VALID_PERMISSIONS:
                invalid_permissions.append(permission)
        
        if invalid_permissions:
            result.add_error(
                "INVALID_PERMISSIONS",
                f"Invalid permissions: {', '.join(invalid_permissions)}",
                suggestion=f"Valid permissions are: {', '.join(self.VALID_PERMISSIONS)}"
            )
        
        # Check for duplicates
        if len(permissions) != len(set(permissions)):
            result.add_warning(
                "DUPLICATE_PERMISSIONS",
                "Duplicate permissions found",
                suggestion="Remove duplicate permissions"
            )
    
    def _validate_parameters(self, parameters: Dict[str, Any], result: ValidationResult) -> None:
        """Validate agent parameters configuration."""
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
            valid_types = ["string", "number", "integer", "boolean", "array", "object"]
            if param_type not in valid_types:
                result.add_error(
                    "INVALID_PARAMETER_TYPE",
                    f"{param_prefix}: Invalid type '{param_type}'",
                    suggestion=f"Valid types are: {', '.join(valid_types)}"
                )
    
    def _validate_examples(self, examples: List[Any], result: ValidationResult) -> None:
        """Validate agent examples."""
        if not isinstance(examples, list):
            result.add_error(
                "INVALID_EXAMPLES_TYPE",
                "Examples must be an array",
                suggestion="Change examples to an array of example objects"
            )
            return
        
        for i, example in enumerate(examples):
            if isinstance(example, str):
                # Simple example string
                if not example.strip():
                    result.add_error(
                        "EMPTY_EXAMPLE",
                        f"Example {i + 1} cannot be empty",
                        suggestion="Provide a meaningful example"
                    )
            elif isinstance(example, dict):
                # Example object
                if "input" not in example:
                    result.add_warning(
                        "MISSING_EXAMPLE_INPUT",
                        f"Example {i + 1} should have 'input' field",
                        suggestion="Add an 'input' field to show example usage"
                    )
                if "output" not in example:
                    result.add_warning(
                        "MISSING_EXAMPLE_OUTPUT",
                        f"Example {i + 1} should have 'output' field",
                        suggestion="Add an 'output' field to show expected result"
                    )
            else:
                result.add_error(
                    "INVALID_EXAMPLE_FORMAT",
                    f"Example {i + 1} must be a string or object",
                    suggestion="Use either an example string or an example object with input/output"
                )
    
    def _validate_temperature(self, temperature: Union[int, float], result: ValidationResult) -> None:
        """Validate temperature parameter."""
        if not isinstance(temperature, (int, float)):
            result.add_error(
                "INVALID_TEMPERATURE_TYPE",
                "Temperature must be a number",
                suggestion="Set temperature to a number between 0 and 1"
            )
            return
        
        if temperature < 0 or temperature > 1:
            result.add_error(
                "INVALID_TEMPERATURE_RANGE",
                f"Temperature must be between 0 and 1, got {temperature}",
                suggestion="Set temperature to a value between 0 and 1"
            )
    
    def _validate_max_tokens(self, max_tokens: int, result: ValidationResult) -> None:
        """Validate max_tokens parameter."""
        if not isinstance(max_tokens, int):
            result.add_error(
                "INVALID_MAX_TOKENS_TYPE",
                "max_tokens must be an integer",
                suggestion="Set max_tokens to an integer value"
            )
            return
        
        if max_tokens <= 0:
            result.add_error(
                "INVALID_MAX_TOKENS_VALUE",
                "max_tokens must be positive",
                suggestion="Set max_tokens to a positive integer"
            )
        elif max_tokens > 100000:
            result.add_warning(
                "VERY_HIGH_MAX_TOKENS",
                f"max_tokens is very high ({max_tokens})",
                suggestion="Consider using a lower value for max_tokens"
            )
    
    def _validate_timeout(self, timeout: Union[int, float], result: ValidationResult) -> None:
        """Validate timeout parameter."""
        if not isinstance(timeout, (int, float)):
            result.add_error(
                "INVALID_TIMEOUT_TYPE",
                "Timeout must be a number",
                suggestion="Set timeout to a number of seconds"
            )
            return
        
        if timeout <= 0:
            result.add_error(
                "INVALID_TIMEOUT_VALUE",
                "Timeout must be positive",
                suggestion="Set timeout to a positive number of seconds"
            )
        elif timeout > 3600:  # 1 hour
            result.add_warning(
                "VERY_LONG_TIMEOUT",
                f"Timeout is very long ({timeout} seconds)",
                suggestion="Consider using a shorter timeout"
            )
    
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