from __future__ import annotations

from typing import Dict, Optional, Tuple

import pandas as pd
import plotly.express as px

from utils import safe_strip


def summarize_attendance(attendance_df: pd.DataFrame, students_df: pd.DataFrame, date_value: str) -> Dict:
    total = len(students_df)
    day_df = attendance_df[attendance_df["date"].astype(str) == safe_strip(date_value)].copy() if not attendance_df.empty else pd.DataFrame()
    present = int((day_df["status"].astype(str).str.lower() == "present").sum()) if not day_df.empty else 0
    absent = int((day_df["status"].astype(str).str.lower() == "absent").sum()) if not day_df.empty else 0
    pending = max(0, total - present - absent)
    return {
        "total": total,
        "present": present,
        "absent": absent,
        "pending": pending,
    }


def build_status_pie(summary: Dict):
    df = pd.DataFrame(
        [
            {"status": "Present", "count": summary.get("present", 0)},
            {"status": "Absent", "count": summary.get("absent", 0)},
            {"status": "Pending", "count": summary.get("pending", 0)},
        ]
    )
    return px.pie(df, names="status", values="count", hole=0.45, title="Attendance Status Distribution")


def build_department_bar(attendance_df: pd.DataFrame):
    if attendance_df.empty:
        return px.bar(title="Department-wise Attendance")
    df = attendance_df.copy()
    df["status"] = df["status"].astype(str).str.title()
    grouped = df.groupby(["department", "status"], dropna=False).size().reset_index(name="count")
    return px.bar(grouped, x="department", y="count", color="status", barmode="group", title="Department-wise Attendance")


def build_date_trend(attendance_df: pd.DataFrame):
    if attendance_df.empty:
        return px.line(title="Attendance Trend")
    df = attendance_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["day"] = df["date"].dt.date
    grouped = df.groupby(["day", "status"]).size().reset_index(name="count")
    return px.line(grouped, x="day", y="count", color="status", markers=True, title="Attendance Trend")


def export_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")
