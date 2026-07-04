from __future__ import annotations

import re
import uuid
from typing import Dict, List, Optional, Sequence, Tuple

import gspread
import pandas as pd
import streamlit as st

from config import (
    ATTENDANCE_HEADERS,
    ATTENDANCE_SHEET,
    DEFAULT_ALLOWED_RADIUS_M,
    REPORTS_HEADERS,
    REPORTS_SHEET,
    SETTINGS_HEADERS,
    SETTINGS_SHEET,
    STAFF_HEADERS,
    STAFF_SHEET,
    STUDENT_HEADERS,
    STUDENTS_SHEET,
    SETTING_ALLOWED_RADIUS_M,
    SETTING_COLLEGE_LATITUDE,
    SETTING_COLLEGE_LONGITUDE,
    SETTING_COLLEGE_NAME,
)
from utils import now_ist, safe_json_dumps, safe_json_loads, safe_strip, timestamp_str, today_str


def _service_account_dict() -> dict:
    if "gcp_service_account" in st.secrets:
        return dict(st.secrets["gcp_service_account"])
    if "gcp" in st.secrets:
        return dict(st.secrets["gcp"])
    if "google_service_account" in st.secrets:
        return dict(st.secrets["google_service_account"])
    raise RuntimeError(
        "Missing Google service account config in Streamlit secrets. "
        "Use [gcp_service_account] in .streamlit/secrets.toml"
    )


def _spreadsheet_id() -> str:
    for key in ("google_sheet_id", "sheet_id", "spreadsheet_id"):
        if key in st.secrets:
            raw = str(st.secrets[key]).strip()
            if not raw:
                break
            m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", raw)
            if m:
                return m.group(1)
            return raw
    raise RuntimeError("Missing google_sheet_id in Streamlit secrets.")


@st.cache_resource(show_spinner=False)
def get_client() -> gspread.Client:
    return gspread.service_account_from_dict(_service_account_dict())


@st.cache_resource(show_spinner=False)
def get_workbook():
    return get_client().open_by_key(_spreadsheet_id())


def _headers_for(sheet_name: str) -> List[str]:
    return {
        STUDENTS_SHEET: STUDENT_HEADERS,
        STAFF_SHEET: STAFF_HEADERS,
        ATTENDANCE_SHEET: ATTENDANCE_HEADERS,
        REPORTS_SHEET: REPORTS_HEADERS,
        SETTINGS_SHEET: SETTINGS_HEADERS,
    }[sheet_name]


def _worksheet(name: str):
    wb = get_workbook()
    try:
        return wb.worksheet(name)
    except gspread.WorksheetNotFound:
        return wb.add_worksheet(title=name, rows="2000", cols="30")


def ensure_structure() -> None:
    ws_map = {
        STUDENTS_SHEET: STUDENT_HEADERS,
        STAFF_SHEET: STAFF_HEADERS,
        ATTENDANCE_SHEET: ATTENDANCE_HEADERS,
        REPORTS_SHEET: REPORTS_HEADERS,
        SETTINGS_SHEET: SETTINGS_HEADERS,
    }
    wb = get_workbook()
    for sheet_name, headers in ws_map.items():
        try:
            ws = wb.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            ws = wb.add_worksheet(title=sheet_name, rows="2000", cols=str(max(20, len(headers) + 2)))
        existing = ws.row_values(1)
        if not existing:
            ws.update("A1", [headers])


def _sheet_df(sheet_name: str) -> pd.DataFrame:
    ws = _worksheet(sheet_name)
    rows = ws.get_all_records()
    if not rows:
        return pd.DataFrame(columns=_headers_for(sheet_name))
    df = pd.DataFrame(rows)
    headers = _headers_for(sheet_name)
    for col in headers:
        if col not in df.columns:
            df[col] = None
    return df[headers]


def _append_row(sheet_name: str, row: Sequence) -> None:
    _worksheet(sheet_name).append_row(list(row), value_input_option="USER_ENTERED")


def _update_row(sheet_name: str, row_index: int, values: List[str]) -> None:
    ws = _worksheet(sheet_name)
    if len(values) <= 26:
        end_col = chr(64 + len(values))
        ws.update(f"A{row_index}:{end_col}{row_index}", [values])
    else:
        ws.update(f"A{row_index}", [values])


