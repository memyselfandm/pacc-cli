# Publishing Workflow

This document outlines the complete workflow for publishing PACC to PyPI, from pre-release preparation to post-publish verification.

## Table of Contents

1. [Pre-publish Checklist](#pre-publish-checklist)
2. [Version Management](#version-management)
3. [Building Distributions](#building-distributions)
4. [Testing Distributions](#testing-distributions)
5. [Publishing to Test PyPI](#publishing-to-test-pypi)
6. [Publishing to Production PyPI](#publishing-to-production-pypi)
7. [Post-publish Verification](#post-publish-verification)
8. [Rollback Procedures](#rollback-procedures)

## Pre-publish Checklist

Before initiating any publish workflow, complete this checklist:

### Code Quality
- [ ] All tests pass: `make test`
- [ ] Coverage meets threshold (>80%): `make coverage`
- [ ] No linting errors: `make lint`
- [ ] Type checking passes: `make type-check`
- [ ] Security scan clean: `make security-check`

### Documentation
- [ ] README.md is up to date
- [ ] CHANGELOG.md updated with new version
- [ ] API documentation current
- [ ] All new features documented
- [ ] Migration guide (if breaking changes)

### Version Control
- [ ] On main/master branch
- [ ] Branch is up to date with remote
- [ ] No uncommitted changes
- [ ] All PRs merged
- [ ] CI/CD pipeline green

### Dependencies
- [ ] requirements.txt up to date
- [ ] pyproject.toml dependencies correct
- [ ] No security vulnerabilities in deps
- [ ] Compatibility ranges appropriate

## Version Management

PACC follows semantic versioning (SemVer): MAJOR.MINOR.PATCH

### Version Bump Process

1. **Determine Version Type**
   - **PATCH** (1.0.0 → 1.0.1): Bug fixes, minor updates
   - **MINOR** (1.0.0 → 1.1.0): New features, backward compatible
   - **MAJOR** (1.0.0 → 2.0.0): Breaking changes

2. **Update Version in Multiple Places**
   ```bash
   # Run the version bump script
   python scripts/publish.py bump-version --type patch

   # Or manually update:
   # - pyproject.toml: version = "X.Y.Z"
   # - pacc/__init__.py: __version__ = "X.Y.Z"
   # - CHANGELOG.md: Add new version section
   ```

3. **Commit Version Changes**
   ```bash
   git add pyproject.toml pacc/__init__.py CHANGELOG.md
   git commit -m "chore: bump version to X.Y.Z"
   git push origin main
   ```

### Updating CHANGELOG

Follow this format for CHANGELOG.md:

```markdown
# Changelog

## [X.Y.Z] - YYYY-MM-DD

### Added
- New features

### Changed
- Changes to existing functionality

### Deprecated
- Features to be removed in future

### Removed
- Features removed in this release

### Fixed
- Bug fixes

### Security
- Security fixes
```

## Building Distributions

Build both source distribution (sdist) and wheel:

### Automated Build

```bash
# Clean previous builds
make clean

# Build distributions
make build

# Or use the publish script
python scripts/publish.py build
```

### Manual Build Process

```bash
# Clean build artifacts
rm -rf build/ dist/ *.egg-info/

# Install build dependencies
pip install --upgrade build twine

# Build source distribution and wheel
python -m build

# Verify distributions created
ls -la dist/
# Should show:
# pacc-X.Y.Z.tar.gz
# pacc-X.Y.Z-py3-none-any.whl
```

### Build Validation

```bash
# Check distributions with twine
twine check dist/*

# Inspect package contents
tar -tzf dist/pacc-*.tar.gz | head -20
unzip -l dist/pacc-*.whl | head -20
```

## Testing Distributions

Before publishing, thoroughly test the distributions:

### Local Installation Test

```bash
# Create test virtual environment
python -m venv test-env
source test-env/bin/activate  # On Windows: test-env\Scripts\activate

# Install from wheel
pip install dist/pacc-*.whl

# Test import
python -c "import pacc; print(pacc.__version__)"

# Test CLI
pacc --version
pacc --help

# Run basic commands
pacc validate ./test-extension

# Deactivate and clean up
deactivate
rm -rf test-env
```

### Installation from Source Test

```bash
# Create another test environment
python -m venv test-sdist
source test-sdist/bin/activate

# Install from source distribution
pip install dist/pacc-*.tar.gz

# Run same tests as above
pacc --version

deactivate
rm -rf test-sdist
```

## Publishing to Test PyPI

Always test with Test PyPI first:

### Using the Publish Script

```bash
# Publish to Test PyPI
python scripts/publish.py publish --test

# Or use Makefile
make publish-test
```

### Manual Publishing to Test PyPI

```bash
# Upload to Test PyPI
twine upload --repository testpypi dist/*

# If using .pypirc, it will use stored credentials
# Otherwise, you'll be prompted for username (__token__) and password
```

### Test Installation from Test PyPI

```bash
# Create clean environment
python -m venv test-pypi-env
source test-pypi-env/bin/activate

# Install from Test PyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ pacc

# Test functionality
pacc --version
pacc --help

# Clean up
deactivate
rm -rf test-pypi-env
```

## Publishing to Production PyPI

After successful Test PyPI validation:

### Final Pre-flight Checks

```bash
# Run the pre-publish validation
python scripts/publish.py validate

# Manually verify:
# - Version number is correct
# - CHANGELOG is updated
# - All tests pass
# - Test PyPI installation works
```

### Production Publish

```bash
# Publish to PyPI
python scripts/publish.py publish --prod

# Or use Makefile
make publish-prod

# Or manually
twine upload dist/*
```

### Tag the Release

```bash
# Create git tag
git tag -a v.X.Y.Z -m "Release version X.Y.Z"

# Push tag
git push origin v.X.Y.Z

# Create GitHub release (if applicable)
gh release create v.X.Y.Z --title "PACC vX.Y.Z" --notes-file RELEASE_NOTES.md
```

## Post-publish Verification

### Package Visibility Check

1. **Check PyPI Page**
   - Visit https://pypi.org/project/pacc/
   - Verify version number
   - Check description renders correctly
   - Verify links work (Homepage, Documentation, etc.)

2. **Check Package Files**
   - Verify both .whl and .tar.gz are available
   - Check file sizes are reasonable
   - Download and inspect if needed

### Installation Verification

```bash
# Wait 1-2 minutes for CDN propagation

# Test in clean environment
python -m venv verify-env
source verify-env/bin/activate

# Install from PyPI
pip install pacc==X.Y.Z

# Run verification tests
python scripts/publish.py verify --version X.Y.Z

# Manual checks
pacc --version
python -c "import pacc; print(pacc.__version__)"

# Test core functionality
echo '{"name": "test-hook"}' > test-hook.json
pacc validate test-hook.json --type hooks

# Clean up
deactivate
rm -rf verify-env test-hook.json
```

### Documentation and Announcement

1. **Update Documentation**
   - Update installation instructions with new version
   - Update any version-specific documentation
   - Publish documentation updates

2. **Announce Release**
   - GitHub release notes
   - Project mailing list/forum
   - Social media (if applicable)
   - Update project website

## Rollback Procedures

If issues are discovered post-publish:

### Yanking a Release

**Note**: Yanking doesn't delete the release but prevents new installations.

```bash
# Yank from PyPI (requires maintainer permissions)
# Via web interface:
# 1. Log in to PyPI
# 2. Go to project page
# 3. Select version
# 4. Click "Yank"

# Document the issue
echo "Version X.Y.Z yanked due to: [reason]" >> CHANGELOG.md
```

### Publishing a Fix

1. **Identify the Issue**
   - Document what went wrong
   - Create issue ticket
   - Determine severity

2. **Fix and Version Bump**
   ```bash
   # For critical issues, bump patch version
   python scripts/publish.py bump-version --type patch

   # Fix the issue
   # Run full test suite
   make test
   ```

3. **Expedited Release**
   ```bash
   # Fast-track through test PyPI
   make build
   make publish-test

   # Quick verification
   pip install --index-url https://test.pypi.org/simple/ pacc

   # Publish fix
   make publish-prod
   ```

4. **Post-mortem**
   - Document what happened
   - Update procedures to prevent recurrence
   - Consider adding tests for the issue

### Emergency Contacts

- PyPI Support: https://github.com/pypa/pypi-support/issues
- Package Maintainers: See MAINTAINERS.md
- Security Issues: security@pypi.org

## Automation Scripts

The `scripts/publish.py` script automates many of these steps:

```bash
# Full automated workflow
python scripts/publish.py release --version X.Y.Z --test-first

# Individual commands
python scripts/publish.py validate     # Pre-publish validation
python scripts/publish.py build        # Build distributions
python scripts/publish.py test-install # Test local installation
python scripts/publish.py publish      # Publish to PyPI
python scripts/publish.py verify       # Post-publish verification
```

## Best Practices

1. **Always Test First**
   - Use Test PyPI for every release
   - Test in clean environments
   - Verify all functionality

2. **Automate Where Possible**
   - Use scripts for repetitive tasks
   - Set up CI/CD for releases
   - Automate version bumping

3. **Document Everything**
   - Keep CHANGELOG current
   - Document known issues
   - Maintain upgrade guides

4. **Security First**
   - Never expose tokens
   - Use 2FA everywhere
   - Rotate credentials regularly

5. **Communication**
   - Announce releases
   - Respond to user issues quickly
   - Maintain release notes
