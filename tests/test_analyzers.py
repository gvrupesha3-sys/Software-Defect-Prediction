"""
End-to-End Automated Test Suite for Analyzers, ML Predictor, and PDF Generator
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from feature_extractor import extract_software_metrics, MODEL_FEATURES
from analyzers.python_analyzer import analyze_python_code
from analyzers.java_analyzer import analyze_java_code
from analyzers.c_analyzer import analyze_c_code
from ml_predictor import predict_defect, load_defect_model
from report_generator import generate_pdf_report
import code_analyzer


class TestAnalyzersAndML(unittest.TestCase):

    def test_01_feature_extractor_21_metrics(self):
        """Verify feature extractor produces all 21 NASA metrics for Python, Java, and C."""
        py_code = "def add(a, b): return a + b\n"
        java_code = "public class T { public static int add(int a, int b) { return a + b; } }\n"
        c_code = "int add(int a, int b) { return a + b; }\n"

        for lang, src in [("Python", py_code), ("Java", java_code), ("C", c_code)]:
            metrics = extract_software_metrics(src, lang)
            self.assertEqual(len(metrics), 21, f"{lang} metrics count mismatch")
            for feat in MODEL_FEATURES:
                self.assertIn(feat, metrics, f"Missing feature {feat} in {lang}")
                self.assertIsInstance(metrics[feat], float)

    def test_02_python_analyzer(self):
        """Test Python static analysis error and bug detection."""
        bad_code = "x = 10 / 0\n"
        issues, meta = analyze_python_code(bad_code)
        self.assertTrue(any("Division by Zero" in i["issue_type"] for i in issues))

    def test_03_java_analyzer(self):
        """Test Java static analysis rules."""
        java_code = "public class J { void f(String s) { if (s.equals(\"hi\")) {} } }\n"
        issues, meta = analyze_java_code(java_code)
        self.assertTrue(any("Null Pointer Risk" in i["issue_type"] for i in issues))

    def test_04_c_analyzer(self):
        """Test C static analysis rules."""
        c_code = "#include <stdio.h>\nvoid f() { char buf[10]; gets(buf); }\n"
        issues, meta = analyze_c_code(c_code)
        self.assertTrue(any("Buffer Overflow" in i["issue_type"] for i in issues))

    def test_05_ml_predictor(self):
        """Verify Random Forest model loads and outputs probability between 0 and 1."""
        metrics = extract_software_metrics("int main() { int x = 1; return x; }", "C")
        res = predict_defect(metrics, "C")
        self.assertIn("prediction_result", res)
        self.assertIn(res["prediction_result"], ["DEFECTIVE", "NON-DEFECTIVE"])
        self.assertGreaterEqual(res["final_probability"], 0.0)
        self.assertLessEqual(res["final_probability"], 1.0)
        self.assertEqual(res["validation_status"], "Directly Validated")

    def test_06_pdf_report_generation(self):
        """Verify ReportLab PDF generation works and creates valid file."""
        analysis_data = code_analyzer.analyze_source_code(
            source_code="def hello():\n    print('Hello World')\n",
            file_name="hello.py",
            language="Python",
            save_to_db=False
        )
        pdf_path = generate_pdf_report(analysis_data)
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(pdf_path), 1000)
        # Cleanup
        try:
            os.remove(pdf_path)
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
