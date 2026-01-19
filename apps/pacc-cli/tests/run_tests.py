"""Simple test runner for PACC."""

import sys
import unittest
from pathlib import Path

# Add the pacc module to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))


def run_tests():
    """Run all tests."""
    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = Path(__file__).parent
    suite = loader.discover(start_dir, pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
