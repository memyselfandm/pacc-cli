# Fragment Integration Testing Guide

This guide documents the comprehensive fragment testing infrastructure created for PACC-56, providing patterns and best practices for reliable fragment testing.

## Overview

The fragment testing system consists of:
- **Deterministic Sample Fragments**: Consistent test fragments that install the same way every time
- **Comprehensive Test Fixtures**: Reliable mocks and fixtures for isolated testing  
- **Integration Test Patterns**: Complete workflow testing using real fragment operations
- **Performance Benchmarks**: Consistent measurement and documentation of performance
- **Enhanced Unit Tests**: Thorough component testing with sample fragments

## Sample Fragment Collections

### Location
```
tests/fixtures/sample_fragments.py
```

### Available Collections

#### 1. Deterministic Collection
**Purpose**: Basic deterministic installation testing  
**Fragment Count**: 6  
**Contents**:
- `test-simple-agent.md` - Simple agent with minimal complexity
- `test-medium-agent.md` - Medium complexity agent with structured content
- `test-simple-command.md` - Basic command fragment
- `test-complex-command.md` - Complex command with validation patterns
- `test-deterministic-hook.json` - Simple hook with fixed behavior
- `test-complex-hook.json` - Complex hook with multiple events

**Key Characteristics**:
- Fixed timestamps and identifiers
- No random elements
- Consistent validation behavior
- Predictable installation order

#### 2. Edge Case Collection
**Purpose**: Edge case and boundary testing  
**Fragment Count**: 4  
**Contents**:
- `minimal-test-agent.md` - Minimal valid agent
- `special-chars-agent.md` - Agent with special characters
- `no-params-command.md` - Command with no parameters
- `minimal-hook.json` - Hook with minimal configuration

**Key Characteristics**:
- Tests boundary conditions
- Special character handling
- Minimal valid configurations
- Edge case validation patterns

#### 3. Versioned Collection
**Purpose**: Version management and upgrade testing  
**Fragment Count**: 3 versions of same fragment  
**Contents**:
- `versioned-test-agent-v1.md` - Version 1.0.0
- `versioned-test-agent-v11.md` - Version 1.1.0 (compatible)
- `versioned-test-agent-v2.md` - Version 2.0.0 (breaking changes)

**Key Characteristics**:
- Semantic versioning
- Breaking change detection
- Upgrade path testing
- Version metadata preservation

#### 4. Dependency Collection
**Purpose**: Dependency resolution and ordering testing  
**Fragment Count**: 3  
**Contents**:
- `base-agent.md` - No dependencies (level 0)
- `dependent-agent.md` - Depends on base-agent (level 1)
- `integrated-command.md` - Depends on both agents (level 2)

**Key Characteristics**:
- Linear dependency chain
- Deterministic resolution order
- Dependency metadata tracking
- Installation order validation

## Usage Patterns

### Creating Test Collections

```python
from tests.fixtures.sample_fragments import SampleFragmentFactory, create_comprehensive_test_suite

# Create all collections
collections = create_comprehensive_test_suite(tmp_path)

# Create specific collection
deterministic_collection = SampleFragmentFactory.create_deterministic_collection(tmp_path)
```

### Using in Tests

```python
def test_fragment_installation_consistency(self):
    collection_path = self.sample_collections["deterministic"]
    
    # Test multiple installations for consistency
    results = []
    for run in range(3):
        if run > 0:
            self._reset_environment()
        
        result = self.installation_manager.install_from_source(
            str(collection_path),
            target_type="project",
            install_all=True
        )
        results.append(result)
    
    # Verify consistency across runs
    first_result = results[0]
    for result in results[1:]:
        assert result.success == first_result.success
        assert result.installed_count == first_result.installed_count
```

## Test Fixtures and Mocks

### Location
```
tests/fixtures/fragment_mocks.py
```

### Available Mocks

#### MockFragmentEnvironment
Complete mock environment with deterministic behavior:

```python
from tests.fixtures.fragment_mocks import ReliableTestFixtures

environment = ReliableTestFixtures.create_mock_environment(tmp_path)

# Add mock fragments
environment.add_mock_fragment("test-agent", "agent", version="1.0.0")

# Use in tests
assert len(environment.installed_fragments) == 1
```

#### MockFragmentValidator
Deterministic validator with consistent results:

```python
from tests.fixtures.fragment_mocks import MockFragmentValidator

validator = MockFragmentValidator(always_valid=True)

# Multiple calls return identical results
result1 = validator.validate_single(fragment_path)
result2 = validator.validate_single(fragment_path)
assert result1.is_valid == result2.is_valid
```

