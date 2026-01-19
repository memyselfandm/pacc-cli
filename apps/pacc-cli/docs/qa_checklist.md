# PACC Quality Assurance Checklist

This checklist should be completed before each release to ensure PACC meets quality standards across all supported platforms and environments.

## Pre-Release QA Checklist

### 1. Code Quality Checks ✓

- [ ] **Linting**: Run `ruff check .` with no errors
- [ ] **Formatting**: Run `ruff format .` to ensure consistent formatting
- [ ] **Type Checking**: Run `mypy pacc` with no errors (when configured)
- [ ] **Import Sorting**: Verify imports are properly organized
- [ ] **Documentation**: Ensure all public APIs have docstrings

### 2. Test Suite Execution ✓

#### Unit Tests
- [ ] Run `pytest tests/unit/` - All tests pass
- [ ] Coverage report shows >80% coverage
- [ ] No warnings or deprecation notices

#### Integration Tests
- [ ] Run `pytest tests/integration/` - All tests pass
- [ ] Git integration tests pass
- [ ] URL handling tests pass
- [ ] Validation workflow tests pass

#### End-to-End Tests
- [ ] Run `pytest tests/e2e/` - All tests pass
- [ ] User journey tests complete successfully
- [ ] Command functionality tests pass

#### Performance Tests
- [ ] Run `pytest tests/performance/` - All benchmarks pass
- [ ] File processing: >4000 files/second
- [ ] No memory leaks detected
- [ ] Response times within acceptable limits

#### Security Tests
- [ ] Run `make security` - No vulnerabilities found
- [ ] Path traversal protection verified
- [ ] Command injection protection verified
- [ ] No sensitive data exposed

### 3. Cross-Platform Testing ✓

Run `python tests/qa/test_cross_platform.py` and verify:

#### Windows
- [ ] Installation works on Windows 10/11
- [ ] Path handling with spaces works correctly
- [ ] Line endings handled properly (CRLF)
- [ ] Command execution works
- [ ] File permissions handled correctly

#### macOS
- [ ] Installation works on macOS 12+ (Monterey and later)
- [ ] Path handling with spaces works correctly
- [ ] Unix permissions work correctly
- [ ] Command execution works
- [ ] Special characters in filenames handled

#### Linux
- [ ] Installation works on Ubuntu 20.04 LTS and later
- [ ] Installation works on CentOS/RHEL 8+
- [ ] Path handling works correctly
- [ ] Unix permissions work correctly
- [ ] Command execution works

### 4. Python Version Compatibility ✓

Test with each supported Python version:
- [ ] Python 3.8 - Install and run tests
- [ ] Python 3.9 - Install and run tests
- [ ] Python 3.10 - Install and run tests
- [ ] Python 3.11 - Install and run tests
- [ ] Python 3.12 - Install and run tests

### 5. Package Manager Compatibility ✓

Run `python tests/qa/test_package_managers.py` and verify:

#### pip
- [ ] Standard installation: `pip install pacc-cli`
- [ ] Editable installation: `pip install -e .`
- [ ] Wheel installation works
- [ ] Uninstallation clean: `pip uninstall pacc-cli`
- [ ] Virtual environment installation works

#### uv
- [ ] Installation: `uv pip install pacc-cli`
- [ ] Virtual environment creation and installation
- [ ] Package information displays correctly
- [ ] Uninstallation works cleanly

#### pipx
- [ ] Installation: `pipx install pacc-cli`
- [ ] Commands available globally
- [ ] Upgrade works: `pipx upgrade pacc-cli`
- [ ] Uninstallation clean: `pipx uninstall pacc-cli`

### 6. Installation Scenarios ✓

#### Global Installation
- [ ] User-level installation works (`--user` flag)
- [ ] Commands accessible from PATH
- [ ] No permission errors for non-admin users

#### Virtual Environment
- [ ] Standard venv installation works
- [ ] Nested venv paths work
- [ ] Paths with spaces work
- [ ] Activation/deactivation doesn't break functionality

#### Local Development
- [ ] Editable install for development works
- [ ] Changes reflected immediately
- [ ] Test runner works from source

### 7. Upgrade and Migration Testing ✓

Run `python tests/qa/test_upgrade_uninstall.py` and verify:

- [ ] Upgrade from previous version preserves config
- [ ] Downgrade to previous version works
- [ ] Configuration migration successful
- [ ] Backup files created during migration
- [ ] No data loss during upgrade
- [ ] Clean uninstallation removes package completely

### 8. Edge Case Testing ✓

Run `python tests/qa/test_edge_cases.py` and verify:

#### Network Conditions
- [ ] Offline installation works (with local files)
- [ ] Handles network timeouts gracefully
- [ ] Proxy settings respected (if applicable)

#### Permission Scenarios
- [ ] Read-only directories handled gracefully
- [ ] No write permissions handled with clear errors
- [ ] Non-admin installation works where possible

#### File System Edge Cases
- [ ] Very long path names handled (platform limits)
- [ ] Large number of files processed efficiently
- [ ] Large file sizes handled appropriately
- [ ] Special characters in filenames work

#### Resource Constraints
- [ ] Low memory conditions handled
- [ ] Disk space checks work
- [ ] CPU-intensive operations don't freeze

