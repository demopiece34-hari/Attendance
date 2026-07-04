from __future__ import annotations

from typing import Optional

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_js_eval import streamlit_js_eval

from config import DEFAULT_ALLOWED_RADIUS_M, SETTING_ALLOWED_RADIUS_M, SETTING_COLLEGE_LATITUDE, SETTING_COLLEGE_LONGITUDE, SETTING_COLLEGE_NAME
from face_recognition import compare_embeddings, embedding_from_json, extract_embedding, image_file_to_bgr
from google_sheets import add_attendance, get_settings, get_student_by_username, get_today_attendance
from location import google_maps_link, location_is_valid, render_dual_location_map
from reports import export_csv_bytes
from utils import current_time_str, get_device_info, safe_float, safe_strip, today_str


def _student_record() -> Optional[dict]:
    username = st.session_state.get("username")
    if not username:
        return None
    return get_student_by_username(username)


def _settings():
    settings = get_settings()
    college_name = settings.get(SETTING_COLLEGE_NAME, "Anna University")
    college_lat = safe_float(settings.get(SETTING_COLLEGE_LATITUDE))
    college_lng = safe_float(settings.get(SETTING_COLLEGE_LONGITUDE))
    radius_m = safe_float(settings.get(SETTING_ALLOWED_RADIUS_M), DEFAULT_ALLOWED_RADIUS_M)
    return college_name, college_lat, college_lng, radius_m


def _browser_location(student_key: str):
    try:
        geo = streamlit_js_eval(
            js_expressions="""
            new Promise((resolve, reject) => {
              if (!navigator.geolocation) {
                reject("Geolocation not supported");
                return;
              }
              navigator.geolocation.getCurrentPosition(
                (pos) => resolve({
                  lat: pos.coords.latitude,
                  lng: pos.coords.longitude,
                  accuracy: pos.coords.accuracy
                }),
                (err) => reject(err.message),
                { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
              );
            })
            """,
            key=f"geo_{student_key}",
        )
        if isinstance(geo, dict) and "lat" in geo and "lng" in geo:
            return float(geo["lat"]), float(geo["lng"]), "browser_geolocation"
    except Exception:
        pass
    return None, None, "unavailable"


