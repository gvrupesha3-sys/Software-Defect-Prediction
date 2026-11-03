"""
Unit and Integration Tests for Database & Authentication Modules
Verifies database initialization, user registration, bcrypt hashing,
user isolation, and issue tracking.
"""

import os
import sys
import unittest
import tempfile
import sqlite3

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database as db
import authentication as auth


class TestDatabaseAndAuth(unittest.TestCase):

    def setUp(self):
        # Create a temporary database for test isolation
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        db.DB_PATH = self.temp_db_path
        db.init_db()

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass

    def test_01_admin_seeded(self):
        """Verify default admin is initialized upon database setup."""
        admin = db.get_user_by_identifier("admin")
        self.assertIsNotNone(admin)
        self.assertEqual(admin["role"], "admin")
        self.assertTrue(db.verify_password("Admin@Defect2026!", admin["password_hash"]))

    def test_02_user_registration_and_login(self):
        """Test regular user creation, bcrypt hashing, and password verification."""
        success, msg = db.create_user("John Doe", "john@example.com", "johndoe", "Secret1234!")
        self.assertTrue(success)

        # Check retrieval
        user = db.get_user_by_identifier("johndoe")
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "john@example.com")
        self.assertEqual(user["role"], "user")

        # Verify password check
        self.assertTrue(db.verify_password("Secret1234!", user["password_hash"]))
        self.assertFalse(db.verify_password("WrongPassword!", user["password_hash"]))

    def test_03_prevent_duplicate_registration(self):
        """Verify duplicate usernames and emails are blocked."""
        db.create_user("Alice Smith", "alice@example.com", "alice123", "Pass12345!")

        # Duplicate username
        ok1, msg1 = db.create_user("Alice Clone", "other@example.com", "alice123", "Pass12345!")
        self.assertFalse(ok1)
        self.assertIn("already taken", msg1)

        # Duplicate email
        ok2, msg2 = db.create_user("Alice Clone 2", "alice@example.com", "different_user", "Pass12345!")
        self.assertFalse(ok2)
        self.assertIn("already registered", msg2)

    def test_04_save_and_retrieve_analysis(self):
        """Test storing an analysis with metrics and detected issues."""
        _, _ = db.create_user("Bob", "bob@example.com", "bobuser", "BobPass123!")
        user = db.get_user_by_identifier("bobuser")

        sample_metrics = {
            "loc": 45.0,
            "cyclomatic_complexity": 3.0,
            "halstead_volume": 120.5
        }
        sample_issues = [
            {
                "issue_type": "Syntax Warning",
                "severity": "High",
                "description": "Unused variable 'x'",
                "line_number": 12,
                "suggested_solution": "Remove unused variable 'x'",
                "tool_name": "Flake8"
            },
            {
                "issue_type": "Security",
                "severity": "Critical",
                "description": "Possible division by zero",
                "line_number": 25,
                "suggested_solution": "Add check for denominator != 0",
                "tool_name": "Static Analyzer"
            }
        ]

        analysis_id, msg = db.save_analysis(
            user_id=user["user_id"],
            file_name="test_script.py",
            programming_language="Python",
            source_code="def test(): pass",
            total_lines=45,
            software_metrics=sample_metrics,
            defect_probability=0.72,
            prediction_result="DEFECTIVE",
            analysis_status="Completed",
            issues=sample_issues
        )

        self.assertIsNotNone(analysis_id)

        # Retrieve and verify
        analysis = db.get_analysis_by_id(analysis_id, user_id=user["user_id"])
        self.assertIsNotNone(analysis)
        self.assertEqual(analysis["file_name"], "test_script.py")
        self.assertEqual(analysis["software_metrics"]["loc"], 45.0)
        self.assertEqual(len(analysis["issues"]), 2)
        self.assertEqual(analysis["issues"][0]["severity"], "Critical")  # Critical ordered first

    def test_05_user_isolation(self):
        """Ensure User A cannot retrieve or delete User B's analysis."""
        db.create_user("User A", "usera@example.com", "usera", "PassA1234!")
        db.create_user("User B", "userb@example.com", "userb", "PassB1234!")
        user_a = db.get_user_by_identifier("usera")
        user_b = db.get_user_by_identifier("userb")

        a_id, _ = db.save_analysis(
            user_id=user_a["user_id"],
            file_name="a.py",
            programming_language="Python",
            source_code="print('A')",
            total_lines=1,
            software_metrics={},
            defect_probability=0.1,
            prediction_result="NON-DEFECTIVE"
        )

        # User B attempts to access User A's analysis
        b_view = db.get_analysis_by_id(a_id, user_id=user_b["user_id"], is_admin=False)
        self.assertIsNone(b_view, "User B should NOT be able to view User A's analysis!")

        # User B attempts to delete User A's analysis
        deleted = db.delete_analysis(a_id, user_id=user_b["user_id"], is_admin=False)
        self.assertFalse(deleted, "User B should NOT be able to delete User A's analysis!")

        # Admin CAN view
        admin_view = db.get_analysis_by_id(a_id, is_admin=True)
        self.assertIsNotNone(admin_view, "Admin SHOULD be able to view analysis!")

    def test_06_dashboard_statistics(self):
        """Verify user and admin statistics calculations."""
        db.create_user("Dev", "dev@example.com", "devuser", "PassDev123!")
        user = db.get_user_by_identifier("devuser")

        db.save_analysis(
            user_id=user["user_id"],
            file_name="main.c",
            programming_language="C",
            source_code="int main() { return 0; }",
            total_lines=1,
            software_metrics={},
            defect_probability=0.85,
            prediction_result="DEFECTIVE"
        )

        stats = db.get_user_stats(user["user_id"])
        self.assertEqual(stats["total_analyses"], 1)
        self.assertEqual(stats["defective_count"], 1)
        self.assertEqual(stats["c_count"], 1)

        admin_stats = db.get_admin_stats()
        self.assertGreaterEqual(admin_stats["total_users"], 2)
        self.assertGreaterEqual(admin_stats["total_analyses"], 1)


if __name__ == "__main__":
    unittest.main()
