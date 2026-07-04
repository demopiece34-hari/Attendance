from __future__ import annotations

import streamlit as st

from auth import login_user, logout_user
from config import APP_ICON, APP_TITLE
from google_sheets import create_default_settings_if_missing, ensure_structure
from staff_dashboard import render_staff_dashboard
from student_dashboard import render_student_dashboard
from utils import init_session_state, render_notice


def _apply_theme(dark_mode: bool):
    if dark_mode:
        background = "#08111f"
        card = "rgba(13, 24, 43, 0.92)"
        text = "#e5eefc"
        accent = "#7dd3fc"
    else:
        background = "#f3f7ff"
        card = "rgba(255,255,255,0.95)"
        text = "#10203a"
        accent = "#2563eb"

    st.markdown(
        f"""
        <style>
        .stApp {{
            background: radial-gradient(circle at top, {background}, #020617 120%);
            color: {text};
        }}
        .hero-card {{
            padding: 1.25rem 1.4rem;
            border-radius: 24px;
            background: {card};
            border: 1px solid rgba(125,211,252,0.18);
            box-shadow: 0 12px 42px rgba(2,6,23,0.22);
            margin-bottom: 1rem;
            animation: fadeIn 0.55s ease;
        }}
        .hero-title {{
            font-size: 2rem;
            font-weight: 800;
            letter-spacing: 0.2px;
            color: {accent};
        }}
        .hero-subtitle {{
            font-size: 0.95rem;
            opacity: 0.9;
            margin-top: 0.3rem;
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(8px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        section[data-testid="stSidebar"] {{
            background: rgba(2,6,23,0.55);
        }}
        .stMetric, .stDataFrame, div[data-testid="stVerticalBlock"] {{
            border-radius: 18px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _login_screen():
    st.markdown(
        """
        <div class="hero-card">
            <div class="hero-title">Student & Staff Attendance Portal</div>
            <div class="hero-subtitle">Secure face verification, browser GPS validation, and Google Sheets-backed attendance records.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_student, tab_staff = st.tabs(["Student Login", "Staff Login"])

    with tab_student:
        with st.form("student_login"):
            username = st.text_input("Student Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login as Student", type="primary")
        if submitted:
            ok, message = login_user(username, password, "student")
            if ok:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    with tab_staff:
        with st.form("staff_login"):
            username = st.text_input("Staff Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login as Staff", type="primary")
        if submitted:
            ok, message = login_user(username, password, "staff")
            if ok:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    with st.expander("First-time setup / notes"):
        st.write("1. Configure Google Sheets credentials in `.streamlit/secrets.toml`.")
        st.write("2. Open the Google Sheet and share it with the service-account email.")
        st.write("3. Add at least one staff account and one student account from the Manage Users tab after login.")
        st.write("4. For student attendance, enroll a face reference and ensure browser GPS permission is granted.")


def main():
    st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="wide", initial_sidebar_state="expanded")
    init_session_state()
    create_default_settings_if_missing()
    ensure_structure()

    st.sidebar.title("🎓 Attendance Portal")
    st.session_state.dark_mode = st.sidebar.toggle("Dark mode", value=bool(st.session_state.get("dark_mode", True)))
    _apply_theme(st.session_state.dark_mode)

    if st.session_state.get("logged_in"):
        st.sidebar.success(f"{st.session_state.get('name')} • {st.session_state.get('role')}")
        if st.sidebar.button("Logout"):
            logout_user()
            st.rerun()
        render_notice()

        if st.session_state.get("role") == "student":
            render_student_dashboard()
        elif st.session_state.get("role") == "staff":
            render_staff_dashboard()
        else:
            st.error("Unknown role.")
    else:
        render_notice()
        _login_screen()


if __name__ == "__main__":
    main()
