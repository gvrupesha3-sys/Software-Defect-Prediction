"""
ML Service Layer for Software Defect Prediction
Interfaces with ml_predictor and provides dataset statistics and evaluation models.
"""

from typing import Dict, Any, List, Optional
import ml_predictor
from feature_extractor import MODEL_FEATURES

# NASA MDP Representative Sample Presets for Interactive Testing
DATASET_PRESETS = {
    "CM1_sample": {
        "name": "NASA CM1 (Spacecraft Instrument - C)",
        "language": "C",
        "metrics": {
            "loc": 45.0, "cyclomatic_complexity": 8.0, "essential_complexity": 3.0, "design_complexity": 5.0,
            "halstead_total_operators_operands": 142.0, "halstead_volume": 680.5, "halstead_program_length": 142.0,
            "halstead_difficulty": 18.2, "halstead_intelligence": 37.4, "halstead_effort": 12385.1,
            "halstead_bugs": 0.23, "halstead_time": 688.0, "loc_code": 36.0, "loc_comment": 4.0,
            "loc_blank": 5.0, "loc_code_and_comment": 0.0, "unique_operators": 18.0, "unique_operands": 24.0,
            "total_operators": 82.0, "total_operands": 60.0, "branch_count": 15.0
        }
    },
    "JM1_sample": {
        "name": "NASA JM1 (Ground System Flight Simulation - C)",
        "language": "C",
        "metrics": {
            "loc": 112.0, "cyclomatic_complexity": 19.0, "essential_complexity": 9.0, "design_complexity": 11.0,
            "halstead_total_operators_operands": 348.0, "halstead_volume": 1892.4, "halstead_program_length": 348.0,
            "halstead_difficulty": 34.6, "halstead_intelligence": 54.7, "halstead_effort": 65477.0,
            "halstead_bugs": 0.63, "halstead_time": 3637.6, "loc_code": 88.0, "loc_comment": 12.0,
            "loc_blank": 12.0, "loc_code_and_comment": 2.0, "unique_operators": 28.0, "unique_operands": 46.0,
            "total_operators": 204.0, "total_operands": 144.0, "branch_count": 37.0
        }
    },
    "KC1_sample": {
        "name": "NASA KC1 (Storage Management - C++)",
        "language": "C",
        "metrics": {
            "loc": 28.0, "cyclomatic_complexity": 3.0, "essential_complexity": 1.0, "design_complexity": 2.0,
            "halstead_total_operators_operands": 78.0, "halstead_volume": 322.8, "halstead_program_length": 78.0,
            "halstead_difficulty": 11.4, "halstead_intelligence": 28.3, "halstead_effort": 3679.9,
            "halstead_bugs": 0.11, "halstead_time": 204.4, "loc_code": 22.0, "loc_comment": 3.0,
            "loc_blank": 3.0, "loc_code_and_comment": 0.0, "unique_operators": 14.0, "unique_operands": 17.0,
            "total_operators": 45.0, "total_operands": 33.0, "branch_count": 5.0
        }
    },
    "KC2_sample": {
        "name": "NASA KC2 (Science Data Processing - C++)",
        "language": "C",
        "metrics": {
            "loc": 76.0, "cyclomatic_complexity": 14.0, "essential_complexity": 6.0, "design_complexity": 9.0,
            "halstead_total_operators_operands": 230.0, "halstead_volume": 1215.0, "halstead_program_length": 230.0,
            "halstead_difficulty": 25.8, "halstead_intelligence": 47.1, "halstead_effort": 31347.0,
            "halstead_bugs": 0.41, "halstead_time": 1741.5, "loc_code": 59.0, "loc_comment": 8.0,
            "loc_blank": 9.0, "loc_code_and_comment": 1.0, "unique_operators": 22.0, "unique_operands": 38.0,
            "total_operators": 134.0, "total_operands": 96.0, "branch_count": 27.0
        }
    },
    "PC1_sample": {
        "name": "NASA PC1 (Earth Orbiting Satellite - C)",
        "language": "C",
        "metrics": {
            "loc": 19.0, "cyclomatic_complexity": 2.0, "essential_complexity": 1.0, "design_complexity": 1.0,
            "halstead_total_operators_operands": 48.0, "halstead_volume": 194.2, "halstead_program_length": 48.0,
            "halstead_difficulty": 8.5, "halstead_intelligence": 22.8, "halstead_effort": 1650.7,
            "halstead_bugs": 0.06, "halstead_time": 91.7, "loc_code": 14.0, "loc_comment": 2.0,
            "loc_blank": 3.0, "loc_code_and_comment": 0.0, "unique_operators": 11.0, "unique_operands": 13.0,
            "total_operators": 27.0, "total_operands": 21.0, "branch_count": 3.0
        }
    }
}

