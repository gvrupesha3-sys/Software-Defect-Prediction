"""
AI-Based Multi-Language Software Defect Prediction and Source Code Analysis System
Main Application Entrypoint
Integrates SQLite Database, Authentication, Multi-Language Static Analyzers (Python, Java, C),
NASA 21-Metric Machine Learning Defect Prediction (Random Forest), and PDF Report Generation.
"""

import os
import streamlit as st
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Load environment configuration
load_dotenv()

# Project modular imports
import database as db
import authentication as auth
import code_analyzer
import report_generator
import dashboard
from feature_extractor import MODEL_FEATURES

# Initialize database schema on startup
db.init_db()

# =====================================================================
# STREAMLIT PAGE CONFIGURATION
# =====================================================================
st.set_page_config(
    page_title="AI Multi-Language Software Defect Prediction System",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize user session state
auth.init_session()

# Custom Professional Styling
st.markdown("""
<style>
    .main-header {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 0.95rem;
        color: #4B5563;
        margin-bottom: 1.2rem;
    }
    .metric-badge {
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .stButton>button {
        border-radius: 6px;
    }
</style>
""", unsafe_allow_html=True)


# =====================================================================
# AUTHENTICATION GUARD
# =====================================================================
if not auth.is_authenticated():
    auth.render_auth_page()
    st.stop()


# =====================================================================
# AUTHENTICATED USER WORKSPACE
# =====================================================================
user = auth.get_current_user()
user_id = user["user_id"]

# Sidebar Navigation
st.sidebar.markdown("""
    <div style="text-align: center; padding-bottom: 10px;">
        <h3 style="color: #1E3A8A; margin: 0;">🛡️ CodeDefect AI</h3>
        <span style="font-size: 0.78rem; color: #6B7280;">Enterprise Quality & Defect Engine</span>
    </div>
""", unsafe_allow_html=True)

auth.render_sidebar_user_info()

nav_options = [
    "📊 User Dashboard",
    "🔍 New Code Analysis",
    "📜 Analysis History",
    "📑 Generated Reports",
    "👤 User Profile"
]

if auth.is_admin():
    nav_options.append("🛡️ Admin Dashboard")

# Navigation selector
selected_page = st.sidebar.radio(
    "Navigation Menu",
    nav_options,
    index=nav_options.index(st.session_state.current_page) if st.session_state.current_page in nav_options else 0
)
st.session_state.current_page = selected_page

st.sidebar.divider()
st.sidebar.caption("System Status: 🟢 Online | NASA ML Engine Active")


# =====================================================================
# DEFAULT SAMPLE CODE FOR MULTI-LANGUAGE DEMONSTRATION
# =====================================================================
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


# =====================================================================
# PAGE 1: USER DASHBOARD
# =====================================================================
if selected_page == "📊 User Dashboard":
    dashboard.render_user_dashboard(user_id)


# =====================================================================
# PAGE 2: NEW CODE ANALYSIS (FILE UPLOAD & CODE EDITOR)
# =====================================================================
elif selected_page == "🔍 New Code Analysis":
    st.markdown('<div class="main-header">🔍 Multi-Language Source Code Analyzer</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Select programming language, upload source files or type code directly to inspect quality, security, and ML defect likelihood.</div>', unsafe_allow_html=True)

    input_tab1, input_tab2 = st.tabs(["💻 Interactive Code Editor", "📁 File Upload"])

    source_code_input = ""
    target_filename = "untitled_code.py"
    selected_language = "Python"

    # -------------------------------------------------------------
    # METHOD B: DIRECT CODE INPUT
    # -------------------------------------------------------------
    with input_tab1:
        col_c1, col_c2, col_c3 = st.columns([1, 1, 1])
        with col_c1:
            selected_language = st.selectbox(
                "Programming Language",
                ["Python", "Java", "C"],
                key="editor_lang"
            )
        with col_c2:
            target_filename = st.text_input(
                "File Name",
                value=f"sample.{'py' if selected_language == 'Python' else 'java' if selected_language == 'Java' else 'c'}",
                key="editor_fname"
            )
        with col_c3:
            load_sample = st.button("📋 Load Sample Code", use_container_width=True)

        if load_sample or "current_editor_code" not in st.session_state:
            st.session_state.current_editor_code = SAMPLE_CODES.get(selected_language, "")

        code_text = st.text_area(
            "Source Code Input",
            value=st.session_state.current_editor_code,
            height=340,
            key="code_editor_area",
            help="Type or paste your Python, Java, or C source code here."
        )
        source_code_input = code_text

        col_b1, col_b2 = st.columns([1, 4])
        with col_b1:
            clear_btn = st.button("🗑️ Clear Code", use_container_width=True)
            if clear_btn:
                st.session_state.current_editor_code = ""
                st.rerun()

    # -------------------------------------------------------------
    # METHOD A: FILE UPLOAD
    # -------------------------------------------------------------
    with input_tab2:
        uploaded_file = st.file_uploader(
            "Upload Source Code File",
            type=["py", "java", "c", "h"],
            help="Supported formats: Python (.py), Java (.java), C (.c, .h). Max file size: 5MB"
        )
        if uploaded_file is not None:
            # File size validation (limit to 5MB)
            if uploaded_file.size > 5 * 1024 * 1024:
                st.error("❌ File size exceeds 5MB limit. Please upload a smaller source file.")
            else:
                target_filename = uploaded_file.name
                selected_language = code_analyzer.detect_language_from_filename(target_filename)
                try:
                    source_code_input = uploaded_file.getvalue().decode("utf-8")
                    st.success(f"✅ Loaded '{target_filename}' ({len(source_code_input.splitlines())} lines) - Detected Language: **{selected_language}**")
                    with st.expander("Preview Uploaded Code", expanded=True):
                        st.code(source_code_input, language=selected_language.lower())
                except Exception as e:
                    st.error(f"❌ Failed to decode file: {e}")

    # Threshold configuration expander
    with st.expander("⚙️ Advanced Machine Learning Settings", expanded=False):
        decision_threshold = st.slider(
            "Defect Classification Decision Threshold",
            min_value=0.10,
            max_value=0.80,
            value=0.30,
            step=0.05,
            help="Decision boundary for flagging DEFECTIVE vs NON-DEFECTIVE. (NASA notebook optimal F1 threshold: 0.30)"
        )

    # ANALYZE BUTTON
    analyze_submitted = st.button("🚀 Analyze Source Code", type="primary", use_container_width=True)

    if analyze_submitted:
        if not source_code_input.strip():
            st.warning("⚠️ Please provide source code before analyzing.")
        else:
            with st.spinner(f"Analyzing {selected_language} code using AST, compilers, complexity extractors, and Random Forest model..."):
                try:
                    analysis_res = code_analyzer.analyze_source_code(
                        source_code=source_code_input,
                        file_name=target_filename,
                        language=selected_language,
                        user_id=user_id,
                        threshold=decision_threshold,
                        save_to_db=True
                    )
                    st.session_state["latest_analysis"] = analysis_res
                    st.success("✅ Analysis completed and saved to history!")
                except Exception as e:
                    st.error(f"❌ Error during code analysis: {e}")

    # DISPLAY ANALYSIS RESULTS IF AVAILABLE
    if "latest_analysis" in st.session_state and st.session_state["latest_analysis"]:
        res = st.session_state["latest_analysis"]

        st.divider()
        st.markdown("### 📋 Analysis Results")

        # Top summary cards
        r1, r2, r3, r4 = st.columns(4)
        with r1:
            st.metric("Target File", res["file_name"])
        with r2:
            st.metric("Language", res["programming_language"])
        with r3:
            st.metric("Total Lines", res["total_lines"])
        with r4:
            st.metric("Software Health Score", f"{res['health_score']}/100")

        # Machine Learning Defect Prediction Banner
        pred_label = res["prediction_result"]
        prob_pct = res["defect_probability"] * 100.0

        pcol1, pcol2, pcol3 = st.columns([1.5, 1, 1])
        with pcol1:
            if "DEFECTIVE" in pred_label and "NON" not in pred_label:
                st.error(f"### 🔴 PREDICTION: {pred_label}")
            else:
                st.success(f"### 🟢 PREDICTION: {pred_label}")
            st.caption(f"Decision Threshold: {res['threshold_used'] * 100:.0f}%")

        with pcol2:
            st.metric("Composite Defect Probability", f"{prob_pct:.2f}%")
        with pcol3:
            st.metric("Random Forest Pure Probability", f"{res['ml_probability'] * 100:.2f}%")

        # Domain Validation Badge
        st.info(f"**Validation Status:** `{res['validation_status']}` — {res['compatibility_note']}")

        # Download PDF Report Button
        pdf_path = report_generator.generate_pdf_report(res, user_info=user)
        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as pdf_file:
                st.download_button(
                    label="📑 Download Full PDF Audit Report",
                    data=pdf_file,
                    file_name=os.path.basename(pdf_path),
                    mime="application/pdf",
                    use_container_width=True
                )

        # Tabbed Details: Detected Issues, 21 NASA Metrics, Source Code
        tab_issues, tab_metrics, tab_src = st.tabs(["⚠️ Detected Issues & Corrections", "📊 21 NASA Software Metrics", "📄 Source Code"])

        with tab_issues:
            issues = res.get("issues", [])
            if issues:
                st.write(f"**Total Findings:** {len(issues)} issues detected")
                for iss in issues:
                    sev = iss.get("severity", "Medium")
                    line_no = iss.get("line_number") or "N/A"
                    tool = iss.get("tool_name", "Static Analyzer")
                    desc = iss.get("description", "")
                    sol = iss.get("suggested_solution", "")
                    itype = iss.get("issue_type", "General")

                    sev_emoji = {
                        "Critical": "🔴",
                        "High": "🟠",
                        "Medium": "🟡",
                        "Low": "🔵",
                        "Informational": "ℹ️"
                    }.get(sev, "⚠️")

                    with st.expander(f"{sev_emoji} [{sev}] Line {line_no}: {itype} ({tool})"):
                        st.markdown(f"**Description:** {desc}")
                        if sol:
                            st.success(f"💡 **Suggested Fix:** {sol}")
            else:
                st.success("🎉 No static syntax errors, memory leaks, or coding issues detected!")

        with tab_metrics:
            st.write("Exact 21 software features extracted and supplied to the Random Forest model:")
            metrics_dict = res.get("software_metrics", {})
            m_df = pd.DataFrame([
                {"Metric Feature": k, "Value": v}
                for k, v in metrics_dict.items()
            ])
            st.dataframe(m_df, use_container_width=True, hide_index=True)

        with tab_src:
            st.code(res.get("source_code", ""), language=res["programming_language"].lower())


# =====================================================================
# PAGE 3: ANALYSIS HISTORY
# =====================================================================
elif selected_page == "📜 Analysis History":
    st.markdown('<div class="main-header">📜 Personal Analysis History</div>', unsafe_allow_html=True)
    st.caption("Review previous source code inspections, inspect stored metrics, and re-download audit reports.")

    analyses = db.get_user_analyses(user_id, limit=100)

    if analyses:
        history_df = pd.DataFrame(analyses)
        st.write(f"Total analyses on record: **{len(analyses)}**")

        for item in analyses:
            a_id = item["analysis_id"]
            fname = item["file_name"]
            lang = item["programming_language"]
            pred = item["prediction_result"]
            prob = item["defect_probability"]
            dt = item["analysis_date"]
            errs = item["error_count"]
            warns = item["warning_count"]

            prob_str = f"{prob * 100:.1f}%" if prob is not None else "N/A"
            icon = "🔴" if "DEFECTIVE" in pred and "NON" not in pred else "🟢"

            with st.expander(f"{icon} #{a_id} | {fname} ({lang}) — {pred} ({prob_str}) | {dt}"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.write(f"**Errors Flagged:** {errs}")
                    st.write(f"**Warnings:** {warns}")
                with c2:
                    st.write(f"**Lines of Code:** {item['total_lines']}")
                with c3:
                    if st.button(f"🔍 View Full Details #{a_id}", key=f"view_{a_id}"):
                        full_record = db.get_analysis_by_id(a_id, user_id=user_id)
                        if full_record:
                            st.session_state["latest_analysis"] = full_record
                            st.session_state.current_page = "🔍 New Code Analysis"
                            st.rerun()

                del_col, _ = st.columns([1, 4])
                with del_col:
                    if st.button("🗑️ Delete Record", key=f"del_{a_id}"):
                        db.delete_analysis(a_id, user_id=user_id)
                        st.success(f"Record #{a_id} deleted.")
                        st.rerun()
    else:
        st.info("No analysis history found. Run your first analysis from the 'New Code Analysis' menu!")


# =====================================================================
# PAGE 4: GENERATED REPORTS
# =====================================================================
elif selected_page == "📑 Generated Reports":
    st.markdown('<div class="main-header">📑 Generated PDF Audit Reports</div>', unsafe_allow_html=True)
    st.caption("Download and print all previously generated defect prediction PDF audit reports.")

    reports = db.get_reports_for_user(user_id)
    if reports:
        for r in reports:
            rep_path = r["report_path"]
            fname = r["file_name"]
            lang = r["programming_language"]
            pred = r["prediction_result"]
            gen_at = r["generated_at"]

            with st.container():
                rc1, rc2 = st.columns([3, 1])
                with rc1:
                    st.markdown(f"**{fname}** (`{lang}`) — *{pred}* | Generated on: {gen_at}")
                    st.caption(f"Path: `{rep_path}`")
                with rc2:
                    if os.path.exists(rep_path):
                        with open(rep_path, "rb") as f:
                            st.download_button(
                                label="📥 Download PDF",
                                data=f,
                                file_name=os.path.basename(rep_path),
                                mime="application/pdf",
                                key=f"rep_down_{r['report_id']}",
                                use_container_width=True
                            )
                    else:
                        st.caption("File moved/missing on disk")
                st.divider()
    else:
        st.info("No PDF reports generated yet. Analyze code and click 'Download PDF Audit Report' to produce formal reports.")


# =====================================================================
# PAGE 5: USER PROFILE
# =====================================================================
elif selected_page == "👤 User Profile":
    st.markdown('<div class="main-header">👤 User Profile & Workspace Settings</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])
    with col1:
        st.write(f"**Full Name:** {user['full_name']}")
        st.write(f"**Username:** @{user['username']}")
        st.write(f"**Email Address:** {user['email']}")
        st.write(f"**Account Role:** `{user['role'].upper()}`")
        st.write(f"**User ID:** #{user['user_id']}")

    with col2:
        st.info("""
        **Security & Privacy:**
        - Passwords hashed with 12 rounds of Bcrypt.
        - Analysis records are completely isolated per user account.
        - NASA machine learning prediction is performed locally.
        """)


# =====================================================================
# PAGE 6: ADMIN DASHBOARD (ADMINS ONLY)
# =====================================================================
elif selected_page == "🛡️ Admin Dashboard":
    dashboard.render_admin_dashboard()