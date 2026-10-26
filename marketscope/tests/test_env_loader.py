"""
Unit tests for Zien Quant Environment Variable Loader
Verifies stdlib .env parsing, comment stripping, quote handling, and non-overwrite guarantee.
"""

import os
import tempfile
import unittest
from pathlib import Path

from marketscope.env_loader import load_dotenv


class TestEnvLoader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_file = Path(self.temp_dir.name) / ".env"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_basic_key_value(self):
        self.env_file.write_text("TEST_MS_KEY1=val1\nTEST_MS_KEY2=val2\n", encoding="utf-8")
        if "TEST_MS_KEY1" in os.environ:
            del os.environ["TEST_MS_KEY1"]
        if "TEST_MS_KEY2" in os.environ:
            del os.environ["TEST_MS_KEY2"]

        loaded = load_dotenv(self.env_file)
        self.assertEqual(loaded.get("TEST_MS_KEY1"), "val1")
        self.assertEqual(loaded.get("TEST_MS_KEY2"), "val2")
        self.assertEqual(os.environ.get("TEST_MS_KEY1"), "val1")
        self.assertEqual(os.environ.get("TEST_MS_KEY2"), "val2")

        # Cleanup
        del os.environ["TEST_MS_KEY1"]
        del os.environ["TEST_MS_KEY2"]

    def test_comments_and_blank_lines(self):
        content = """
        # Full line comment
        TEST_COMMENT_KEY=alpha # inline comment

        # Another comment
        TEST_EMPTY_VAL=
        """
        self.env_file.write_text(content, encoding="utf-8")
        if "TEST_COMMENT_KEY" in os.environ:
            del os.environ["TEST_COMMENT_KEY"]
        if "TEST_EMPTY_VAL" in os.environ:
            del os.environ["TEST_EMPTY_VAL"]

        loaded = load_dotenv(self.env_file)
        self.assertEqual(loaded.get("TEST_COMMENT_KEY"), "alpha")
        self.assertEqual(os.environ.get("TEST_COMMENT_KEY"), "alpha")
        self.assertEqual(loaded.get("TEST_EMPTY_VAL"), "")

        # Cleanup
        del os.environ["TEST_COMMENT_KEY"]
        del os.environ["TEST_EMPTY_VAL"]

    def test_quotes_handling(self):
        content = """
        TEST_DOUBLE_QUOTES="hello world"
        TEST_SINGLE_QUOTES='hello universe'
        TEST_QUOTED_HASH="value with # hash symbol"
        """
        self.env_file.write_text(content, encoding="utf-8")
        keys = ["TEST_DOUBLE_QUOTES", "TEST_SINGLE_QUOTES", "TEST_QUOTED_HASH"]
        for k in keys:
            if k in os.environ:
                del os.environ[k]

        loaded = load_dotenv(self.env_file)
        self.assertEqual(loaded.get("TEST_DOUBLE_QUOTES"), "hello world")
        self.assertEqual(loaded.get("TEST_SINGLE_QUOTES"), "hello universe")
        self.assertEqual(loaded.get("TEST_QUOTED_HASH"), "value with # hash symbol")

        for k in keys:
            del os.environ[k]

    def test_never_overwrites_existing_env(self):
        os.environ["TEST_PREEXISTING_KEY"] = "original_value"
        self.env_file.write_text("TEST_PREEXISTING_KEY=new_ignored_value\n", encoding="utf-8")

        loaded = load_dotenv(self.env_file)
        self.assertNotIn("TEST_PREEXISTING_KEY", loaded)
        self.assertEqual(os.environ["TEST_PREEXISTING_KEY"], "original_value")

        del os.environ["TEST_PREEXISTING_KEY"]

    def test_missing_file_handled_gracefully(self):
        missing = Path(self.temp_dir.name) / "does_not_exist.env"
        loaded = load_dotenv(missing)
        self.assertEqual(loaded, {})


if __name__ == "__main__":
    unittest.main()