# Empirical Research Metrics from Project Notebook 01_Data_Inspection_and_Cleaning.ipynb
NASA_DATASETS_INFO = {
    "CM1": {"name": "NASA CM1", "description": "Spacecraft instrument flight software in C", "samples": 498, "features": 22, "defect_rate": "9.6%"},
    "JM1": {"name": "NASA JM1", "description": "Real-time ground flight simulation in C", "samples": 13204, "features": 22, "defect_rate": "19.3%"},
    "KC1": {"name": "NASA KC1", "description": "Storage management ground software in C++", "samples": 2109, "features": 22, "defect_rate": "15.4%"},
    "KC2": {"name": "NASA KC2", "description": "Science data processing ground software in C++", "samples": 522, "features": 22, "defect_rate": "20.5%"},
    "PC1": {"name": "NASA PC1", "description": "Earth orbiting satellite flight software in C", "samples": 1109, "features": 22, "defect_rate": "6.9%"},
    "Combined": {"name": "Combined Cleaned Dataset", "description": "Unified and deduplicated NASA MDP corpus", "samples": 11891, "features": 23, "defect_rate": "21.4% (2,542 defective / 9,349 clean)"}
}

MODEL_BENCHMARKS = [
    {
        "model_name": "Random Forest (Tuned Threshold 0.30)",
        "accuracy": 75.07,
        "precision": 42.28,
        "recall": 45.19,
        "f1_score": 43.68,
        "is_active": True,
        "notes": "Optimal operational balance between precision and defect recall"
    },
    {
        "model_name": "Random Forest (Default Threshold 0.50)",
        "accuracy": 79.15,
        "precision": 53.71,
        "recall": 18.47,
        "f1_score": 27.49,
        "is_active": False,
        "notes": "High accuracy but misses 81% of defective modules due to class imbalance"
    },
    {
        "model_name": "Logistic Regression",
        "accuracy": 71.58,
        "precision": 37.67,
        "recall": 50.10,
        "f1_score": 43.00,
        "is_active": False,
        "notes": "Linear decision boundary baseline"
    },
    {
        "model_name": "Decision Tree (CART)",
        "accuracy": 64.65,
        "precision": 32.71,
        "recall": 61.69,
        "f1_score": 42.75,
        "is_active": False,
        "notes": "Prone to high variance and false positives"
    }
]

THRESHOLD_ANALYSIS_DATA = [
    {"threshold": 0.20, "accuracy": 63.26, "precision": 32.50, "recall": 66.60, "f1": 43.69},
    {"threshold": 0.25, "accuracy": 70.74, "precision": 37.62, "recall": 55.80, "f1": 44.94},
    {"threshold": 0.30, "accuracy": 75.07, "precision": 42.28, "recall": 45.19, "f1": 43.68},
    {"threshold": 0.35, "accuracy": 77.72, "precision": 47.51, "recall": 39.29, "f1": 43.01},
    {"threshold": 0.40, "accuracy": 78.86, "precision": 50.99, "recall": 30.45, "f1": 38.13},
    {"threshold": 0.45, "accuracy": 79.23, "precision": 53.06, "recall": 25.54, "f1": 34.48},
    {"threshold": 0.50, "accuracy": 79.23, "precision": 54.14, "recall": 19.25, "f1": 28.41}
]


def execute_direct_prediction(metrics: Dict[str, float], language: str, threshold: float = 0.30) -> Dict[str, Any]:
    """Execute prediction directly on metric vector."""
    return ml_predictor.predict_defect(metrics, language=language, issues=[], threshold=threshold)
