#!/usr/bin/env python3
"""
Zien Quant Root CLI Management Utility Forwarder
Delegates directly to marketscope.manage.
Usage from repo root:
    python manage.py doctor
    python manage.py init-owner
    python manage.py status
    python manage.py backup
    python manage.py import-stock-master
"""

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent
marketscope_dir = root_dir / "marketscope"

if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
if str(marketscope_dir) not in sys.path:
    sys.path.insert(0, str(marketscope_dir))

import marketscope.manage as ms_manage

if __name__ == "__main__":
    ms_manage.main()
