"""
Machine Learning Defect Predictor Module
Loads and applies the pre-trained Random Forest Defect Model (200 trees, NASA MDP datasets).
Enforces exact 21-feature input formatting, probability calculation, and multi-language
validation boundaries (C avionics baseline vs Java/Python metric approximation).
"""

import os
import joblib
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from feature_extractor import MODEL_FEATURES


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Model path resolution: check models/ folder first, then project root
MODEL_PATHS = [
    os.path.join(BASE_DIR, "models", "random_forest_defect_model.pkl"),
    os.path.join(BASE_DIR, "random_forest_defect_model.pkl")
]

_CACHED_MODEL = None


def load_defect_model():
    """
    Load and cache the trained Random Forest model.
    """
    global _CACHED_MODEL
    if _CACHED_MODEL is not None:
        return _CACHED_MODEL

    for path in MODEL_PATHS:
        if os.path.exists(path):
            try:
                _CACHED_MODEL = joblib.load(path)
                return _CACHED_MODEL
            except Exception as e:
                raise RuntimeError(f"Found model at {path} but failed to load: {e}")

    raise FileNotFoundError(
        "Random Forest model file 'random_forest_defect_model.pkl' not found in root or models/ directory."
    )


def calculate_static_risk_score(issues: List[Dict[str, Any]]) -> float:
    """
    Compute a normalized static code risk score (0.0 to 100.0)
    derived from detected issue counts weighted by severity.
    """
    weights = {
        "Critical": 30.0,
        "High": 15.0,
        "Medium": 6.0,
        "Low": 2.0,
        "Informational": 0.5
    }

    raw_score = sum(weights.get(issue.get("severity", "Low"), 2.0) for issue in issues)
    # Scale with diminishing returns to cap between 0 and 100
    risk_score = min(round(raw_score, 2), 100.0)
    return risk_score


def predict_defect(
    metrics: Dict[str, float],
    language: str,
    issues: Optional[List[Dict[str, Any]]] = None,
    threshold: float = 0.30
) -> Dict[str, Any]:
    """
    Execute defect prediction using the 21-feature Random Forest model.
    Combines machine learning statistical probability with static analysis findings.
    
    Args:
        metrics: Dictionary of 21 extracted software metrics.
        language: Programming language ('Python', 'Java', 'C').
        issues: List of static code issues detected by language analyzers.
        threshold: Classification decision boundary (default: 0.30 based on notebook evaluation).
    """
    model = load_defect_model()
    issues = issues or []
    lang_normalized = language.strip().capitalize()

    # 1. Format input DataFrame strictly in exact feature order
    feature_row = [float(metrics.get(feat, 0.0)) for feat in MODEL_FEATURES]
    input_df = pd.DataFrame([feature_row], columns=MODEL_FEATURES)

    # 2. Model Probability Calculation
    probabilities = model.predict_proba(input_df)[0]
    classes = list(model.classes_)

    if 1 in classes:
        defect_idx = classes.index(1)
        ml_defect_prob = float(probabilities[defect_idx])
    else:
        ml_defect_prob = 0.0

    # 3. Static Risk Score Calculation
    static_risk = calculate_static_risk_score(issues)

    # If critical syntax or compilation errors exist, code is definitively defective
    has_critical_error = any(issue.get("severity") == "Critical" for issue in issues)

    # 4. Multi-Language Validation Status
    # NASA MDP datasets (CM1, JM1, KC1, KC2, PC1) are C/C++ avionics software
    if lang_normalized in ("C", "Cpp", "C++"):
        validation_status = "Directly Validated"
        compatibility_note = (
            "Direct NASA Model Alignment: The Random Forest model was trained on NASA MDP "
            "C/C++ flight software datasets. Feature metrics and failure distributions directly align."
        )
    elif lang_normalized == "Java":
        validation_status = "Metric Approximation"
        compatibility_note = (
            "Cross-Language Metric Approximation: Software metrics (LOC, Halstead, McCabe) "
            "are compatible, but Java object-oriented constructs (inheritance, GC) differ from "
            "NASA C datasets. ML prediction is an estimated heuristic supplemented by static analysis."
        )
    elif lang_normalized == "Python":
        validation_status = "Metric Approximation"
        compatibility_note = (
            "Cross-Language Metric Approximation: Dynamic typing and high-level standard libraries "
            "in Python alter typical Halstead/McCabe distributions compared to NASA C datasets. "
            "ML defect probability should be evaluated alongside AST & Flake8 findings."
        )
    else:
        validation_status = "Experimental"
        compatibility_note = "Experimental Metric Evaluation."

    # 5. Hybrid Composite Probability
    # 70% ML Model Probability + 30% Static Code Risk (with critical override)
    if has_critical_error:
        final_probability = 1.0
        prediction_result = "DEFECTIVE"
    else:
        final_probability = (ml_defect_prob * 0.70) + ((static_risk / 100.0) * 0.30)
        final_probability = min(max(final_probability, 0.0), 1.0)
        prediction_result = "DEFECTIVE" if final_probability >= threshold else "NON-DEFECTIVE"

    # 6. Overall Software Health Score (0-100, where 100 is cleanest)
    health_score = max(0.0, round(100.0 - (final_probability * 100.0), 1))

    return {
        "prediction_result": prediction_result,
        "final_probability": round(final_probability, 4),
        "ml_probability": round(ml_defect_prob, 4),
        "static_risk_score": static_risk,
        "health_score": health_score,
        "threshold_used": threshold,
        "validation_status": validation_status,
        "compatibility_note": compatibility_note,
        "input_features": dict(zip(MODEL_FEATURES, feature_row)),
        "has_critical_error": has_critical_error
    }
