"""
Unit and Integration Tests for MongoDB Module
Verifies PyMongo configuration, bcrypt hashing, connection diagnostics,
activity logging, and graceful offline handling.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database as db


class TestMongoDB(unittest.TestCase):

    def test_01_connection_diagnostics(self):
        """Verify connection tester returns clean boolean and message without crashing."""
        is_conn, msg = db.test_connection()
        self.assertIsInstance(is_conn, bool)
        self.assertIsInstance(msg, str)
        self.assertGreater(len(msg), 0)

        info = db.get_connection_info()
        self.assertIn("connected", info)
        self.assertIn("message", info)
        self.assertIn("database_name", info)
        self.assertIn("masked_uri", info)

    def test_02_password_hashing_bcrypt(self):
        """Verify password hashing with bcrypt works properly."""
        plain = "MySecretPassword2026!"
        hashed = db.hash_password(plain)
        self.assertTrue(hashed.startswith("$2b$") or hashed.startswith("$2a$"))
        self.assertTrue(db.verify_password(plain, hashed))
        self.assertFalse(db.verify_password("WrongPassword!", hashed))

    def test_03_activity_logging_offline_safe(self):
        """Verify log_activity does not crash if database is disconnected."""
        # Should execute silently without throwing an exception
        db.log_activity("test_user", "tester", "TEST_ACTION", "Testing logging robustness")

    def test_04_user_stats_offline_safe(self):
        """Verify get_user_stats returns clean dictionary structure even if disconnected."""
        stats = db.get_user_stats("nonexistent_user")
        self.assertIn("total_analyses", stats)
        self.assertIn("defective_count", stats)
        self.assertIn("language_distribution", stats)

    def test_05_admin_stats_offline_safe(self):
        """Verify get_admin_stats returns clean dictionary structure even if disconnected."""
        stats = db.get_admin_stats()
        self.assertIn("total_users", stats)
        self.assertIn("total_analyses", stats)
        self.assertIn("recent_analyses", stats)


if __name__ == "__main__":
    unittest.main()
