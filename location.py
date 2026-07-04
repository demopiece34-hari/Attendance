from __future__ import annotations

import math
from typing import Optional, Tuple

import folium
import streamlit as st
from streamlit_folium import st_folium


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def location_is_valid(
    student_lat: Optional[float],
    student_lng: Optional[float],
    college_lat: Optional[float],
    college_lng: Optional[float],
    radius_m: float,
) -> Tuple[bool, Optional[float], str]:
    if None in (student_lat, student_lng, college_lat, college_lng):
        return False, None, "missing_location"

    try:
        distance = haversine_m(float(student_lat), float(student_lng), float(college_lat), float(college_lng))
        ok = distance <= float(radius_m)
        return ok, distance, "ok" if ok else "out_of_radius"
    except Exception:
        return False, None, "invalid_location"


def google_maps_link(lat: float, lng: float, label: str = "Current Location") -> str:
    return f"https://www.google.com/maps?q={lat},{lng}({label})"


def render_dual_location_map(
    student_lat: float,
    student_lng: float,
    college_lat: float,
    college_lng: float,
    distance_m: Optional[float] = None,
    zoom_start: int = 17,
) -> None:
    center_lat = (student_lat + college_lat) / 2.0
    center_lng = (student_lng + college_lng) / 2.0
    m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom_start, control_scale=True)

    folium.Marker(
        [college_lat, college_lng],
        tooltip="College",
        popup="College location",
        icon=folium.Icon(color="green", icon="home"),
    ).add_to(m)

    folium.Marker(
        [student_lat, student_lng],
        tooltip="Student",
        popup=f"Student location<br>Distance: {distance_m:.1f} m" if distance_m is not None else "Student location",
        icon=folium.Icon(color="red", icon="user"),
    ).add_to(m)

    folium.PolyLine(
        locations=[[college_lat, college_lng], [student_lat, student_lng]],
        color="blue",
        weight=3,
        opacity=0.8,
    ).add_to(m)

    st_folium(m, width=None, height=420)


def parse_location_pair(lat_value, lng_value):
    try:
        return float(lat_value), float(lng_value)
    except Exception:
        return None, None
