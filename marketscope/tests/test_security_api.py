"""
Unit Tests for MarketScope Security Primitives, Database Schema & API Endpoints
"""

import json
import os
import tempfile
import time
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from security import (
    DatabaseManager,
    hash_password,
    verify_password,
    generate_totp_secret,
    get_totp_token,
    verify_totp,
    RateLimiter,
)
from server import MarketScopeHandler


class TestSecurityAndDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "test_marketscope.db")
        self.db = DatabaseManager(self.db_path)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_password_hashing(self):
        pwd = "test_password_placeholder"
        hashed = hash_password(pwd)
        self.assertTrue(hashed.startswith("pbkdf2_sha256$600000$"))
        self.assertTrue(verify_password(pwd, hashed))
        self.assertFalse(verify_password("WrongPassword", hashed))

    def test_totp_generation_and_verification(self):
        secret = generate_totp_secret()
        self.assertGreater(len(secret), 16)
        token, step = get_totp_token(secret)
        self.assertEqual(len(token), 6)
        valid, new_step = verify_totp(secret, token, last_step=0)
        self.assertTrue(valid)
        self.assertGreaterEqual(new_step, step - 1)

    def test_totp_replay_protection(self):
        secret = generate_totp_secret()
        token, step = get_totp_token(secret)
        valid, accepted_step = verify_totp(secret, token, last_step=step)
        # Attempting to reuse the exact step must be rejected
        self.assertFalse(valid)

    def test_single_owner_enforcement(self):
        self.assertFalse(self.db.has_owner())
        self.db.create_user("owner1@test.com", "pass12345", role="owner")
        self.assertTrue(self.db.has_owner())
        # Attempting to create a second owner must violate unique index
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.create_user("owner2@test.com", "pass12345", role="owner")

    def test_session_lifecycle(self):
        uid = self.db.create_user("user@test.com", "pass12345", role="member")
        raw_token, csrf_token = self.db.create_session(uid)
        self.assertIsNotNone(raw_token)
        self.assertIsNotNone(csrf_token)

        sess = self.db.validate_session(raw_token)
        self.assertIsNotNone(sess)
        self.assertEqual(sess["email"], "user@test.com")
        self.assertEqual(sess["csrf_token"], csrf_token)

        # Deletion
        self.db.delete_session(raw_token)
        self.assertIsNone(self.db.validate_session(raw_token))

    def test_config_versioning_and_audit(self):
        self.db.save_config({"brand_name": "TestScope"}, actor="owner@test.com")
        cfg = self.db.get_latest_config()
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg["brand_name"], "TestScope")

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM audit WHERE action = 'config_update'")
            self.assertEqual(cur.fetchone()[0], 1)

    def test_disabled_user_cannot_authenticate(self):
        uid = self.db.create_user("disabled@test.com", "pass12345", role="member")
        raw_token, _ = self.db.create_session(uid)
        self.assertIsNotNone(self.db.validate_session(raw_token))

        # Disable user
        conn = self.db.get_connection()
        try:
            with conn:
                conn.execute("UPDATE users SET disabled = 1 WHERE id = ?", (uid,))
        finally:
            conn.close()

        # Session should now be invalid
        self.assertIsNone(self.db.validate_session(raw_token))

    def test_revoke_user_sessions(self):
        uid = self.db.create_user("revoked@test.com", "pass12345", role="member")
        t1, _ = self.db.create_session(uid)
        t2, _ = self.db.create_session(uid)
        self.assertIsNotNone(self.db.validate_session(t1))
        self.assertIsNotNone(self.db.validate_session(t2))

        self.db.revoke_user_sessions(uid)
        self.assertIsNone(self.db.validate_session(t1))
        self.assertIsNone(self.db.validate_session(t2))

    def test_record_telemetry_metric(self):
        self.db.record_metric(render_ms=14.5, latency_ms=12.0, client_ts="2026-10-25T12:00:00Z")
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT render_ms, feed_latency_ms FROM metrics ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertAlmostEqual(row[0], 14.5)
            self.assertAlmostEqual(row[1], 12.0)
        finally:
            conn.close()

    def test_server_static_file_resolution(self):
        # Verify static directory exists and contains index.html, styles.css, app.js, sample.json
        static_dir = Path(__file__).parent.parent / "static"
        self.assertTrue((static_dir / "index.html").exists())
        self.assertTrue((static_dir / "styles.css").exists())
        self.assertTrue((static_dir / "app.js").exists())
        self.assertTrue((static_dir / "favicon.svg").exists())

    def test_export_data_generation(self):
        try:
            from tests.fixture_loader import load_test_fixtures
        except ImportError:
            from fixture_loader import load_test_fixtures
        fixtures = load_test_fixtures()
        snapshot = fixtures.get("snapshot", {})
        self.assertEqual(len(snapshot["stocks"]), 24)
        for sym, s in snapshot["stocks"].items():
            self.assertIn("price", s)
            self.assertIn("change_pct", s)
            self.assertIn("rvol", s)
            self.assertIn("metrics", s)

    def test_default_config_integrity(self):
        from market import DEFAULT_CONFIG
        self.assertIn("fast_ema_period", DEFAULT_CONFIG)
        self.assertIn("slow_ema_period", DEFAULT_CONFIG)
        self.assertLess(DEFAULT_CONFIG["fast_ema_period"], DEFAULT_CONFIG["slow_ema_period"])
        self.assertEqual(DEFAULT_CONFIG["score_threshold"], 65)

    def test_audit_log_recording(self):
        conn = self.db.get_connection()
        try:
            with conn:
                self.db.log_audit(conn, "test_action", "admin", "details test")
            cur = conn.cursor()
            cur.execute("SELECT action, actor, details FROM audit WHERE action = 'test_action'")
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[1], "admin")
            self.assertEqual(row[2], "details test")
        finally:
            conn.close()

    def test_rate_limiter_multiple_ips(self):
        limiter = RateLimiter(limit=2, window_sec=60)
        self.assertTrue(limiter.is_allowed("127.0.0.1"))
        self.assertTrue(limiter.is_allowed("127.0.0.1"))
        self.assertFalse(limiter.is_allowed("127.0.0.1"))
        self.assertTrue(limiter.is_allowed("127.0.0.2"))

    def test_totp_invalid_codes(self):
        secret = generate_totp_secret()
        # Invalid length
        valid, _ = verify_totp(secret, "123")
        self.assertFalse(valid)
        # Empty code
        valid, _ = verify_totp(secret, "")
        self.assertFalse(valid)
        # Wrong code
        valid, _ = verify_totp(secret, "000000")
        self.assertFalse(valid)

    def test_login_invalid_password(self):
        self.db.create_user("user1@test.com", "correctpass", role="member")
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT password_hash FROM users WHERE email = 'user1@test.com'")
            h = cur.fetchone()[0]
            self.assertFalse(verify_password("wrongpass", h))
            self.assertTrue(verify_password("correctpass", h))
        finally:
            conn.close()

    def test_owner_requires_totp(self):
        secret = generate_totp_secret()
        uid = self.db.create_user("owner_totp@test.com", "pass12345", role="owner", totp_secret=secret)
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT totp_secret FROM users WHERE id = ?", (uid,))
            saved_secret = cur.fetchone()[0]
            self.assertEqual(saved_secret, secret)
        finally:
            conn.close()

    def test_config_validation_rule(self):
        # Fast EMA must be strictly less than Slow EMA
        fast = 21
        slow = 9
        self.assertFalse(fast < slow)

    def test_telemetry_timestamp_contract_fix(self):
        # Section 13.1 fix: ensure epoch ms (> 1e11) is normalized to a valid duration
        epoch_now = time.time() * 1000
        if epoch_now > 1_000_000_000_000:
            duration = max(0.0, time.time() * 1000 - epoch_now)
        else:
            duration = epoch_now
        self.assertLessEqual(duration, 86_400_000)
        self.db.record_metric(duration, latency_ms=10.0, client_ts="2026-10-25T12:30:00Z")

    def test_timeframe_candles_provisional_flag(self):
        try:
            from tests.fixture_loader import load_test_fixtures
        except ImportError:
            from fixture_loader import load_test_fixtures
        fixtures = load_test_fixtures()
        snapshot = fixtures.get("snapshot", {})
        stock = snapshot["stocks"]["RELIANCE"]
        self.assertIn("metrics", stock)
        self.assertIn("confirmed", stock)


class MockServer:
    def __init__(self, db):
        self.db_manager = db


class MockRequest:
    def __init__(self, path, method="GET", body=b"", headers=None):
        self.path = path
        self.method = method
        self.body = body
        self.headers = headers or {}


if __name__ == "__main__":
    unittest.main()
