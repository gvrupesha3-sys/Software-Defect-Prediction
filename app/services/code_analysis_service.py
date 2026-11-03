"""
Code Analysis Service Layer
Coordinates multi-language static analysis, metric extraction, and report generation.
"""

import os
from typing import Dict, Any, Optional
import code_analyzer
import report_generator
import database as db

SAMPLE_CODES = {
    "Python": '''def calculate_average(numbers):
    total = 0
    for number in numbers:
        total += number

    if len(numbers) > 0:
        return total / len(numbers)
    else:
        return 0

values = [10, 20, 30, 40]
result = calculate_average(values)
print("Average is:", result)
''',
    "Java": '''public class AverageCalculator {
    public static double computeAverage(int[] numbers) {
        if (numbers == null || numbers.length == 0) {
            return 0.0;
        }
        int sum = 0;
        for (int i = 0; i < numbers.length; i++) {
            sum += numbers[i];
        }
        return (double) sum / numbers.length;
    }

    public static void main(String[] args) {
        int[] data = {10, 20, 30, 40};
        System.out.println("Average: " + computeAverage(data));
    }
}
''',
    "C": '''#include <stdio.h>

double compute_average(int arr[], int size) {
    if (size <= 0) {
        return 0.0;
    }
    int sum = 0;
    for (int i = 0; i < size; i++) {
        sum += arr[i];
    }
    return (double) sum / size;
}

int main() {
    int data[] = {10, 20, 30, 40};
    int count = sizeof(data) / sizeof(data[0]);
    double avg = compute_average(data, count);
    printf("Average is: %.2f\\n", avg);
    return 0;
}
'''
}


def analyze_code_payload(
    source_code: str,
    file_name: str,
    language: str,
    user_id: Optional[str] = None,
    threshold: float = 0.30
) -> Dict[str, Any]:
    """Execute complete analysis pipeline and persist to MongoDB."""
    result = code_analyzer.analyze_source_code(
        source_code=source_code,
        file_name=file_name,
        language=language,
        user_id=user_id,
        threshold=threshold,
        save_to_db=(user_id is not None)
    )
    return result


def generate_analysis_pdf(analysis_id: str, user_dict: Optional[dict] = None) -> Optional[str]:
    """Generate or retrieve PDF audit report for given analysis."""
    record = db.get_analysis_by_id(analysis_id, is_admin=True)
    if not record:
        return None

    # Check if report already exists on disk
    reports = record.get("reports", [])
    if reports:
        last_rep = reports[-1].get("report_path")
        if last_rep and os.path.exists(last_rep):
            return last_rep

    # Generate new PDF report
    pdf_path = report_generator.generate_pdf_report(record, user_info=user_dict)
    if pdf_path and os.path.exists(pdf_path):
        db.save_report_record(record.get("user_id"), analysis_id, pdf_path)
        return pdf_path
    return None
