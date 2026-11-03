"""
Code Analyzer Dispatcher Module
Coordinates source code parsing, multi-language static analysis,
feature metric extraction, and machine learning defect prediction.
"""

import os
from typing import Dict, Any, List, Optional, Tuple
from analyzers.python_analyzer import analyze_python_code
from analyzers.java_analyzer import analyze_java_code
from analyzers.c_analyzer import analyze_c_code
from feature_extractor import extract_software_metrics
from ml_predictor import predict_defect
import database as db


def detect_language_from_filename(filename: str) -> str:
    """Infer programming language from file extension."""
    ext = os.path.splitext(filename)[1].lower()
    if ext in (".py", ".pyw"):
        return "Python"
    elif ext in (".java",):
        return "Java"
    elif ext in (".c", ".h"):
        return "C"
    return "Python"


def analyze_source_code(
    source_code: str,
    file_name: str = "untitled_code.py",
    language: Optional[str] = None,
    user_id: Optional[int] = None,
    threshold: float = 0.30,
    save_to_db: bool = True
) -> Dict[str, Any]:
    """
    Master analysis pipeline:
    1. Language routing.
    2. Static analysis & issue detection.
    3. 21 NASA software metrics extraction.
    4. ML defect prediction (Random Forest).
    5. Database persistence (if authenticated).
    """
    if not source_code or not source_code.strip():
        raise ValueError("Source code cannot be empty.")

    # Detect or validate language
    if not language or language == "Auto-Detect":
        language = detect_language_from_filename(file_name)
    else:
        language = language.strip().capitalize()

    # 1. Run language-specific static analysis
    if language == "Python":
        issues, meta = analyze_python_code(source_code, file_name)
    elif language == "Java":
        issues, meta = analyze_java_code(source_code, file_name)
    elif language in ("C", "C++", "Cpp"):
        language = "C"
        issues, meta = analyze_c_code(source_code, file_name)
    else:
        language = "Python"
        issues, meta = analyze_python_code(source_code, file_name)

    # 2. Extract exact 21 NASA software metrics
    metrics = extract_software_metrics(source_code, language)

    # 3. Machine learning defect prediction
    ml_results = predict_defect(metrics, language, issues, threshold=threshold)

    total_lines = len(source_code.splitlines())

    # Count issues by severity
    critical_count = sum(1 for i in issues if i.get("severity") == "Critical")
    high_count = sum(1 for i in issues if i.get("severity") == "High")
    medium_count = sum(1 for i in issues if i.get("severity") == "Medium")
    low_count = sum(1 for i in issues if i.get("severity") == "Low")
    info_count = sum(1 for i in issues if i.get("severity") == "Informational")

    analysis_result = {
        "analysis_id": None,
        "file_name": file_name,
        "programming_language": language,
        "source_code": source_code,
        "total_lines": total_lines,
        "software_metrics": metrics,
        "issues": issues,
        "metadata": meta,
        "prediction_result": ml_results["prediction_result"],
        "defect_probability": ml_results["final_probability"],
        "ml_probability": ml_results["ml_probability"],
        "static_risk_score": ml_results["static_risk_score"],
        "health_score": ml_results["health_score"],
        "threshold_used": ml_results["threshold_used"],
        "validation_status": ml_results["validation_status"],
        "compatibility_note": ml_results["compatibility_note"],
        "issue_counts": {
            "critical": critical_count,
            "high": high_count,
            "medium": medium_count,
            "low": low_count,
            "info": info_count,
            "total_errors": critical_count + high_count,
            "total_warnings": medium_count + low_count + info_count
        }
    }

    # 4. Save to SQLite database if requested and user_id is provided
    if save_to_db and user_id is not None:
        analysis_id, status_msg = db.save_analysis(
            user_id=user_id,
            file_name=file_name,
            programming_language=language,
            source_code=source_code,
            total_lines=total_lines,
            software_metrics=metrics,
            defect_probability=ml_results["final_probability"],
            prediction_result=ml_results["prediction_result"],
            analysis_status="Completed",
            issues=issues
        )
        analysis_result["analysis_id"] = analysis_id

    return analysis_result