def render_student_dashboard():
    student = _student_record()
    if not student:
        st.error("Student profile not found. Please log in again.")
        return

    college_name, college_lat, college_lng, radius_m = _settings()

    st.markdown(
        f"""
        <div class="hero-card">
            <div class="hero-title">Student Attendance Portal</div>
            <div class="hero-subtitle">{college_name} • {student.get('department')} • {student.get('name')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    attendance_today = get_today_attendance(today_str())
    mine = attendance_today[attendance_today["student_id"].astype(str) == str(student.get("student_id"))] if not attendance_today.empty else pd.DataFrame()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Today Status", mine.iloc[0]["status"] if not mine.empty else "Pending")
    c2.metric("Face Enrollment", "Ready" if safe_strip(student.get("face_embedding")) else "Missing")
    c3.metric("Allowed Radius", f"{radius_m:.0f} m")
    c4.metric("Attendance Date", today_str())

    tab_mark, tab_history, tab_profile = st.tabs(["Mark Attendance", "History", "Profile"])

    with tab_mark:
        st.subheader("Mark Attendance")
        st.info("Allow camera and location permissions in your browser.")

        camera = st.camera_input("Capture live face", key="student_camera")
        lat, lng, source = _browser_location(str(student.get("student_id")))

        manual_col1, manual_col2 = st.columns(2)
        with manual_col1:
            manual_lat = st.number_input("Fallback Latitude", value=float(lat or college_lat or 0.0), format="%.6f")
        with manual_col2:
            manual_lng = st.number_input("Fallback Longitude", value=float(lng or college_lng or 0.0), format="%.6f")

        use_manual = st.checkbox("Use fallback coordinates", value=False)
        current_lat = manual_lat if use_manual else lat
        current_lng = manual_lng if use_manual else lng

        if current_lat is not None and current_lng is not None:
            st.success(f"Location acquired: {current_lat:.6f}, {current_lng:.6f} ({source})")
        else:
            st.warning("GPS coordinates are not available yet.")

        if st.button("Verify Face + Location & Mark Attendance", type="primary"):
            if not safe_strip(student.get("face_embedding")):
                st.error("Face reference is missing. Contact staff.")
                return
            if current_lat is None or current_lng is None:
                st.error("Location permission not available.")
                return
            if camera is None:
                st.error("Please capture your face first.")
                return

            try:
                image_bgr = image_file_to_bgr(camera)
                face_result = extract_embedding(image_bgr)
                if not face_result["ok"]:
                    st.error(face_result["error"])
                    return

                stored_embedding = embedding_from_json(student.get("face_embedding"))
                if not stored_embedding:
                    st.error("Stored face embedding is invalid.")
                    return

                match = compare_embeddings(stored_embedding, face_result["embedding"])
                if not match["match"]:
                    st.error(f"Face mismatch. Similarity: {match['similarity']:.3f}")
                    return

                ok, distance_m, location_status = location_is_valid(current_lat, current_lng, college_lat, college_lng, radius_m)
                if not ok:
                    st.error(f"You are outside the allowed radius. Distance: {distance_m:.1f} m")
                    maps_url = google_maps_link(current_lat, current_lng, "Student")
                    st.markdown(f"[Open in Google Maps]({maps_url})")
                    if college_lat is not None and college_lng is not None:
                        render_dual_location_map(current_lat, current_lng, college_lat, college_lng, distance_m=distance_m)
                    return

                added = add_attendance(
                    {
                        "student_id": student.get("student_id"),
                        "name": student.get("name"),
                        "department": student.get("department"),
                        "status": "Present",
                        "latitude": current_lat,
                        "longitude": current_lng,
                        "distance_m": round(distance_m or 0.0, 2),
                        "marked_by": student.get("username"),
                        "device_info": get_device_info(),
                        "face_score": round(float(face_result.get("face_score", 0.0)), 3),
                        "location_status": location_status,
                        "notes": "Marked via student portal",
                    }
                )
                if not added:
                    st.warning("Attendance already marked for today.")
                    return

                st.success(f"Attendance marked successfully at {current_time_str()}.")
                st.balloons()
                if college_lat is not None and college_lng is not None:
                    render_dual_location_map(current_lat, current_lng, college_lat, college_lng, distance_m=distance_m)

            except Exception as exc:
                st.error(f"Failed to mark attendance: {exc}")

    with tab_history:
        st.subheader("Attendance History")
        history = get_today_attendance(today_str())
        if history.empty:
            st.info("No attendance records found for today.")
        else:
            student_history = history[history["student_id"].astype(str) == str(student.get("student_id"))].copy()
            if student_history.empty:
                st.info("No records for this student today.")
            else:
                st.dataframe(student_history, use_container_width=True, hide_index=True)
                st.download_button(
                    "Download My Attendance",
                    data=export_csv_bytes(student_history),
                    file_name=f"attendance_{student.get('student_id')}_{today_str()}.csv",
                    mime="text/csv",
                )
                status_count = student_history["status"].value_counts().reset_index()
                status_count.columns = ["Status", "Count"]
                fig = px.bar(status_count, x="Status", y="Count", title="Today's Status")
                st.plotly_chart(fig, use_container_width=True)

    with tab_profile:
        st.subheader("Profile")
        st.write(f"**Student ID:** {student.get('student_id')}")
        st.write(f"**Name:** {student.get('name')}")
        st.write(f"**Department:** {student.get('department')}")
        st.write(f"**Username:** {student.get('username')}")
        st.write(f"**Allowed Radius:** {student.get('allowed_radius_m')} m")
        st.write(f"**Face Reference Updated:** {student.get('face_reference_updated_at') or 'Not set'}")
        if safe_strip(student.get("face_embedding")):
            st.success("Face reference is enrolled.")
        else:
            st.warning("Face reference is missing.")
