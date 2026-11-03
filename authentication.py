"""
Authentication and Session Management Module
Handles user registration, login, logout, password hashing, input validation,
and session state protection for Streamlit.
"""

import re
import streamlit as st
from typing import Optional, Dict, Any, Tuple
import database as db


def init_session():
    """
    Ensure all authentication and navigation session variables are initialized.
    Call this at the very beginning of the app lifecycle.
    """
    if "is_authenticated" not in st.session_state:
        st.session_state.is_authenticated = False
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "username" not in st.session_state:
        st.session_state.username = None
    if "email" not in st.session_state:
        st.session_state.email = None
    if "full_name" not in st.session_state:
        st.session_state.full_name = None
    if "role" not in st.session_state:
        st.session_state.role = None
    if "current_page" not in st.session_state:
        st.session_state.current_page = "Dashboard"
    if "selected_analysis_id" not in st.session_state:
        st.session_state.selected_analysis_id = None


def is_authenticated() -> bool:
    """Check if a user is currently logged in."""
    init_session()
    return st.session_state.is_authenticated and st.session_state.user_id is not None


def is_admin() -> bool:
    """Check if the currently logged-in user is an administrator."""
    init_session()
    return is_authenticated() and st.session_state.role == "admin"


def get_current_user() -> Optional[Dict[str, Any]]:
    """Return current logged in user details dictionary."""
    if not is_authenticated():
        return None
    return {
        "user_id": st.session_state.user_id,
        "username": st.session_state.username,
        "email": st.session_state.email,
        "full_name": st.session_state.full_name,
        "role": st.session_state.role,
    }


def validate_email(email: str) -> bool:
    """Validate email format using standard regex."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email.strip()))


def validate_username(username: str) -> Tuple[bool, str]:
    """Validate username rules: length 3-30, alphanumeric and underscores only."""
    username = username.strip()
    if len(username) < 3:
        return False, "Username must be at least 3 characters long."
    if len(username) > 30:
        return False, "Username must not exceed 30 characters."
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        return False, "Username can only contain letters, numbers, and underscores."
    return True, ""


def validate_password(password: str) -> Tuple[bool, str]:
    """
    Validate password rules:
    At least 8 characters, containing at least one letter and one number.
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not any(c.isalpha() for c in password):
        return False, "Password must include at least one letter."
    if not any(c.isdigit() for c in password):
        return False, "Password must include at least one number."
    return True, ""


def login(identifier: str, password: str) -> Tuple[bool, str]:
    """
    Authenticate user by username or email and plaintext password.
    Returns (success, message).
    """
    identifier = identifier.strip()
    if not identifier or not password:
        return False, "Please enter both username/email and password."

    conn_ok, conn_msg = db.test_connection()
    if not conn_ok:
        return False, f"Database Connection Error: {conn_msg}. Please configure MONGODB_URI in your .env file."

    user = db.get_user_by_identifier(identifier)
    if not user:
        return False, "Invalid username/email or password."

    if not db.verify_password(password, user["password_hash"]):
        return False, "Invalid username/email or password."

    # Successful authentication - populate session state
    st.session_state.is_authenticated = True
    st.session_state.user_id = user["user_id"]
    st.session_state.username = user["username"]
    st.session_state.email = user["email"]
    st.session_state.full_name = user["full_name"]
    st.session_state.role = user["role"]
    st.session_state.current_page = "Dashboard"

    # Log login activity
    db.log_activity(user["user_id"], user["username"], "USER_LOGIN", "User logged in successfully")

    return True, f"Welcome back, {user['full_name']}!"


def logout():
    """Clear session state and log out the user."""
    st.session_state.is_authenticated = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.email = None
    st.session_state.full_name = None
    st.session_state.role = None
    st.session_state.selected_analysis_id = None
    st.session_state.current_page = "Login"
    st.rerun()


def register(full_name: str, email: str, username: str, password: str, confirm_password: str) -> Tuple[bool, str]:
    """
    Validate and register a new user account.
    """
    full_name = full_name.strip()
    email = email.strip().lower()
    username = username.strip()

    if not full_name:
        return False, "Full Name is required."

    is_valid_email = validate_email(email)
    if not is_valid_email:
        return False, "Please enter a valid email address (e.g. name@example.com)."

    user_valid, user_msg = validate_username(username)
    if not user_valid:
        return False, user_msg

    pass_valid, pass_msg = validate_password(password)
    if not pass_valid:
        return False, pass_msg

    if password != confirm_password:
        return False, "Passwords do not match. Please re-enter identical passwords."

    return db.create_user(full_name, email, username, password, role="user")


