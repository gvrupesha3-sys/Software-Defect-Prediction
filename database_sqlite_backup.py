"""
Database Module for AI-Based Multi-Language Software Defect Prediction System
Manages SQLite database initialization, user accounts, analysis history,
detected code issues, and generated PDF reports.
"""

import os
import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import bcrypt
from dotenv import load_dotenv

# Load environment variables if available
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base directory and database path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "defect_prediction.db")
DB_PATH = os.getenv("DB_PATH", DEFAULT_DB_PATH)


def get_db_connection() -> sqlite3.Connection:
    """
    Establish and return a connection to the SQLite database.
    Configures Row factory for dictionary-like access and enables foreign keys.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def hash_password(plain_password: str) -> str:
    """
    Securely hash a password using bcrypt with salt.
    """
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a stored bcrypt hash.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def init_db():
    """
    Initialize SQLite database tables, indices, and default admin account.
    Safe to call multiple times (uses CREATE TABLE IF NOT EXISTS).
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # ---------------------------------------------------------
        # TABLE 1: users
        # ---------------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL COLLATE NOCASE,
                username TEXT UNIQUE NOT NULL COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('admin', 'user')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # ---------------------------------------------------------
        # TABLE 2: code_analysis_history
        # ---------------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS code_analysis_history (
                analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                programming_language TEXT NOT NULL,
                source_code TEXT NOT NULL,
                total_lines INTEGER NOT NULL,
                software_metrics TEXT NOT NULL,
                defect_probability REAL,
                prediction_result TEXT NOT NULL,
                analysis_status TEXT NOT NULL,
                analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );
        """)

        # ---------------------------------------------------------
        # TABLE 3: detected_issues
        # ---------------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS detected_issues (
                issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                issue_type TEXT NOT NULL,
                severity TEXT NOT NULL CHECK(severity IN ('Critical', 'High', 'Medium', 'Low', 'Informational')),
                description TEXT NOT NULL,
                line_number INTEGER,
                suggested_solution TEXT,
                tool_name TEXT NOT NULL,
                FOREIGN KEY (analysis_id) REFERENCES code_analysis_history(analysis_id) ON DELETE CASCADE
            );
        """)

        # ---------------------------------------------------------
        # TABLE 4: reports
        # ---------------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                analysis_id INTEGER NOT NULL,
                report_path TEXT NOT NULL,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (analysis_id) REFERENCES code_analysis_history(analysis_id) ON DELETE CASCADE
            );
        """)

        # Indices for optimal query performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_user ON code_analysis_history(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_date ON code_analysis_history(analysis_date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_analysis ON detected_issues(analysis_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_user ON reports(user_id);")

        conn.commit()

    # Seed default administrator account if not present
    seed_default_admin()


def seed_default_admin():
    """
    Seed a default administrator account from environment variables or safe defaults.
    """
    admin_user = os.getenv("ADMIN_USERNAME", "admin")
    admin_email = os.getenv("ADMIN_EMAIL", "admin@defectprediction.ai")
    admin_pass = os.getenv("ADMIN_PASSWORD", "Admin@Defect2026!")
    admin_name = os.getenv("ADMIN_FULL_NAME", "System Administrator")

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE username = ? OR email = ?", (admin_user, admin_email))
            existing = cursor.fetchone()

            if not existing:
                pwd_hash = hash_password(admin_pass)
                cursor.execute("""
                    INSERT INTO users (full_name, email, username, password_hash, role)
                    VALUES (?, ?, ?, ?, 'admin')
                """, (admin_name, admin_email, admin_user, pwd_hash))
                conn.commit()
                logger.info(f"Default admin user '{admin_user}' initialized successfully.")
    except Exception as e:
        logger.error(f"Error seeding admin user: {e}")


# =====================================================================
# USER MANAGEMENT FUNCTIONS
# =====================================================================

def create_user(full_name: str, email: str, username: str, password: str, role: str = "user") -> Tuple[bool, str]:
    """
    Create a new registered user.
    Returns (success, message).
    """
    full_name = full_name.strip()
    email = email.strip().lower()
    username = username.strip()

    if not full_name or not email or not username or not password:
        return False, "All registration fields are required."

    if role not in ("user", "admin"):
        role = "user"

    pwd_hash = hash_password(password)

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Check unique username
            cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                return False, f"Username '{username}' is already taken. Please choose another."

            # Check unique email
            cursor.execute("SELECT user_id FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                return False, f"Email '{email}' is already registered. Please login or use a different email."

            cursor.execute("""
                INSERT INTO users (full_name, email, username, password_hash, role)
                VALUES (?, ?, ?, ?, ?)
            """, (full_name, email, username, pwd_hash, role))
            conn.commit()
            return True, "Registration successful! You can now log in."

    except sqlite3.IntegrityError as e:
        logger.warning(f"Integrity error during registration: {e}")
        return False, "A user with this username or email already exists."
    except Exception as e:
        logger.error(f"Database error creating user: {e}")
        return False, f"System error occurred during registration: {str(e)}"


def get_user_by_identifier(identifier: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve user record by username or email.
    """
    identifier = identifier.strip()
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, full_name, email, username, password_hash, role, created_at
                FROM users
                WHERE username = ? OR email = ?
            """, (identifier, identifier))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logger.error(f"Database error getting user: {e}")
        return None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve user record by user_id.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, full_name, email, username, role, created_at
                FROM users
                WHERE user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logger.error(f"Database error getting user by id: {e}")
        return None


def get_all_users() -> List[Dict[str, Any]]:
    """
    Retrieve all users for Admin Dashboard.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, full_name, email, username, role, created_at
                FROM users
                ORDER BY created_at DESC
            """)
            return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Database error getting all users: {e}")
        return []


# =====================================================================
# CODE ANALYSIS HISTORY & ISSUES
# =====================================================================

def save_analysis(
    user_id: int,
    file_name: str,
    programming_language: str,
    source_code: str,
    total_lines: int,
    software_metrics: Dict[str, Any],
    defect_probability: Optional[float],
    prediction_result: str,
    analysis_status: str = "Completed",
    issues: Optional[List[Dict[str, Any]]] = None
) -> Tuple[Optional[int], str]:
    """
    Save a completed code analysis and its detected issues.
    Returns (analysis_id, status_message).
    """
    try:
        metrics_json = json.dumps(software_metrics)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO code_analysis_history (
                    user_id, file_name, programming_language, source_code,
                    total_lines, software_metrics, defect_probability,
                    prediction_result, analysis_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, file_name, programming_language, source_code,
                total_lines, metrics_json, defect_probability,
                prediction_result, analysis_status
            ))
            analysis_id = cursor.lastrowid

            # Save detected issues if any
            if issues and analysis_id:
                for issue in issues:
                    cursor.execute("""
                        INSERT INTO detected_issues (
                            analysis_id, issue_type, severity, description,
                            line_number, suggested_solution, tool_name
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        analysis_id,
                        issue.get("issue_type", "General Issue"),
                        issue.get("severity", "Medium"),
                        issue.get("description", ""),
                        issue.get("line_number"),
                        issue.get("suggested_solution", ""),
                        issue.get("tool_name", "Static Analyzer")
                    ))

            conn.commit()
            return analysis_id, "Analysis saved successfully."

    except Exception as e:
        logger.error(f"Database error saving analysis: {e}")
        return None, f"Failed to save analysis: {str(e)}"


