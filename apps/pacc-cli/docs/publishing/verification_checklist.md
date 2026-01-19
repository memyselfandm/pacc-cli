# Verification Checklist

Post-publication verification ensures your package is properly published and functional. This checklist covers all verification steps after publishing to PyPI.

## Quick Checklist

- [ ] Package visible on PyPI
- [ ] Installation test
- [ ] Import test
- [ ] Command-line test
- [ ] Documentation links
- [ ] Metadata verification

## Detailed Verification Steps

### 1. Package Visibility on PyPI

#### Production PyPI
- [ ] Navigate to https://pypi.org/project/pacc/
- [ ] Verify latest version number matches release
- [ ] Check release date is correct
- [ ] Confirm both wheel (.whl) and source (.tar.gz) are available

#### Test PyPI
- [ ] Navigate to https://test.pypi.org/project/pacc/
- [ ] Verify test version is available
- [ ] Check upload timestamp

#### Package Files
- [ ] Download links work for both distributions
- [ ] File sizes are reasonable (not empty or suspiciously large)
- [ ] Checksums/hashes are displayed

### 2. Installation Test

Create a clean environment and test installation:

```bash
# Create fresh virtual environment
python -m venv verify-install
source verify-install/bin/activate  # Windows: verify-install\Scripts\activate

# Test standard installation
pip install pacc==X.Y.Z  # Specific version

# Verify installation
pip show pacc
# Check:
# - Version: X.Y.Z
# - Summary: matches description
# - Home-page: correct URL
# - Author: correct
# - License: correct

# Test installation with extras (if applicable)
pip install pacc[url]==X.Y.Z

# Clean up
deactivate
rm -rf verify-install
```

### 3. Import Test

Test Python imports work correctly:

```bash
# Quick import test
python -c "import pacc; print(pacc.__version__)"
# Should output: X.Y.Z

# Detailed import test
python << 'EOF'
import pacc
from pacc import cli
from pacc.validators import HooksValidator
from pacc.core import file_utils

# Verify version
assert pacc.__version__ == "X.Y.Z"

# Verify key components exist
assert hasattr(cli, 'main')
assert hasattr(HooksValidator, 'validate')

print("✓ All imports successful")
EOF
```

### 4. Command-line Test

Verify CLI functionality:

```bash
# Basic command test
pacc --version
# Should output: pacc version X.Y.Z

pacc --help
# Should display help with all commands

# Test core commands
pacc list --help
pacc install --help
pacc validate --help

# Functional test
echo '{"name": "test-hook", "events": ["PreToolUse"]}' > test-hook.json
pacc validate test-hook.json --type hooks
# Should validate successfully

# Clean up
rm test-hook.json
```

### 5. Documentation Links

Verify all package links work:

#### PyPI Page Links
- [ ] Homepage link → GitHub repository
- [ ] Documentation link → ReadTheDocs or docs site
- [ ] Bug Tracker → GitHub Issues
- [ ] Changelog → CHANGELOG.md
- [ ] Source → GitHub repository

#### README Rendering
- [ ] README displays correctly on PyPI
- [ ] Images load (if any)
- [ ] Code blocks formatted properly
- [ ] Links in README work

### 6. Metadata Verification

Check package metadata is correct:

```bash
# Download and inspect metadata
pip download --no-deps pacc==X.Y.Z
tar -xzf pacc-X.Y.Z.tar.gz
cat pacc-X.Y.Z/PKG-INFO

# Verify metadata fields:
# - Name: pacc
# - Version: X.Y.Z
# - Summary: (correct description)
# - Keywords: (all present)
# - Classifiers: (all correct)
# - Requires-Python: >=3.8
# - License: MIT
# - Project-URL: (all links)

# Check wheel metadata
unzip -p pacc-X.Y.Z-py3-none-any.whl pacc-X.Y.Z.dist-info/METADATA

# Clean up
rm -rf pacc-X.Y.Z*
```

## Integration Tests

### With Other Tools

Test PACC works with common Python tools:

```bash
# Test with pip-tools
pip-compile --output-file requirements.txt pyproject.toml

# Test with pipenv
pipenv install pacc==X.Y.Z
pipenv run pacc --version

# Test with poetry
poetry add pacc==X.Y.Z
poetry run pacc --version
```

### Cross-Platform Testing

If possible, test on multiple platforms:

- [ ] **Linux**: Ubuntu/Debian
- [ ] **macOS**: Latest version
- [ ] **Windows**: Windows 10/11
- [ ] **Python versions**: 3.8, 3.9, 3.10, 3.11, 3.12

## Performance Verification

### Installation Speed

```bash
time pip install --no-cache-dir pacc==X.Y.Z
# Should complete in < 30 seconds
```

### Import Speed

```bash
time python -c "import pacc"
# Should complete in < 1 second
```

### Command Execution

```bash
time pacc --version
# Should complete in < 0.5 seconds
```

## Security Verification

### Dependency Audit

```bash
# Check for known vulnerabilities
pip install safety
safety check --packages pacc

# Or using pip-audit
pip install pip-audit
pip-audit
```

### Package Integrity

```bash
# Verify package signatures (if signed)
# Check PyPI shows "Signed" indicator

# Verify no unexpected files
pip show -f pacc | grep -E "\.(exe|dll|so|dylib)$"
# Should be empty unless expected
```

## Documentation Verification

### API Documentation
- [ ] All modules documented
- [ ] Examples work
- [ ] Version number correct

### User Guides
- [ ] Installation guide updated
- [ ] Quick start guide works
- [ ] Migration guide (if applicable)

## Community Verification

### Announcement Checklist
- [ ] GitHub Release created
- [ ] Release notes published
- [ ] Twitter/Social media announcement
- [ ] Discord/Slack notification
- [ ] Mailing list announcement

### User Feedback Monitoring
- [ ] Watch GitHub issues for problems
- [ ] Monitor PyPI download stats
- [ ] Check social media mentions
- [ ] Review any immediate feedback

## Rollback Readiness

Ensure you can rollback if needed:

- [ ] Previous version still installable
- [ ] Rollback procedure documented
- [ ] Team knows how to yank release
- [ ] Hotfix process ready

## Automated Verification Script

Run the automated verification:

```bash
# Using the publish script
python scripts/publish.py verify --version X.Y.Z

# Or run all checks
make verify-release VERSION=X.Y.Z
```

## Sign-off

### Final Approval
- [ ] Technical Lead approval
- [ ] Documentation reviewed
- [ ] All tests passed
- [ ] No critical issues reported

### Post-Release Monitoring
- [ ] Set up alerts for issues
- [ ] Schedule follow-up review (24h)
- [ ] Document lessons learned

## Troubleshooting

### Package Not Visible
- Wait 1-5 minutes for CDN propagation
- Check https://pypi.org/project/pacc/X.Y.Z/
- Clear browser cache
- Try different DNS

### Installation Fails
- Check PyPI status page
- Verify package uploaded correctly
- Test with --verbose flag
- Check for dependency conflicts

### Import Errors
- Verify all files included in package
- Check MANIFEST.in
- Review build logs
- Test source distribution

## Verification Complete

Once all items are checked:

1. Update release status in project tracker
2. Close release milestone
3. Archive release artifacts
4. Begin monitoring for issues

Remember: Thorough verification prevents user frustration and maintains project reputation.
