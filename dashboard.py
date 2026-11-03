"""
Dashboard Module
Renders interactive User Dashboard and Administrative Dashboard
with real-time metrics, charts, and recent activity logs using Streamlit and Altair.
Integrates MongoDB Atlas statistics and audit logs.
"""

from typing import Any
import streamlit as st
import pandas as pd
import altair as alt
import database as db
from authentication import is_admin


def render_user_dashboard(user_id: Any):
    """Render the primary user analytics dashboard."""
    st.subheader("📊 Software Testing & Analysis Dashboard")
    st.caption("Overview of your source code defect prediction metrics and static audit history.")

    # Show connection notice if MongoDB is disconnected
    conn_info = db.get_connection_info()
    if not conn_info["connected"]:
        st.warning(f"⚠️ **MongoDB Connection Notice:** {conn_info['message']}. Please configure `MONGODB_URI` in `.env` to ensure continuous data persistence.")

    stats = db.get_user_stats(user_id)

    # 1. Metric Cards Row 1: High Level Totals
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Total Analyses", stats["total_analyses"])
    with m2:
        st.metric("Defective Predicted", stats["defective_count"], delta=f"{stats['defective_count']} flagged", delta_color="inverse")
    with m3:
        st.metric("Non-Defective", stats["non_defective_count"])
    with m4:
        st.metric("Critical / High Errors", stats["total_errors"], delta_color="inverse")
    with m5:
        st.metric("Warnings / Notices", stats["total_warnings"])

    # 2. Metric Cards Row 2: Language Distribution
    l1, l2, l3 = st.columns(3)
    with l1:
        st.metric("🐍 Python Analyzed", stats["python_count"])
    with l2:
        st.metric("☕ Java Analyzed", stats["java_count"])
    with l3:
        st.metric("⚡ C Analyzed", stats["c_count"])

    st.divider()

    # 3. Interactive Charts
    if stats["total_analyses"] > 0:
        c1, c2 = st.columns(2)

        with c1:
            st.markdown("##### 🎯 Defect Prediction Distribution")
            pred_df = pd.DataFrame([
                {"Outcome": "Defective", "Count": stats["defective_count"]},
                {"Outcome": "Non-Defective", "Count": stats["non_defective_count"]}
            ])
            chart_pred = alt.Chart(pred_df).mark_arc(innerRadius=45).encode(
                theta=alt.Theta(field="Count", type="quantitative"),
                color=alt.Color(field="Outcome", type="nominal", scale=alt.Scale(domain=["Defective", "Non-Defective"], range=["#EF4444", "#10B981"])),
                tooltip=["Outcome", "Count"]
            ).properties(height=260)
            st.altair_chart(chart_pred, use_container_width=True)

        with c2:
            st.markdown("##### 🌐 Language-Wise Analysis Distribution")
            lang_data = [{"Language": k, "Analyses": v} for k, v in stats["language_distribution"].items()]
            if lang_data:
                lang_df = pd.DataFrame(lang_data)
                chart_lang = alt.Chart(lang_df).mark_bar(cornerRadius=6).encode(
                    x=alt.X("Language:N", title="Language"),
                    y=alt.Y("Analyses:Q", title="Analyses Count"),
                    color=alt.Color("Language:N", scale=alt.Scale(scheme="category10")),
                    tooltip=["Language", "Analyses"]
                ).properties(height=260)
                st.altair_chart(chart_lang, use_container_width=True)
            else:
                st.info("No language distribution data available.")

        # Severity breakdown chart if issues exist
        if stats["severity_distribution"]:
            st.markdown("##### ⚠️ Detected Issues by Severity Level")
            sev_data = [{"Severity": k, "Issues": v} for k, v in stats["severity_distribution"].items()]
            sev_df = pd.DataFrame(sev_data)
            chart_sev = alt.Chart(sev_df).mark_bar().encode(
                x=alt.X("Severity:N", sort=["Critical", "High", "Medium", "Low", "Informational"]),
                y=alt.Y("Issues:Q"),
                color=alt.Color("Severity:N", scale=alt.Scale(
                    domain=["Critical", "High", "Medium", "Low", "Informational"],
                    range=["#DC2626", "#EA580C", "#D97706", "#2563EB", "#6B7280"]
                )),
                tooltip=["Severity", "Issues"]
            ).properties(height=220)
            st.altair_chart(chart_sev, use_container_width=True)

    else:
        st.info("👋 Welcome! You haven't analyzed any source code yet. Click **'New Code Analysis'** in the sidebar to start.")

    st.divider()

    # 4. Recent Analysis Activity Table
    st.markdown("##### 🕒 Recent Code Analyses")
    recent = db.get_user_analyses(user_id, limit=5)
    if recent:
        recent_df = pd.DataFrame(recent)[
            ["analysis_id", "file_name", "programming_language", "prediction_result", "defect_probability", "error_count", "warning_count", "analysis_date"]
        ]
        recent_df["defect_probability"] = recent_df["defect_probability"].apply(lambda p: f"{p * 100:.2f}%" if p is not None else "N/A")
        recent_df.columns = ["ID", "File Name", "Language", "Prediction", "Defect Probability", "Errors", "Warnings", "Date Analyzed"]
        st.dataframe(recent_df, use_container_width=True, hide_index=True)
    else:
        st.caption("No recent analyses recorded.")