def get_user_analyses(user_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Retrieve code analysis history for a specific user (enforcing user isolation).
    Includes count of detected errors and warnings.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    h.analysis_id,
                    h.user_id,
                    h.file_name,
                    h.programming_language,
                    h.total_lines,
                    h.defect_probability,
                    h.prediction_result,
                    h.analysis_status,
                    h.analysis_date,
                    COUNT(CASE WHEN i.severity IN ('Critical', 'High') THEN 1 END) AS error_count,
                    COUNT(CASE WHEN i.severity IN ('Medium', 'Low', 'Informational') THEN 1 END) AS warning_count,
                    COUNT(i.issue_id) AS total_issues
                FROM code_analysis_history h
                LEFT JOIN detected_issues i ON h.analysis_id = i.analysis_id
                WHERE h.user_id = ?
                GROUP BY h.analysis_id
                ORDER BY h.analysis_date DESC
                LIMIT ?
            """, (user_id, limit))
            return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Database error retrieving user analyses: {e}")
        return []


def get_analysis_by_id(analysis_id: int, user_id: Optional[int] = None, is_admin: bool = False) -> Optional[Dict[str, Any]]:
    """
    Retrieve single analysis record with issues and metrics.
    Enforces user ownership unless user is an admin.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if is_admin or user_id is None:
                cursor.execute("""
                    SELECT h.*, u.username, u.full_name
                    FROM code_analysis_history h
                    JOIN users u ON h.user_id = u.user_id
                    WHERE h.analysis_id = ?
                """, (analysis_id,))
            else:
                cursor.execute("""
                    SELECT h.*, u.username, u.full_name
                    FROM code_analysis_history h
                    JOIN users u ON h.user_id = u.user_id
                    WHERE h.analysis_id = ? AND h.user_id = ?
                """, (analysis_id, user_id))

            row = cursor.fetchone()
            if not row:
                return None

            result = dict(row)
            try:
                result["software_metrics"] = json.loads(result["software_metrics"])
            except Exception:
                result["software_metrics"] = {}

            # Fetch detected issues
            cursor.execute("""
                SELECT issue_id, issue_type, severity, description, line_number, suggested_solution, tool_name
                FROM detected_issues
                WHERE analysis_id = ?
                ORDER BY 
                    CASE severity
                        WHEN 'Critical' THEN 1
                        WHEN 'High' THEN 2
                        WHEN 'Medium' THEN 3
                        WHEN 'Low' THEN 4
                        ELSE 5
                    END,
                    line_number ASC
            """, (analysis_id,))
            result["issues"] = [dict(issue) for issue in cursor.fetchall()]

            return result
    except Exception as e:
        logger.error(f"Database error getting analysis #{analysis_id}: {e}")
        return None


def delete_analysis(analysis_id: int, user_id: Optional[int] = None, is_admin: bool = False) -> bool:
    """
    Delete an analysis record with cascade to issues and reports.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if is_admin or user_id is None:
                cursor.execute("DELETE FROM code_analysis_history WHERE analysis_id = ?", (analysis_id,))
            else:
                cursor.execute("DELETE FROM code_analysis_history WHERE analysis_id = ? AND user_id = ?", (analysis_id, user_id))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Database error deleting analysis #{analysis_id}: {e}")
        return False


# =====================================================================
# REPORT STORAGE & TRACKING
# =====================================================================

def save_report_record(user_id: int, analysis_id: int, report_path: str) -> Optional[int]:
    """
    Record a generated PDF report path in the database.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reports (user_id, analysis_id, report_path)
                VALUES (?, ?, ?)
            """, (user_id, analysis_id, report_path))
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Database error saving report record: {e}")
        return None


def get_reports_for_user(user_id: int) -> List[Dict[str, Any]]:
    """
    Retrieve generated reports for a user.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.report_id, r.analysis_id, r.report_path, r.generated_at,
                       h.file_name, h.programming_language, h.prediction_result
                FROM reports r
                JOIN code_analysis_history h ON r.analysis_id = h.analysis_id
                WHERE r.user_id = ?
                ORDER BY r.generated_at DESC
            """, (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Database error retrieving reports: {e}")
        return []


# =====================================================================
# DASHBOARD STATISTICS & METRICS
# =====================================================================

def get_user_stats(user_id: int) -> Dict[str, Any]:
    """
    Calculate summary statistics for a user's dashboard.
    """
    stats = {
        "total_analyses": 0,
        "defective_count": 0,
        "non_defective_count": 0,
        "total_errors": 0,
        "total_warnings": 0,
        "python_count": 0,
        "java_count": 0,
        "c_count": 0,
        "language_distribution": {},
        "prediction_distribution": {},
        "severity_distribution": {}
    }
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Analyses counts & language breakdown
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN prediction_result LIKE '%DEFECTIVE%' AND prediction_result NOT LIKE '%NON%' THEN 1 ELSE 0 END) as defective,
                    SUM(CASE WHEN prediction_result LIKE '%NON-DEFECTIVE%' THEN 1 ELSE 0 END) as non_defective,
                    SUM(CASE WHEN programming_language = 'Python' THEN 1 ELSE 0 END) as py_count,
                    SUM(CASE WHEN programming_language = 'Java' THEN 1 ELSE 0 END) as java_count,
                    SUM(CASE WHEN programming_language = 'C' THEN 1 ELSE 0 END) as c_count
                FROM code_analysis_history
                WHERE user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            if row and row["total"]:
                stats["total_analyses"] = row["total"] or 0
                stats["defective_count"] = row["defective"] or 0
                stats["non_defective_count"] = row["non_defective"] or 0
                stats["python_count"] = row["py_count"] or 0
                stats["java_count"] = row["java_count"] or 0
                stats["c_count"] = row["c_count"] or 0

            # Language distribution map
            cursor.execute("""
                SELECT programming_language, COUNT(*) as count
                FROM code_analysis_history
                WHERE user_id = ?
                GROUP BY programming_language
            """, (user_id,))
            for r in cursor.fetchall():
                stats["language_distribution"][r["programming_language"]] = r["count"]

            # Prediction distribution map
            stats["prediction_distribution"] = {
                "Defective": stats["defective_count"],
                "Non-Defective": stats["non_defective_count"]
            }

            # Issues severity breakdown
            cursor.execute("""
                SELECT i.severity, COUNT(i.issue_id) as count
                FROM detected_issues i
                JOIN code_analysis_history h ON i.analysis_id = h.analysis_id
                WHERE h.user_id = ?
                GROUP BY i.severity
            """, (user_id,))
            for r in cursor.fetchall():
                sev = r["severity"]
                count = r["count"]
                stats["severity_distribution"][sev] = count
                if sev in ("Critical", "High"):
                    stats["total_errors"] += count
                else:
                    stats["total_warnings"] += count

            return stats
    except Exception as e:
        logger.error(f"Database error calculating user stats: {e}")
        return stats


def get_admin_stats() -> Dict[str, Any]:
    """
    Calculate global system statistics for the Admin Dashboard.
    """
    stats = {
        "total_users": 0,
        "total_analyses": 0,
        "total_defective": 0,
        "total_non_defective": 0,
        "total_reports": 0,
        "language_distribution": {},
        "severity_distribution": {},
        "recent_analyses": []
    }
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # User count
            cursor.execute("SELECT COUNT(*) as count FROM users")
            u_row = cursor.fetchone()
            if u_row:
                stats["total_users"] = u_row["count"]

            # Analysis counts
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN prediction_result LIKE '%DEFECTIVE%' AND prediction_result NOT LIKE '%NON%' THEN 1 ELSE 0 END) as defective,
                    SUM(CASE WHEN prediction_result LIKE '%NON-DEFECTIVE%' THEN 1 ELSE 0 END) as non_defective
                FROM code_analysis_history
            """)
            a_row = cursor.fetchone()
            if a_row and a_row["total"]:
                stats["total_analyses"] = a_row["total"] or 0
                stats["total_defective"] = a_row["defective"] or 0
                stats["total_non_defective"] = a_row["non_defective"] or 0

            # Total reports
            cursor.execute("SELECT COUNT(*) as count FROM reports")
            r_row = cursor.fetchone()
            if r_row:
                stats["total_reports"] = r_row["count"]

            # Language breakdown
            cursor.execute("""
                SELECT programming_language, COUNT(*) as count
                FROM code_analysis_history
                GROUP BY programming_language
            """)
            for r in cursor.fetchall():
                stats["language_distribution"][r["programming_language"]] = r["count"]

            # Severity breakdown
            cursor.execute("""
                SELECT severity, COUNT(*) as count
                FROM detected_issues
                GROUP BY severity
            """)
            for r in cursor.fetchall():
                stats["severity_distribution"][r["severity"]] = r["count"]

            # Recent 10 analyses across system
            cursor.execute("""
                SELECT h.analysis_id, u.username, h.file_name, h.programming_language,
                       h.prediction_result, h.defect_probability, h.analysis_date
                FROM code_analysis_history h
                JOIN users u ON h.user_id = u.user_id
                ORDER BY h.analysis_date DESC
                LIMIT 10
            """)
            stats["recent_analyses"] = [dict(r) for r in cursor.fetchall()]

            return stats
    except Exception as e:
        logger.error(f"Database error calculating admin stats: {e}")
        return stats


if __name__ == "__main__":
    # Self-test initialization when executed directly
    print("Initializing Database...")
    init_db()
    print("Database initialized successfully at:", DB_PATH)
