"""Format-specific validators for PACC."""

import json
import re
from typing import List, Optional, Dict, Any, Union
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from .base import BaseValidator, ValidationResult


class JSONValidator(BaseValidator):
    """Validator for JSON files."""
    
    def __init__(self, name: Optional[str] = None):
        """Initialize JSON validator."""
        super().__init__(name or "JSONValidator")
        # Enable common JSON validation rules by default
        self.enable_rule("SYNTAX_CHECK")
        self.enable_rule("DUPLICATE_KEYS")
        self.enable_rule("TRAILING_COMMAS")
    
    def validate_content(self, content: str, file_path: Optional[Path] = None) -> ValidationResult:
        """Validate JSON content.
        
        Args:
            content: JSON content to validate
            file_path: Optional path to the file being validated
            
        Returns:
            ValidationResult with any issues found
        """
        result = ValidationResult(is_valid=True, file_path=file_path, validator_name=self.name)
        
        if not content.strip():
            result.add_error("Empty JSON file", rule_id="EMPTY_FILE")
            return result
        
        # Basic syntax validation
        if self.is_rule_enabled("SYNTAX_CHECK"):
            try:
                parsed_data = json.loads(content)
                result.metadata['parsed_data'] = parsed_data
            except json.JSONDecodeError as e:
                result.add_error(
                    f"Invalid JSON syntax: {e.msg}",
                    line_number=e.lineno,
                    column_number=e.colno,
                    rule_id="SYNTAX_ERROR"
                )
                return result
        
        # Check for trailing commas (common issue)
        if self.is_rule_enabled("TRAILING_COMMAS"):
            self._check_trailing_commas(content, result)
        
        # Check for duplicate keys (Python's json.loads allows them)
        if self.is_rule_enabled("DUPLICATE_KEYS"):
            self._check_duplicate_keys(content, result)
        
        return result
    
    def _check_trailing_commas(self, content: str, result: ValidationResult) -> None:
        """Check for trailing commas in JSON.
        
        Args:
            content: JSON content
            result: ValidationResult to add issues to
        """
        lines = content.split('\n')
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.endswith(',}') or stripped.endswith(',]'):
                result.add_warning(
                    "Trailing comma before closing bracket",
                    line_number=line_num,
                    rule_id="TRAILING_COMMA"
                )
    
    def _check_duplicate_keys(self, content: str, result: ValidationResult) -> None:
        """Check for duplicate keys in JSON objects.
        
        Args:
            content: JSON content
            result: ValidationResult to add issues to
        """
        # This is a simplified check - a full implementation would need proper JSON parsing
        try:
            # Use object_pairs_hook to detect duplicates
            def check_duplicates(pairs):
                keys = [pair[0] for pair in pairs]
                if len(keys) != len(set(keys)):
                    duplicates = [key for key in keys if keys.count(key) > 1]
                    for duplicate in set(duplicates):
                        result.add_warning(
                            f"Duplicate key: '{duplicate}'",
                            rule_id="DUPLICATE_KEY"
                        )
                return dict(pairs)
            
            json.loads(content, object_pairs_hook=check_duplicates)
        except json.JSONDecodeError:
            # Already handled in main validation
            pass
    
    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions."""
        return ['.json', '.jsonc']


class YAMLValidator(BaseValidator):
    """Validator for YAML files."""
    
    def __init__(self, name: Optional[str] = None):
        """Initialize YAML validator."""
        super().__init__(name or "YAMLValidator")
        # Enable common YAML validation rules by default
        self.enable_rule("SYNTAX_CHECK")
        self.enable_rule("INDENTATION")
        self.enable_rule("DUPLICATE_KEYS")
    
    def validate_content(self, content: str, file_path: Optional[Path] = None) -> ValidationResult:
        """Validate YAML content.
        
        Args:
            content: YAML content to validate
            file_path: Optional path to the file being validated
            
        Returns:
            ValidationResult with any issues found
        """
        result = ValidationResult(is_valid=True, file_path=file_path, validator_name=self.name)
        
        if not HAS_YAML:
            result.add_warning(
                "PyYAML not available - limited YAML validation",
                rule_id="MISSING_DEPENDENCY"
            )
            return self._basic_yaml_validation(content, result)
        
        if not content.strip():
            result.add_error("Empty YAML file", rule_id="EMPTY_FILE")
            return result
        
        # Basic syntax validation
        if self.is_rule_enabled("SYNTAX_CHECK"):
            try:
                parsed_data = yaml.safe_load(content)
                result.metadata['parsed_data'] = parsed_data
            except yaml.YAMLError as e:
                line_num = getattr(e, 'problem_mark', None)
                line_number = line_num.line + 1 if line_num else None
                column_number = line_num.column + 1 if line_num else None
                
                result.add_error(
                    f"Invalid YAML syntax: {e}",
                    line_number=line_number,
                    column_number=column_number,
                    rule_id="SYNTAX_ERROR"
                )
                return result
        
        # Check indentation consistency
        if self.is_rule_enabled("INDENTATION"):
            self._check_indentation(content, result)
        
        return result
    
    def _basic_yaml_validation(self, content: str, result: ValidationResult) -> ValidationResult:
        """Basic YAML validation without PyYAML.
        
        Args:
            content: YAML content
            result: ValidationResult to update
            
        Returns:
            Updated ValidationResult
        """
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # Check for common YAML syntax issues
            stripped = line.strip()
            
            # Check for tabs (YAML doesn't allow tabs for indentation)
            if '\t' in line:
                result.add_error(
                    "YAML doesn't allow tabs for indentation",
                    line_number=line_num,
                    rule_id="TAB_INDENTATION"
                )
            
            # Check for common syntax patterns
            if stripped.startswith('- ') and ':' in stripped:
                # List item with mapping - check format
                if not re.match(r'^- \w+:', stripped):
                    result.add_warning(
                        "Potential formatting issue in list item",
                        line_number=line_num,
                        rule_id="LIST_FORMAT"
                    )
        
        return result
    
    def _check_indentation(self, content: str, result: ValidationResult) -> None:
        """Check YAML indentation consistency.
        
        Args:
            content: YAML content
            result: ValidationResult to add issues to
        """
        lines = content.split('\n')
        indent_levels = set()
        
        for line_num, line in enumerate(lines, 1):
            if not line.strip():  # Skip empty lines
                continue
            
            # Calculate indentation
            indent = len(line) - len(line.lstrip())
            if indent > 0:
                indent_levels.add(indent)
        
        # Check if indentation is consistent (multiples of 2 or 4)
        if indent_levels:
            min_indent = min(indent_levels)
            if min_indent not in [2, 4]:
                result.add_warning(
                    f"Unusual indentation size: {min_indent} (prefer 2 or 4 spaces)",
                    rule_id="INDENTATION_SIZE"
                )
            
            # Check if all indents are multiples of the minimum
            for indent in indent_levels:
                if indent % min_indent != 0:
                    result.add_warning(
                        "Inconsistent indentation levels",
                        rule_id="INCONSISTENT_INDENTATION"
                    )
                    break
    
    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions."""
        return ['.yaml', '.yml']


