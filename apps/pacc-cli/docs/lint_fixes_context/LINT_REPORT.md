# PACC CLI Linting Report

Generated on: 2025-09-26

## 🎯 Executive Summary

**Total Issues Found: 805**

### Issue Breakdown by Type
- **E501 Line too long**: ~60-70% of issues (line length > 100 chars)
- **PLR0915 Too many statements**: Functions exceeding 50 statements
- **PLR0912 Too many branches**: Functions exceeding 12 branches
- **PLR0913 Too many arguments**: Functions exceeding 5 arguments
- **ARG00X Unused arguments**: Unused function/lambda arguments
- **RUF013 Implicit Optional**: Missing Optional type hints
- **C401 Unnecessary generator**: Generator -> set/list comprehension
- **B028 Explicit stacklevel**: Missing stacklevel in warnings
- **Other**: Various minor style and complexity issues

### Configuration Issues
⚠️ **Deprecated Configuration**: Top-level linter settings in `pyproject.toml` are deprecated. Need to move to `lint` section.

---

## 📂 Issues by Codebase Section

### 1. Core & CLI (pacc/cli.py, pacc/core/)

**Total Issues: ~150-180**

#### pacc/cli.py (Major Issues)
- **PLR0915**: Line 465 - `_add_plugin_parser()` has 101 statements (limit: 50)
- **PLR0915**: Line 946 - `_add_fragment_parser()` has 94 statements (limit: 50)
- **E501 Line length violations**:
  - Line 149: Install command description (101 chars)
  - Line 470: Plugin command description (103 chars)
  - Line 600: Plugin update help text (121 chars)
  - Line 627: Sync command description (120 chars)
  - Line 726: Convert command description (106 chars)

#### pacc/core/ modules
- **pacc/core/config.py**: Multiple PLR0915 violations (functions too long)
- **pacc/core/paths.py**: E501 line length issues
- **pacc/core/file_utils.py**: ARG unused argument issues

**Recommendations**:
- Split large parser methods into smaller helper functions
- Break down complex CLI setup into modular components
- Shorten description strings or use multi-line formatting

---

### 2. Plugin System (pacc/plugins/)

**Total Issues: ~120-140**

#### Major Issues
- **pacc/plugins/manager.py**:
  - PLR0915: Multiple functions exceeding statement limits
  - PLR0912: Complex branching in plugin operations
  - E501: Long lines in method signatures and docstrings

- **pacc/plugins/installer.py**:
  - PLR0913: Functions with too many arguments
  - ARG005: Unused arguments in callback functions

- **pacc/plugins/git_operations.py**:
  - B028: Missing stacklevel in warning calls
  - RUF013: Implicit Optional type hints

**Common Patterns**:
- Long method signatures for plugin configuration
- Complex error handling with deep nesting
- Extended docstrings causing line length violations

**Recommendations**:
- Extract plugin configuration into dataclasses
- Simplify error handling flows
- Use multi-line docstring formatting

---

### 3. Validators (pacc/validators/)

**Total Issues: ~80-100**

#### Key Files with Issues
- **pacc/validators/hooks.py**: PLR0915, E501 violations
- **pacc/validators/mcp.py**: Complex validation logic with high statement count
- **pacc/validators/agents.py**: Long lines in validation rules
- **pacc/validators/commands.py**: ARG unused arguments in helper functions

**Common Issues**:
- Validation functions with extensive rule checking (high statement count)
- Long regular expressions causing line length violations
- Unused arguments in validation callbacks

**Recommendations**:
- Break validation logic into smaller, focused functions
- Extract regex patterns to module constants
- Use validation result objects instead of multiple return values

---

### 4. UI & Selection (pacc/ui/, pacc/selection/)

**Total Issues: ~60-80**

#### pacc/ui/ Issues
- **pacc/ui/display.py**: E501 line length in formatted output strings
- **pacc/ui/progress.py**: PLR complexity in progress calculation logic
- **pacc/ui/prompts.py**: Long function signatures for interactive prompts

#### pacc/selection/ Issues
- **pacc/selection/interactive.py**: PLR0915 in selection workflows
- **pacc/selection/strategies.py**: Complex branching logic

**Recommendations**:
- Use string formatting methods to reduce line length
- Split complex UI workflows into smaller functions
- Extract selection logic into strategy classes

---

### 5. Sources & Fragments (pacc/sources/, pacc/fragments/)

**Total Issues: ~40-60**

#### pacc/sources/ Issues
- **pacc/sources/resolver.py**: PLR0915 in URL resolution logic
- **pacc/sources/git.py**: E501 in Git command construction
- **pacc/sources/local.py**: ARG unused arguments in file scanning

#### pacc/fragments/ Issues
- **pacc/fragments/manager.py**: Complex fragment processing logic
- **pacc/fragments/storage.py**: Long file path handling methods

**Recommendations**:
- Simplify source resolution with helper classes
- Extract Git command building to utility functions
- Use Path objects consistently to reduce string manipulation

---

### 6. Support Modules

**Total Issues: ~80-100**

#### pacc/packaging/
- **extractor.py**: PLR0915 in archive extraction logic
- **formats.py**: E501 in format detection patterns

#### pacc/recovery/
- **strategies.py**: Complex retry logic with high statement count
- **backups.py**: Long file operation chains

#### pacc/performance/
- **caching.py**: PLR0913 in cache configuration methods
- **optimization.py**: Complex performance measurement logic

