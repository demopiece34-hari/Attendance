from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

import pandas as pd
import plotly.express as px
import streamlit as st

from config import DEFAULT_ALLOWED_RADIUS_M, SETTING_ALLOWED_RADIUS_M, SETTING_COLLEGE_LATITUDE, SETTING_COLLEGE_LONGITUDE
from face_recognition import extract_embedding, image_file_to_bgr
from google_sheets import (
    add_attendance,
    attendance_df,
    create_default_settings_if_missing,
    get_daily_status_frame,
    get_present_pending_absent,
    get_settings,
    mark_absent_bulk,
    reports_df,
    save_face_embedding,
    staff_df,
    students_df,
    upsert_staff,
    upsert_student,
    log_report,
)
from location import location_is_valid
from reports import build_date_trend, build_department_bar, build_status_pie, export_csv_bytes, summarize_attendance
from utils import current_time_str, get_device_info, hash_password, now_ist, safe_float, safe_json_dumps, safe_strip, timestamp_str, today_str


def _settings():
    settings = get_settings()
    college_lat = safe_float(settings.get(SETTING_COLLEGE_LATITUDE))
    college_lng = safe_float(settings.get(SETTING_COLLEGE_LONGITUDE))
    radius_m = safe_float(settings.get(SETTING_ALLOWED_RADIUS_M), DEFAULT_ALLOWED_RADIUS_M)
    return settings, college_lat, college_lng, radius_m


def _summary_cards(summary: dict):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Students", summary["total"])
    c2.metric("Present", summary["present"])
    c3.metric("Pending", summary["pending"])
    c4.metric("Absent", summary["absent"])


