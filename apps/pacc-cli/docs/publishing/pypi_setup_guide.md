# PyPI Account Setup Guide

This guide walks you through setting up PyPI and Test PyPI accounts for publishing PACC packages.

## Table of Contents

1. [Creating a PyPI Account](#creating-a-pypi-account)
2. [Creating a Test PyPI Account](#creating-a-test-pypi-account)
3. [API Token Configuration](#api-token-configuration)
4. [Security Best Practices](#security-best-practices)
5. [Troubleshooting](#troubleshooting)

## Creating a PyPI Account

PyPI (Python Package Index) is the official repository for Python packages. To publish PACC, you'll need an account.

### Steps to Create a PyPI Account

1. **Visit PyPI Registration Page**
   - Navigate to https://pypi.org/account/register/
   - Choose a strong username that represents you or your organization

2. **Fill in Registration Details**
   - **Username**: Choose wisely - this cannot be changed later
   - **Email**: Use a secure email address you have access to
   - **Password**: Use a strong, unique password (consider using a password manager)

3. **Verify Your Email**
   - Check your email for a verification link
   - Click the link to activate your account

4. **Enable Two-Factor Authentication (2FA)**
   - Go to Account Settings → Security
   - Add 2FA using an authenticator app (recommended) or SMS
   - Save backup codes in a secure location

5. **Complete Your Profile**
   - Add a profile description
   - Set up a recovery email (optional but recommended)

## Creating a Test PyPI Account

Test PyPI is a separate instance for testing package uploads without affecting the production index.

### Steps to Create a Test PyPI Account

1. **Visit Test PyPI Registration**
   - Navigate to https://test.pypi.org/account/register/
   - Note: Test PyPI accounts are separate from production PyPI

2. **Register with Same Username**
   - Use the same username as your PyPI account for consistency
   - Email and password can be different

3. **Follow Same Security Steps**
   - Enable 2FA
   - Verify email
   - Complete profile

### Important Test PyPI Notes

- Test PyPI is periodically cleaned - packages may be deleted
- Dependencies might not be available on Test PyPI
- Use `--index-url https://test.pypi.org/simple/` when installing from Test PyPI

## API Token Configuration

API tokens are the recommended way to authenticate when uploading packages.

### Creating API Tokens

#### For PyPI:

1. **Navigate to Account Settings**
   - Log in to https://pypi.org
   - Go to Account Settings → API tokens

2. **Create New Token**
   - Click "Add API token"
   - **Token name**: `pacc-publish` (or descriptive name)
   - **Scope**: Choose "Entire account" for first upload, then scope to project

3. **Save Token Securely**
   - Copy the token immediately (shown only once)
   - Store in password manager
   - Format: `pypi-AgEIcHlwaS5vcmcCJGNhNjE5...`

#### For Test PyPI:

1. **Same Process on Test PyPI**
   - Log in to https://test.pypi.org
   - Account Settings → API tokens
   - Create token with name like `pacc-test-publish`

### Configuring .pypirc File

Create `~/.pypirc` with proper permissions:

```bash
touch ~/.pypirc
chmod 600 ~/.pypirc
```

Add the following content:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi-AgEIcHlwaS5vcmcCJGNhNjE5... # Your PyPI token

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-AgEIcHlwaS5vcmcCJGNhNjE5... # Your Test PyPI token
```

### Environment Variable Alternative

Instead of storing tokens in `.pypirc`, use environment variables:

```bash
# In ~/.bashrc or ~/.zshrc
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-AgEIcHlwaS5vcmcCJGNhNjE5...

# For Test PyPI
export TWINE_TEST_USERNAME=__token__
export TWINE_TEST_PASSWORD=pypi-AgEIcHlwaS5vcmcCJGNhNjE5...
```

## Security Best Practices

### Token Management

1. **Never Commit Tokens**
   - Add `.pypirc` to global gitignore
   - Never hardcode tokens in scripts
   - Use environment variables in CI/CD

2. **Scope Tokens Appropriately**
   - After first upload, create project-scoped token
   - Use different tokens for different projects
   - Rotate tokens regularly

3. **Secure Storage**
   - Use password manager for tokens
   - Encrypt `.pypirc` if possible
   - Set restrictive file permissions (600)

### Account Security

1. **Strong Authentication**
   - Use unique, strong password
   - Enable 2FA on both PyPI and Test PyPI
   - Use hardware keys if available

2. **Email Security**
   - Use secure email provider
   - Enable 2FA on email account
   - Monitor for suspicious activity

3. **Access Control**
   - Regularly review API tokens
   - Delete unused tokens
   - Monitor account activity

### CI/CD Security

1. **GitHub Actions**
   ```yaml
   - name: Publish to PyPI
     env:
       TWINE_USERNAME: __token__
       TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
   ```

2. **GitLab CI**
   ```yaml
   publish:
     variables:
       TWINE_USERNAME: __token__
       TWINE_PASSWORD: $PYPI_API_TOKEN
   ```

3. **Best Practices**
   - Use repository secrets
   - Limit secret access to protected branches
   - Rotate CI/CD tokens regularly

## Troubleshooting

### Common Issues and Solutions

#### Authentication Failures

**Problem**: "403 Forbidden" or "Invalid credentials"

**Solutions**:
- Verify token starts with `pypi-`
- Check username is exactly `__token__`
- Ensure no extra whitespace in token
- Verify using correct index (PyPI vs Test PyPI)

#### Missing 2FA

**Problem**: "Two factor authentication required"

**Solution**:
- Enable 2FA on your account
- Use API tokens instead of password
- Ensure token has correct permissions

#### Package Name Conflicts

**Problem**: "Package name already exists"

**Solutions**:
- Check if name is taken: `pip search <package-name>`
- Consider namespacing: `myorg-pacc`
- For Test PyPI, name might be temporarily taken

#### Upload Errors

**Problem**: "HTTPError: 400 Bad Request"

**Common Causes**:
- Invalid package metadata
- Missing required files
- Malformed distribution

**Debug Steps**:
1. Validate with twine: `twine check dist/*`
2. Check package structure: `tar -tzf dist/*.tar.gz`
3. Verify metadata: `python setup.py check`

### Getting Help

1. **Official Resources**
   - PyPI Help: https://pypi.org/help/
   - Packaging Guide: https://packaging.python.org/
   - Twine Documentation: https://twine.readthedocs.io/

2. **Community Support**
   - Python Packaging Discourse: https://discuss.python.org/c/packaging/
   - Stack Overflow: [python-packaging] tag
   - PyPA GitHub Issues

3. **PACC-Specific Help**
   - GitHub Issues: https://github.com/anthropics/pacc/issues
   - Documentation: See main README
   - Contact maintainers for project-specific issues

## Next Steps

After setting up your accounts and tokens:

1. Review the [Publishing Workflow](publishing_workflow.md)
2. Test with Test PyPI first
3. Set up CI/CD automation
4. Document your process for team members

Remember: Security is paramount when publishing packages. Take time to properly secure your accounts and tokens.
