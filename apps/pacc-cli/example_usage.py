"""Example usage of PACC Wave 1 components."""

import sys
from pathlib import Path

# Add pacc to path for this example
sys.path.insert(0, '.')

from pacc.core.file_utils import DirectoryScanner, FileFilter, FilePathValidator
from pacc.validation.formats import JSONValidator, YAMLValidator, FormatDetector
from pacc.validation.base import CompositeValidator
from pacc.ui.components import SelectableItem, MultiSelectList, SearchFilter
from pacc.errors.reporting import ErrorReporter, ErrorContext


def demo_file_scanning():
    """Demonstrate file scanning capabilities."""
    print("=== File Scanning Demo ===")
    
    # Scan current directory for Python files
    scanner = DirectoryScanner()
    file_filter = FileFilter()
    
    # Find Python files
    python_files = scanner.find_files_by_extension('.', {'.py'}, recursive=True)
    print(f"Found {len(python_files)} Python files")
    
    # Filter to exclude test files
    filtered_files = (file_filter
                     .add_pattern_filter(['*.py'])
                     .add_exclude_hidden()
                     .filter_files(python_files))
    
    for file_path in filtered_files[:5]:  # Show first 5
        print(f"  📄 {file_path}")
    
    print()


def demo_validation():
    """Demonstrate validation capabilities."""
    print("=== Validation Demo ===")
    
    # Test JSON validation
    json_validator = JSONValidator()
    
    valid_json = '{"name": "PACC", "version": "0.1.0"}'
    result = json_validator.validate_content(valid_json)
    print(f"Valid JSON: {result.is_valid} (issues: {len(result.issues)})")
    
    invalid_json = '{"name": "PACC", "version": 0.1.0}'  # Missing quotes
    result = json_validator.validate_content(invalid_json)
    print(f"Invalid JSON: {result.is_valid} (issues: {len(result.issues)})")
    if result.issues:
        print(f"  Error: {result.issues[0].message}")
    
    # Test format detection
    format_type = FormatDetector.detect_format(Path("test.json"), valid_json)
    print(f"Detected format: {format_type}")
    
    print()


def demo_ui_components():
    """Demonstrate UI components (non-interactive)."""
    print("=== UI Components Demo ===")
    
    # Create some selectable items
    items = [
        SelectableItem("1", "JSON Hook", "Pre-tool use hook for JSON validation"),
        SelectableItem("2", "YAML Validator", "Validates YAML configuration files"),
        SelectableItem("3", "MCP Server", "Model Context Protocol server"),
        SelectableItem("4", "Custom Agent", "AI agent for code review"),
    ]
    
    # Test search filtering
    search_filter = SearchFilter()
    search_filter.set_query("JSON")
    filtered = search_filter.filter_items(items)
    
    print(f"Items matching 'JSON': {len(filtered)}")
    for item in filtered:
        print(f"  • {item.display_text}: {item.description}")
    
    # Test fuzzy search
    search_filter.set_query("val")
    fuzzy_filtered = search_filter.fuzzy_filter_items(items)
    
    print(f"\\nItems fuzzy matching 'val': {len(fuzzy_filtered)}")
    for item in fuzzy_filtered:
        print(f"  • {item.display_text}")
    
    print()


def demo_error_handling():
    """Demonstrate error handling."""
    print("=== Error Handling Demo ===")
    
    reporter = ErrorReporter(verbose=True)
    
    # Test validation error reporting
    reporter.report_validation_error(
        "Invalid JSON syntax",
        file_path=Path("test.json"),
        line_number=5,
        validation_type="JSON"
    )
    
    # Get error summary
    summary = reporter.get_error_summary()
    print(f"Total errors reported: {summary['total_errors']}")
    print(f"Error types: {list(summary['error_types'].keys())}")
    
    print()


def main():
    """Run all demonstrations."""
    print("🚀 PACC Wave 1 Foundation Layer Demo")
    print("=" * 50)
    print()
    
    try:
        demo_file_scanning()
        demo_validation()
        demo_ui_components()
        demo_error_handling()
        
        print("✅ All demos completed successfully!")
        print("\\nThe PACC foundation layer is ready for Wave 2 development.")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()