def _find_row_by_key(sheet_name: str, key_col: str, key_value: str) -> Optional[int]:
    ws = _worksheet(sheet_name)
    values = ws.get_all_values()
    if not values:
        return None
    header = values[0]
    if key_col not in header:
        return None
    idx = header.index(key_col)
    for i, row in enumerate(values[1:], start=2):
        if idx < len(row) and safe_strip(row[idx]) == safe_strip(key_value):
            return i
    return None


def get_settings() -> Dict[str, str]:
    df = _sheet_df(SETTINGS_SHEET)
    result: Dict[str, str] = {}
    if df.empty:
        return result
    for _, row in df.iterrows():
        key = safe_strip(row.get("key"))
        value = safe_strip(row.get("value"))
        if key:
            result[key] = value
    return result


def upsert_setting(key: str, value: str) -> None:
    row_idx = _find_row_by_key(SETTINGS_SHEET, "key", key)
    data_row = [key, value, timestamp_str()]
    if row_idx:
        _update_row(SETTINGS_SHEET, row_idx, data_row)
    else:
        _append_row(SETTINGS_SHEET, data_row)


def create_default_settings_if_missing() -> None:
    existing = get_settings()
    defaults = {
        SETTING_COLLEGE_NAME: "Anna University",
        SETTING_COLLEGE_LATITUDE: "13.0827",
        SETTING_COLLEGE_LONGITUDE: "80.2707",
        SETTING_ALLOWED_RADIUS_M: "100",
    }
    for key, value in defaults.items():
        if not existing.get(key):
            upsert_setting(key, value)


def students_df() -> pd.DataFrame:
    return _sheet_df(STUDENTS_SHEET)


def staff_df() -> pd.DataFrame:
    return _sheet_df(STAFF_SHEET)


def attendance_df() -> pd.DataFrame:
    return _sheet_df(ATTENDANCE_SHEET)


def reports_df() -> pd.DataFrame:
    return _sheet_df(REPORTS_SHEET)


def get_student_by_username(username: str) -> Optional[Dict]:
    df = students_df()
    if df.empty:
        return None
    hit = df[df["username"].astype(str).str.lower() == safe_strip(username).lower()]
    if hit.empty:
        return None
    return hit.iloc[0].to_dict()


def get_staff_by_username(username: str) -> Optional[Dict]:
    df = staff_df()
    if df.empty:
        return None
    hit = df[df["username"].astype(str).str.lower() == safe_strip(username).lower()]
    if hit.empty:
        return None
    return hit.iloc[0].to_dict()


def upsert_student(record: Dict) -> None:
    student_id = safe_strip(record.get("student_id"))
    row = [
        student_id,
        safe_strip(record.get("name")),
        safe_strip(record.get("department")),
        safe_strip(record.get("username")).lower(),
        safe_strip(record.get("password_hash")),
        safe_strip(record.get("face_embedding")),
        safe_strip(record.get("face_reference_updated_at")),
        safe_strip(record.get("active", "TRUE")),
        safe_strip(record.get("allowed_latitude")),
        safe_strip(record.get("allowed_longitude")),
        safe_strip(record.get("allowed_radius_m", "100")),
        safe_strip(record.get("created_at", timestamp_str())),
        safe_strip(record.get("updated_at", timestamp_str())),
    ]
    row_idx = _find_row_by_key(STUDENTS_SHEET, "student_id", student_id)
    if row_idx:
        _update_row(STUDENTS_SHEET, row_idx, row)
    else:
        _append_row(STUDENTS_SHEET, row)


def upsert_staff(record: Dict) -> None:
    staff_id = safe_strip(record.get("staff_id"))
    row = [
        staff_id,
        safe_strip(record.get("name")),
        safe_strip(record.get("department")),
        safe_strip(record.get("username")).lower(),
        safe_strip(record.get("password_hash")),
        safe_strip(record.get("role", "staff")),
        safe_strip(record.get("active", "TRUE")),
        safe_strip(record.get("created_at", timestamp_str())),
        safe_strip(record.get("updated_at", timestamp_str())),
    ]
    row_idx = _find_row_by_key(STAFF_SHEET, "staff_id", staff_id)
    if row_idx:
        _update_row(STAFF_SHEET, row_idx, row)
    else:
        _append_row(STAFF_SHEET, row)


def save_face_embedding(student_id: str, embedding: List[float]) -> None:
    df = students_df()
    hit = df[df["student_id"].astype(str) == safe_strip(student_id)]
    if hit.empty:
        raise ValueError("Student not found")
    row = hit.iloc[0].to_dict()
    row["face_embedding"] = safe_json_dumps([float(x) for x in embedding])
    row["face_reference_updated_at"] = timestamp_str()
    row["updated_at"] = timestamp_str()
    upsert_student(row)


