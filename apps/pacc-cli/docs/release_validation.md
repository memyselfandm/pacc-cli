# PACC Release Validation Procedures

This document outlines the comprehensive validation procedures that must be completed before releasing any version of PACC to ensure quality, compatibility, and reliability across all supported platforms.

## Overview

The release validation process consists of several stages:

1. **Pre-Release Testing** - Comprehensive test suite execution
2. **Build Validation** - Package building and distribution testing
3. **Cross-Platform Validation** - Multi-platform compatibility testing
4. **Integration Validation** - Real-world usage scenario testing
5. **Performance Validation** - Performance benchmark verification
6. **Security Validation** - Security vulnerability assessment
7. **Documentation Validation** - Documentation accuracy verification
8. **Final Release Checklist** - Last-minute verification steps

## Stage 1: Pre-Release Testing

### Automated Test Suite

Run the comprehensive automated test suite:

```bash
# Navigate to the CLI application directory
cd apps/pacc-cli

# Run all QA tests
python tests/qa/run_qa_tests.py

# Or run specific test categories
python tests/qa/run_qa_tests.py --quick              # Quick validation
python tests/qa/run_qa_tests.py --cross-platform    # Platform tests
python tests/qa/run_qa_tests.py --package-managers  # Package manager tests
python tests/qa/run_qa_tests.py --edge-cases        # Edge case tests
```

**Success Criteria:**
- All unit tests pass (100% success rate)
- All integration tests pass (100% success rate)
- All end-to-end tests pass (100% success rate)
- Performance tests meet benchmarks (>4000 files/second)
- No security vulnerabilities detected

### Manual Testing Verification

1. **Command Line Interface**
   ```bash
   # Test all major commands manually
   pacc --version
   pacc --help
   pacc validate --help
   pacc install --help
   pacc list --help
   ```

2. **Core Functionality**
   ```bash
   # Test core workflows
   pacc validate tests/fixtures/valid_hook.json
   pacc install tests/fixtures/valid_hook.json --project --dry-run
   pacc list --project
   ```

3. **Error Handling**
   ```bash
   # Test error conditions
   pacc validate tests/fixtures/invalid_hook.json
   pacc install /nonexistent/path
   pacc install tests/fixtures/corrupted.json
   ```

## Stage 2: Build Validation

### Package Building

1. **Clean Build Environment**
   ```bash
   # Remove previous builds
   rm -rf build/ dist/ *.egg-info/

   # Ensure clean git state
   git status  # Should show no uncommitted changes
   ```

2. **Build Package**
   ```bash
   # Build wheel and source distribution
   python -m build

   # Verify build artifacts
   ls -la dist/
   # Should contain both .whl and .tar.gz files
   ```

3. **Validate Distribution**
   ```bash
   # Check package metadata
   twine check dist/*

   # Extract and inspect wheel contents
   unzip -l dist/pacc-*.whl
   ```

**Success Criteria:**
- Build completes without errors
- Both wheel (.whl) and source distribution (.tar.gz) created
- `twine check` passes without warnings
- Wheel contains all expected files and directories

### Installation Testing

1. **Test Wheel Installation**
   ```bash
   # Create fresh virtual environment
   python -m venv test_wheel_install
   source test_wheel_install/bin/activate

   # Install from wheel
   pip install dist/pacc-*.whl

   # Test functionality
   pacc --version
   pacc --help

   # Clean up
   deactivate
   rm -rf test_wheel_install
   ```

2. **Test Source Installation**
   ```bash
   # Create fresh virtual environment
   python -m venv test_source_install
   source test_source_install/bin/activate

   # Install from source
   pip install dist/pacc-*.tar.gz

   # Test functionality
   pacc --version
   pacc --help

   # Clean up
   deactivate
   rm -rf test_source_install
   ```

## Stage 3: Cross-Platform Validation

### Platform-Specific Testing

Run validation on each target platform:

#### macOS (Primary Development Platform)
```bash
# Run comprehensive tests
python tests/qa/test_cross_platform.py
python tests/qa/test_package_managers.py

# Test with different Python versions
python3.8 -m pytest tests/unit/
python3.9 -m pytest tests/unit/
python3.10 -m pytest tests/unit/
python3.11 -m pytest tests/unit/
python3.12 -m pytest tests/unit/
```