def _user_tag():
    st.markdown(
        f"""
        <div class="hero-card">
            <div class="hero-title">Staff Control Center</div>
            <div class="hero-subtitle">Logged in as {st.session_state.get("name")} • {st.session_state.get("department")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _department_filter():
    df = students_df()
    departments = ["All"] + sorted([d for d in df["department"].dropna().astype(str).unique().tolist() if d])
    return st.sidebar.selectbox("Department", departments, index=0)


def _filtered_students(date_value: str, department_choice: str):
    frame = get_daily_status_frame(date_value)
    if frame.empty:
        return frame
    if department_choice != "All":
        frame = frame[frame["department"].astype(str) == department_choice]
    return frame


def _add_student_form():
    st.markdown("### Enroll / Update Student")
    with st.form("add_student_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            student_id = st.text_input("Student ID")
            name = st.text_input("Student Name")
            department = st.text_input("Department")
            username = st.text_input("Username")
        with c2:
            password = st.text_input("Password", type="password")
            allowed_lat = st.number_input("Allowed Latitude", format="%.6f", value=13.0827)
            allowed_lng = st.number_input("Allowed Longitude", format="%.6f", value=80.2707)
            allowed_radius = st.number_input("Allowed Radius (m)", min_value=10.0, max_value=1000.0, value=100.0, step=10.0)

        camera = st.camera_input("Capture face reference for this student")
        submitted = st.form_submit_button("Save Student", type="primary")

    if submitted:
        if not all([student_id, name, department, username, password]):
            st.error("All student fields are required.")
            return
        face_embedding = ""
        if camera is not None:
            try:
                image_bgr = image_file_to_bgr(camera)
                result = extract_embedding(image_bgr)
                if not result["ok"]:
                    st.error(result["error"])
                    return
                face_embedding = safe_json_dumps(result["embedding"])
            except Exception as exc:
                st.error(f"Face capture failed: {exc}")
                return
        else:
            st.warning("Student saved without face reference. Attendance will fail until a face is enrolled.")

        upsert_student(
            {
                "student_id": student_id,
                "name": name,
                "department": department,
                "username": username,
                "password_hash": hash_password(password),
                "face_embedding": face_embedding,
                "face_reference_updated_at": timestamp_str() if face_embedding else "",
                "active": "TRUE",
                "allowed_latitude": str(allowed_lat),
                "allowed_longitude": str(allowed_lng),
                "allowed_radius_m": str(allowed_radius),
                "created_at": timestamp_str(),
                "updated_at": timestamp_str(),
            }
        )
        st.success("Student saved successfully.")
        st.rerun()


def _add_staff_form():
    st.markdown("### Add Staff")
    with st.form("add_staff_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            staff_id = st.text_input("Staff ID")
            name = st.text_input("Staff Name")
            department = st.text_input("Department")
        with c2:
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            role = st.selectbox("Role", ["staff", "admin"], index=0)
        submitted = st.form_submit_button("Save Staff", type="primary")

    if submitted:
        if not all([staff_id, name, department, username, password]):
            st.error("All staff fields are required.")
            return
        upsert_staff(
            {
                "staff_id": staff_id,
                "name": name,
                "department": department,
                "username": username,
                "password_hash": hash_password(password),
                "role": role,
                "active": "TRUE",
                "created_at": timestamp_str(),
                "updated_at": timestamp_str(),
            }
        )
        st.success("Staff saved successfully.")
        st.rerun()


def render_staff_dashboard():
    create_default_settings_if_missing()
    settings, college_lat, college_lng, radius_m = _settings()

    _user_tag()

    date_value = st.sidebar.date_input("Select date", value=pd.to_datetime(today_str()).date())
    department_choice = _department_filter()

    present, pending, absent = get_present_pending_absent(str(date_value))
    total_students = len(students_df())
    summary = summarize_attendance(attendance_df(), students_df(), str(date_value))
    _summary_cards(summary)

    tab_overview, tab_students, tab_reports, tab_manage = st.tabs(["Overview", "Student Control", "Reports", "Manage Users"])

    with tab_overview:
        st.subheader("Daily Overview")
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(build_status_pie(summary), use_container_width=True)
        with c2:
            day_frame = _filtered_students(str(date_value), department_choice)
            if not day_frame.empty:
                plot_df = day_frame.copy()
                plot_df["status"] = plot_df["status"].astype(str).str.title()
                fig = px.histogram(plot_df, x="status", title="Status Count")
                st.plotly_chart(fig, use_container_width=True)
        st.write(f"College Coordinates: {college_lat}, {college_lng} | Allowed Radius: {radius_m} m")
        st.write(f"Total attendance records today: {len(get_present_pending_absent(str(date_value))[0]) + len(get_present_pending_absent(str(date_value))[1]) + len(get_present_pending_absent(str(date_value))[2])}")

    with tab_students:
        st.subheader("Student List")
        frame = _filtered_students(str(date_value), department_choice)
        if frame.empty:
            st.info("No students available.")
        else:
            st.dataframe(frame, use_container_width=True, hide_index=True)

        pending_df = pending.copy()
        if department_choice != "All" and not pending_df.empty:
            pending_df = pending_df[pending_df["department"].astype(str) == department_choice]

        st.markdown("### Mark Pending Students Absent")
        if pending_df.empty:
            st.info("No pending students.")
        else:
            options = pending_df["student_id"].astype(str).tolist()
            selected = st.multiselect(
                "Select one or more pending students",
                options=options,
                default=[],
                format_func=lambda sid: f"{sid} — {pending_df[pending_df['student_id'].astype(str) == sid].iloc[0]['name']}",
            )
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Select All Pending"):
                    st.session_state["selected_pending_all"] = True
                    st.rerun()
            with col_b:
                if st.button("Mark Selected Absent", type="primary"):
                    rows = []
                    for sid in selected:
                        row = pending_df[pending_df["student_id"].astype(str) == sid].iloc[0].to_dict()
                        rows.append({"student_id": row["student_id"], "name": row["name"], "department": row["department"]})
                    if not rows:
                        st.warning("Select at least one student.")
                    else:
                        ok, skipped = mark_absent_bulk(rows, marked_by=st.session_state.get("username", "staff"))
                        st.success(f"Marked absent: {ok}. Skipped: {skipped}.")
                        st.rerun()

            if st.session_state.pop("selected_pending_all", False):
                rows = [
                    {"student_id": r["student_id"], "name": r["name"], "department": r["department"]}
                    for _, r in pending_df.iterrows()
                ]
                ok, skipped = mark_absent_bulk(rows, marked_by=st.session_state.get("username", "staff"))
                st.success(f"Marked all pending absent: {ok}. Skipped: {skipped}.")
                st.rerun()

    with tab_reports:
        st.subheader("Attendance Reports")
        attendance = attendance_df().copy()
        if attendance.empty:
            st.info("No attendance data available yet.")
        else:
            attendance["date"] = pd.to_datetime(attendance["date"], errors="coerce")
            attendance = attendance.dropna(subset=["date"])
            st.plotly_chart(build_date_trend(attendance.copy()), use_container_width=True)
            st.plotly_chart(build_department_bar(attendance.copy()), use_container_width=True)

            from_date = st.date_input("From Date", value=(pd.to_datetime(today_str()) - pd.Timedelta(days=7)).date(), key="from_date")
            to_date = st.date_input("To Date", value=pd.to_datetime(today_str()).date(), key="to_date")
            filtered = attendance[
                (attendance["date"].dt.date >= from_date)
                & (attendance["date"].dt.date <= to_date)
            ].copy()
            if department_choice != "All":
                filtered = filtered[filtered["department"].astype(str) == department_choice]
            st.dataframe(filtered, use_container_width=True, hide_index=True)

            log_report(
                report_type="attendance_export",
                generated_by=st.session_state.get("username", "staff"),
                date_from=str(from_date),
                date_to=str(to_date),
                department=department_choice,
                rows=len(filtered),
                notes="Generated from staff dashboard",
            )
            st.download_button(
                "Download Report CSV",
                data=export_csv_bytes(filtered),
                file_name=f"attendance_report_{from_date}_{to_date}.csv",
                mime="text/csv",
            )

    with tab_manage:
        st.subheader("User Management")
        st.caption("Use this section to enroll students and create staff accounts.")
        col1, col2 = st.columns(2)
        with col1:
            _add_student_form()
        with col2:
            _add_staff_form()