class MarkdownValidator(BaseValidator):
    """Validator for Markdown files."""
    
    def __init__(self, name: Optional[str] = None):
        """Initialize Markdown validator."""
        super().__init__(name or "MarkdownValidator")
        # Enable common Markdown validation rules by default
        self.enable_rule("FRONTMATTER")
        self.enable_rule("HEADERS")
        self.enable_rule("LINKS")
        self.enable_rule("CODE_BLOCKS")
    
    def validate_content(self, content: str, file_path: Optional[Path] = None) -> ValidationResult:
        """Validate Markdown content.
        
        Args:
            content: Markdown content to validate
            file_path: Optional path to the file being validated
            
        Returns:
            ValidationResult with any issues found
        """
        result = ValidationResult(is_valid=True, file_path=file_path, validator_name=self.name)
        
        if not content.strip():
            result.add_error("Empty Markdown file", rule_id="EMPTY_FILE")
            return result
        
        lines = content.split('\n')
        
        # Check YAML frontmatter
        if self.is_rule_enabled("FRONTMATTER"):
            self._check_frontmatter(lines, result)
        
        # Check headers
        if self.is_rule_enabled("HEADERS"):
            self._check_headers(lines, result)
        
        # Check links
        if self.is_rule_enabled("LINKS"):
            self._check_links(lines, result)
        
        # Check code blocks
        if self.is_rule_enabled("CODE_BLOCKS"):
            self._check_code_blocks(lines, result)
        
        return result
    
    def _check_frontmatter(self, lines: List[str], result: ValidationResult) -> None:
        """Check YAML frontmatter in Markdown.
        
        Args:
            lines: Lines of the Markdown file
            result: ValidationResult to add issues to
        """
        if not lines or lines[0].strip() != '---':
            return
        
        # Find end of frontmatter
        end_line = None
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == '---':
                end_line = i
                break
        
        if end_line is None:
            result.add_error(
                "Unclosed YAML frontmatter",
                line_number=1,
                rule_id="UNCLOSED_FRONTMATTER"
            )
            return
        
        # Extract and validate YAML
        frontmatter_content = '\n'.join(lines[1:end_line])
        if HAS_YAML:
            try:
                yaml.safe_load(frontmatter_content)
                result.metadata['has_frontmatter'] = True
            except yaml.YAMLError as e:
                result.add_error(
                    f"Invalid YAML in frontmatter: {e}",
                    line_number=1,
                    rule_id="INVALID_FRONTMATTER"
                )
        else:
            result.add_info(
                "YAML frontmatter found but cannot validate (PyYAML not available)",
                line_number=1,
                rule_id="FRONTMATTER_FOUND"
            )
    
    def _check_headers(self, lines: List[str], result: ValidationResult) -> None:
        """Check Markdown headers.
        
        Args:
            lines: Lines of the Markdown file
            result: ValidationResult to add issues to
        """
        header_levels = []
        
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('#'):
                # Count header level
                level = 0
                for char in stripped:
                    if char == '#':
                        level += 1
                    else:
                        break
                
                if level > 6:
                    result.add_warning(
                        f"Header level {level} exceeds maximum (6)",
                        line_number=line_num,
                        rule_id="HEADER_LEVEL_TOO_HIGH"
                    )
                
                # Check for space after #
                if level < len(stripped) and stripped[level] != ' ':
                    result.add_warning(
                        "Missing space after # in header",
                        line_number=line_num,
                        rule_id="HEADER_SPACING"
                    )
                
                header_levels.append((line_num, level))
        
        # Check header hierarchy
        if len(header_levels) > 1:
            for i in range(1, len(header_levels)):
                prev_level = header_levels[i-1][1]
                curr_level = header_levels[i][1]
                curr_line = header_levels[i][0]
                
                if curr_level > prev_level + 1:
                    result.add_warning(
                        f"Header level jumps from {prev_level} to {curr_level}",
                        line_number=curr_line,
                        rule_id="HEADER_SKIP_LEVEL"
                    )
    
    def _check_links(self, lines: List[str], result: ValidationResult) -> None:
        """Check Markdown links.
        
        Args:
            lines: Lines of the Markdown file
            result: ValidationResult to add issues to
        """
        link_pattern = re.compile(r'\[([^\]]*)\]\(([^)]*)\)')
        
        for line_num, line in enumerate(lines, 1):
            matches = link_pattern.findall(line)
            for text, url in matches:
                if not url.strip():
                    result.add_warning(
                        "Empty link URL",
                        line_number=line_num,
                        rule_id="EMPTY_LINK_URL"
                    )
                
                if not text.strip():
                    result.add_warning(
                        "Empty link text",
                        line_number=line_num,
                        rule_id="EMPTY_LINK_TEXT"
                    )
    
    def _check_code_blocks(self, lines: List[str], result: ValidationResult) -> None:
        """Check Markdown code blocks.
        
        Args:
            lines: Lines of the Markdown file
            result: ValidationResult to add issues to
        """
        in_code_block = False
        code_block_start = None
        
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            if stripped.startswith('```'):
                if not in_code_block:
                    in_code_block = True
                    code_block_start = line_num
                else:
                    in_code_block = False
                    code_block_start = None
        
        # Check for unclosed code blocks
        if in_code_block and code_block_start:
            result.add_error(
                "Unclosed code block",
                line_number=code_block_start,
                rule_id="UNCLOSED_CODE_BLOCK"
            )
    
    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions."""
        return ['.md', '.markdown']


class FormatDetector:
    """Detects file format based on content and extension."""
    
    @staticmethod
    def detect_format(file_path: Path, content: Optional[str] = None) -> str:
        """Detect file format.
        
        Args:
            file_path: Path to the file
            content: Optional file content
            
        Returns:
            Detected format ('json', 'yaml', 'markdown', 'unknown')
        """
        # First try by extension
        ext = file_path.suffix.lower()
        
        if ext in ['.json', '.jsonc']:
            return 'json'
        elif ext in ['.yaml', '.yml']:
            return 'yaml'
        elif ext in ['.md', '.markdown']:
            return 'markdown'
        
        # If no clear extension, try content detection
        if content:
            return FormatDetector._detect_by_content(content)
        
        return 'unknown'
    
    @staticmethod
    def _detect_by_content(content: str) -> str:
        """Detect format by analyzing content.
        
        Args:
            content: File content to analyze
            
        Returns:
            Detected format
        """
        stripped = content.strip()
        
        if not stripped:
            return 'unknown'
        
        # Try JSON
        if (stripped.startswith('{') and stripped.endswith('}')) or \
           (stripped.startswith('[') and stripped.endswith(']')):
            try:
                json.loads(content)
                return 'json'
            except json.JSONDecodeError:
                pass
        
        # Try YAML
        if HAS_YAML:
            try:
                yaml.safe_load(content)
                # Additional heuristics for YAML
                if ':' in content and not stripped.startswith('{'):
                    return 'yaml'
            except yaml.YAMLError:
                pass
        
        # Try Markdown
        if any(line.strip().startswith('#') for line in content.split('\n')[:10]):
            return 'markdown'
        
        return 'unknown'
    
    @staticmethod
    def get_validator_for_format(format_type: str) -> Optional[BaseValidator]:
        """Get appropriate validator for format.
        
        Args:
            format_type: Format type to get validator for
            
        Returns:
            Validator instance or None
        """
        validators = {
            'json': JSONValidator(),
            'yaml': YAMLValidator(),
            'markdown': MarkdownValidator(),
        }
        
        return validators.get(format_type)