#### Windows (GitHub Actions or Windows VM)
```cmd
# Run cross-platform tests
python tests\qa\test_cross_platform.py

# Test Windows-specific scenarios
python tests\qa\test_edge_cases.py

# Test package managers
python tests\qa\test_package_managers.py
```

#### Linux (GitHub Actions or Linux VM)
```bash
# Run cross-platform tests
python tests/qa/test_cross_platform.py

# Test package managers
python tests/qa/test_package_managers.py

# Test in containers
docker run -v $(pwd):/app python:3.8 bash -c "cd /app && pip install -e . && python -m pytest tests/"
docker run -v $(pwd):/app python:3.9 bash -c "cd /app && pip install -e . && python -m pytest tests/"
```

**Success Criteria:**
- All tests pass on all platforms
- No platform-specific regressions
- Installation works with all supported package managers
- File path handling works correctly across platforms

### Container Testing

Test in isolated container environments:

```bash
# Test with different Python versions
for version in 3.8 3.9 3.10 3.11 3.12; do
    echo "Testing Python $version"
    docker run --rm -v $(pwd):/app python:$version-slim bash -c "
        cd /app &&
        pip install -e . &&
        python -c 'import pacc; print(pacc.__version__)' &&
        pacc --version
    "
done
```

## Stage 4: Integration Validation

### Real-World Usage Scenarios

1. **New User Installation**
   ```bash
   # Simulate new user experience
   python -m venv new_user_test
   source new_user_test/bin/activate

   # Install from PyPI test or wheel
   pip install dist/pacc-*.whl

   # Follow getting started guide
   pacc --help
   pacc validate --help

   # Test with sample extension
   pacc validate examples/sample_hook.json
   pacc install examples/sample_hook.json --project --dry-run
   ```

2. **Upgrade Scenario**
   ```bash
   # Simulate upgrade from previous version
   python -m venv upgrade_test
   source upgrade_test/bin/activate

   # Install previous version (if available)
   # pip install pacc-cli==<previous_version>

   # Upgrade to new version
   pip install --upgrade dist/pacc-*.whl

   # Verify upgrade worked
   pacc --version
   ```

3. **Team Collaboration Scenario**
   ```bash
   # Test team configuration sharing
   mkdir team_test && cd team_test

   # Initialize project with pacc
   pacc init --team-config

   # Install shared extensions
   pacc install ../examples/team_hooks/ --project

   # Verify configuration
   pacc list --project
   ```

### Integration with Claude Code

If Claude Code is available, test actual integration:

1. **Settings Integration**
   - Install extension using PACC
   - Verify settings.json is updated correctly
   - Test extension functionality in Claude Code

2. **Project Isolation**
   - Install extensions at project level
   - Verify they don't affect other projects
   - Test uninstallation cleans up correctly

## Stage 5: Performance Validation

### Benchmark Verification

```bash
# Run performance benchmarks
python tests/performance/test_benchmarks.py

# Verify benchmarks meet targets:
# - File processing: >4000 files/second
# - Memory usage: <100MB for typical operations
# - Command response time: <1 second
```

### Load Testing

```bash
# Test with large number of files
python tests/qa/test_edge_cases.py

# Test with large configuration files
# Test with deeply nested directory structures
# Test with many concurrent operations
```

## Stage 6: Security Validation

### Automated Security Scanning

```bash
# Run security tests
make security

# Check for known vulnerabilities
pip-audit

# Scan for secrets
detect-secrets scan --all-files
```

### Manual Security Review

1. **Input Validation**
   - Test with malicious file paths
   - Test with malformed JSON/YAML
   - Test with very large inputs

2. **File System Security**
   - Verify path traversal protection
   - Test file permission handling
   - Verify no arbitrary file overwrites

3. **Command Injection Protection**
   - Test with malicious commands in configurations
   - Verify shell command sanitization

## Stage 7: Documentation Validation

### Documentation Accuracy

1. **Installation Instructions**
   - Follow installation guide exactly
   - Test all provided commands
   - Verify version compatibility

