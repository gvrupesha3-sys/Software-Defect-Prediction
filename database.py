"""
MongoDB Centralized Database Layer for AI-Based Software Defect Prediction System
Migrated from SQLite to MongoDB Atlas using PyMongo.
Manages:
- users collection: Accounts, hashed credentials (Werkzeug/Bcrypt), and RBAC roles.
- predictions collection: ML defect prediction outputs, model metadata, probabilities.
- code_analysis collection: Source files, 21 NASA metrics, static issues, and report links.
- activity_logs collection: User and system operational audit trail.
"""

import os
import re
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import bcrypt
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, DuplicateKeyError

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB Atlas Configuration
DEFAULT_URI = "mongodb://localhost:27017"
MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "defect_prediction_db")

# Singleton Client Cache
_MONGO_CLIENT = None
_MONGO_DB = None
_CONNECTION_STATUS = {"tested": False, "connected": False, "message": "Uninitialized", "target": "None"}


def get_mongo_client() -> Optional[MongoClient]:
    """
    Get or create a cached MongoClient singleton with connection pooling and timeouts.
    Tries configured MONGODB_URI first, then falls back to local MongoDB (mongodb://localhost:27017).
    """
    global _MONGO_CLIENT, _MONGO_DB, _CONNECTION_STATUS

    if _MONGO_CLIENT is not None:
        return _MONGO_CLIENT

    configured_uri = os.getenv("MONGODB_URI", "").strip()

    # Determine candidate connection URIs
    candidates = []
    if configured_uri and "<username>" not in configured_uri and "<password>" not in configured_uri:
        candidates.append((configured_uri, "MongoDB Atlas (Configured URI)"))
    candidates.append((DEFAULT_URI, "Local MongoDB (mongodb://localhost:27017)"))

    last_error = ""
    for uri, desc in candidates:
        try:
            client = MongoClient(
                uri,
                serverSelectionTimeoutMS=2500,
                connectTimeoutMS=2500,
                socketTimeoutMS=2500,
                maxPoolSize=50,
                retryWrites=True
            )
            # Verify connection with ping
            client.admin.command('ping')
            _MONGO_CLIENT = client
            _MONGO_DB = client[MONGODB_DB_NAME]
            _CONNECTION_STATUS = {
                "tested": True,
                "connected": True,
                "message": f"Successfully connected to {desc} (database: '{MONGODB_DB_NAME}').",
                "target": desc
            }
            logger.info(f"MongoDB connection established to {desc}")
            return _MONGO_CLIENT
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            last_error = str(e)
            continue
        except Exception as e:
            last_error = str(e)
            continue

    _CONNECTION_STATUS = {
        "tested": True,
        "connected": False,
        "message": f"Could not connect to MongoDB Atlas or local MongoDB. Details: {last_error}",
        "target": "None"
    }
    logger.warning(_CONNECTION_STATUS["message"])
    return None


def get_db():
    """Return the active MongoDB database object or None if disconnected."""
    client = get_mongo_client()
    if client is not None:
        return client[MONGODB_DB_NAME]
    return None


def test_connection() -> Tuple[bool, str]:
    """Test MongoDB Atlas connectivity and return (is_connected, status_message)."""
    global _MONGO_CLIENT, _CONNECTION_STATUS
    if _MONGO_CLIENT is None or not _CONNECTION_STATUS["connected"]:
        _MONGO_CLIENT = None
        get_mongo_client()
    return _CONNECTION_STATUS["connected"], _CONNECTION_STATUS["message"]


def get_connection_info() -> Dict[str, Any]:
    """Return dictionary with detailed connection diagnostics."""
    test_connection()
    uri = os.getenv("MONGODB_URI", "")
    masked_uri = re.sub(r'//([^:]+):([^@]+)@', r'//\1:****@', uri) if uri else "Not Configured"
    return {
        "connected": _CONNECTION_STATUS["connected"],
        "message": _CONNECTION_STATUS["message"],
        "database_name": MONGODB_DB_NAME,
        "masked_uri": masked_uri,
        "target": _CONNECTION_STATUS.get("target", "Unknown")
    }


# =====================================================================
# PASSWORD HASHING (WERKZEUG & BCRYPT COMPATIBILITY)
# =====================================================================

