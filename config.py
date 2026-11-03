import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    SECRET_KEY = os.getenv("APP_SECRET_KEY", "defect_prediction_secret_key_2026_academic")
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload limit
    UPLOAD_EXTENSIONS = ['.py', '.java', '.c', '.h', '.cpp', '.csv']
    REPORTS_DIR = os.path.join(BASE_DIR, "reports")
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "defect_prediction_db")
