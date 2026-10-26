"""
Zien Quant Environment Variable Loader
Standard library only.
Reads .env configuration files without requiring external packages like python-dotenv.
Preserves existing environment variables (never overwrites).
"""

from __future__ import annotations
import os
import re
from pathlib import Path
from typing import Dict, Optional


def load_dotenv(dotenv_path: Optional[str | Path] = None) -> Dict[str, str]:
    """
    Loads environment variables from a .env file into os.environ.
    Existing environment variables are NOT overwritten.
    
    Returns a dictionary of newly set key-value pairs.
    """
    if dotenv_path is None:
        # Search root directory or current directory
        current_dir = Path(__file__).resolve().parent
        potential_paths = [
            current_dir.parent / ".env",
            current_dir / ".env",
            Path.cwd() / ".env",
        ]
        target_path = None
        for p in potential_paths:
            if p.is_file():
                target_path = p
                break
        if target_path is None:
            return {}
    else:
        target_path = Path(dotenv_path)
        if not target_path.is_file():
            return {}

    loaded: Dict[str, str] = {}

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if "=" not in line:
                    continue

                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip()

                if not key:
                    continue

                # Strip comments if not enclosed in quotes
                if val.startswith('"') and val.endswith('"') and len(val) >= 2:
                    val = val[1:-1].replace('\\"', '"').replace('\\n', '\n')
                elif val.startswith("'") and val.endswith("'") and len(val) >= 2:
                    val = val[1:-1].replace("\\'", "'")
                else:
                    # Remove trailing inline comment if present
                    if " #" in val:
                        val = val.split(" #", 1)[0].strip()

                # Do NOT overwrite existing environment variables
                if key not in os.environ:
                    os.environ[key] = val
                    loaded[key] = val
    except Exception:
        pass

    return loaded