#### Deterministic Patches
Mock time and random functions for consistent testing:

```python
@pytest.fixture
def deterministic_patches():
    patches = ReliableTestFixtures.patch_for_determinism()
    # All timestamps will be fixed at 2024-01-01T00:00:00Z
```

## Integration Test Patterns

### Location
```
tests/integration/test_fragment_sample_integration.py
```

### Key Test Patterns

#### 1. Consistency Testing
Test that operations produce identical results across multiple runs:

```python
def test_deterministic_collection_install_consistency(self):
    """Test that deterministic collection installs exactly the same way every time."""
    for i in range(3):
        if i > 0:
            self._reset_test_environment()
        
        result = self.installation_manager.install_from_source(...)
        results.append(result)
    
    # Compare all results for consistency
    # Assert identical success, counts, fragments, metadata
```

#### 2. Complete Workflow Testing
Test install → update → remove workflows:

```python
def test_install_update_remove_workflow(self):
    """Test complete install -> update -> remove workflow with sample fragments."""
    # 1. Install fragments
    install_result = self.installation_manager.install_from_source(...)
    
    # 2. Update fragments
    update_result = self.update_manager.update_fragment(...)
    
    # 3. Remove fragments
    remove_result = self.storage_manager.remove_fragment(...)
    
    # Verify each step and final state
```

#### 3. Error Recovery Testing
Test consistent error handling:

```python
def test_error_handling_consistency(self):
    """Test that error conditions are handled consistently."""
    results = []
    for run in range(3):
        result = self.installation_manager.install_from_source(invalid_path)
        results.append(result)
    
    # All runs should handle errors the same way
```

#### 4. Cross-Component Integration
Test data consistency across all components:

```python
def test_cross_component_data_integrity(self):
    """Test data integrity across all fragment components."""
    # Install fragments
    install_result = self.installation_manager.install_from_source(...)
    
    # Verify consistency between:
    # - Installation manager results
    # - Storage manager data  
    # - Validator behavior
    # - CLAUDE.md integration
```

## Unit Test Enhancement Patterns

### Location
```
tests/unit/test_fragment_components_enhanced.py
```

### Enhanced Test Patterns

#### 1. Deterministic Validation Testing
```python
def test_validate_deterministic_fragments_consistency(self):
    """Test validator produces consistent results for deterministic fragments."""
    for fragment_path in fragment_paths:
        results = []
        for run in range(3):
            result = self.validator.validate_single(fragment_path)
            results.append(result)
        
        # All results should be identical
        first_result = results[0]
        for result in results[1:]:
            assert result.is_valid == first_result.is_valid
```

#### 2. Storage Consistency Testing
```python
def test_store_and_retrieve_deterministic_fragments(self):
    """Test storing and retrieving sample fragments consistently."""
    # Store fragment multiple times
    for run in range(3):
        location = self.storage_manager.store_fragment(...)
        retrieved = self.storage_manager.get_fragment(name)
        
        # Results should be consistent across runs
```

#### 3. Component Integration Reliability
```python
def test_full_workflow_reliability(self):
    """Test full validate -> install -> store -> retrieve workflow reliability."""
    for run in range(3):
        # 1. Validate all fragments
        # 2. Install collection  
        # 3. Verify storage
        # 4. Retrieve each fragment
        
        # Assert consistency across all runs
```

## Performance Benchmarking

### Location
```
tests/performance/test_fragment_benchmarks.py
```

### Benchmark Categories

#### 1. Validation Benchmarks
```python
def benchmark_fragment_validation(self):
    """Benchmark fragment validation operations."""
    # Test validation performance for each collection type
    # Measure: mean time, throughput, consistency
```

#### 2. Installation Benchmarks
```python
def benchmark_fragment_installation(self):
    """Benchmark fragment installation operations."""
    # Test installation performance for different collection sizes
    # Compare single vs. collection installation
```

#### 3. Storage Benchmarks
```python
def benchmark_fragment_storage(self):
    """Benchmark fragment storage operations."""
    # Test listing, retrieving, removing performance
    # Measure scalability with fragment count
```

#### 4. Update Benchmarks
```python
def benchmark_fragment_updates(self):
    """Benchmark fragment update operations."""
    # Test version update performance
    # Compare compatible vs. breaking changes
```

### Running Benchmarks

#### In Tests
```python
pytest tests/performance/test_fragment_benchmarks.py -v
```

#### Standalone
```python
python tests/performance/test_fragment_benchmarks.py
# Generates: fragment_performance_report.json
```

