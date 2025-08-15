#!/bin/bash
# Test installation script for pacc

set -e  # Exit on error

echo "🧪 Testing PyPI installation for pacc"
echo "============================================="

# Create temporary directory
TEMP_DIR=$(mktemp -d)
cd $TEMP_DIR

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv test_env
source test_env/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Test installation from TestPyPI
echo "🔍 Testing installation from TestPyPI..."
if pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ pacc; then
    echo "✅ TestPyPI installation successful"
    
    # Test basic functionality
    echo "🏃 Testing basic functionality..."
    pacc --version
    pacc --help
    
    # Run basic import test
    echo "🐍 Testing Python import..."
    python -c "import pacc; print('✅ Import successful')"
    
else
    echo "❌ TestPyPI installation failed"
fi

# Test installation from PyPI (if available)
echo ""
echo "🔍 Testing installation from PyPI..."
pip uninstall -y pacc || true
if pip install pacc; then
    echo "✅ PyPI installation successful"
    pacc --version
else
    echo "ℹ️  Package not yet available on PyPI"
fi

# Cleanup
deactivate
cd -
rm -rf $TEMP_DIR

echo ""
echo "🎉 Testing complete!"
