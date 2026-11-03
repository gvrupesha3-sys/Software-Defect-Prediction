from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.forms import LoginForm, RegisterForm, ProfileForm, ChangePasswordForm
from app.models import User
import database as db

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        ident = form.username_or_email.data.strip()
        pwd = form.password.data
        user_doc = db.get_user_by_identifier(ident)

        if user_doc and db.verify_password(pwd, user_doc.get("password_hash", "")):
            user = User(user_doc)
            login_user(user, remember=form.remember_me.data)
            db.log_activity(user.id, user.username, "USER_LOGIN", "Successful login")
            flash(f"Welcome back, {user.full_name or user.username}!", "success")
            next_page = request.args.get("next")
            return redirect(next_page) if next_page else redirect(url_for("dashboard.dashboard"))
        else:
            flash("Invalid username/email or password. Please try again.", "danger")

    return render_template("login.html", form=form)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        full_name = form.full_name.data.strip()
        username = form.username.data.strip()
        email = form.email.data.strip().lower()
        pwd = form.password.data

        success, msg = db.create_user(
            full_name=full_name,
            email=email,
            username=username,
            password=pwd,
            role="user"
        )
        if success:
            flash("Your account has been created successfully! Please sign in.", "success")
            return redirect(url_for("auth.login"))
        else:
            flash(msg, "danger")

    return render_template("register.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    db.log_activity(current_user.id, current_user.username, "USER_LOGOUT", "User logged out")
    logout_user()
    flash("You have been signed out safely.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    profile_form = ProfileForm(prefix="profile", full_name=current_user.full_name, email=current_user.email)
    pwd_form = ChangePasswordForm(prefix="pwd")

    if request.method == "POST":
        if "profile-submit" in request.form and profile_form.validate_on_submit():
            ok, msg = db.update_user_profile(current_user.id, profile_form.full_name.data, profile_form.email.data)
            if ok:
                flash("Profile details updated successfully.", "success")
                return redirect(url_for("auth.profile"))
            else:
                flash(msg, "danger")

        elif "pwd-submit" in request.form and pwd_form.validate_on_submit():
            user_doc = db.get_user_by_id(current_user.id)
            if user_doc and db.verify_password(pwd_form.current_password.data, user_doc.get("password_hash", "")):
                ok, msg = db.update_user_password(current_user.id, pwd_form.new_password.data)
                if ok:
                    flash("Password changed successfully.", "success")
                    return redirect(url_for("auth.profile"))
                else:
                    flash(msg, "danger")
            else:
                flash("Current password is incorrect.", "danger")

    stats = db.get_user_stats(current_user.id)
    return render_template("profile.html", profile_form=profile_form, pwd_form=pwd_form, stats=stats)
