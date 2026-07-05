from __future__ import annotations

from typing import Tuple

import streamlit as st

from google_sheets import get_staff_by_username, get_student_by_username
from utils import clear_session_user, normalize_username, verify_password


def login_user(username: str, password: str, role: str) -> Tuple[bool, str]:
    username = normalize_username(username)
    if not username or not password:
        return False, "Username and password are required."

    if role == "student":
        user = get_student_by_username(username)
        if not user:
            return False, "Student account not found."
        if str(user.get("active", "TRUE")).upper() != "TRUE":
            return False, "Student account is disabled."
        sheet_password = str(user.get("password", "")).strip()
        st.write(user)
        st.write("Entered:", password)
        st.write("Sheet:", repr(sheet_password))

        if password == sheet_password:
            st.session_state.logged_in = True
            st.session_state.role = "student"
            st.session_state.user_id = user.get("student_id")
            st.session_state.username = user.get("username")
            st.session_state.name = user.get("name")
            st.session_state.department = user.get("department")
            return True, "Student login successful."

        return False, "Invalid student credentials."

    if role == "staff":
        user = get_staff_by_username(username)
        if not user:
            return False, "Staff account not found."
        if str(user.get("active", "TRUE")).upper() != "TRUE":
            return False, "Staff account is disabled."
        sheet_password = str(user.get("password_hash", "")).strip()

        if password == sheet_password:
            st.session_state.logged_in = True
            st.session_state.role = "staff"
            st.session_state.user_id = user.get("staff_id")
            st.session_state.username = user.get("username")
            st.session_state.name = user.get("name")
            st.session_state.department = user.get("department")
            return True, "Staff login successful."

        return False, "Invalid staff credentials."


def logout_user() -> None:
    clear_session_user()
