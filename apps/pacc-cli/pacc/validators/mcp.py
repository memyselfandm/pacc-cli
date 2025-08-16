"""MCP (Model Context Protocol) validator for Claude Code MCP server extensions."""

import json
import os
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from .base import BaseValidator, ValidationResult


class MCPValidator(BaseValidator):
    """Validator for Claude Code MCP server extensions."""
    
    # Valid transport types for MCP servers
    VALID_TRANSPORT_TYPES = {
        "stdio",
        "sse",
        "websocket"
    }
    
    # Standard MCP server configuration fields
    REQUIRED_SERVER_FIELDS = ["command"]
    OPTIONAL_SERVER_FIELDS = {
        "args": list,
        "env": dict,
        "cwd": str,
        "timeout": (int, float),
        "restart": bool,
        "transport": str
    }
    
    def __init__(self, max_file_size: int = 10 * 1024 * 1024, 
                 enable_connection_testing: bool = False):
        """Initialize MCP validator.
        
        Args:
            max_file_size: Maximum file size to validate
            enable_connection_testing: Whether to test actual connections to servers
        """
        super().__init__(max_file_size)
        self.enable_connection_testing = enable_connection_testing
    
    def get_extension_type(self) -> str:
        """Return the extension type this validator handles."""
        return "mcp"
    
    def validate_single(self, file_path: Union[str, Path]) -> ValidationResult:
        """Validate a single MCP configuration file."""
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
        
        # Validate JSON syntax
        json_error, mcp_data = self._validate_json_syntax(file_path)
        if json_error:
            result.add_error(
                json_error.code,
                json_error.message,
                line_number=json_error.line_number,
                suggestion=json_error.suggestion
            )
            return result
        
        # Validate MCP configuration structure
        self._validate_mcp_structure(mcp_data, result)
        
        # Extract metadata for successful validations
        if result.is_valid and mcp_data:
            result.metadata = {
                "server_count": len(mcp_data.get("mcpServers", {})),
                "servers": list(mcp_data.get("mcpServers", {}).keys()),
                "has_global_config": any(
                    key in mcp_data for key in ["timeout", "maxRetries", "environment"]
                )
            }
        
        return result
    
    def _find_extension_files(self, directory: Path) -> List[Path]:
        """Find MCP configuration files in the given directory."""
        mcp_files = []
        
        # Look for .mcp.json files (standard MCP config files)
        mcp_files.extend(directory.rglob("*.mcp.json"))
        
        # Look for mcp.json files
        mcp_files.extend(directory.rglob("mcp.json"))
        
        # Look for .json files that might contain MCP configurations
        for json_file in directory.rglob("*.json"):
            if json_file.name in [".mcp.json", "mcp.json"]:
                continue  # Already added above
                
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    content = f.read(1024)  # Read first 1KB
                    if "mcpServers" in content:
                        mcp_files.append(json_file)
            except Exception:
                # If we can't read it, let the full validation handle the error
                pass
        
        return mcp_files
    
    def _validate_mcp_structure(self, mcp_data: Dict[str, Any], result: ValidationResult) -> None:
        """Validate the overall structure of an MCP configuration."""
        file_path = result.file_path
        
        # Check that data is a dictionary
        if not isinstance(mcp_data, dict):
            result.add_error(
                "INVALID_MCP_FORMAT",
                "MCP configuration must be a JSON object",
                suggestion="Ensure the root element is a JSON object {}"
            )
            return
        
        # MCP configuration should have mcpServers field
        if "mcpServers" not in mcp_data:
            result.add_error(
                "MISSING_MCP_SERVERS",
                "MCP configuration must contain 'mcpServers' field",
                suggestion="Add an 'mcpServers' object containing server configurations"
            )
            return
        
        servers = mcp_data["mcpServers"]
        if not isinstance(servers, dict):
            result.add_error(
                "INVALID_MCP_SERVERS_FORMAT",
                "'mcpServers' must be an object",
                suggestion="Change 'mcpServers' to an object with server names as keys"
            )
            return
        
        if not servers:
            result.add_warning(
                "NO_MCP_SERVERS",
                "No MCP servers defined in configuration",
                suggestion="Add at least one server configuration"
            )
            return
        
        # Validate each server configuration
        for server_name, server_config in servers.items():
            self._validate_server_configuration(server_name, server_config, result)
        
        # Validate optional global configuration fields
        self._validate_global_configuration(mcp_data, result)
    
    def _validate_server_configuration(self, server_name: str, 
                                     server_config: Any, result: ValidationResult) -> None:
        """Validate a single MCP server configuration."""
        server_prefix = f"Server '{server_name}'"
        
        # Validate server name
        if not isinstance(server_name, str) or not server_name.strip():
            result.add_error(
                "INVALID_SERVER_NAME",
                f"Server name must be a non-empty string",
                suggestion="Use a descriptive name for the server"
            )
            return
        
        # Server configuration must be an object
        if not isinstance(server_config, dict):
            result.add_error(
                "INVALID_SERVER_CONFIG_FORMAT",
                f"{server_prefix}: Server configuration must be an object",
                suggestion="Change server configuration to an object with command and other fields"
            )
            return
        
        # Validate required fields
        for field in self.REQUIRED_SERVER_FIELDS:
            if field not in server_config:
                result.add_error(
                    "MISSING_REQUIRED_SERVER_FIELD",
                    f"{server_prefix}: Missing required field '{field}'",
                    suggestion=f"Add the '{field}' field to the server configuration"
                )
        
        # Validate field types
        for field, expected_type in self.OPTIONAL_SERVER_FIELDS.items():
            if field in server_config:
                value = server_config[field]
                if not isinstance(value, expected_type):
                    type_name = expected_type.__name__ if not isinstance(expected_type, tuple) else " or ".join(t.__name__ for t in expected_type)
                    result.add_error(
                        "INVALID_SERVER_FIELD_TYPE",
                        f"{server_prefix}: Field '{field}' must be of type {type_name}",
                        suggestion=f"Change '{field}' to the correct type"
                    )
        
        # Skip detailed validation if required fields are missing
        if not all(field in server_config for field in self.REQUIRED_SERVER_FIELDS):
            return
        
        # Validate command
        self._validate_server_command(server_name, server_config["command"], result)
        
        # Validate optional fields
        if "args" in server_config:
            self._validate_server_args(server_name, server_config["args"], result)
        
        if "env" in server_config:
            self._validate_server_env(server_name, server_config["env"], result)
        
        if "cwd" in server_config:
            self._validate_server_cwd(server_name, server_config["cwd"], result)
        
        if "timeout" in server_config:
            self._validate_server_timeout(server_name, server_config["timeout"], result)
        
        if "transport" in server_config:
            self._validate_server_transport(server_name, server_config["transport"], result)
    
    def _validate_server_command(self, server_name: str, command: Any, result: ValidationResult) -> None:
        """Validate server command."""
        server_prefix = f"Server '{server_name}'"
        
        if not isinstance(command, str):
            result.add_error(
                "INVALID_COMMAND_TYPE",
                f"{server_prefix}: 'command' must be a string",
                suggestion="Set 'command' to the executable path or command name"
            )
            return
        
        if not command.strip():
            result.add_error(
                "EMPTY_COMMAND",
                f"{server_prefix}: 'command' cannot be empty",
                suggestion="Provide the executable path or command name"
            )
            return
        
        # Check if command is an absolute path
        if os.path.isabs(command):
            self._validate_executable_path(server_name, command, result)
        else:
            # Check if command exists in PATH
            if shutil.which(command) is None:
                result.add_warning(
                    "COMMAND_NOT_IN_PATH",
                    f"{server_prefix}: Command '{command}' not found in PATH",
                    suggestion="Ensure the command is installed and available in PATH, or use an absolute path"
                )
        
        # Security checks
        if any(char in command for char in [';', '&', '|', '`', '$', '(', ')']):
            result.add_warning(
                "COMMAND_CONTAINS_SHELL_CHARS",
                f"{server_prefix}: Command contains shell metacharacters",
                suggestion="Use only the executable path, pass arguments via 'args' field"
            )
    
    def _validate_executable_path(self, server_name: str, path: str, result: ValidationResult) -> None:
        """Validate an executable path."""
        server_prefix = f"Server '{server_name}'"
        
        path_obj = Path(path)
        
        if not path_obj.exists():
            result.add_error(
                "EXECUTABLE_NOT_FOUND",
                f"{server_prefix}: Executable not found at '{path}'",
                suggestion="Check the path and ensure the executable exists"
            )
            return
        
        if not path_obj.is_file():
            result.add_error(
                "EXECUTABLE_NOT_FILE",
                f"{server_prefix}: Path '{path}' is not a file",
                suggestion="Provide a path to an executable file"
            )
            return
        
        # Check if file is executable (Unix-like systems)
        if os.name != 'nt' and not os.access(path, os.X_OK):
            result.add_warning(
                "EXECUTABLE_NOT_EXECUTABLE",
                f"{server_prefix}: File '{path}' is not executable",
                suggestion="Make the file executable with chmod +x"
            )
    
    def _validate_server_args(self, server_name: str, args: List[Any], result: ValidationResult) -> None:
        """Validate server arguments."""
        server_prefix = f"Server '{server_name}'"
        
        if not isinstance(args, list):
            result.add_error(
                "INVALID_ARGS_TYPE",
                f"{server_prefix}: 'args' must be an array",
                suggestion="Change 'args' to an array of strings"
            )
            return
        
        for i, arg in enumerate(args):
            if not isinstance(arg, str):
                result.add_error(
                    "INVALID_ARG_TYPE",
                    f"{server_prefix}: Argument {i + 1} must be a string",
                    suggestion="Ensure all arguments are strings"
                )
    
    def _validate_server_env(self, server_name: str, env: Dict[str, Any], result: ValidationResult) -> None:
        """Validate server environment variables."""
        server_prefix = f"Server '{server_name}'"
        
        if not isinstance(env, dict):
            result.add_error(
                "INVALID_ENV_TYPE",
                f"{server_prefix}: 'env' must be an object",
                suggestion="Change 'env' to an object with string keys and values"
            )
            return
        
        for key, value in env.items():
            if not isinstance(key, str):
                result.add_error(
                    "INVALID_ENV_KEY_TYPE",
                    f"{server_prefix}: Environment variable key must be a string",
                    suggestion="Ensure all environment variable keys are strings"
                )
            
            if not isinstance(value, str):
                result.add_error(
                    "INVALID_ENV_VALUE_TYPE",
                    f"{server_prefix}: Environment variable value for '{key}' must be a string",
                    suggestion="Ensure all environment variable values are strings"
                )
    
    def _validate_server_cwd(self, server_name: str, cwd: str, result: ValidationResult) -> None:
        """Validate server working directory."""
        server_prefix = f"Server '{server_name}'"
        
        if not isinstance(cwd, str):
            result.add_error(
                "INVALID_CWD_TYPE",
                f"{server_prefix}: 'cwd' must be a string",
                suggestion="Set 'cwd' to a directory path string"
            )
            return
        
        if not cwd.strip():
            result.add_error(
                "EMPTY_CWD",
                f"{server_prefix}: 'cwd' cannot be empty",
                suggestion="Provide a valid directory path for 'cwd'"
            )
            return
        
        cwd_path = Path(cwd)
        if not cwd_path.exists():
            result.add_warning(
                "CWD_NOT_FOUND",
                f"{server_prefix}: Working directory '{cwd}' does not exist",
                suggestion="Ensure the directory exists or will be created before server starts"
            )
        elif not cwd_path.is_dir():
            result.add_error(
                "CWD_NOT_DIRECTORY",
                f"{server_prefix}: Working directory '{cwd}' is not a directory",
                suggestion="Provide a path to a directory"
            )
    
    def _validate_server_timeout(self, server_name: str, timeout: Union[int, float], 
                                result: ValidationResult) -> None:
        """Validate server timeout."""
        server_prefix = f"Server '{server_name}'"
        
        if not isinstance(timeout, (int, float)):
            result.add_error(
                "INVALID_TIMEOUT_TYPE",
                f"{server_prefix}: 'timeout' must be a number",
                suggestion="Set 'timeout' to a number of seconds"
            )
            return
        
        if timeout <= 0:
            result.add_error(
                "INVALID_TIMEOUT_VALUE",
                f"{server_prefix}: 'timeout' must be positive",
                suggestion="Use a positive number for timeout in seconds"
            )
        elif timeout > 3600:  # 1 hour
            result.add_warning(
                "VERY_LONG_TIMEOUT",
                f"{server_prefix}: Timeout is very long ({timeout} seconds)",
                suggestion="Consider using a shorter timeout"
            )
    
    def _validate_server_transport(self, server_name: str, transport: str, 
                                  result: ValidationResult) -> None:
        """Validate server transport type."""
        server_prefix = f"Server '{server_name}'"
        
        if not isinstance(transport, str):
            result.add_error(
                "INVALID_TRANSPORT_TYPE",
                f"{server_prefix}: 'transport' must be a string",
                suggestion="Set 'transport' to a transport type string"
            )
            return
        
        if transport not in self.VALID_TRANSPORT_TYPES:
            result.add_error(
                "INVALID_TRANSPORT_VALUE",
                f"{server_prefix}: Invalid transport type '{transport}'",
                suggestion=f"Valid transport types are: {', '.join(self.VALID_TRANSPORT_TYPES)}"
            )
    
    def _validate_global_configuration(self, mcp_data: Dict[str, Any], 
                                     result: ValidationResult) -> None:
        """Validate global MCP configuration fields."""
        # Validate global timeout
        if "timeout" in mcp_data:
            timeout = mcp_data["timeout"]
            if not isinstance(timeout, (int, float)):
                result.add_error(
                    "INVALID_GLOBAL_TIMEOUT_TYPE",
                    "Global 'timeout' must be a number",
                    suggestion="Set global timeout to a number of seconds"
                )
            elif timeout <= 0:
                result.add_error(
                    "INVALID_GLOBAL_TIMEOUT_VALUE",
                    "Global 'timeout' must be positive",
                    suggestion="Use a positive number for global timeout"
                )
        
        # Validate global maxRetries
        if "maxRetries" in mcp_data:
            max_retries = mcp_data["maxRetries"]
            if not isinstance(max_retries, int):
                result.add_error(
                    "INVALID_MAX_RETRIES_TYPE",
                    "'maxRetries' must be an integer",
                    suggestion="Set maxRetries to an integer value"
                )
            elif max_retries < 0:
                result.add_error(
                    "INVALID_MAX_RETRIES_VALUE",
                    "'maxRetries' cannot be negative",
                    suggestion="Use 0 or a positive integer for maxRetries"
                )
        
        # Validate global environment
        if "environment" in mcp_data:
            env = mcp_data["environment"]
            if not isinstance(env, dict):
                result.add_error(
                    "INVALID_GLOBAL_ENV_TYPE",
                    "Global 'environment' must be an object",
                    suggestion="Change global environment to an object with string keys and values"
                )
            else:
                for key, value in env.items():
                    if not isinstance(key, str):
                        result.add_error(
                            "INVALID_GLOBAL_ENV_KEY_TYPE",
                            "Global environment variable key must be a string",
                            suggestion="Ensure all environment variable keys are strings"
                        )
                    if not isinstance(value, str):
                        result.add_error(
                            "INVALID_GLOBAL_ENV_VALUE_TYPE",
                            f"Global environment variable value for '{key}' must be a string",
                            suggestion="Ensure all environment variable values are strings"
                        )
    
    def test_server_connection(self, server_name: str, server_config: Dict[str, Any],
                              result: ValidationResult) -> None:
        """Test actual connection to an MCP server (optional feature)."""
        if not self.enable_connection_testing:
            return
        
        server_prefix = f"Server '{server_name}'"
        
        try:
            # For stdio transport, try to start the process briefly
            if server_config.get("transport", "stdio") == "stdio":
                command = server_config["command"]
                args = server_config.get("args", [])
                env = dict(os.environ)
                env.update(server_config.get("env", {}))
                
                # Try to start the process with a short timeout
                proc = subprocess.Popen(
                    [command] + args,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    cwd=server_config.get("cwd"),
                    timeout=5
                )
                
                # Send a simple test message
                try:
                    stdout, stderr = proc.communicate(
                        input=b'{"jsonrpc": "2.0", "method": "ping", "id": 1}\n',
                        timeout=2
                    )
                    
                    if proc.returncode != 0:
                        result.add_warning(
                            "SERVER_CONNECTION_FAILED",
                            f"{server_prefix}: Server process exited with code {proc.returncode}",
                            suggestion="Check server implementation and dependencies"
                        )
                    else:
                        result.add_info(
                            "SERVER_CONNECTION_OK",
                            f"{server_prefix}: Server process started successfully",
                        )
                        
                except subprocess.TimeoutExpired:
                    proc.kill()
                    result.add_warning(
                        "SERVER_CONNECTION_TIMEOUT",
                        f"{server_prefix}: Server did not respond within timeout",
                        suggestion="Check if server implements MCP protocol correctly"
                    )
                    
        except FileNotFoundError:
            result.add_error(
                "SERVER_EXECUTABLE_NOT_FOUND",
                f"{server_prefix}: Cannot execute server command",
                suggestion="Ensure the server executable exists and is accessible"
            )
        except PermissionError:
            result.add_error(
                "SERVER_PERMISSION_DENIED",
                f"{server_prefix}: Permission denied executing server",
                suggestion="Check executable permissions"
            )
        except Exception as e:
            result.add_warning(
                "SERVER_CONNECTION_ERROR",
                f"{server_prefix}: Error testing server connection: {e}",
                suggestion="Check server configuration and dependencies"
            )