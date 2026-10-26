"""
Root test forwarder for Zien Quant.
Discovers and loads all test suites from marketscope/tests.
"""

import sys
import unittest
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
ms_dir = root_dir / "marketscope"
ms_tests_dir = ms_dir / "tests"

if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
if str(ms_dir) not in sys.path:
    sys.path.insert(0, str(ms_dir))


def load_tests(loader, standard_tests, pattern):
    package_tests = loader.discover(start_dir=str(ms_tests_dir), pattern="test_*.py", top_level_dir=str(root_dir))
    standard_tests.addTests(package_tests)
    return standard_tests


if __name__ == "__main__":
    unittest.main()