def render_admin_dashboard():
    """Render the system administrator dashboard."""
    if not is_admin():
        st.error("⛔ Access Denied: You do not have administrative privileges.")
        return

    st.subheader("🛡️ System Administration & Global Analytics")
    st.caption("Global usage statistics, model performance metrics, MongoDB Atlas status, and user management.")

    # MongoDB Atlas Status Card
    conn_info = db.get_connection_info()
    stat_col1, stat_col2 = st.columns([1, 2])
    with stat_col1:
        if conn_info["connected"]:
            st.success("🟢 **MongoDB Atlas: Connected**")
        else:
            st.error("🔴 **MongoDB Atlas: Disconnected**")
    with stat_col2:
        st.caption(f"Database: `{conn_info['database_name']}` | Cluster URI: `{conn_info['masked_uri']}`")

    st.divider()

    stats = db.get_admin_stats()

    # Top metrics row
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        st.metric("Total Registered Users", stats["total_users"])
    with a2:
        st.metric("Global Analyses Performed", stats["total_analyses"])
    with a3:
        st.metric("Total Defective Flags", stats["total_defective"])
    with a4:
        st.metric("PDF Reports Generated", stats["total_reports"])

    st.divider()

    tab_users, tab_history, tab_logs = st.tabs(["👥 User Directory", "🌐 Global Predictions", "📜 Activity Audit Logs"])

    # Tab 1: User Management Table
    with tab_users:
        users = db.get_all_users()
        if users:
            users_df = pd.DataFrame(users)[["user_id", "full_name", "username", "email", "role", "created_at"]]
            users_df.columns = ["User ID", "Full Name", "Username", "Email", "System Role", "Registration Date"]
            st.dataframe(users_df, use_container_width=True, hide_index=True)
        else:
            st.caption("No registered users found.")

    # Tab 2: Recent Global Activity
    with tab_history:
        recent = stats.get("recent_analyses", [])
        if recent:
            rec_df = pd.DataFrame(recent)
            rec_df["defect_probability"] = rec_df["defect_probability"].apply(lambda p: f"{p * 100:.2f}%" if p is not None else "N/A")
            rec_df.columns = ["Analysis ID", "User ID", "Filename", "Language", "Prediction", "Defect Probability", "Timestamp", "_id", "Username"]
            display_cols = ["Analysis ID", "Username", "Filename", "Language", "Prediction", "Defect Probability", "Timestamp"]
            st.dataframe(rec_df[[c for c in display_cols if c in rec_df.columns]], use_container_width=True, hide_index=True)
        else:
            st.caption("No system analyses recorded yet.")

    # Tab 3: System Activity Logs
    with tab_logs:
        logs = db.get_recent_activity_logs(limit=30)
        if logs:
            logs_df = pd.DataFrame(logs)[["timestamp", "username", "action", "details"]]
            logs_df.columns = ["Timestamp", "Username", "Action", "Details"]
            st.dataframe(logs_df, use_container_width=True, hide_index=True)
        else:
            st.caption("No activity logs recorded yet.")
