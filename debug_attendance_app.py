from __future__ import annotations

import traceback
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

IMPORT_ERRORS: Dict[str, str] = {}
MODULES: Dict[str, Any] = {}

def _try_import(name: str, alias: Optional[str] = None):
    try:
        module = __import__(name, fromlist=["*"])
        MODULES[alias or name] = module
        return module
    except Exception as exc:
        IMPORT_ERRORS[alias or name] = f"{type(exc).__name__}: {exc}"
        return None

config = _try_import("config")
utils = _try_import("utils")
google_sheets = _try_import("google_sheets")
auth = _try_import("auth")
face_recognition = _try_import("face_recognition")
location = _try_import("location")
reports = _try_import("reports")
student_dashboard = _try_import("student_dashboard")
staff_dashboard = _try_import("staff_dashboard")

safe_strip = getattr(utils, "safe_strip", lambda x: "" if x is None else str(x).strip())
safe_float = getattr(utils, "safe_float", lambda x, default=None: default)
normalize_username = getattr(utils, "normalize_username", lambda x: str(x).strip().lower())
now_ist = getattr(utils, "now_ist", lambda: pd.Timestamp.now())
today_str = getattr(utils, "today_str", lambda: pd.Timestamp.now().date().isoformat())

login_user = getattr(auth, "login_user", None)
get_settings = getattr(google_sheets, "get_settings", None)
ensure_structure = getattr(google_sheets, "ensure_structure", None)
create_default_settings_if_missing = getattr(google_sheets, "create_default_settings_if_missing", None)
students_df = getattr(google_sheets, "students_df", None)
staff_df = getattr(google_sheets, "staff_df", None)
attendance_df = getattr(google_sheets, "attendance_df", None)
get_student_by_username = getattr(google_sheets, "get_student_by_username", None)
get_staff_by_username = getattr(google_sheets, "get_staff_by_username", None)
get_student_face_embedding = getattr(google_sheets, "get_student_face_embedding", None)

extract_embedding = getattr(face_recognition, "extract_embedding", None)
image_file_to_bgr = getattr(face_recognition, "image_file_to_bgr", None)
embedding_from_json = getattr(face_recognition, "embedding_from_json", None)
compare_embeddings = getattr(face_recognition, "compare_embeddings", None)

st.set_page_config(page_title="Attendance Debug Console", page_icon="🧪", layout="wide")

st.title("🧪 Attendance System Debug Console")
st.caption("Temporary diagnostic page to identify the first failing step.")

def status(label: str, ok: bool, detail: str = ""):
    icon = "✅" if ok else "❌"
    color = "#16a34a" if ok else "#ef4444"
    st.markdown(f"**<span style='color:{color}'>{icon} {label}</span>**", unsafe_allow_html=True)
    if detail:
        st.caption(detail)

st.subheader("1) Import checks")
if IMPORT_ERRORS:
    for name, err in IMPORT_ERRORS.items():
        status(f"Import failed: {name}", False, err)
else:
    status("All modules imported", True)

st.subheader("2) Google Sheets / settings")
try:
    if callable(get_settings):
        settings = get_settings()
        st.write("Settings keys:", list(settings.keys()))
        st.json(settings)
        status("Settings loaded", True, f"{len(settings)} keys")
    else:
        status("Settings loaded", False, "get_settings() unavailable")
except Exception as exc:
    status("Settings loaded", False, f"{type(exc).__name__}: {exc}")
    st.code(traceback.format_exc())

for label, fn in [("students_df", students_df), ("staff_df", staff_df), ("attendance_df", attendance_df)]:
    try:
        if callable(fn):
            df = fn()
            status(label, True, f"{len(df)} rows / {len(df.columns)} cols")
            st.write(df.head(5))
        else:
            status(label, False, "function unavailable")
    except Exception as exc:
        status(label, False, f"{type(exc).__name__}: {exc}")

st.subheader("3) Init test")
if st.button("Run ensure_structure + create_default_settings_if_missing"):
    try:
        if callable(ensure_structure):
            ensure_structure()
        if callable(create_default_settings_if_missing):
            create_default_settings_if_missing()
        status("Google Sheets init", True, "Structure/settings OK")
    except Exception as exc:
        status("Google Sheets init", False, f"{type(exc).__name__}: {exc}")
        st.code(traceback.format_exc())

st.subheader("4) Login test")
role = st.selectbox("Role", ["student", "staff"])
username = st.text_input("Username / Roll No")
password = st.text_input("Password", type="password")

if st.button("Test login"):
    try:
        uname = normalize_username(username)
        st.write("Normalized username:", repr(uname))
        user = None
        if role == "student" and callable(get_student_by_username):
            user = get_student_by_username(uname)
        elif role == "staff" and callable(get_staff_by_username):
            user = get_staff_by_username(uname)

        if not user:
            status("User lookup", False, "No matching user")
        else:
            status("User lookup", True, "User found")
            st.json(user)
            sheet_password = str(user.get("password_hash", "")).strip()
            st.write("Entered password repr:", repr(password.strip()))
            st.write("Sheet password repr:", repr(sheet_password))
            st.write("Match:", password.strip() == sheet_password)

            if callable(login_user):
                ok, msg = login_user(username, password, role)
                status("login_user()", ok, msg)
            else:
                status("login_user()", False, "login_user unavailable")
    except Exception as exc:
        status("Login test", False, f"{type(exc).__name__}: {exc}")
        st.code(traceback.format_exc())

st.subheader("5) Face test")
camera = st.camera_input("Capture selfie", key="debug_selfie")
if st.button("Run face embedding test") and camera is not None:
    try:
        if callable(image_file_to_bgr) and callable(extract_embedding):
            image_bgr = image_file_to_bgr(camera)
            result = extract_embedding(image_bgr)
            st.json(result)
            status("Face embedding", bool(result.get("ok")), result.get("error") or "OK")
        else:
            status("Face embedding", False, "face helpers unavailable")
    except Exception as exc:
        status("Face embedding", False, f"{type(exc).__name__}: {exc}")
        st.code(traceback.format_exc())

st.subheader("6) Stored embedding test")
if st.button("Check stored face embedding"):
    try:
        if callable(get_student_by_username) and callable(embedding_from_json):
            u = normalize_username(username)
            user = get_student_by_username(u) if u else None
            if not user:
                status("Stored embedding", False, "No user selected")
            else:
                emb = embedding_from_json(user.get("face_embedding", ""))
                status("Stored embedding", emb is not None, f"Length: {len(emb) if emb else 0}")
        else:
            status("Stored embedding", False, "helpers unavailable")
    except Exception as exc:
        status("Stored embedding", False, f"{type(exc).__name__}: {exc}")
        st.code(traceback.format_exc())

st.subheader("7) Attendance preview")
try:
    if callable(attendance_df):
        df = attendance_df()
        st.dataframe(df.head(20), use_container_width=True, hide_index=True)
    else:
        st.warning("attendance_df() unavailable")
except Exception as exc:
    status("Attendance preview", False, f"{type(exc).__name__}: {exc}")
    st.code(traceback.format_exc())

st.caption("Use this file as a temporary main file to isolate the exact failing step.")