def hash_password(plain_password: str) -> str:
    """Securely hash password using werkzeug security with bcrypt fallback."""
    try:
        from werkzeug.security import generate_password_hash
        return generate_password_hash(plain_password)
    except Exception:
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against stored hash (supports Werkzeug and bcrypt)."""
    if not hashed_password or not plain_password:
        return False
    # Check if bcrypt hash
    if hashed_password.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        except Exception:
            pass
    # Werkzeug verification
    try:
        from werkzeug.security import check_password_hash
        return check_password_hash(hashed_password, plain_password)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


# =====================================================================
# DATABASE INITIALIZATION & INDEXES
# =====================================================================

def init_db():
    """
    Initialize MongoDB collections and create unique/performance indices.
    Seeds default admin account if not present.
    """
    db = get_db()
    if db is None:
        logger.warning("MongoDB not connected during init_db(). Skipping index creation.")
        return False

    try:
        # Collection 1: users
        users_col = db["users"]
        users_col.create_index([("username", ASCENDING)], unique=True)
        users_col.create_index([("email", ASCENDING)], unique=True)

        # Collection 2: code_analysis
        analysis_col = db["code_analysis"]
        analysis_col.create_index([("analysis_id", ASCENDING)], unique=True)
        analysis_col.create_index([("user_id", ASCENDING)])
        analysis_col.create_index([("analysis_date", DESCENDING)])

        # Collection 3: predictions
        predictions_col = db["predictions"]
        predictions_col.create_index([("prediction_id", ASCENDING)], unique=True)
        predictions_col.create_index([("user_id", ASCENDING)])
        predictions_col.create_index([("analysis_id", ASCENDING)])
        predictions_col.create_index([("created_at", DESCENDING)])

        # Collection 4: activity_logs
        logs_col = db["activity_logs"]
        logs_col.create_index([("user_id", ASCENDING)])
        logs_col.create_index([("timestamp", DESCENDING)])

        logger.info("MongoDB collections and indexes ensured successfully.")
        seed_default_admin()
        return True
    except Exception as e:
        logger.error(f"Error during MongoDB init_db: {e}")
        return False


def seed_default_admin():
    """Seed default administrator account from environment variables if not present."""
    db = get_db()
    if db is None:
        return

    admin_user = os.getenv("ADMIN_USERNAME", "admin")
    admin_email = os.getenv("ADMIN_EMAIL", "admin@defectprediction.ai").lower()
    admin_pass = os.getenv("ADMIN_PASSWORD", "Admin@Defect2026!")
    admin_name = os.getenv("ADMIN_FULL_NAME", "System Administrator")

    try:
        users_col = db["users"]
        existing = users_col.find_one({
            "$or": [{"username": admin_user}, {"email": admin_email}]
        })

        if not existing:
            pwd_hash = hash_password(admin_pass)
            users_col.insert_one({
                "user_id": "admin_1",
                "full_name": admin_name,
                "email": admin_email,
                "username": admin_user,
                "password_hash": pwd_hash,
                "role": "admin",
                "created_at": datetime.utcnow()
            })
            log_activity("admin_1", admin_user, "SYSTEM_INIT", "Default admin account initialized")
            logger.info(f"Default admin user '{admin_user}' seeded into MongoDB.")
    except Exception as e:
        logger.error(f"Error seeding admin into MongoDB: {e}")


# =====================================================================
# AUDIT & ACTIVITY LOGGING
# =====================================================================

def log_activity(user_id: Any, username: str, action: str, details: Any = None):
    """Record an event in the activity_logs collection."""
    db = get_db()
    if db is None:
        return

    try:
        db["activity_logs"].insert_one({
            "log_id": f"log_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
            "user_id": str(user_id),
            "username": str(username),
            "action": action,
            "details": details if isinstance(details, (dict, list, str, int, float, bool)) else str(details),
            "timestamp": datetime.utcnow()
        })
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")


def get_recent_activity_logs(limit: int = 30) -> List[Dict[str, Any]]:
    """Retrieve recent system activity logs."""
    db = get_db()
    if db is None:
        return []
    try:
        logs = list(db["activity_logs"].find({}, {"_id": 0}).sort("timestamp", DESCENDING).limit(limit))
        return logs
    except Exception as e:
        logger.error(f"Error fetching activity logs: {e}")
        return []


# =====================================================================
# USER MANAGEMENT (MONGODB)
# =====================================================================

def create_user(full_name: str, email: str, username: str, password: str, role: str = "user") -> Tuple[bool, str]:
    """Register a new user account in MongoDB Atlas."""
    db = get_db()
    if db is None:
        return False, "Database connection is unavailable. Please check your MongoDB configuration."

    full_name = full_name.strip()
    email = email.strip().lower()
    username = username.strip()

    if not full_name or not email or not username or not password:
        return False, "All fields are required."

    if role not in ("admin", "user"):
        role = "user"

    users_col = db["users"]

    # Check for existing username or email
    if users_col.find_one({"username": {"$regex": f"^{re.escape(username)}$", "$options": "i"}}):
        return False, f"Username '{username}' is already taken. Please choose another."

    if users_col.find_one({"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}}):
        return False, f"Email '{email}' is already registered. Please login or use a different email."

    pwd_hash = hash_password(password)
    user_id_gen = f"usr_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"

    try:
        users_col.insert_one({
            "user_id": user_id_gen,
            "full_name": full_name,
            "email": email,
            "username": username,
            "password_hash": pwd_hash,
            "role": role,
            "created_at": datetime.utcnow()
        })
        log_activity(user_id_gen, username, "USER_REGISTRATION", f"Registered new account: {username}")
        return True, "Registration successful! You can now sign in."
    except DuplicateKeyError:
        return False, "A user with this username or email already exists."
    except Exception as e:
        logger.error(f"MongoDB error creating user: {e}")
        return False, f"Database error during registration: {str(e)}"


def get_user_by_identifier(identifier: str) -> Optional[Dict[str, Any]]:
    """Retrieve user record by username or email from MongoDB."""
    db = get_db()
    if db is None:
        return None

    ident = identifier.strip()
    try:
        user = db["users"].find_one({
            "$or": [
                {"username": {"$regex": f"^{re.escape(ident)}$", "$options": "i"}},
                {"email": {"$regex": f"^{re.escape(ident)}$", "$options": "i"}}
            ]
        })
        if user:
            user["_id"] = str(user["_id"])
            return user
        return None
    except Exception as e:
        logger.error(f"Error querying user by identifier '{identifier}': {e}")
        return None


def get_user_by_id(user_id: Any) -> Optional[Dict[str, Any]]:
    """Retrieve user record by user_id."""
    db = get_db()
    if db is None:
        return None
    try:
        u_str = str(user_id)
        user = db["users"].find_one({"$or": [{"user_id": u_str}, {"user_id": user_id}]})
        if user:
            user["_id"] = str(user["_id"])
            return user
        return None
    except Exception as e:
        logger.error(f"Error getting user by id: {e}")
        return None


def get_all_users() -> List[Dict[str, Any]]:
    """Retrieve all registered users for Admin Dashboard."""
    db = get_db()
    if db is None:
        return []
    try:
        users = list(db["users"].find({}, {"password_hash": 0}).sort("created_at", DESCENDING))
        for u in users:
            u["_id"] = str(u["_id"])
        return users
    except Exception as e:
        logger.error(f"Error getting all users: {e}")
        return []


def update_user_role(user_id: Any, new_role: str) -> bool:
    """Update user role (admin or user)."""
    db = get_db()
    if db is None or new_role not in ("admin", "user"):
        return False
    u_str = str(user_id)
    try:
        res = db["users"].update_one(
            {"$or": [{"user_id": u_str}, {"user_id": user_id}]},
            {"$set": {"role": new_role}}
        )
        log_activity(u_str, "admin", "ROLE_CHANGE", f"Changed role for user {u_str} to {new_role}")
        return res.modified_count > 0
    except Exception as e:
        logger.error(f"Error updating user role: {e}")
        return False


def delete_user(user_id: Any) -> bool:
    """Delete a user account and associated analyses/predictions."""
    db = get_db()
    if db is None:
        return False
    u_str = str(user_id)
    try:
        res = db["users"].delete_one({"$or": [{"user_id": u_str}, {"user_id": user_id}]})
        if res.deleted_count > 0:
            db["code_analysis"].delete_many({"$or": [{"user_id": u_str}, {"user_id": user_id}]})
            db["predictions"].delete_many({"$or": [{"user_id": u_str}, {"user_id": user_id}]})
            log_activity("admin", "admin", "USER_DELETED", f"Deleted user {u_str}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting user {u_str}: {e}")
        return False


def update_user_profile(user_id: Any, full_name: str, email: str) -> Tuple[bool, str]:
    """Update profile details for an authenticated user."""
    db = get_db()
    if db is None:
        return False, "Database not connected"
    u_str = str(user_id)
    email = email.strip().lower()
    full_name = full_name.strip()

    try:
        # Check if email is taken by another user
        existing = db["users"].find_one({
            "email": {"$regex": f"^{re.escape(email)}$", "$options": "i"},
            "user_id": {"$ne": u_str}
        })
        if existing:
            return False, "Email is already registered by another account."

        db["users"].update_one(
            {"$or": [{"user_id": u_str}, {"user_id": user_id}]},
            {"$set": {"full_name": full_name, "email": email}}
        )
        return True, "Profile updated successfully."
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        return False, str(e)


def update_user_password(user_id: Any, new_password: str) -> Tuple[bool, str]:
    """Change password for a user."""
    db = get_db()
    if db is None:
        return False, "Database not connected"
    u_str = str(user_id)
    pwd_hash = hash_password(new_password)
    try:
        db["users"].update_one(
            {"$or": [{"user_id": u_str}, {"user_id": user_id}]},
            {"$set": {"password_hash": pwd_hash}}
        )
        log_activity(u_str, "user", "PASSWORD_CHANGE", "Password updated successfully")
        return True, "Password changed successfully."
    except Exception as e:
        return False, str(e)


# =====================================================================
# CODE ANALYSIS & PREDICTIONS (MONGODB)
# =====================================================================

def save_analysis(
    user_id: Any,
    file_name: str,
    programming_language: str,
    source_code: str,
    total_lines: int,
    software_metrics: Dict[str, Any],
    defect_probability: Optional[float],
    prediction_result: str,
    analysis_status: str = "Completed",
    issues: Optional[List[Dict[str, Any]]] = None
) -> Tuple[Optional[str], str]:
    """Store source code analysis and prediction output in MongoDB Atlas."""
    db = get_db()
    if db is None:
        return None, "Database unavailable. Analysis results not saved."

    u_id = str(user_id)
    analysis_id = f"ana_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    pred_id = f"pred_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    model_name = "Random Forest (200 Trees, NASA MDP Datasets)"

    # Format detected issues
    formatted_issues = []
    if issues:
        for idx, iss in enumerate(issues, 1):
            formatted_issues.append({
                "issue_id": f"{analysis_id}_iss_{idx}",
                "issue_type": iss.get("issue_type", "General Issue"),
                "severity": iss.get("severity", "Medium"),
                "description": iss.get("description", ""),
                "line_number": iss.get("line_number"),
                "suggested_solution": iss.get("suggested_solution", ""),
                "tool_name": iss.get("tool_name", "Static Analyzer")
            })

    try:
        now = datetime.utcnow()

        # 1. Store in code_analysis collection
        analysis_doc = {
            "analysis_id": analysis_id,
            "user_id": u_id,
            "file_name": file_name,
            "programming_language": programming_language,
            "source_code": source_code,
            "total_lines": total_lines,
            "software_metrics": software_metrics,
            "defect_probability": defect_probability,
            "prediction_result": prediction_result,
            "model_name": model_name,
            "analysis_status": analysis_status,
            "analysis_date": now,
            "detected_issues": formatted_issues,
            "reports": []
        }
        db["code_analysis"].insert_one(analysis_doc)

        # 2. Store in predictions collection
        pred_doc = {
            "prediction_id": pred_id,
            "analysis_id": analysis_id,
            "user_id": u_id,
            "file_name": file_name,
            "programming_language": programming_language,
            "defect_probability": defect_probability,
            "prediction_result": prediction_result,
            "model_name": model_name,
            "software_metrics": software_metrics,
            "created_at": now
        }
        db["predictions"].insert_one(pred_doc)

        # 3. Log activity
        log_activity(u_id, "User", "CODE_ANALYSIS", f"Analyzed {file_name} ({programming_language}): {prediction_result}")

        return analysis_id, "Analysis saved successfully in MongoDB."
    except Exception as e:
        logger.error(f"Error saving analysis in MongoDB: {e}")
        return None, f"Failed to save analysis: {str(e)}"


def save_prediction_direct(
    user_id: Any,
    dataset_name: str,
    software_metrics: Dict[str, Any],
    defect_probability: float,
    prediction_result: str,
    threshold_used: float,
    ml_probability: float,
    validation_status: str
) -> Tuple[Optional[str], str]:
    """Store direct NASA defect prediction in MongoDB predictions collection."""
    db = get_db()
    if db is None:
        return None, "Database unavailable."

    u_id = str(user_id)
    pred_id = f"pred_direct_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    model_name = "Random Forest (200 Trees, NASA MDP Datasets)"

    try:
        now = datetime.utcnow()
        doc = {
            "prediction_id": pred_id,
            "analysis_id": None,
            "user_id": u_id,
            "file_name": f"NASA Metric Vector ({dataset_name})",
            "programming_language": "NASA Metrics",
            "dataset_origin": dataset_name,
            "software_metrics": software_metrics,
            "defect_probability": defect_probability,
            "ml_probability": ml_probability,
            "threshold_used": threshold_used,
            "prediction_result": prediction_result,
            "validation_status": validation_status,
            "model_name": model_name,
            "created_at": now
        }
        db["predictions"].insert_one(doc)
        log_activity(u_id, "User", "ML_PREDICTION", f"Ran direct prediction on {dataset_name}: {prediction_result}")
        return pred_id, "Prediction saved successfully."
    except Exception as e:
        logger.error(f"Error saving direct prediction: {e}")
        return None, str(e)


def get_user_analyses(user_id: Any, limit: int = 100) -> List[Dict[str, Any]]:
    """Retrieve code analysis history for a specific user from MongoDB."""
    db = get_db()
    if db is None:
        return []

    u_id = str(user_id)
    try:
        cursor = db["code_analysis"].find(
            {"$or": [{"user_id": u_id}, {"user_id": user_id}]},
            {"source_code": 0}
        ).sort("analysis_date", DESCENDING).limit(limit)

        results = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            issues = doc.get("detected_issues", [])
            error_count = sum(1 for i in issues if i.get("severity") in ("Critical", "High"))
            warning_count = sum(1 for i in issues if i.get("severity") in ("Medium", "Low", "Informational"))
            doc["error_count"] = error_count
            doc["warning_count"] = warning_count
            doc["total_issues"] = len(issues)
            results.append(doc)

        return results
    except Exception as e:
        logger.error(f"Error retrieving user analyses from MongoDB: {e}")
        return []


def get_user_predictions(user_id: Any, limit: int = 100) -> List[Dict[str, Any]]:
    """Retrieve full prediction history for a specific user from MongoDB."""
    db = get_db()
    if db is None:
        return []

    u_id = str(user_id)
    try:
        preds = list(db["predictions"].find(
            {"$or": [{"user_id": u_id}, {"user_id": user_id}]}
        ).sort("created_at", DESCENDING).limit(limit))

        for p in preds:
            p["_id"] = str(p["_id"])
        return preds
    except Exception as e:
        logger.error(f"Error retrieving user predictions: {e}")
        return []


def get_analysis_by_id(analysis_id: Any, user_id: Any = None, is_admin: bool = False) -> Optional[Dict[str, Any]]:
    """Retrieve single complete analysis record with full source code and issues."""
    db = get_db()
    if db is None:
        return None

    a_str = str(analysis_id)
    query: Dict[str, Any] = {
        "$or": [{"analysis_id": a_str}, {"analysis_id": analysis_id}]
    }

    if not is_admin and user_id is not None:
        u_str = str(user_id)
        query["$and"] = [{"$or": [{"user_id": u_str}, {"user_id": user_id}]}]

    try:
        doc = db["code_analysis"].find_one(query)
        if not doc:
            return None

        doc["_id"] = str(doc["_id"])
        doc["issues"] = doc.get("detected_issues", [])
        return doc
    except Exception as e:
        logger.error(f"Error retrieving analysis #{analysis_id}: {e}")
        return None


def delete_analysis(analysis_id: Any, user_id: Any = None, is_admin: bool = False) -> bool:
    """Delete an analysis and its corresponding prediction record from MongoDB."""
    db = get_db()
    if db is None:
        return False

    a_str = str(analysis_id)
    query: Dict[str, Any] = {
        "$or": [{"analysis_id": a_str}, {"analysis_id": analysis_id}]
    }

    if not is_admin and user_id is not None:
        u_str = str(user_id)
        query["$and"] = [{"$or": [{"user_id": u_str}, {"user_id": user_id}]}]

    try:
        res = db["code_analysis"].delete_one(query)
        if res.deleted_count > 0:
            db["predictions"].delete_many({"$or": [{"analysis_id": a_str}, {"analysis_id": analysis_id}]})
            log_activity(user_id or "admin", "User", "ANALYSIS_DELETED", f"Deleted analysis #{analysis_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting analysis #{analysis_id}: {e}")
        return False


# =====================================================================
# REPORTS (MONGODB)
# =====================================================================

def save_report_record(user_id: Any, analysis_id: Any, report_path: str) -> Optional[str]:
    """Add report path to the code_analysis document and log report creation."""
    db = get_db()
    if db is None:
        return None

    a_str = str(analysis_id)
    rep_id = f"rep_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    rep_entry = {
        "report_id": rep_id,
        "report_path": report_path,
        "generated_at": datetime.utcnow()
    }

    try:
        db["code_analysis"].update_one(
            {"$or": [{"analysis_id": a_str}, {"analysis_id": analysis_id}]},
            {"$push": {"reports": rep_entry}}
        )
        log_activity(user_id, "User", "REPORT_GENERATED", f"Generated PDF report for analysis #{analysis_id}")
        return rep_id
    except Exception as e:
        logger.error(f"Error saving report record in MongoDB: {e}")
        return None


def get_reports_for_user(user_id: Any) -> List[Dict[str, Any]]:
    """Retrieve all reports generated for a given user."""
    db = get_db()
    if db is None:
        return []

    u_str = str(user_id)
    try:
        cursor = db["code_analysis"].find(
            {
                "$or": [{"user_id": u_str}, {"user_id": user_id}],
                "reports.0": {"$exists": True}
            },
            {"analysis_id": 1, "file_name": 1, "programming_language": 1, "prediction_result": 1, "reports": 1, "defect_probability": 1, "analysis_date": 1}
        ).sort("analysis_date", DESCENDING)

        report_list = []
        for doc in cursor:
            for rep in doc.get("reports", []):
                report_list.append({
                    "report_id": rep.get("report_id"),
                    "analysis_id": doc.get("analysis_id"),
                    "file_name": doc.get("file_name"),
                    "programming_language": doc.get("programming_language"),
                    "prediction_result": doc.get("prediction_result"),
                    "defect_probability": doc.get("defect_probability"),
                    "report_path": rep.get("report_path"),
                    "generated_at": rep.get("generated_at")
                })
        return report_list
    except Exception as e:
        logger.error(f"Error retrieving reports for user: {e}")
        return []


# =====================================================================
# AGGREGATION & STATISTICS (MONGODB AGGREGATION PIPELINE)
# =====================================================================

def get_user_stats(user_id: Any) -> Dict[str, Any]:
    """Compute user summary statistics using MongoDB aggregation pipelines."""
    stats = {
        "total_analyses": 0,
        "total_predictions": 0,
        "defective_count": 0,
        "non_defective_count": 0,
        "total_errors": 0,
        "total_warnings": 0,
        "defect_rate": 0.0,
        "python_count": 0,
        "java_count": 0,
        "c_count": 0,
        "language_distribution": {},
        "prediction_distribution": {},
        "severity_distribution": {}
    }

    db = get_db()
    if db is None:
        return stats

    u_str = str(user_id)

    try:
        analyses = list(db["code_analysis"].find({"$or": [{"user_id": u_str}, {"user_id": user_id}]}))
        predictions = list(db["predictions"].find({"$or": [{"user_id": u_str}, {"user_id": user_id}]}))

        stats["total_analyses"] = len(analyses)
        stats["total_predictions"] = len(predictions)

        # Count from predictions
        for p in predictions:
            pred = p.get("prediction_result", "")
            if "DEFECTIVE" in pred and "NON" not in pred:
                stats["defective_count"] += 1
            else:
                stats["non_defective_count"] += 1

        if (stats["defective_count"] + stats["non_defective_count"]) > 0:
            stats["defect_rate"] = round(
                (stats["defective_count"] / (stats["defective_count"] + stats["non_defective_count"])) * 100.0, 1
            )

        for a in analyses:
            lang = a.get("programming_language", "Python")
            if lang == "Python":
                stats["python_count"] += 1
            elif lang == "Java":
                stats["java_count"] += 1
            elif lang == "C":
                stats["c_count"] += 1

            stats["language_distribution"][lang] = stats["language_distribution"].get(lang, 0) + 1

            # Tally issues
            for iss in a.get("detected_issues", []):
                sev = iss.get("severity", "Medium")
                stats["severity_distribution"][sev] = stats["severity_distribution"].get(sev, 0) + 1
                if sev in ("Critical", "High"):
                    stats["total_errors"] += 1
                else:
                    stats["total_warnings"] += 1

        stats["prediction_distribution"] = {
            "Defective": stats["defective_count"],
            "Non-Defective": stats["non_defective_count"]
        }
        return stats
    except Exception as e:
        logger.error(f"Error calculating user stats: {e}")
        return stats


def get_admin_stats() -> Dict[str, Any]:
    """Compute system-wide admin metrics using MongoDB aggregation."""
    stats = {
        "total_users": 0,
        "total_analyses": 0,
        "total_predictions": 0,
        "total_defective": 0,
        "total_non_defective": 0,
        "defect_rate": 0.0,
        "total_reports": 0,
        "language_distribution": {},
        "severity_distribution": {},
        "recent_analyses": [],
        "recent_predictions": []
    }

    db = get_db()
    if db is None:
        return stats

    try:
        stats["total_users"] = db["users"].count_documents({})
        stats["total_analyses"] = db["code_analysis"].count_documents({})
        stats["total_predictions"] = db["predictions"].count_documents({})

        # Defective vs non-defective count
        stats["total_defective"] = db["predictions"].count_documents({"prediction_result": "DEFECTIVE"})
        stats["total_non_defective"] = db["predictions"].count_documents({"prediction_result": "NON-DEFECTIVE"})

        if stats["total_predictions"] > 0:
            stats["defect_rate"] = round((stats["total_defective"] / stats["total_predictions"]) * 100.0, 1)

        # Count total reports
        reports_pipeline = [
            {"$unwind": "$reports"},
            {"$count": "total_reports"}
        ]
        r_res = list(db["code_analysis"].aggregate(reports_pipeline))
        if r_res:
            stats["total_reports"] = r_res[0].get("total_reports", 0)

        # Language distribution
        lang_pipeline = [
            {"$group": {"_id": "$programming_language", "count": {"$sum": 1}}}
        ]
        for row in db["code_analysis"].aggregate(lang_pipeline):
            if row["_id"]:
                stats["language_distribution"][row["_id"]] = row["count"]

        # Severity breakdown
        sev_pipeline = [
            {"$unwind": "$detected_issues"},
            {"$group": {"_id": "$detected_issues.severity", "count": {"$sum": 1}}}
        ]
        for row in db["code_analysis"].aggregate(sev_pipeline):
            if row["_id"]:
                stats["severity_distribution"][row["_id"]] = row["count"]

        # Recent 10 analyses
        recent = list(db["code_analysis"].find(
            {},
            {"analysis_id": 1, "user_id": 1, "file_name": 1, "programming_language": 1, "prediction_result": 1, "defect_probability": 1, "analysis_date": 1}
        ).sort("analysis_date", DESCENDING).limit(10))

        for r in recent:
            r["_id"] = str(r["_id"])
            u = db["users"].find_one({"$or": [{"user_id": str(r.get("user_id"))}, {"user_id": r.get("user_id")}]})
            r["username"] = u["username"] if u else "unknown"

        stats["recent_analyses"] = recent

        # Recent predictions
        recent_p = list(db["predictions"].find({}).sort("created_at", DESCENDING).limit(10))
        for p in recent_p:
            p["_id"] = str(p["_id"])
            u = db["users"].find_one({"$or": [{"user_id": str(p.get("user_id"))}, {"user_id": p.get("user_id")}]})
            p["username"] = u["username"] if u else "unknown"
        stats["recent_predictions"] = recent_p

        return stats
    except Exception as e:
        logger.error(f"Error computing admin stats in MongoDB: {e}")
        return stats


if __name__ == "__main__":
    print("Testing MongoDB Database Connection...")
    ok, msg = test_connection()
    print("Connection Status:", "CONNECTED" if ok else "NOT CONNECTED")
    print("Message:", msg)
    if ok:
        init_db()
        print("Database initialized successfully.")