### Performance Report Structure
```json
{
  "benchmark_info": {
    "timestamp": "2024-01-01 00:00:00 UTC",
    "iterations": 10,
    "warmup_runs": 3
  },
  "summary": {
    "total_operations": 15,
    "fastest_operation": {...},
    "slowest_operation": {...}
  },
  "detailed_results": {
    "validation": [...],
    "installation": [...],
    "storage": [...],
    "updates": [...]
  },
  "performance_analysis": {
    "operation_categories": {...},
    "performance_patterns": [...],
    "recommendations": [...]
  }
}
```

## Best Practices

### 1. Deterministic Testing
- Use fixed timestamps: `"2024-01-01T00:00:00Z"`
- Sort results for consistent ordering
- Avoid random elements in test data
- Mock external dependencies

### 2. Environment Reset
Always reset between test iterations:

```python
def _reset_test_environment(self):
    # Remove fragments directory
    if fragments_dir.exists():
        shutil.rmtree(fragments_dir)
    
    # Reset project files
    self._setup_project_files()
```

### 3. Comprehensive Assertions
Test multiple aspects for each operation:

```python
# Core functionality
assert result.success, f"Operation failed: {result.error_message}"

# Consistency  
assert result.installed_count == expected_count

# Data integrity
assert installed_names == expected_names

# Performance
assert result.mean_time < timeout_threshold
```

### 4. Error Condition Testing
Test both success and failure paths:

```python
# Test valid operations
valid_result = manager.operation(valid_input)
assert valid_result.success

# Test invalid operations
with pytest.raises(ExpectedError):
    manager.operation(invalid_input)
```

## Integration with CI/CD

### Test Categories
- **Unit Tests**: Fast component testing with mocks
- **Integration Tests**: Full workflow testing with samples  
- **Performance Tests**: Benchmark testing for regression detection
- **End-to-End Tests**: Complete system testing

### Test Selection
```bash
# Run all fragment tests
pytest tests/ -k fragment

# Run only integration tests
pytest tests/integration/test_fragment_sample_integration.py

# Run performance benchmarks
pytest tests/performance/test_fragment_benchmarks.py --benchmark

# Run with coverage
pytest tests/ --cov=pacc.fragments --cov-report=html
```

### Performance Regression Detection
Set performance thresholds in CI:

```python
# In performance tests
assert result.mean_time < 5.0, f"Performance regression: {result.operation}"
assert result.throughput > 0.1, f"Throughput too low: {result.operation}"
```

## Extending the Test Suite

### Adding New Sample Fragments
1. Create new fragments in `SampleFragmentFactory`
2. Ensure deterministic content (no timestamps, random elements)
3. Add to appropriate collection
4. Update collection manifest

### Adding New Test Patterns
1. Follow existing pattern structure
2. Include consistency checks across multiple runs
3. Add appropriate assertions for both success and failure
4. Document the pattern in this guide

### Adding New Benchmarks
1. Follow `BenchmarkResult` structure
2. Include warmup runs and multiple iterations  
3. Add performance thresholds and assertions
4. Update performance report generation

## Troubleshooting

### Common Issues

#### Inconsistent Test Results
- Check for non-deterministic elements (timestamps, random values)
- Ensure proper environment reset between runs
- Verify mock behavior is consistent

#### Performance Variance
- Increase warmup runs for more stable measurements
- Check system load during benchmarking
- Use coefficient of variation to detect high variance

#### Integration Test Failures
- Verify sample fragment collections are valid
- Check component initialization order
- Ensure proper cleanup in teardown methods

### Debugging Tips
```python
# Enable debug logging
import logging
logging.getLogger('pacc.fragments').setLevel(logging.DEBUG)

# Add timing information
import time
start_time = time.perf_counter()
# ... operation ...
elapsed = time.perf_counter() - start_time
print(f"Operation took {elapsed:.4f}s")

# Verify sample fragment integrity
validation_result = validator.validate_single(fragment_path)
if not validation_result.is_valid:
    print(f"Invalid fragment: {validation_result.errors}")
```

## Conclusion

This comprehensive fragment testing infrastructure provides:
- **Reliability**: Deterministic sample fragments ensure consistent test behavior
- **Coverage**: Integration tests exercise complete workflows with real operations
- **Performance**: Benchmark suite documents and monitors performance characteristics  
- **Maintainability**: Well-structured fixtures and patterns support easy extension

The testing system serves as both a validation tool for current functionality and a foundation for future comprehensive testing in PACC-58.