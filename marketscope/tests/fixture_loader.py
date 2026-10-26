"""
MarketScope Test Fixture Loader
Loads static JSON fixtures under tests/fixtures/ for unit testing.
Labeled: TEST FIXTURE.
Nothing under tests/ may be imported by runtime code.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "session_fixtures.json"


def load_test_fixtures() -> Dict[str, Any]:
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_fixture_stock_candles(symbol: str) -> List[Dict[str, Any]]:
    fixtures = load_test_fixtures()
    stock_data = fixtures.get("stocks", {}).get(symbol.upper())
    if not stock_data:
        raise KeyError(f"Symbol {symbol} not found in TEST FIXTURE")
    return stock_data["candles"]
