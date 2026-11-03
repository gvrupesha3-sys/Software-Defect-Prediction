from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
import database as db

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Access Denied: You must be an administrator to view this page.", "danger")
            return redirect(url_for("dashboard.dashboard"))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route("/")
@login_required
@admin_required
def admin_dashboard():
    stats = db.get_admin_stats()
    conn_info = db.get_connection_info()
    logs = db.get_recent_activity_logs(limit=40)
    users = db.get_all_users()
    return render_template(
        "admin.html",
        stats=stats,
        conn_info=conn_info,
        logs=logs,
        users_count=len(users)
    )


@admin_bp.route("/users")
@login_required
@admin_required
def admin_users():
    users = db.get_all_users()
    return render_template("admin_users.html", users=users)


@admin_bp.route("/users/<user_id>/role", methods=["POST"])
@login_required
@admin_required
def change_role(user_id):
    new_role = request.form.get("role")
    if new_role not in ("admin", "user"):
        flash("Invalid role selection.", "danger")
        return redirect(url_for("admin.admin_users"))

    if str(user_id) == str(current_user.id):
        flash("You cannot modify your own administrative role.", "warning")
        return redirect(url_for("admin.admin_users"))

    ok = db.update_user_role(user_id, new_role)
    if ok:
        flash(f"User role updated to '{new_role}'.", "success")
    else:
        flash("Failed to update user role.", "danger")
    return redirect(url_for("admin.admin_users"))


@admin_bp.route("/users/<user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    if str(user_id) == str(current_user.id):
        flash("Security restriction: You cannot delete your own administrative account.", "danger")
        return redirect(url_for("admin.admin_users"))

    ok = db.delete_user(user_id)
    if ok:
        flash(f"User account #{user_id} deleted successfully.", "success")
    else:
        flash("Failed to delete user account.", "danger")
    return redirect(url_for("admin.admin_users"))
