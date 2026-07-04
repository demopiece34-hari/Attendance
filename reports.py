from __future__ import annotations

from typing import Dict

import pandas as pd
import plotly.express as px

from utils import safe_strip


def summarize_attendance(attendance_df: pd.DataFrame, students_df: pd.DataFrame, date_value: str) -> Dict:
    total = len(students_df)
    day_df = attendance_df[attendance_df["date"].astype(str) == safe_strip(date_value)].copy() if not attendance_df.empty else pd.DataFrame()
    present = int((day_df["status"].astype(str).str.lower() == "present").sum()) if not day_df.empty else 0
    absent = int((day_df["status"].astype(str).str.lower() == "absent").sum()) if not day_df.empty else 0
    pending = max(0, total - present - absent)
    return {"total": total, "present": present, "absent": absent, "pending": pending}


def summarize_date_range(attendance_df: pd.DataFrame, start_date, end_date) -> Dict:
    if attendance_df.empty:
        return {"records": 0, "present": 0, "absent": 0, "pending": 0}
    df = attendance_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    mask = (df["date"].dt.date >= start_date) & (df["date"].dt.date <= end_date)
    df = df[mask]
    return {
        "records": len(df),
        "present": int((df["status"].astype(str).str.lower() == "present").sum()),
        "absent": int((df["status"].astype(str).str.lower() == "absent").sum()),
        "pending": int((df["status"].astype(str).str.lower() == "pending").sum()),
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


def build_weekly_summary(attendance_df: pd.DataFrame):
    if attendance_df.empty:
        return pd.DataFrame(columns=["week", "status", "count"])
    df = attendance_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["week"] = df["date"].dt.to_period("W").astype(str)
    grouped = df.groupby(["week", "status"]).size().reset_index(name="count")
    return grouped


def build_monthly_summary(attendance_df: pd.DataFrame):
    if attendance_df.empty:
        return pd.DataFrame(columns=["month", "status", "count"])
    df = attendance_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["month"] = df["date"].dt.to_period("M").astype(str)
    grouped = df.groupby(["month", "status"]).size().reset_index(name="count")
    return grouped
