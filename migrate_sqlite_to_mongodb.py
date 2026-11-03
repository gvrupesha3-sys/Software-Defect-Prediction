"""
SQLite to MongoDB Atlas Migration Utility
Transfers existing SQLite users, code analysis history, detected issues,
and generated reports into MongoDB Atlas collections (users, predictions, code_analysis, activity_logs).
Preserves existing SQLite records without deleting or modifying them.
"""

import os
import sys
import sqlite3
import json
from datetime import datetime
from dotenv import load_dotenv

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import database as db

# Load environment configuration
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_DB_PATH = os.path.join(BASE_DIR, "defect_prediction.db")


def run_migration():
    """Execute migration from SQLite to MongoDB Atlas / Local MongoDB."""
    print("=" * 60)
    print("[*] SQLite to MongoDB Data Migration Script")
    print("=" * 60)

    # 1. Verify SQLite Database Exists
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"[!] SQLite database not found at: {SQLITE_DB_PATH}")
        print("Nothing to migrate. A fresh MongoDB database will be initialized.")
        return

    # 2. Verify MongoDB Connection
    is_connected, msg = db.test_connection()
    if not is_connected:
        print("[!] Cannot connect to MongoDB.")
        print(f"Details: {msg}")
        print("\nPlease ensure MONGODB_URI is properly configured in your .env file or local MongoDB is running.")
        return

    print(f"[+] Connected to MongoDB ({db.MONGODB_DB_NAME})")

    # Initialize collections and indexes
    db.init_db()
    mongo_db = db.get_db()

    # 3. Connect to SQLite
    sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.cursor()

    migrated_users = 0
    skipped_users = 0
    migrated_analyses = 0
    skipped_analyses = 0

    print("\n--- Phase 1: Migrating Users ---")
    try:
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()

        users_col = mongo_db["users"]
        for u in users:
            username = u["username"]
            email = u["email"]

            # Check if user already exists in MongoDB
            existing = users_col.find_one({
                "$or": [{"username": username}, {"email": email}]
            })

            if not existing:
                try:
                    created_at_val = datetime.fromisoformat(u["created_at"]) if u["created_at"] else datetime.now()
                except Exception:
                    created_at_val = datetime.now()

                users_col.insert_one({
                    "user_id": str(u["user_id"]),
                    "full_name": u["full_name"],
                    "email": email,
                    "username": username,
                    "password_hash": u["password_hash"],
                    "role": u["role"],
                    "created_at": created_at_val
                })
                migrated_users += 1
                print(f"  [+] Migrated user: @{username} ({u['role']})")
            else:
                skipped_users += 1
                print(f"  [~] User @{username} already exists in MongoDB (Skipped)")

    except Exception as e:
        print(f"[!] Error reading SQLite users: {e}")

    print(f"Users Migration Completed: {migrated_users} migrated, {skipped_users} already present.")

    print("\n--- Phase 2: Migrating Code Analysis History & Predictions ---")
    try:
        cursor.execute("SELECT * FROM code_analysis_history")
        analyses = cursor.fetchall()

        analysis_col = mongo_db["code_analysis"]
        predictions_col = mongo_db["predictions"]

        for a in analyses:
            a_id = str(a["analysis_id"])

            existing = analysis_col.find_one({"analysis_id": a_id})
            if not existing:
                # Fetch related detected issues from SQLite
                cursor.execute("SELECT * FROM detected_issues WHERE analysis_id = ?", (a["analysis_id"],))
                raw_issues = cursor.fetchall()
                formatted_issues = []
                for idx, iss in enumerate(raw_issues, 1):
                    formatted_issues.append({
                        "issue_id": f"{a_id}_iss_{idx}",
                        "issue_type": iss["issue_type"],
                        "severity": iss["severity"],
                        "description": iss["description"],
                        "line_number": iss["line_number"],
                        "suggested_solution": iss["suggested_solution"],
                        "tool_name": iss["tool_name"]
                    })

                # Fetch related reports
                cursor.execute("SELECT * FROM reports WHERE analysis_id = ?", (a["analysis_id"],))
                raw_reports = cursor.fetchall()
                formatted_reports = []
                for r in raw_reports:
                    try:
                        gen_at = datetime.fromisoformat(r["generated_at"]) if r["generated_at"] else datetime.now()
                    except Exception:
                        gen_at = datetime.now()
                    formatted_reports.append({
                        "report_id": f"rep_{r['report_id']}",
                        "report_path": r["report_path"],
                        "generated_at": gen_at
                    })

                # Parse metrics JSON
                try:
                    metrics = json.loads(a["software_metrics"])
                except Exception:
                    metrics = {}

                try:
                    a_date = datetime.fromisoformat(a["analysis_date"]) if a["analysis_date"] else datetime.now()
                except Exception:
                    a_date = datetime.now()

                model_name = "Random Forest (200 Trees, NASA MDP Datasets)"

                # Insert into code_analysis collection
                analysis_col.insert_one({
                    "analysis_id": a_id,
                    "user_id": str(a["user_id"]),
                    "file_name": a["file_name"],
                    "programming_language": a["programming_language"],
                    "source_code": a["source_code"],
                    "total_lines": a["total_lines"],
                    "software_metrics": metrics,
                    "defect_probability": a["defect_probability"],
                    "prediction_result": a["prediction_result"],
                    "model_name": model_name,
                    "analysis_status": a["analysis_status"],
                    "analysis_date": a_date,
                    "detected_issues": formatted_issues,
                    "reports": formatted_reports
                })

                # Insert into predictions collection
                predictions_col.insert_one({
                    "prediction_id": f"pred_{a_id}",
                    "analysis_id": a_id,
                    "user_id": str(a["user_id"]),
                    "file_name": a["file_name"],
                    "programming_language": a["programming_language"],
                    "defect_probability": a["defect_probability"],
                    "prediction_result": a["prediction_result"],
                    "model_name": model_name,
                    "software_metrics": metrics,
                    "created_at": a_date
                })

                migrated_analyses += 1
                print(f"  [+] Migrated analysis #{a_id}: {a['file_name']} ({a['programming_language']})")
            else:
                skipped_analyses += 1
                print(f"  [~] Analysis #{a_id} already exists in MongoDB (Skipped)")

    except Exception as e:
        print(f"[!] Error migrating analyses: {e}")

    sqlite_conn.close()

    # 4. Log migration completion in MongoDB activity_logs
    db.log_activity(
        "system",
        "MigrationTool",
        "DATA_MIGRATION",
        f"Migrated {migrated_users} users and {migrated_analyses} analysis records from SQLite to MongoDB."
    )

    print("\n" + "=" * 60)
    print("[*] MIGRATION SUMMARY")
    print(f"  - Users Migrated:             {migrated_users}")
    print(f"  - Users Already in MongoDB:   {skipped_users}")
    print(f"  - Analyses Migrated:          {migrated_analyses}")
    print(f"  - Analyses Already in MongoDB:{skipped_analyses}")
    print("=" * 60)
    print("Note: Original SQLite database remains intact and unmodified.")


if __name__ == "__main__":
    run_migration()