2. **API Documentation**
   - Test all documented examples
   - Verify command line options
   - Check help text accuracy

3. **Troubleshooting Guide**
   - Verify error conditions and solutions
   - Test recovery procedures
   - Update based on new issues

### Documentation Completeness

- [ ] README.md updated with current version
- [ ] CHANGELOG.md includes all changes
- [ ] API documentation reflects current functionality
- [ ] Installation guide covers all platforms
- [ ] Migration guide updated for breaking changes

## Stage 8: Final Release Checklist

### Version and Metadata

- [ ] Version number updated in all files:
  - [ ] `setup.py` or `pyproject.toml`
  - [ ] `pacc/__init__.py`
  - [ ] `CHANGELOG.md`
- [ ] Git tag created with correct version
- [ ] Package metadata is accurate
- [ ] Dependencies are correctly specified

### Quality Gates

- [ ] All automated tests pass (100% success rate)
- [ ] All manual tests completed successfully
- [ ] Cross-platform validation complete
- [ ] Performance benchmarks met
- [ ] Security scan clean
- [ ] Documentation validated

### Release Readiness

- [ ] Build artifacts created and validated
- [ ] PyPI upload credentials available
- [ ] Release notes prepared
- [ ] Rollback plan documented

## Release Execution

### Pre-Upload Steps

1. **Final Validation**
   ```bash
   # Run complete QA suite one more time
   python tests/qa/run_qa_tests.py
   ```

2. **Upload to Test PyPI** (Optional)
   ```bash
   # Upload to test repository
   twine upload --repository testpypi dist/*

   # Test installation from test PyPI
   pip install --index-url https://test.pypi.org/simple/ pacc
   ```

### Production Upload

```bash
# Upload to production PyPI
twine upload dist/*

# Verify upload
pip install pacc-cli
pacc --version
```

### Post-Release Validation

1. **Installation Testing**
   ```bash
   # Test installation from PyPI
   python -m venv post_release_test
   source post_release_test/bin/activate
   pip install pacc-cli
   pacc --version
   pacc --help
   ```

2. **Monitor for Issues**
   - Watch PyPI download statistics
   - Monitor issue tracker for reports
   - Check installation compatibility

## Rollback Procedures

If critical issues are discovered after release:

1. **Immediate Response**
   - Assess issue severity
   - Determine if rollback needed
   - Communicate with users

2. **PyPI Management**
   - Remove problematic version (if necessary)
   - Upload fixed version
   - Update documentation

3. **User Communication**
   - Issue advisory notice
   - Provide workaround instructions
   - Update troubleshooting guide

## Release Validation Report Template

```markdown
# PACC Release Validation Report

**Version**: vX.Y.Z
**Date**: YYYY-MM-DD
**Validator**: [Name]

## Test Results Summary
- [ ] Pre-Release Testing: PASS/FAIL
- [ ] Build Validation: PASS/FAIL
- [ ] Cross-Platform Validation: PASS/FAIL
- [ ] Integration Validation: PASS/FAIL
- [ ] Performance Validation: PASS/FAIL
- [ ] Security Validation: PASS/FAIL
- [ ] Documentation Validation: PASS/FAIL

## Issues Found
[List any issues discovered and their resolution]

## Release Readiness
- [ ] All validation stages completed
- [ ] All issues resolved
- [ ] Release approved

**Validator Signature**: ________________
**Release Manager Approval**: ________________
```

## Automation and CI/CD Integration

### GitHub Actions Integration

The validation procedures should be integrated into CI/CD pipeline:

```yaml
# .github/workflows/release-validation.yml
name: Release Validation
on:
  push:
    tags: ['v*']

jobs:
  validate:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: [3.8, 3.9, '3.10', 3.11, 3.12]

    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v3
        with:
          python-version: ${{ matrix.python-version }}
      - name: Run QA Tests
        run: |
          cd apps/pacc-cli
          python tests/qa/run_qa_tests.py --quick
```

### Continuous Monitoring

Post-release monitoring should include:
- Download statistics tracking
- Error rate monitoring
- User feedback collection
- Performance regression detection

---

*This document should be updated after each release to incorporate lessons learned and improve the validation process.*
