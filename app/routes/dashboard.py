from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
import database as db
from app.services.ml_service import NASA_DATASETS_INFO, MODEL_BENCHMARKS, THRESHOLD_ANALYSIS_DATA

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.dashboard"))
    return redirect(url_for("auth.login"))


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    stats = db.get_user_stats(current_user.id)
    recent_analyses = db.get_user_analyses(current_user.id, limit=5)
    recent_predictions = db.get_user_predictions(current_user.id, limit=5)
    conn_info = db.get_connection_info()

    return render_template(
        "dashboard.html",
        stats=stats,
        recent_analyses=recent_analyses,
        recent_predictions=recent_predictions,
        conn_info=conn_info
    )


@dashboard_bp.route("/history")
@login_required
def history():
    analyses = db.get_user_analyses(current_user.id, limit=100)
    predictions = db.get_user_predictions(current_user.id, limit=100)
    return render_template("history.html", analyses=analyses, predictions=predictions)


@dashboard_bp.route("/history/delete/<analysis_id>", methods=["POST"])
@login_required
def delete_history_item(analysis_id):
    ok = db.delete_analysis(analysis_id, user_id=current_user.id, is_admin=current_user.is_admin)
    if ok:
        flash(f"Analysis #{analysis_id} deleted successfully.", "success")
    else:
        flash(f"Could not delete analysis #{analysis_id}.", "danger")
    return redirect(url_for("dashboard.history"))


@dashboard_bp.route("/analytics")
@login_required
def analytics():
    stats = db.get_user_stats(current_user.id)
    reports = db.get_reports_for_user(current_user.id)
    return render_template(
        "analytics.html",
        stats=stats,
        reports=reports,
        datasets_info=NASA_DATASETS_INFO,
        model_benchmarks=MODEL_BENCHMARKS,
        threshold_curve=THRESHOLD_ANALYSIS_DATA
    )
