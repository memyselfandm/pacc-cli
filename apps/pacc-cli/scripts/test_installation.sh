#!/bin/bash
# Test PACC installation in various scenarios

set -e

echo "PACC Installation Test Suite"
echo "============================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PACC_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "\nPACC root directory: $PACC_ROOT"

# Function to print colored output
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
        return 1
    fi
}

# Test 1: Direct module execution
echo -e "\n${YELLOW}Test 1: Direct module execution${NC}"
cd "$PACC_ROOT"
python -m pacc --version
print_status $? "Direct module execution works"

# Test 2: Editable installation in virtual environment
echo -e "\n${YELLOW}Test 2: Editable installation${NC}"
TEMP_VENV=$(mktemp -d)
python -m venv "$TEMP_VENV"

# Activate virtual environment
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source "$TEMP_VENV/Scripts/activate"
else
    source "$TEMP_VENV/bin/activate"
fi

pip install -e "$PACC_ROOT"
pacc --version
EDITABLE_STATUS=$?
deactivate

rm -rf "$TEMP_VENV"
print_status $EDITABLE_STATUS "Editable installation works"

# Test 3: Wheel installation
echo -e "\n${YELLOW}Test 3: Wheel installation${NC}"
TEMP_BUILD=$(mktemp -d)
cd "$TEMP_BUILD"

# Build wheel
pip install build
python -m build --wheel "$PACC_ROOT"

# Create new venv for wheel test
TEMP_VENV2=$(mktemp -d)
python -m venv "$TEMP_VENV2"

if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source "$TEMP_VENV2/Scripts/activate"
else
    source "$TEMP_VENV2/bin/activate"
fi

pip install dist/*.whl
pacc --help | grep -q "PACC - Package manager for Claude Code"
WHEEL_STATUS=$?
deactivate

cd ..
rm -rf "$TEMP_BUILD" "$TEMP_VENV2"
print_status $WHEEL_STATUS "Wheel installation works"

# Test 4: Run verification script
echo -e "\n${YELLOW}Test 4: Full functionality verification${NC}"
cd "$PACC_ROOT"
python scripts/verify_installation.py
print_status $? "All functionality checks passed"

# Summary
echo -e "\n${GREEN}Installation tests completed!${NC}"