def get_student_face_embedding(student_id: str) -> Optional[List[float]]:
    df = students_df()
    if df.empty:
        return None
    hit = df[df["student_id"].astype(str) == safe_strip(student_id)]
    if hit.empty:
        return None
    raw = safe_strip(hit.iloc[0].get("face_embedding"))
    data = safe_json_loads(raw, default=None)
    if isinstance(data, list):
        return [float(x) for x in data]
    return None


def attendance_exists(student_id: str, date_value: str) -> bool:
    df = attendance_df()
    if df.empty:
        return False
    hit = df[
        (df["student_id"].astype(str) == safe_strip(student_id))
        & (df["date"].astype(str) == safe_strip(date_value))
    ]
    return not hit.empty


def add_attendance(record: Dict) -> bool:
    student_id = safe_strip(record.get("student_id"))
    date_value = safe_strip(record.get("date", today_str()))
    if attendance_exists(student_id, date_value):
        return False

    row = [
        safe_strip(record.get("attendance_id", str(uuid.uuid4()))),
        date_value,
        safe_strip(record.get("time", now_ist().strftime("%H:%M:%S"))),
        student_id,
        safe_strip(record.get("name")),
        safe_strip(record.get("department")),
        safe_strip(record.get("status", "Present")),
        safe_strip(record.get("latitude")),
        safe_strip(record.get("longitude")),
        safe_strip(record.get("distance_m")),
        safe_strip(record.get("marked_by")),
        safe_strip(record.get("device_info")),
        safe_strip(record.get("face_score")),
        safe_strip(record.get("location_status")),
        safe_strip(record.get("notes")),
        safe_strip(record.get("created_at", timestamp_str())),
    ]
    _append_row(ATTENDANCE_SHEET, row)
    return True


def mark_absent(student_id: str, name: str, department: str, marked_by: str, notes: str = "Marked absent by staff") -> bool:
    return add_attendance(
        {
            "student_id": student_id,
            "name": name,
            "department": department,
            "status": "Absent",
            "marked_by": marked_by,
            "notes": notes,
            "location_status": "staff_marked_absent",
        }
    )


def mark_absent_bulk(rows: List[Dict], marked_by: str) -> Tuple[int, int]:
    success = 0
    skipped = 0
    for item in rows:
        ok = mark_absent(
            student_id=item.get("student_id", ""),
            name=item.get("name", ""),
            department=item.get("department", ""),
            marked_by=marked_by,
        )
        if ok:
            success += 1
        else:
            skipped += 1
    return success, skipped


def get_today_attendance(date_value: str) -> pd.DataFrame:
    df = attendance_df()
    if df.empty:
        return df
    return df[df["date"].astype(str) == safe_strip(date_value)].copy()


def get_daily_status_frame(date_value: str) -> pd.DataFrame:
    students = students_df().copy()
    if students.empty:
        return students

    attendance = get_today_attendance(date_value)
    if attendance.empty:
        students["status"] = "Pending"
        students["time"] = ""
        students["marked_by"] = ""
        students["distance_m"] = ""
        return students

    merged = students.merge(
        attendance[["student_id", "status", "time", "marked_by", "distance_m"]],
        on="student_id",
        how="left",
        suffixes=("", "_att"),
    )
    merged["status"] = merged["status_att"].fillna("Pending")
    merged["time"] = merged["time"].fillna("")
    merged["marked_by"] = merged["marked_by"].fillna("")
    merged["distance_m"] = merged["distance_m"].fillna("")
    return merged.drop(columns=[c for c in ["status_att"] if c in merged.columns])


def get_present_pending_absent(date_value: str):
    frame = get_daily_status_frame(date_value)
    if frame.empty:
        empty = frame.copy()
        return empty, empty, empty
    present = frame[frame["status"].astype(str).str.lower() == "present"].copy()
    pending = frame[frame["status"].astype(str).str.lower() == "pending"].copy()
    absent = frame[frame["status"].astype(str).str.lower() == "absent"].copy()
    return present, pending, absent


def log_report(report_type: str, generated_by: str, date_from: str, date_to: str, department: str, rows: int, notes: str = "") -> None:
    _append_row(
        REPORTS_SHEET,
        [
            str(uuid.uuid4()),
            timestamp_str(),
            generated_by,
            report_type,
            date_from,
            date_to,
            department,
            str(rows),
            notes,
        ],
    )
