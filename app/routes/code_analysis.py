import os
from flask import Blueprint, render_template, request, flash, send_file, jsonify, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.forms import CodeAnalysisForm
from app.services.code_analysis_service import analyze_code_payload, generate_analysis_pdf, SAMPLE_CODES
import code_analyzer
import database as db

code_analysis_bp = Blueprint("code_analysis", __name__)

@code_analysis_bp.route("/code-analysis", methods=["GET", "POST"])
@login_required
def code_analysis():
    form = CodeAnalysisForm()
    analysis_result = None

    # Handle analysis submission
    if form.validate_on_submit():
        source_code = ""
        file_name = form.file_name.data or "untitled.py"
        language = form.language.data
        threshold = float(form.threshold.data)

        # 1. Check if a file was uploaded
        if form.code_file.data:
            uploaded = form.code_file.data
            safe_name = secure_filename(uploaded.filename)
            file_name = safe_name
            language = code_analyzer.detect_language_from_filename(safe_name)
            try:
                source_code = uploaded.read().decode("utf-8", errors="replace")
            except Exception as e:
                flash(f"Error reading uploaded file: {e}", "danger")
        else:
            source_code = form.source_code.data

        if not source_code or not source_code.strip():
            flash("Please provide source code or upload a source file to analyze.", "warning")
        else:
            try:
                analysis_result = analyze_code_payload(
                    source_code=source_code,
                    file_name=file_name,
                    language=language,
                    user_id=current_user.id,
                    threshold=threshold
                )
                flash(f"Successfully analyzed {file_name} ({language})!", "success")
            except Exception as e:
                flash(f"Error executing code analysis: {e}", "danger")

    # If GET request with view_id, load past analysis from database
    view_id = request.args.get("view_id")
    if view_id and not analysis_result:
        doc = db.get_analysis_by_id(view_id, user_id=current_user.id, is_admin=current_user.is_admin)
        if doc:
            analysis_result = doc

    return render_template(
        "code_analysis.html",
        form=form,
        analysis_result=analysis_result,
        sample_codes=SAMPLE_CODES
    )


@code_analysis_bp.route("/reports/download/<analysis_id>")
@login_required
def download_report(analysis_id):
    """Generate and deliver PDF software defect audit report."""
    user_dict = {
        "user_id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name
    }
    pdf_path = generate_analysis_pdf(analysis_id, user_dict=user_dict)
    if pdf_path and os.path.exists(pdf_path):
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=os.path.basename(pdf_path),
            mimetype="application/pdf"
        )
    flash("Report file could not be generated or located.", "danger")
    return abort(404)


@code_analysis_bp.route("/code-analysis/api/sample/<language>")
@login_required
def get_sample_code_api(language):
    """API to load default sample code dynamically."""
    code = SAMPLE_CODES.get(language.strip().capitalize())
    if code:
        ext = "py" if language.lower() == "python" else "java" if language.lower() == "java" else "c"
        return jsonify({"success": True, "code": code, "filename": f"sample.{ext}"})
    return jsonify({"success": False, "message": "Language sample not available"}), 404