#### Error Conditions
- [ ] Corrupted JSON files detected and reported
- [ ] Missing dependencies reported clearly
- [ ] Circular dependencies detected
- [ ] Version conflicts reported

### 9. Documentation Verification ✓

- [ ] README.md is up to date
- [ ] Installation guide is accurate
- [ ] API documentation is complete
- [ ] Changelog updated with new version
- [ ] Migration guide updated (if applicable)
- [ ] Troubleshooting guide covers common issues

### 10. Package Distribution ✓

#### Build Verification
- [ ] `python -m build` creates wheel and sdist
- [ ] Wheel contains all necessary files
- [ ] Source distribution is complete
- [ ] Package metadata is correct
- [ ] Version number updated correctly

#### PyPI Readiness
- [ ] Package name available/owned on PyPI
- [ ] Description renders correctly on PyPI
- [ ] All classifiers are appropriate
- [ ] Dependencies correctly specified
- [ ] Python version requirements accurate

### 11. Final Integration Testing ✓

Perform these tests with the final release candidate:

1. **Fresh Installation Test**
   - [ ] Create new virtual environment
   - [ ] Install from built wheel
   - [ ] Run all basic commands
   - [ ] Install a test extension
   - [ ] Verify functionality

2. **Upgrade Test**
   - [ ] Install previous version
   - [ ] Create test configuration
   - [ ] Upgrade to new version
   - [ ] Verify configuration preserved
   - [ ] Test new features

3. **CLI Command Tests**
   - [ ] `pacc --version` shows correct version
   - [ ] `pacc --help` displays all commands
   - [ ] `pacc install` works with local files
   - [ ] `pacc validate` catches errors correctly
   - [ ] `pacc list` shows installed extensions

### 12. Performance Validation ✓

- [ ] Installation completes in <30 seconds
- [ ] Command response time <1 second
- [ ] Memory usage stays under 100MB
- [ ] No significant performance regression from previous version

### 13. Security Review ✓

- [ ] No hardcoded credentials or secrets
- [ ] Path traversal vulnerabilities fixed
- [ ] Command injection prevented
- [ ] File permissions set correctly
- [ ] No unsafe pickle/eval usage

## Release Validation Procedures

### Pre-Release Steps

1. **Version Bump**
   ```bash
   # Update version in setup.py, __init__.py, and pyproject.toml
   # Update CHANGELOG.md with release notes
   ```

2. **Run Full Test Suite**
   ```bash
   # From project root
   cd apps/pacc-cli
   make test
   make benchmark
   make security
   ```

3. **Run QA Test Suite**
   ```bash
   # Run all QA tests
   python tests/qa/test_cross_platform.py
   python tests/qa/test_package_managers.py
   python tests/qa/test_upgrade_uninstall.py
   python tests/qa/test_edge_cases.py
   ```

4. **Build Distribution**
   ```bash
   # Clean previous builds
   rm -rf dist/ build/ *.egg-info

   # Build new distribution
   python -m build

   # Check distribution
   twine check dist/*
   ```

5. **Test Installation from Wheel**
   ```bash
   # Create test environment
   python -m venv test_release
   source test_release/bin/activate  # On Windows: test_release\Scripts\activate

   # Install from wheel
   pip install dist/pacc-*.whl

   # Run smoke tests
   pacc --version
   pacc --help
   ```

### Release Steps

1. **Tag Release**
   ```bash
   git tag -a v1.0.0 -m "Release version 1.0.0"
   git push origin v1.0.0
   ```

2. **Upload to Test PyPI** (optional)
   ```bash
   twine upload --repository testpypi dist/*

   # Test installation from Test PyPI
   pip install --index-url https://test.pypi.org/simple/ pacc
   ```

3. **Upload to PyPI**
   ```bash
   twine upload dist/*
   ```

4. **Post-Release Verification**
   ```bash
   # Wait a few minutes for PyPI to update

   # Test installation from PyPI
   pip install pacc-cli
   pacc --version
   ```

### Post-Release Monitoring

1. **Monitor PyPI Statistics**
   - Check download counts
   - Monitor for installation issues

2. **Monitor Issue Tracker**
   - Watch for bug reports
   - Respond to user questions

3. **Update Documentation**
   - Update website/docs with new version
   - Update installation instructions if needed

## Automated QA Script

For convenience, use the master QA test runner:

```bash
# Run all QA tests
python tests/qa/run_qa_tests.py

# Run specific test categories
python tests/qa/run_qa_tests.py --cross-platform
python tests/qa/run_qa_tests.py --package-managers
python tests/qa/run_qa_tests.py --edge-cases
python tests/qa/run_qa_tests.py --upgrade
```

## Sign-Off

Before release, the following roles should sign off:

- [ ] **Lead Developer**: Code quality and functionality
- [ ] **QA Engineer**: All tests pass, checklist complete
- [ ] **Documentation**: Docs are accurate and complete
- [ ] **Release Manager**: Package ready for distribution

**Release Version**: ________________
**Release Date**: ________________
**Approved By**: ________________

---

*This checklist is a living document and should be updated based on lessons learned from each release.*