#### pacc/errors/
- **exceptions.py**: Long error message formatting
- **handlers.py**: Complex error recovery workflows

#### pacc/validation/
- **base.py**: PLR0915 in base validation logic
- **schemas.py**: Long schema definition methods

#### pacc/security/
- **scanning.py**: Complex security rule processing
- **policies.py**: Long security policy definitions

**Recommendations**:
- Extract complex algorithms into separate utility modules
- Use configuration objects instead of long parameter lists
- Implement builder patterns for complex object construction

---

### 7. Tests (tests/)

**Total Issues: ~150-200**

#### Major Test Issues

**tests/test_cli.py**:
- PLR0915: Test methods with extensive setup/teardown (>50 statements)
- E501: Long assertion messages and test data

**tests/test_plugins/**:
- Multiple files with PLR0915 violations
- Complex test scenarios with deep nesting
- Long test data strings causing line length issues

**tests/integration/**:
- PLR0912: Test methods with complex branching
- E501: Long file paths and command strings

**tests/utils/**:
- **mocks.py**:
  - RUF013: Implicit Optional in mock method signatures
  - ARG005: Unused lambda arguments in mock setup
- **performance.py**:
  - E501: Long assertion messages in performance checks
  - RUF013: Missing Optional type hints

**Common Test Patterns**:
- Large test methods that test multiple scenarios
- Complex mock setups with unused parameters
- Long assertion messages for better test failure reporting

**Recommendations**:
- Split large test methods into focused test cases
- Use parametrized tests for multiple scenario testing
- Extract common test utilities to reduce duplication
- Use multi-line strings for long test assertions

---

### 8. Examples & Scripts (examples/, scripts/)

**Total Issues: ~50-80**

#### examples/ Issues
- **config_integration_example.py**:
  - PLR0912: Too many branches (15 > 12) in validation function
  - PLR0915: Too many statements (80 > 50) in main example function
  - ARG005: Unused lambda arguments in config path mocking
  - C401: Unnecessary generator (should use set comprehension)

#### scripts/ Issues
- Long command-line argument parsing
- Complex setup logic in utility scripts

**Recommendations**:
- Break example functions into smaller, focused demonstrations
- Use proper argument handling in lambda functions
- Convert generators to comprehensions where appropriate
- Simplify script logic with helper functions

---

## 🚨 Priority Recommendations

### High Priority (Critical Issues)
1. **Fix pyproject.toml configuration**: Move linter settings to `lint` section
2. **Reduce function complexity**: Target the 15+ PLR0915 violations in core modules
3. **Address CLI parser bloat**: Split `_add_plugin_parser` and `_add_fragment_parser` methods

### Medium Priority (Code Quality)
1. **Line length violations**: ~400+ E501 issues to address
2. **Type hints**: Fix RUF013 implicit Optional issues
3. **Unused arguments**: Clean up ARG005 violations

### Low Priority (Style Improvements)
1. **Generator optimizations**: Convert unnecessary generators to comprehensions
2. **Warning improvements**: Add stacklevel to warning calls
3. **Test organization**: Split large test methods for better maintainability

---

## 📊 File-Level Issue Counts (Top 20)

1. **pacc/cli.py**: ~40-50 issues (mostly E501, PLR0915)
2. **pacc/plugins/manager.py**: ~25-35 issues
3. **tests/test_cli.py**: ~20-30 issues
4. **pacc/core/config.py**: ~15-25 issues
5. **tests/test_plugins/test_manager.py**: ~15-20 issues
6. **pacc/validators/hooks.py**: ~10-15 issues
7. **pacc/plugins/installer.py**: ~10-15 issues
8. **examples/config_integration_example.py**: ~8-10 issues
9. **pacc/fragments/manager.py**: ~8-12 issues
10. **pacc/sources/resolver.py**: ~8-10 issues
11. **tests/utils/performance.py**: ~6-8 issues
12. **pacc/ui/display.py**: ~6-8 issues
13. **pacc/validators/mcp.py**: ~5-8 issues
14. **pacc/plugins/git_operations.py**: ~5-8 issues
15. **tests/utils/mocks.py**: ~5-6 issues
16. **pacc/selection/interactive.py**: ~5-6 issues
17. **pacc/core/paths.py**: ~4-6 issues
18. **pacc/packaging/extractor.py**: ~4-6 issues
19. **pacc/recovery/strategies.py**: ~4-5 issues
20. **pacc/performance/caching.py**: ~4-5 issues

---

## 🛠️ Automated Fix Potential

- **~200 hidden fixes available** with `--unsafe-fixes` option
- Most E501 line length issues can be auto-formatted
- Some ARG unused argument issues can be auto-resolved
- Generator -> comprehension conversions can be automated

**Recommendation**: Run `ruff check --fix --unsafe-fixes` to automatically resolve simple issues before manual cleanup.

---

## 🎯 Success Metrics

**Target Goals**:
- Reduce total issues from 805 to <100
- Eliminate all PLR0915 violations (functions too long)
- Fix all E501 line length violations
- Address all RUF013 type hint issues
- Clean up all ARG005 unused argument issues

**Implementation Strategy**:
1. **Automated fixes first**: Use ruff's auto-fix capabilities
2. **Parallel fixing**: Assign sections to different agents/developers
3. **Incremental validation**: Run linting after each section fix
4. **Configuration update**: Fix pyproject.toml deprecation warnings

This comprehensive report provides a roadmap for systematically addressing all linting issues across the PACC CLI codebase while maintaining code quality and functionality.
