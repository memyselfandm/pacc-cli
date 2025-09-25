# Credential Management Guide

Secure credential management is critical for publishing packages to PyPI. This guide covers best practices for managing PyPI tokens and credentials.

## Table of Contents

1. [Storing API Tokens](#storing-api-tokens)
2. [Environment Variables](#environment-variables)
3. [.pypirc Configuration](#pypirc-configuration)
4. [CI/CD Secrets](#cicd-secrets)
5. [Token Rotation](#token-rotation)

## Storing API Tokens

### Password Manager (Recommended)

Store PyPI tokens in a password manager for maximum security:

1. **Choose a Password Manager**
   - 1Password, Bitwarden, LastPass, KeePass
   - Use one with secure notes feature
   - Enable 2FA on password manager

2. **Store Token Information**
   ```
   Title: PyPI Publishing Token - PACC
   Username: __token__
   Password: pypi-AgEIcHlwaS5vcmcCJGNhNjE5...
   URL: https://pypi.org/manage/account/token/
   Notes: Created [date], Scope: pacc project
   ```

3. **Backup Considerations**
   - Export encrypted backup
   - Store backup in separate secure location
   - Test recovery process

### Secure File Storage

If not using a password manager:

```bash
# Create secure directory
mkdir -p ~/.secrets
chmod 700 ~/.secrets

# Store token
echo "pypi-AgEIcHlwaS5vcmcCJGNhNjE5..." > ~/.secrets/pypi-token
chmod 600 ~/.secrets/pypi-token

# Add to shell profile for easy access
echo 'export PYPI_TOKEN=$(cat ~/.secrets/pypi-token)' >> ~/.bashrc
```

### macOS Keychain

For macOS users:

```bash
# Store in keychain
security add-generic-password \
  -a "$USER" \
  -s "PyPI-PACC-Token" \
  -w "pypi-AgEIcHlwaS5vcmcCJGNhNjE5..."

# Retrieve from keychain
security find-generic-password \
  -a "$USER" \
  -s "PyPI-PACC-Token" \
  -w
```

### Linux Secret Service

For Linux users with secret-tool:

```bash
# Store token
echo -n "pypi-AgEIcHlwaS5vcmcCJGNhNjE5..." | \
  secret-tool store --label="PyPI PACC Token" \
  service pypi username __token__

# Retrieve token
secret-tool lookup service pypi username __token__
```

## Environment Variables

### Basic Setup

Configure environment variables for twine:

```bash
# ~/.bashrc or ~/.zshrc
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-AgEIcHlwaS5vcmcCJGNhNjE5...

# For Test PyPI
export TWINE_REPOSITORY_URL=https://test.pypi.org/legacy/
export TWINE_USERNAME_TESTPYPI=__token__
export TWINE_PASSWORD_TESTPYPI=pypi-AgEIcHlwaS5vcmcCJGNhNjE5...
```

### Using envrc (direnv)

For project-specific credentials:

```bash
# Install direnv
brew install direnv  # macOS
apt install direnv   # Ubuntu

# Create .envrc in project
cat > .envrc << 'EOF'
# Load PyPI credentials
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=$(security find-generic-password -a "$USER" -s "PyPI-PACC-Token" -w)

# Test PyPI
export TWINE_USERNAME_TESTPYPI=__token__
export TWINE_PASSWORD_TESTPYPI=$(security find-generic-password -a "$USER" -s "TestPyPI-PACC-Token" -w)
EOF

# Allow direnv
direnv allow

# Add .envrc to .gitignore
echo ".envrc" >> .gitignore
```

### Temporary Environment Variables

For one-time use:

```bash
# Single command
TWINE_PASSWORD="pypi-AgEI..." twine upload dist/*

# Session-only
export TWINE_PASSWORD="pypi-AgEI..."
# ... do work ...
unset TWINE_PASSWORD
```

## .pypirc Configuration

### Basic Configuration

Create `~/.pypirc`:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi-AgEIcHlwaS5vcmcCJGNhNjE5...

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-AgEIcHlwaS5vcmcCJGNhNjE5...
```

### Secure .pypirc

```bash
# Set restrictive permissions
chmod 600 ~/.pypirc

# Verify permissions
ls -la ~/.pypirc
# Should show: -rw-------

# Add to global gitignore
echo ".pypirc" >> ~/.gitignore_global
git config --global core.excludesfile ~/.gitignore_global
```

### Using Keyring with .pypirc

For enhanced security, use keyring instead of plaintext:

```bash
# Install keyring
pip install keyring

# Store password in keyring
python -c "import keyring; keyring.set_password('pypi', '__token__', 'pypi-AgEI...')"

# .pypirc without password
cat > ~/.pypirc << 'EOF'
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
EOF
```

## CI/CD Secrets

### GitHub Actions

1. **Add Repository Secret**
   - Go to Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `PYPI_API_TOKEN`
   - Value: `pypi-AgEIcHlwaS5vcmcCJGNhNjE5...`

2. **Use in Workflow**
   ```yaml
   name: Publish Package

   on:
     release:
       types: [published]

   jobs:
     publish:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v3

         - name: Set up Python
           uses: actions/setup-python@v4
           with:
             python-version: '3.10'

         - name: Build package
           run: |
             pip install build
             python -m build

         - name: Publish to PyPI
           env:
             TWINE_USERNAME: __token__
             TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
           run: |
             pip install twine
             twine upload dist/*
   ```

### GitLab CI

1. **Add CI/CD Variable**
   - Settings → CI/CD → Variables
   - Add variable:
     - Key: `PYPI_API_TOKEN`
     - Value: `pypi-AgEIcHlwaS5vcmcCJGNhNjE5...`
     - Type: Variable
     - Protected: Yes
     - Masked: Yes

2. **Use in Pipeline**
   ```yaml
   publish:
     stage: deploy
     only:
       - tags
     script:
       - pip install build twine
       - python -m build
       - TWINE_USERNAME=__token__ TWINE_PASSWORD=$PYPI_API_TOKEN twine upload dist/*
   ```

### CircleCI

1. **Add Environment Variable**
   - Project Settings → Environment Variables
   - Add: `PYPI_API_TOKEN`

2. **Use in Config**
   ```yaml
   version: 2.1

   jobs:
     publish:
       docker:
         - image: python:3.10
       steps:
         - checkout
         - run:
             name: Build and publish
             command: |
               pip install build twine
               python -m build
               TWINE_USERNAME=__token__ \
               TWINE_PASSWORD=$PYPI_API_TOKEN \
               twine upload dist/*
   ```

### Jenkins

1. **Add Credentials**
   - Manage Jenkins → Manage Credentials
   - Add Credentials → Secret text
   - ID: `pypi-api-token`
   - Secret: `pypi-AgEIcHlwaS5vcmcCJGNhNjE5...`

2. **Use in Pipeline**
   ```groovy
   pipeline {
     agent any

     environment {
       PYPI_TOKEN = credentials('pypi-api-token')
     }

     stages {
       stage('Publish') {
         steps {
           sh '''
             pip install build twine
             python -m build
             TWINE_USERNAME=__token__ \
             TWINE_PASSWORD=$PYPI_TOKEN \
             twine upload dist/*
           '''
         }
       }
     }
   }
   ```

## Token Rotation

### Rotation Schedule

Implement regular token rotation:

1. **Quarterly Rotation** (Recommended)
   - Set calendar reminder
   - Rotate all tokens every 3 months
   - Document rotation in security log

2. **Event-Based Rotation**
   - After team member leaves
   - After security incident
   - After major release
   - If token may be compromised

### Rotation Process

1. **Create New Token**
   ```bash
   # Log in to PyPI
   # Account settings → API tokens
   # Create new token with same scope
   ```

2. **Test New Token**
   ```bash
   # Test with Test PyPI first
   TWINE_USERNAME=__token__ \
   TWINE_PASSWORD="new-token" \
   twine upload --repository testpypi dist/*
   ```

3. **Update All Locations**
   - [ ] Password manager
   - [ ] Local .pypirc
   - [ ] Environment variables
   - [ ] CI/CD secrets
   - [ ] Team documentation
   - [ ] Backup locations

4. **Verify Updates**
   ```bash
   # Test each system
   make publish-test  # Local
   # Trigger CI/CD test job
   # Verify team access
   ```

5. **Revoke Old Token**
   - Wait 24-48 hours
   - Monitor for issues
   - Revoke old token on PyPI
   - Document in security log

### Security Log Template

Maintain a security log:

```markdown
# PyPI Token Rotation Log

## 2024-01-15 - Quarterly Rotation
- Old token: Last 4 chars: ...a4b2
- New token: Last 4 chars: ...c8d1
- Updated: .pypirc, GitHub Actions, 1Password
- Verified: All systems functional
- Revoked old: 2024-01-17

## 2023-10-15 - Quarterly Rotation
- Old token: Last 4 chars: ...e5f3
- New token: Last 4 chars: ...a4b2
- Updated: All locations
- Issue: CI/CD needed manual trigger
- Resolved: Updated workflow permissions
```

### Emergency Rotation

If token is compromised:

1. **Immediate Actions**
   ```bash
   # Revoke compromised token IMMEDIATELY
   # Via PyPI web interface

   # Create new token
   # Update critical systems first
   ```

2. **Investigate**
   - Check PyPI upload history
   - Review access logs
   - Identify exposure source

3. **Communicate**
   - Notify team
   - Update security advisory if needed
   - Document incident

### Automation Tools

Consider automation for token management:

1. **HashiCorp Vault**
   ```bash
   # Store token
   vault kv put secret/pypi token="pypi-AgEI..."

   # Retrieve in CI/CD
   export TWINE_PASSWORD=$(vault kv get -field=token secret/pypi)
   ```

2. **AWS Secrets Manager**
   ```bash
   # Store token
   aws secretsmanager create-secret \
     --name pypi-token \
     --secret-string "pypi-AgEI..."

   # Retrieve
   TWINE_PASSWORD=$(aws secretsmanager get-secret-value \
     --secret-id pypi-token \
     --query SecretString --output text)
   ```

3. **Rotation Scripts**
   ```python
   # scripts/rotate_token.py
   #!/usr/bin/env python3
   """Automated token rotation helper."""

   import os
   import sys
   from datetime import datetime

   def rotate_token():
       # 1. Prompt for new token
       # 2. Test token
       # 3. Update all locations
       # 4. Verify
       # 5. Log rotation
       pass
   ```

## Best Practices Summary

1. **Never commit tokens** to version control
2. **Use unique tokens** for each environment
3. **Rotate regularly** - at least quarterly
4. **Monitor usage** - check PyPI logs
5. **Secure storage** - encrypted at rest
6. **Limit scope** - project-specific when possible
7. **Document process** - for team continuity
8. **Test recovery** - ensure you can rotate quickly
9. **Use 2FA** - on all accounts
10. **Audit regularly** - review all token locations
