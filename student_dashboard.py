from __future__ import annotations

from typing import Optional, Tuple

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium
from streamlit_js_eval import streamlit_js_eval

from config import (
    DEFAULT_ALLOWED_RADIUS_M,
    SETTING_ALLOWED_RADIUS_M,
    SETTING_COLLEGE_LATITUDE,
    SETTING_COLLEGE_LONGITUDE,
    SETTING_COLLEGE_NAME,
)
from face_recognition import compare_embeddings, embedding_from_json, extract_embedding, image_file_to_bgr
from google_sheets import (
    add_attendance,
    get_settings,
    get_student_by_username,
    get_student_face_embedding,
    get_today_attendance,
    students_df,
)
from location import google_maps_link, location_is_valid, parse_location_pair, render_dual_location_map
from reports import export_csv_bytes
from utils import current_time_str, now_ist, parse_query_float, safe_float, safe_strip, today_str, timestamp_str, get_device_info


def _student_record() -> Optional[dict]:
    username = st.session_state.get("username")
    if not username:
        return None
    return get_student_by_username(username)


def _settings():
    settings = get_settings()
    college_lat = safe_float(settings.get(SETTING_COLLEGE_LATITUDE))
    college_lng = safe_float(settings.get(SETTING_COLLEGE_LONGITUDE))
    radius_m = safe_float(settings.get(SETTING_ALLOWED_RADIUS_M), DEFAULT_ALLOWED_RADIUS_M)
    college_name = settings.get(SETTING_COLLEGE_NAME, "Anna University")
    return college_name, college_lat, college_lng, radius_m


def _get_browser_location(student_id: str):
    lat = parse_query_float("lat")
    lng = parse_query_float("lng")

    if lat is not None and lng is not None:
        return lat, lng, "query_params"

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
            key=f"geo_{student_id}",
        )
        if isinstance(geo, dict) and "lat" in geo and "lng" in geo:
            return float(geo["lat"]), float(geo["lng"]), "browser_geolocation"
    except Exception:
        pass

    return None, None, "unavailable"


def _location_helper_card():
    st.info("Allow location access in your browser. If GPS does not appear, use the manual fallback fields below.")


def _attendance_history(student_id: str):
    df = get_today_attendance(today_str())
    if df.empty:
        return pd.DataFrame()
    return df[df["student_id"].astype(str) == str(student_id)].sort_values(by="created_at", ascending=False)


def _render_profile(student: dict):
    col1, col2 = st.columns([1.2, 1])
    with col1:
        st.markdown("### Profile")
        st.write(f"**Student ID:** {student.get('student_id')}")
        st.write(f"**Name:** {student.get('name')}")
        st.write(f"**Department:** {student.get('department')}")
        st.write(f"**Username:** {student.get('username')}")
        st.write(f"**Allowed Radius:** {student.get('allowed_radius_m')} m")
        st.write(f"**Reference Updated:** {student.get('face_reference_updated_at') or 'Not set'}")
    with col2:
        st.markdown("### Face Reference")
        has_face = bool(safe_strip(student.get("face_embedding")))
        if has_face:
            st.success("Face reference is enrolled.")
        else:
            st.warning("No face reference enrolled yet.")
        st.caption("Staff can enroll or refresh the reference face during student onboarding.")


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

    top1, top2, top3, top4 = st.columns(4)
    today_att = get_today_attendance(today_str())
    student_today = today_att[today_att["student_id"].astype(str) == str(student.get("student_id"))] if not today_att.empty else pd.DataFrame()

    with top1:
        st.metric("Today Status", student_today.iloc[0]["status"] if not student_today.empty else "Pending")
    with top2:
        st.metric("Face Match", "Ready" if safe_strip(student.get("face_embedding")) else "Not Enrolled")
    with top3:
        st.metric("Allowed Radius", f"{radius_m:.0f} m")
    with top4:
        st.metric("Attendance Date", today_str())

    tab_mark, tab_history, tab_profile = st.tabs(["Mark Attendance", "History", "Profile"])

    with tab_mark:
        st.subheader("Mark Attendance")
        _location_helper_card()

        st.markdown("#### Capture live face")
        camera = st.camera_input("Take a live webcam capture", key="student_camera")
        lat, lng, source = _get_browser_location(str(student.get("student_id")))

        manual_col1, manual_col2 = st.columns(2)
        with manual_col1:
            manual_lat = st.number_input("Fallback Latitude", value=float(lat or college_lat or 0.0), format="%.6f")
        with manual_col2:
            manual_lng = st.number_input("Fallback Longitude", value=float(lng or college_lng or 0.0), format="%.6f")

        use_manual = st.checkbox("Use fallback coordinates instead of browser GPS", value=False)
        current_lat = manual_lat if use_manual else lat
        current_lng = manual_lng if use_manual else lng

        if current_lat is not None and current_lng is not None:
            st.success(f"Location acquired: {current_lat:.6f}, {current_lng:.6f} ({source})")
        else:
            st.warning("No GPS coordinates available yet.")

        if college_lat is not None and college_lng is not None:
            st.caption(f"College coordinates: {college_lat:.6f}, {college_lng:.6f}")

        if camera is not None and st.button("Verify Face + Location & Mark Attendance", type="primary"):
            if not safe_strip(student.get("face_embedding")):
                st.error("Your face reference is not enrolled. Contact staff.")
                return
            if current_lat is None or current_lng is None:
                st.error("GPS permission is missing or coordinates are unavailable.")
                return

            try:
                image_bgr = image_file_to_bgr(camera)
                face_result = extract_embedding(image_bgr)
                if not face_result["ok"]:
                    st.error(face_result["error"])
                    return

                stored_embedding = embedding_from_json(student.get("face_embedding"))
                if not stored_embedding:
                    st.error("Stored face reference is invalid or missing.")
                    return

                match = compare_embeddings(stored_embedding, face_result["embedding"])
                if not match["match"]:
                    st.error(f"Face mismatch. Similarity: {match['similarity']:.3f} / {match['threshold']:.2f}")
                    return

                ok, distance_m, location_status = location_is_valid(
                    current_lat,
                    current_lng,
                    college_lat,
                    college_lng,
                    radius_m,
                )

                if not ok:
                    st.error(f"You are outside the allowed radius. Distance from college: {distance_m:.1f} m")
                    st.link_button("Open in Google Maps", google_maps_link(current_lat, current_lng, "Student"))
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
                st.session_state.attendance_refresh += 1
                render_dual_location_map(current_lat, current_lng, college_lat, college_lng, distance_m=distance_m)

            except Exception as exc:
                st.error(f"Failed to mark attendance: {exc}")

        if camera is not None and current_lat is not None and current_lng is not None and college_lat is not None and college_lng is not None:
            ok, distance_m, _ = location_is_valid(current_lat, current_lng, college_lat, college_lng, radius_m)
            st.caption(f"Distance from college: {distance_m:.1f} m" if distance_m is not None else "Distance unavailable")
            if not ok:
                st.warning("Move closer to the college and recheck location.")
                render_dual_location_map(current_lat, current_lng, college_lat, college_lng, distance_m=distance_m)

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

                status_count = student_history["status"].value_counts().reset_index()
                status_count.columns = ["Status", "Count"]
                fig = px.bar(status_count, x="Status", y="Count", title="Today's Status")
                st.plotly_chart(fig, use_container_width=True)

                st.download_button(
                    "Download My Attendance",
                    data=export_csv_bytes(student_history),
                    file_name=f"attendance_{student.get('student_id')}_{today_str()}.csv",
                    mime="text/csv",
                )

    with tab_profile:
        _render_profile(student)
