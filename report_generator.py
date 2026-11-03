"""
Professional PDF Report Generator Module
Uses ReportLab to generate downloadable software quality & defect audit reports.
Includes project metadata, 21 NASA software metrics, detected static issues,
and machine learning defect probabilities.
"""

import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import database as db


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


def generate_pdf_report(
    analysis_data: Dict[str, Any],
    user_info: Optional[Dict[str, Any]] = None,
    output_path: Optional[str] = None
) -> str:
    """
    Generate a professional multi-page software defect audit report.
    Returns the absolute path to the generated PDF.
    """
    analysis_id = analysis_data.get("analysis_id") or "UNSAVED"
    filename = analysis_data.get("file_name", "source_code")
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_name = os.path.splitext(filename)[0]

    if not output_path:
        pdf_filename = f"Defect_Report_ID{analysis_id}_{clean_name}_{timestamp_str}.pdf"
        output_path = os.path.join(REPORTS_DIR, pdf_filename)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1E3A8A'),
        alignment=TA_CENTER
    )
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#4B5563'),
        alignment=TA_CENTER
    )
    h1_style = ParagraphStyle(
        'Heading1Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor('#1E3A8A'),
        spaceBefore=12,
        spaceAfter=6
    )
    cell_style = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#1F2937')
    )
    cell_bold = ParagraphStyle(
        'CellBold',
        parent=cell_style,
        fontName='Helvetica-Bold'
    )
    cell_center = ParagraphStyle(
        'CellCenter',
        parent=cell_style,
        alignment=TA_CENTER
    )

    elements = []

    # 1. Header & Title Banner
    elements.append(Paragraph("🛡️ AI-BASED SOFTWARE DEFECT PREDICTION & CODE AUDIT", title_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("Multi-Language Static Code Analysis & NASA Machine Learning Quality Engine", subtitle_style))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1E3A8A'), spaceAfter=12))

    # 2. Executive Summary Info Table
    user_name = user_info.get("full_name", "Developer / Tester") if user_info else "Developer / Tester"
    user_email = user_info.get("email", "N/A") if user_info else "N/A"
    analysis_date = datetime.now().strftime("%B %d, %Y - %H:%M:%S")

    pred_res = analysis_data.get("prediction_result", "UNKNOWN")
    prob_val = analysis_data.get("defect_probability", 0.0) * 100.0
    lang = analysis_data.get("programming_language", "Python")
    total_loc = analysis_data.get("total_lines", 0)

    summary_table_data = [
        [
            Paragraph("<b>Analysis ID:</b>", cell_style), Paragraph(str(analysis_id), cell_style),
            Paragraph("<b>Target File:</b>", cell_style), Paragraph(filename, cell_bold)
        ],
        [
            Paragraph("<b>Analyst / User:</b>", cell_style), Paragraph(f"{user_name} ({user_email})", cell_style),
            Paragraph("<b>Language:</b>", cell_style), Paragraph(lang, cell_style)
        ],
        [
            Paragraph("<b>Audit Date:</b>", cell_style), Paragraph(analysis_date, cell_style),
            Paragraph("<b>Total Lines:</b>", cell_style), Paragraph(str(total_loc), cell_style)
        ],
        [
            Paragraph("<b>Defect Prediction:</b>", cell_style),
            Paragraph(f"<font color='{'red' if 'DEFECTIVE' in pred_res and 'NON' not in pred_res else 'green'}'><b>{pred_res}</b></font>", cell_style),
            Paragraph("<b>Defect Probability:</b>", cell_style),
            Paragraph(f"<b>{prob_val:.2f}%</b>", cell_style)
        ]
    ]

    summary_table = Table(summary_table_data, colWidths=[100, 170, 90, 180])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 14))

    # 3. Model & Validation Methodology
    elements.append(Paragraph("Machine Learning Model & Domain Validation", h1_style))
    val_status = analysis_data.get("validation_status", "Metric Approximation")
    note = analysis_data.get("compatibility_note", "")
    ml_prob = analysis_data.get("ml_probability", 0.0) * 100.0
    static_risk = analysis_data.get("static_risk_score", 0.0)

    methodology_text = (
        f"<b>Validation Status:</b> {val_status}<br/>"
        f"<b>Random Forest Pure Model Probability:</b> {ml_prob:.2f}% | "
        f"<b>Static Code Risk Factor:</b> {static_risk:.2f}%<br/>"
        f"<b>Scientific Domain Alignment:</b> {note}"
    )
    elements.append(Paragraph(methodology_text, cell_style))
    elements.append(Spacer(1, 14))

    # 4. Detected Issues & Static Code Findings
    issues: List[Dict[str, Any]] = analysis_data.get("issues", [])
    elements.append(Paragraph(f"Static Analysis Findings & Defect Detections ({len(issues)} Issues Found)", h1_style))

    if issues:
        issues_table_data = [
            [
                Paragraph("<b>Line</b>", cell_bold),
                Paragraph("<b>Severity</b>", cell_bold),
                Paragraph("<b>Issue Type</b>", cell_bold),
                Paragraph("<b>Description & Suggested Fix</b>", cell_bold),
                Paragraph("<b>Detector</b>", cell_bold)
            ]
        ]

        sev_colors = {
            "Critical": "#DC2626",
            "High": "#EA580C",
            "Medium": "#D97706",
            "Low": "#2563EB",
            "Informational": "#4B5563"
        }

        for issue in issues[:35]:  # Limit to 35 for readable PDF layout
            line_no = str(issue.get("line_number") or "-")
            sev = issue.get("severity", "Medium")
            s_color = sev_colors.get(sev, "#4B5563")
            itype = issue.get("issue_type", "Warning")
            desc = issue.get("description", "")
            sol = issue.get("suggested_solution", "")
            tool = issue.get("tool_name", "Static Tool")

            desc_block = f"<b>{desc}</b>"
            if sol:
                desc_block += f"<br/><font color='#059669'><i>Fix: {sol}</i></font>"

            issues_table_data.append([
                Paragraph(line_no, cell_center),
                Paragraph(f"<font color='{s_color}'><b>{sev}</b></font>", cell_style),
                Paragraph(itype, cell_style),
                Paragraph(desc_block, cell_style),
                Paragraph(tool, cell_style)
            ])

        issues_table = Table(issues_table_data, colWidths=[35, 65, 100, 270, 70])
        issues_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#94A3B8')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(issues_table)
    else:
        elements.append(Paragraph("✅ <b>Clean Code:</b> No static warnings, security hazards, or syntax issues detected.", cell_style))

    elements.append(Spacer(1, 14))

    # 5. Software Metrics (Exact 21 NASA Features)
    metrics: Dict[str, float] = analysis_data.get("software_metrics", {})
    elements.append(Paragraph("Software Metrics Profile (21 NASA Standard Features)", h1_style))

    metric_items = list(metrics.items())
    half = (len(metric_items) + 1) // 2

    metrics_table_data = [
        [
            Paragraph("<b>Metric Feature</b>", cell_bold), Paragraph("<b>Value</b>", cell_bold),
            Paragraph("<b>Metric Feature</b>", cell_bold), Paragraph("<b>Value</b>", cell_bold)
        ]
    ]

    for i in range(half):
        col1_k, col1_v = metric_items[i]
        if i + half < len(metric_items):
            col2_k, col2_v = metric_items[i + half]
            col2_k_str = col2_k
            col2_v_str = f"{col2_v:.4f}"
        else:
            col2_k_str, col2_v_str = "", ""

        metrics_table_data.append([
            Paragraph(col1_k, cell_style),
            Paragraph(f"{col1_v:.4f}", cell_bold),
            Paragraph(col2_k_str, cell_style),
            Paragraph(col2_v_str, cell_bold)
        ])

    metrics_table = Table(metrics_table_data, colWidths=[170, 100, 170, 100])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(metrics_table)
    elements.append(Spacer(1, 16))

    # 6. Footer Disclaimer
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#6B7280'),
        alignment=TA_CENTER
    )
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CBD5E1'), spaceAfter=6))
    elements.append(Paragraph(
        "Report generated by AI-Based Multi-Language Software Defect Prediction System. "
        "NASA MDP machine learning models indicate statistical defect likelihood; static warnings identify localized syntax/logic risks. "
        "Intended for academic verification and software quality testing.",
        disclaimer_style
    ))

    # Build the PDF document
    doc.build(elements)

    # Record report in database if user_id and analysis_id are available
    if user_info and user_info.get("user_id") and analysis_data.get("analysis_id"):
        db.save_report_record(
            user_id=user_info["user_id"],
            analysis_id=analysis_data["analysis_id"],
            report_path=output_path
        )

    return output_path
