from __future__ import annotations

from pathlib import Path

APP_TITLE = "Anna University Attendance Portal"
APP_ICON = "🎓"
BASE_DIR = Path(__file__).resolve().parent

# Google Sheets
STUDENTS_SHEET = "Students"
STAFF_SHEET = "Staff"
ATTENDANCE_SHEET = "Attendance"
REPORTS_SHEET = "Reports"
SETTINGS_SHEET = "Settings"

DEFAULT_SHEETS = [
    STUDENTS_SHEET,
    STAFF_SHEET,
    ATTENDANCE_SHEET,
    REPORTS_SHEET,
    SETTINGS_SHEET,
]

# Attendance rules
DEFAULT_ALLOWED_RADIUS_M = 100.0
FACE_MATCH_THRESHOLD = 0.74
MIN_FACE_SIZE = 60  # pixels
MAX_FACE_COUNT = 1

# Academic defaults
DEFAULT_COLLEGE_NAME = "Anna University"
DEFAULT_DEPARTMENT_FILTER = "All Departments"

# Sheet headers
STUDENT_HEADERS = [
    "student_id",
    "name",
    "department",
    "username",
    "password_hash",
    "face_embedding",
    "face_reference_updated_at",
    "active",
    "allowed_latitude",
    "allowed_longitude",
    "allowed_radius_m",
    "created_at",
    "updated_at",
]

STAFF_HEADERS = [
    "staff_id",
    "name",
    "department",
    "username",
    "password_hash",
    "role",
    "active",
    "created_at",
    "updated_at",
]

ATTENDANCE_HEADERS = [
    "attendance_id",
    "date",
    "time",
    "student_id",
    "name",
    "department",
    "status",
    "latitude",
    "longitude",
    "distance_m",
    "marked_by",
    "device_info",
    "face_score",
    "location_status",
    "notes",
    "created_at",
]

REPORTS_HEADERS = [
    "report_id",
    "generated_at",
    "generated_by",
    "report_type",
    "date_from",
    "date_to",
    "department",
    "rows",
    "notes",
]

SETTINGS_HEADERS = [
    "key",
    "value",
    "updated_at",
]

# Settings keys
SETTING_COLLEGE_NAME = "college_name"
SETTING_COLLEGE_LATITUDE = "college_latitude"
SETTING_COLLEGE_LONGITUDE = "college_longitude"
SETTING_ALLOWED_RADIUS_M = "allowed_radius_m"
SETTING_DEFAULT_DEPARTMENT = "default_department"
SETTING_DARK_MODE_DEFAULT = "dark_mode_default"

# UI
SIDEBAR_WIDTH = 320
MAX_HISTORY_ROWS = 5000
