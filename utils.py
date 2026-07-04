from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import platform
import re
from datetime import datetime
from typing import Any, Optional

import streamlit as st
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger("attendance_app")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


def now_ist() -> datetime:
    return datetime.now(IST)


def today_str() -> str:
    return now_ist().date().isoformat()


def current_time_str() -> str:
    return now_ist().strftime("%H:%M:%S")


def timestamp_str() -> str:
    return now_ist().strftime("%Y-%m-%d %H:%M:%S")


def safe_strip(value: Any) -> str:
    return "" if value is None else str(value).strip()


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def safe_json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def safe_json_loads(value: Any, default: Any = None) -> Any:
    if value in (None, "", "nan"):
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def normalize_username(username: str) -> str:
    username = safe_strip(username).lower()
    username = re.sub(r"\s+", "", username)
    return username


def hash_password(password: str, salt: Optional[str] = None) -> str:
    if salt is None:
        salt = os.urandom(16).hex()
    iterations = 120_000
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return f"pbkdf2_sha256${iterations}${salt}${derived}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algo, iterations, salt, hex_hash = stored_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        ).hex()
        return hmac.compare_digest(derived, hex_hash)
    except Exception:
        return False


def get_device_info() -> str:
    try:
        headers = getattr(st, "context", None)
        if headers and hasattr(st.context, "headers"):
            ua = st.context.headers.get("user-agent", "")
            if ua:
                return ua
    except Exception:
        pass
    return f"{platform.system()} {platform.release()}"


def init_session_state() -> None:
    defaults = {
        "logged_in": False,
        "role": None,
        "user_id": None,
        "username": None,
        "name": None,
        "department": None,
        "dark_mode": True,
        "selected_date": today_str(),
        "last_message": None,
        "attendance_refresh": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_session_user() -> None:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.name = None
    st.session_state.department = None


def set_notice(message: str, level: str = "info") -> None:
    st.session_state.last_message = (level, message)


def render_notice() -> None:
    msg = st.session_state.get("last_message")
    if not msg:
        return
    level, text = msg
    if level == "success":
        st.success(text)
    elif level == "warning":
        st.warning(text)
    elif level == "error":
        st.error(text)
    else:
        st.info(text)
    st.session_state.last_message = None


def make_csv_download_name(prefix: str, date_value: str) -> str:
    return f"{prefix}_{date_value}.csv"


def parse_query_float(name: str) -> Optional[float]:
    try:
        if name not in st.query_params:
            return None
        raw = st.query_params.get(name)
        if isinstance(raw, list):
            raw = raw[0] if raw else None
        return safe_float(raw)
    except Exception:
        return None


def clear_query_params() -> None:
    try:
        st.query_params.clear()
    except Exception:
        pass


def compact_status_badge(text: str, status: str) -> str:
    colors = {
        "success": "#16a34a",
        "warning": "#f59e0b",
        "error": "#ef4444",
        "info": "#3b82f6",
        "neutral": "#64748b",
    }
    color = colors.get(status, colors["neutral"])
    return f"<span style='padding:0.35rem 0.65rem;border-radius:999px;background:{color}22;color:{color};font-weight:700;font-size:0.82rem'>{text}</span>"


def ensure_columns(df, columns):
    for col in columns:
        if col not in df.columns:
            df[col] = None
    return df[columns]
