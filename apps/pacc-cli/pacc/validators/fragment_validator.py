"""Fragment validator for Claude Code memory fragment extensions."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .base import BaseValidator, ValidationResult
from .utils import parse_claude_frontmatter


class FragmentValidator(BaseValidator):
    """Validator for Claude Code memory fragment extensions."""
    
    # Optional fields that can be present in fragment YAML frontmatter
    OPTIONAL_FRONTMATTER_FIELDS = {
        "title": str,
        "description": str, 
        "tags": (list, str),  # Can be list or comma-separated string
        "category": str,
        "author": str,
        "created": str,
        "modified": str
    }
    
    # Dangerous patterns that could indicate malicious content
    SECURITY_PATTERNS = [
        # Command injection patterns
        r'\$\([^)]*\)',  # $(command)
        r'`[^`]*`',      # `command`
        r'\|\s*\w+',     # | command
        r'>\s*/[/\w]*',  # > /path/file
        
        # Script injection patterns
        r'<script[^>]*>',   # <script> tags
        r'javascript:',     # javascript: URLs
        r'eval\s*\(',      # eval( calls
        r'exec\s*\(',      # exec( calls
        
        # File system manipulation
        r'rm\s+-rf',       # rm -rf commands
        r'sudo\s+\w+',     # sudo commands
        r'/etc/passwd',    # sensitive files
        r'/etc/shadow',    # sensitive files
        
        # Network access patterns
        r'curl\s+[^\s]*',  # curl commands
        r'wget\s+[^\s]*',  # wget commands
        r'nc\s+[^\s]*',    # netcat
        
        # Environment variable access that might be suspicious
        r'\$\{[^}]*\}',    # ${VAR} expansions
        r'process\.env',   # Node.js env access
        r'os\.environ',    # Python env access
    ]
    
    def __init__(self, max_file_size: int = 10 * 1024 * 1024):
        """Initialize fragment validator."""
        super().__init__(max_file_size)
        
        # Pre-compile regex patterns for performance
        self._yaml_frontmatter_pattern = re.compile(
            r'^---\s*\n?(.*?)\n?---\s*\n(.*)', 
            re.DOTALL
        )
        self._security_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.SECURITY_PATTERNS]
    
    def get_extension_type(self) -> str:
        """Return the extension type this validator handles."""
        return "fragments"
    
    def validate_single(self, file_path: Union[str, Path]) -> ValidationResult:
        """Validate a single fragment file."""
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
        
        # Check file extension
        if file_path.suffix.lower() != '.md':
            result.add_warning(
                "UNEXPECTED_FILE_EXTENSION",
                f"Fragment file has unexpected extension '{file_path.suffix}', expected '.md'",
                suggestion="Use .md extension for fragment files"
            )
        
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
        
        # Handle empty files
        if not content.strip():
            result.add_error(
                "EMPTY_FILE",
                "Fragment file is empty",
                suggestion="Add content to the fragment file"
            )
            return result
        
        # Parse frontmatter and markdown content
        frontmatter_error, frontmatter, markdown_content = self._parse_fragment_file(content, result)
        if frontmatter_error:
            return result
        
        # Validate frontmatter if present
        if frontmatter:
            self._validate_frontmatter(frontmatter, result)
        
        # Validate markdown content
        self._validate_markdown_content(markdown_content, result)
        
        # Security scanning
        self._scan_for_security_issues(content, result)
        
        # Extract metadata for successful validations
        if result.is_valid or not result.errors:  # Include if only warnings
            metadata = {
                "has_frontmatter": frontmatter is not None and isinstance(frontmatter, dict),
                "markdown_length": len(markdown_content.strip()),
                "total_length": len(content),
                "line_count": len(content.splitlines())
            }
            
            # Always set these fields, even if no frontmatter
            metadata.update({
                "title": "",
                "description": "",
                "category": "",
                "author": "",
                "tags": []
            })
            
            if frontmatter:
                # Extract common metadata fields from frontmatter
                metadata.update({
                    "title": frontmatter.get("title", ""),
                    "description": frontmatter.get("description", ""),
                    "category": frontmatter.get("category", ""),
                    "author": frontmatter.get("author", "")
                })
                
                # Handle tags (can be list or comma-separated string)
                tags = frontmatter.get("tags", [])
                if isinstance(tags, str):
                    # Handle both comma-separated strings and YAML array strings like "[tag1, tag2]"
                    if tags.startswith('[') and tags.endswith(']'):
                        # Parse as YAML array string
                        tags = tags[1:-1]  # Remove brackets
                    tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
                elif isinstance(tags, list):
                    # Already a proper list
                    tags = [str(tag).strip() for tag in tags if str(tag).strip()]
                else:
                    tags = []
                metadata["tags"] = tags
            
            result.metadata = metadata
        
        return result
    
    def _find_extension_files(self, directory: Path) -> List[Path]:
        """Find fragment files in the given directory."""
        fragment_files = []
        
        # Look for .md files that could be fragments
        for md_file in directory.rglob("*.md"):
            # Basic heuristics to identify fragments vs other markdown files
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read(2048)  # Read first 2KB
                    
                    # Consider it a fragment if:
                    # 1. Has YAML frontmatter, OR
                    # 2. Filename contains "fragment", OR  
                    # 3. Is in a "fragments" directory, OR
                    # 4. Has fragment-like patterns in content
                    is_fragment = (
                        content.startswith("---") or
                        "fragment" in md_file.name.lower() or
                        "fragments" in str(md_file).lower() or
                        any(pattern in content.lower() for pattern in ["memory", "recall", "note", "reference"])
                    )
                    
                    if is_fragment:
                        fragment_files.append(md_file)
                        
            except Exception:
                # If we can't read it, let the full validation handle the error
                fragment_files.append(md_file)
        
        return fragment_files
    
    def _parse_fragment_file(self, content: str, result: ValidationResult) -> tuple[Optional[bool], Optional[Dict[str, Any]], str]:
        """Parse fragment file into optional frontmatter and markdown content."""
        # Check for YAML frontmatter (optional for fragments)
        match = self._yaml_frontmatter_pattern.match(content)
        
        if not match:
            # No frontmatter - this is valid for fragments
            return None, None, content
        
        yaml_content = match.group(1)
        markdown_content = match.group(2)
        
        # Parse YAML frontmatter using lenient Claude Code parser
        frontmatter = parse_claude_frontmatter(yaml_content)
        
        if frontmatter is None:
            # If parsing failed, try to get a better error message
            import yaml
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
        
        if frontmatter and not isinstance(frontmatter, dict):
            result.add_error(
                "INVALID_FRONTMATTER_FORMAT",
                "YAML frontmatter must be a dictionary/object",
                suggestion="Ensure frontmatter contains key-value pairs"
            )
            return True, None, ""
        
        return None, frontmatter, markdown_content
    
    def _validate_frontmatter(self, frontmatter: Dict[str, Any], result: ValidationResult) -> None:
        """Validate fragment YAML frontmatter structure and content."""
        file_path = result.file_path
        
        # Validate field types for known fields
        for field, expected_type in self.OPTIONAL_FRONTMATTER_FIELDS.items():
            if field in frontmatter:
                value = frontmatter[field]
                
                # Skip None values - they'll be handled by specific field validators
                if value is None:
                    continue
                
                # Handle tuple types (multiple allowed types)
                if isinstance(expected_type, tuple):
                    if not any(isinstance(value, t) for t in expected_type):
                        type_names = " or ".join(t.__name__ for t in expected_type)
                        result.add_error(
                            "INVALID_FIELD_TYPE",
                            f"Field '{field}' must be of type {type_names}, got {type(value).__name__}",
                            suggestion=f"Change '{field}' to the correct type"
                        )
                else:
                    if not isinstance(value, expected_type):
                        result.add_error(
                            "INVALID_FIELD_TYPE",
                            f"Field '{field}' must be of type {expected_type.__name__}, got {type(value).__name__}",
                            suggestion=f"Change '{field}' to a {expected_type.__name__} value"
                        )
        
        # Validate specific fields
        self._validate_title(frontmatter.get("title"), result)
        self._validate_description(frontmatter.get("description"), result)
        self._validate_tags(frontmatter.get("tags"), result)
        
        # Check for unknown fields (info level only)
        known_fields = set(self.OPTIONAL_FRONTMATTER_FIELDS.keys())
        for field in frontmatter:
            if field not in known_fields:
                result.add_info(
                    "UNKNOWN_FRONTMATTER_FIELD",
                    f"Unknown field '{field}' in fragment frontmatter",
                    suggestion=f"Common fields are: {', '.join(sorted(known_fields))}"
                )
    
    def _validate_title(self, title: Any, result: ValidationResult) -> None:
        """Validate fragment title."""
        if title is None:
            # None title (empty YAML value) should be treated as empty string
            result.add_warning(
                "EMPTY_TITLE", 
                "Fragment title is empty",
                suggestion="Provide a descriptive title for the fragment"
            )
            return
        
        if not isinstance(title, str):
            result.add_error(
                "INVALID_TITLE_TYPE",
                "Fragment title must be a string",
                suggestion="Change title to a string value"
            )
            return
        
        if not title.strip():
            result.add_warning(
                "EMPTY_TITLE",
                "Fragment title is empty",
                suggestion="Provide a descriptive title for the fragment"
            )
            return
        
        # Check title length
        if len(title) > 200:
            result.add_warning(
                "TITLE_TOO_LONG",
                f"Fragment title is very long ({len(title)} characters)",
                suggestion="Use a shorter, more concise title"
            )
        
        if len(title) < 3:
            result.add_info(
                "TITLE_TOO_SHORT",
                "Fragment title is very short",
                suggestion="Consider a more descriptive title"
            )
    
    def _validate_description(self, description: Any, result: ValidationResult) -> None:
        """Validate fragment description.""" 
        if description is None:
            # None description (empty YAML value) should be treated as empty string
            result.add_warning(
                "EMPTY_DESCRIPTION",
                "Fragment description is empty", 
                suggestion="Provide a description of the fragment content"
            )
            return
        
        if not isinstance(description, str):
            result.add_error(
                "INVALID_DESCRIPTION_TYPE",
                "Fragment description must be a string",
                suggestion="Change description to a string value"
            )
            return
        
        if not description.strip():
            result.add_warning(
                "EMPTY_DESCRIPTION",
                "Fragment description is empty",
                suggestion="Provide a description of the fragment content"
            )
            return
        
        if len(description) > 1000:
            result.add_warning(
                "DESCRIPTION_TOO_LONG",
                f"Fragment description is very long ({len(description)} characters)",
                suggestion="Consider using a more concise description"
            )
    
    def _validate_tags(self, tags: Any, result: ValidationResult) -> None:
        """Validate fragment tags."""
        if tags is None:
            return  # Tags are optional
        
        # Tags can be a list or a comma-separated string
        if isinstance(tags, str):
            # Parse comma-separated string
            tag_list = [tag.strip() for tag in tags.split(",")]
        elif isinstance(tags, list):
            tag_list = tags
        else:
            result.add_error(
                "INVALID_TAGS_TYPE",
                f"Tags must be a list or comma-separated string, got {type(tags).__name__}",
                suggestion='Use format like: ["tag1", "tag2"] or "tag1, tag2"'
            )
            return
        
        # Validate individual tags
        for i, tag in enumerate(tag_list):
            if not isinstance(tag, str):
                result.add_error(
                    "INVALID_TAG_TYPE",
                    f"Tag {i+1} must be a string, got {type(tag).__name__}",
                    suggestion="Use string values for tags"
                )
                continue
            
            if not tag.strip():
                result.add_warning(
                    "EMPTY_TAG",
                    f"Tag {i+1} is empty",
                    suggestion="Remove empty tags or provide tag values"
                )
                continue
            
            # Validate tag format (no spaces, reasonable length)
            tag = tag.strip()
            if ' ' in tag:
                result.add_info(
                    "TAG_WITH_SPACES",
                    f"Tag '{tag}' contains spaces",
                    suggestion="Consider using underscores or hyphens instead of spaces"
                )
            
            if len(tag) > 50:
                result.add_warning(
                    "TAG_TOO_LONG",
                    f"Tag '{tag}' is very long ({len(tag)} characters)",
                    suggestion="Use shorter, more concise tags"
                )
        
        # Check for too many tags
        if len(tag_list) > 20:
            result.add_warning(
                "TOO_MANY_TAGS",
                f"Fragment has many tags ({len(tag_list)})",
                suggestion="Consider using fewer, more specific tags"
            )
    
    def _validate_markdown_content(self, markdown_content: str, result: ValidationResult) -> None:
        """Validate the markdown content of the fragment."""
        if not markdown_content.strip():
            result.add_error(
                "EMPTY_MARKDOWN_CONTENT", 
                "Fragment has no markdown content",
                suggestion="Add content to the fragment"
            )
            return
        
        # Check for very short content
        if len(markdown_content.strip()) < 10:
            result.add_warning(
                "VERY_SHORT_CONTENT",
                "Fragment markdown content is very short",
                suggestion="Provide more detailed content"
            )
            return
        
        lines = markdown_content.split('\n')
        
        # Check for headers (good practice for organization)
        has_headers = any(line.strip().startswith('#') for line in lines)
        if not has_headers and len(markdown_content.strip()) > 500:
            result.add_info(
                "NO_HEADERS_FOUND",
                "Consider using headers to organize the fragment content",
                suggestion="Add headers (# ## ###) to structure the content"
            )
        
        # Check for code blocks (often useful in technical fragments)
        has_code_blocks = '```' in markdown_content
        if not has_code_blocks and len(markdown_content.strip()) > 100 and any(keyword in markdown_content.lower() for keyword in ['code', 'command', 'function', 'script']):
            result.add_info(
                "CONSIDER_CODE_BLOCKS",
                "Content mentions code but has no code blocks",
                suggestion="Use ```language ... ``` blocks for code examples"
            )
        
        # Check for lists (good for organizing information)
        has_lists = any(line.strip().startswith(('-', '*', '+')) or re.match(r'^\s*\d+\.', line) for line in lines)
        if not has_lists and len(markdown_content.strip()) > 300:
            result.add_info(
                "CONSIDER_LISTS",
                "Consider using lists to organize information",
                suggestion="Use - or * for bullet points, or 1. 2. 3. for numbered lists"
            )
    
    def _scan_for_security_issues(self, content: str, result: ValidationResult) -> None:
        """Scan fragment content for potential security issues."""
        content_lower = content.lower()
        
        # Remove code blocks before scanning to avoid false positives
        content_without_code = re.sub(r'```[^`]*```', '', content, flags=re.DOTALL)
        
        # Check for suspicious patterns outside code blocks
        for pattern in self._security_patterns:
            matches = pattern.findall(content_without_code)
            if matches:
                # Group similar matches
                unique_matches = set(matches[:5])  # Limit to first 5 unique matches
                match_preview = ', '.join(unique_matches)
                if len(match_preview) > 100:
                    match_preview = match_preview[:100] + "..."
                
                result.add_warning(
                    "POTENTIAL_SECURITY_ISSUE",
                    f"Fragment contains potentially dangerous pattern: {match_preview}",
                    suggestion="Review content for security implications before use"
                )
        
        # Check for excessive external links
        link_pattern = re.compile(r'https?://[^\s\]]+', re.IGNORECASE)
        links = link_pattern.findall(content)
        if len(links) > 10:
            result.add_info(
                "MANY_EXTERNAL_LINKS",
                f"Fragment contains many external links ({len(links)})",
                suggestion="Verify all external links are necessary and trustworthy"
            )
        
        # Check for embedded base64 or encoded content (could hide malicious data)
        if re.search(r'data:[^;]+;base64,[A-Za-z0-9+/=]{50,}', content):
            result.add_warning(
                "EMBEDDED_BASE64_CONTENT",
                "Fragment contains embedded base64 content",
                suggestion="Review embedded content for security implications"
            )
        
        # Check for references to sensitive paths or files
        sensitive_paths = ['/etc/', '/root/', '/home/', 'C:\\Windows\\', 'C:\\Users\\', '/var/log/']
        for path in sensitive_paths:
            if path in content:
                result.add_info(
                    "SENSITIVE_PATH_REFERENCE",
                    f"Fragment references potentially sensitive path: {path}",
                    suggestion="Ensure path references are appropriate for the fragment context"
                )