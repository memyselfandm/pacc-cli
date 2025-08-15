# PyPI Registration Guide for pacc

## Prerequisites

Before registering on PyPI, ensure you have:
1. A PyPI account (register at https://pypi.org/account/register/)
2. Two-factor authentication enabled (recommended)
3. API token generated (https://pypi.org/manage/account/)

## Step-by-Step Registration Process

### 1. Test on TestPyPI First

TestPyPI is a separate instance for testing:

```bash
# Install build tools
pip install --upgrade build twine

# Build the package
python -m build

# Upload to TestPyPI
python -m twine upload --repository testpypi dist/*

# Test installation from TestPyPI
pip install --index-url https://test.pypi.org/simple/ --no-deps pacc
```

### 2. Prepare for Production PyPI

1. **Verify Package Name Availability**
   ```bash
   python scripts/package_registration/check_pypi_availability.py pacc
   ```

2. **Review Package Metadata**
   - Ensure version number follows semantic versioning
   - Check description is clear and concise
   - Verify all URLs are correct
   - Confirm license is properly specified

3. **Test Package Locally**
   ```bash
   # Install in development mode
   pip install -e .
   
   # Run tests
   pytest
   
   # Test command-line interface
   pacc --help
   ```

### 3. Upload to PyPI

```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info

# Build fresh distribution
python -m build

# Upload to PyPI
python -m twine upload dist/*
```

### 4. Post-Registration Steps

1. **Verify Installation**
   ```bash
   # Create fresh virtual environment
   python -m venv test_env
   source test_env/bin/activate  # On Windows: test_env\Scripts\activate
   
   # Install from PyPI
   pip install pacc
   
   # Test functionality
   pacc --version
   ```

2. **Update Documentation**
   - Add PyPI badges to README
   - Update installation instructions
   - Add link to PyPI page

3. **Configure Automated Releases**
   - Set up GitHub Actions for automatic PyPI uploads
   - Use trusted publishing (recommended)

## API Token Configuration

### Creating a .pypirc file

Create `~/.pypirc` with the following content:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = <your-pypi-token>

[testpypi]
username = __token__
password = <your-testpypi-token>
```

**Security Note**: Set appropriate permissions:
```bash
chmod 600 ~/.pypirc
```

## Troubleshooting Common Issues

### Package Name Already Taken
- Run the availability checker to find alternatives
- Consider namespacing (e.g., `myorg-pacc`)

### Version Already Exists
- PyPI doesn't allow re-uploading the same version
- Increment version number in pyproject.toml
- Delete local dist/ folder and rebuild

### Missing Metadata
- Ensure all required fields in pyproject.toml are filled
- Validate with: `python -m build --sdist`

### Authentication Errors
- Verify API token is correct
- Ensure token has upload permissions
- Check if using __token__ as username

## Best Practices

1. **Always test on TestPyPI first**
2. **Use semantic versioning** (MAJOR.MINOR.PATCH)
3. **Include comprehensive README** with examples
4. **Add badges** for version, downloads, and build status
5. **Set up automated testing** before each release
6. **Tag releases in Git** matching PyPI versions
7. **Use trusted publishing** with GitHub Actions

## Additional Resources

- [PyPI Publishing Guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/)
- [Semantic Versioning](https://semver.org/)
- [Python Packaging User Guide](https://packaging.python.org/)
- [Trusted Publishing](https://docs.pypi.org/trusted-publishers/)

---
Generated on: 2025-08-14 18:54:45