# =====================================================================
# UI AUTHENTICATION COMPONENTS
# =====================================================================

def render_auth_page():
    """
    Render professional combined Welcome / Login / Registration portal.
    """
    st.markdown("""
        <div style="text-align: center; padding: 20px 0 10px 0;">
            <h1 style="color: #1E3A8A; margin-bottom: 5px;">🛡️ AI-Based Software Defect Prediction System</h1>
            <h4 style="color: #4B5563; font-weight: normal;">
                Multi-Language Source Code Analysis & NASA Machine Learning Quality Engine
            </h4>
        </div>
    """, unsafe_allow_html=True)

    # Check MongoDB Connection
    conn_info = db.get_connection_info()
    if not conn_info["connected"]:
        st.warning(
            f"⚠️ **MongoDB Atlas Not Connected:** {conn_info['message']}\n\n"
            f"👉 Please configure your `MONGODB_URI` in the `.env` file to enable database operations."
        )

    tab_login, tab_register, tab_about = st.tabs(["🔐 Sign In", "📝 Create Account", "ℹ️ About the Platform"])

    # -----------------------------------------------------------------
    # TAB 1: LOGIN
    # -----------------------------------------------------------------
    with tab_login:
        col_pad1, col_center, col_pad2 = st.columns([1, 2, 1])
        with col_center:
            st.markdown("### Access Your Testing Workspace")
            st.caption("Enter your credentials to access static analysis, ML defect prediction, and reports.")

            with st.form("login_form", clear_on_submit=False):
                identifier = st.text_input("Username or Email Address", placeholder="Enter username or email")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                
                submitted = st.form_submit_button("🚀 Sign In to Dashboard", use_container_width=True, type="primary")

                if submitted:
                    success, message = login(identifier, password)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")

            st.info("💡 **Default Admin Account:** Username: `admin` | Password: `Admin@Defect2026!`")

    # -----------------------------------------------------------------
    # TAB 2: REGISTER
    # -----------------------------------------------------------------
    with tab_register:
        col_pad1, col_center, col_pad2 = st.columns([1, 2, 1])
        with col_center:
            st.markdown("### Register New Account")
            st.caption("Create a personalized software testing account to save and track your code analyses.")

            with st.form("register_form", clear_on_submit=False):
                full_name = st.text_input("Full Name", placeholder="e.g. Rupesh Kumar")
                email = st.text_input("Email Address", placeholder="e.g. rupesh@example.com")
                username = st.text_input("Username", placeholder="e.g. rupesh_dev")
                
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    password = st.text_input("Password", type="password", help="At least 8 chars, 1 letter, 1 number")
                with col_p2:
                    confirm_password = st.text_input("Confirm Password", type="password")

                reg_submitted = st.form_submit_button("📝 Register Account", use_container_width=True, type="primary")

                if reg_submitted:
                    success, message = register(full_name, email, username, password, confirm_password)
                    if success:
                        st.success(message)
                        st.info("You can now switch to the 'Sign In' tab above to log into your account.")
                    else:
                        st.error(f"❌ {message}")

    # -----------------------------------------------------------------
    # TAB 3: ABOUT
    # -----------------------------------------------------------------
    with tab_about:
        st.markdown("""
        ### Multi-Language AI-Based Defect Prediction System
        
        This enterprise-grade software quality platform combines **Static Code Analysis** with **NASA Machine Learning Defect Prediction Models** across three primary programming languages:
        
        - 🐍 **Python Analysis:** AST parsing, syntax diagnostics, Radon Halstead & McCabe complexity, Flake8 style & error auditing, Bandit security audits.
        - ☕ **Java Analysis:** javac compilation checks, PMD / Checkstyle / SpotBugs defect inspection, null pointer detection, exception flow audits.
        - ⚡ **C Analysis:** GCC diagnostics, Cppcheck static memory & buffer overflow inspection, Lizard cyclomatic metrics.
        - 📊 **Machine Learning Engine:** Trained on 11,891 NASA software defect records (CM1, JM1, KC1, KC2, PC1) using 21 comprehensive software metrics.
        - 📑 **Comprehensive Reporting:** Automated PDF report generation with detailed line-by-line defect suggestions.
        """)


def render_sidebar_user_info():
    """Render logged-in user summary and logout button in Streamlit sidebar."""
    if is_authenticated():
        st.sidebar.markdown(f"**👤 {st.session_state.full_name}**")
        st.sidebar.caption(f"Role: `{st.session_state.role.upper()}` | User: `@{st.session_state.username}`")
        if st.sidebar.button("🚪 Logout", use_container_width=True):
            logout()
        st.sidebar.divider()
