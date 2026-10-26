"""
Root test suite forwarder for Zien Quant.
Discovers all tests in marketscope/tests so that:
    python -m unittest discover -s tests
runs the complete test suite from repository root.
"""

import sys
import unittest
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
ms_dir = root_dir / "marketscope"

if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
if str(ms_dir) not in sys.path:
    sys.path.insert(0, str(ms_dir))


def load_tests(loader, tests, pattern):
    ms_tests_dir = ms_dir / "tests"
    return loader.discover(start_dir=str(ms_tests_dir), pattern=pattern or "test_*.py", top_level_dir=str(root_dir))
