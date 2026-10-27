"""Reject malformed settings/metrics and credentials changed during sign-in."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import math
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parent.parent))
import server as service
from security import DatabaseManager, generate_totp_secret, hash_password


class EndpointInputValidationTests(unittest.TestCase):
    def handler(self, body):
        handler = object.__new__(service.MarketScopeHandler)
        handler.db = MagicMock()
        handler.db.get_latest_config.return_value = None
        handler.db.save_config.return_value = 7
        handler._get_current_session = MagicMock(return_value={
            "role": "owner", "email": "owner@example.test", "csrf_token": "test-only-token",
        })
        handler.headers = {"X-CSRF-Token": "test-only-token"}
        handler._parse_json_body = MagicMock(return_value=body)
        handler._send_json = MagicMock()
        return handler

    def test_invalid_configuration_numbers_never_persist(self):
        for body in (
            {"weight_trend": "NaN"}, {"min_rr_hurdle": "NaN"},
            {"fast_ema_period": math.inf}, {"weight_vwap": "Infinity"},
            {"slow_ema_period": "1e1000"}, {"fast_ema_period": True},
            {"fast_ema_period": 9.5}, {"rsi_period": None},
            {"norm_trend": 0}, {"norm_momentum": -1},
            {"norm_vwap": "0"}, {"norm_rsi": 0},
        ):
            with self.subTest(body=body):
                handler = self.handler(body)
                handler._handle_config_update()
                self.assertEqual(handler._send_json.call_args.kwargs["status"], 400)
                handler.db.save_config.assert_not_called()

    def test_valid_numeric_strings_are_persisted_as_numbers(self):
        handler = self.handler({"fast_ema_period": "9", "weight_trend": "35.0"})
        handler._handle_config_update()
        saved = handler.db.save_config.call_args.args[0]
        self.assertEqual(saved["fast_ema_period"], 9)
        self.assertIsInstance(saved["fast_ema_period"], int)
        self.assertIsInstance(saved["weight_trend"], float)

    def test_unsupported_market_interval_returns_before_archive_or_feed(self):
        handler = self.handler({})
        with patch.object(service, "get_session_state", side_effect=AssertionError("Unexpected state access")):
            for interval in ("0", "-5", "2", "999999"):
                handler._handle_market({"timeframe": [interval]})
                self.assertEqual(handler._send_json.call_args.kwargs["status"], 400)

    def test_bad_metric_types_receive_errors_instead_of_closed_connections(self):
        for field in ("render_ms", "feed_latency_ms"):
            for value in ("broken", None, {}, [], True, -1, math.inf, math.nan):
                with self.subTest(field=field, value=value):
                    handler = self.handler({field: value})
                    handler._handle_metrics()
                    self.assertEqual(handler._send_json.call_args.kwargs["status"], 400)
                    handler.db.record_metric.assert_not_called()

    def test_valid_metrics_are_clamped_to_bounded_durations(self):
        handler = self.handler({"render_ms": "12.5", "feed_latency_ms": 999999})
        handler._handle_metrics()
        handler.db.record_metric.assert_called_once_with(12.5, 60000, None)


class CredentialStateRaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = DatabaseManager(str(Path(self.tmp.name) / "auth.db"))
        self.secret = generate_totp_secret()
        self.user_id = self.db.create_user("owner@example.test", "test-only-password", role="owner", totp_secret=self.secret)
        with self.db.get_connection() as connection:
            row = connection.execute("SELECT password_hash,totp_secret FROM users WHERE id=?", (self.user_id,)).fetchone()
            self.verified_credentials = dict(row)

    def tearDown(self):
        self.tmp.cleanup()

    def test_replaced_authenticator_cannot_issue_session_from_old_verification(self):
        with self.db.get_connection() as connection:
            connection.execute("UPDATE users SET totp_secret=?,totp_last_step=0 WHERE id=?", (generate_totp_secret(), self.user_id))
        issued = self.db.create_authenticated_session(self.user_id, 100, expected_credentials=self.verified_credentials)
        self.assertIsNone(issued)
        with self.db.get_connection() as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM sessions").fetchone()[0], 0)

    def test_changed_password_cannot_issue_session_from_old_verification(self):
        with self.db.get_connection() as connection:
            connection.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password("new-test-only-password"), self.user_id))
        self.assertIsNone(self.db.create_authenticated_session(self.user_id, 100, expected_credentials=self.verified_credentials))


if __name__ == "__main__":
    unittest.main()
