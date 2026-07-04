from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np
import streamlit as st
from insightface.app import FaceAnalysis

from config import FACE_MATCH_THRESHOLD, MAX_FACE_COUNT
from utils import safe_json_loads

MP_FACE_DETECTION = mp.solutions.face_detection


@st.cache_resource(show_spinner=False)
def load_mediapipe_detector():
    return MP_FACE_DETECTION.FaceDetection(
        model_selection=0,
        min_detection_confidence=0.60,
    )


@st.cache_resource(show_spinner=False)
def load_insightface_app():
    app = FaceAnalysis(
        name="buffalo_l",
        providers=["CPUExecutionProvider"],
    )
    app.prepare(ctx_id=1, det_size=(640, 640))
    return app


def _to_rgb(image_bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)


def _to_bgr(image_rgb: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)


def _clip(value: int, lower: int, upper: int) -> int:
    return max(lower, min(upper, value))


def _expand_bbox(
    bbox: Tuple[int, int, int, int],
    image_shape: Tuple[int, int, int],
    padding_ratio: float = 0.35,
) -> Tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    height, width = image_shape[:2]

    face_w = max(1, x2 - x1)
    face_h = max(1, y2 - y1)
    pad_x = int(face_w * padding_ratio)
    pad_y = int(face_h * padding_ratio)

    x1 = _clip(x1 - pad_x, 0, width - 1)
    y1 = _clip(y1 - pad_y, 0, height - 1)
    x2 = _clip(x2 + pad_x, 1, width)
    y2 = _clip(y2 + pad_y, 1, height)

    if x2 <= x1:
        x2 = min(width, x1 + 1)
    if y2 <= y1:
        y2 = min(height, y1 + 1)

    return x1, y1, x2, y2


def _crop_face(image_bgr: np.ndarray, bbox: Tuple[int, int, int, int]) -> np.ndarray:
    x1, y1, x2, y2 = _expand_bbox(bbox, image_bgr.shape, padding_ratio=0.35)
    crop = image_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        raise ValueError("Face crop is empty.")
    return crop


def _bbox_iou(a: Tuple[float, float, float, float], b: Tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)

    denom = area_a + area_b - inter_area
    if denom <= 0:
        return 0.0
    return float(inter_area / denom)


def detect_faces(image_bgr: np.ndarray) -> Dict:
    detector = load_mediapipe_detector()
    image_rgb = _to_rgb(image_bgr)
    height, width = image_rgb.shape[:2]
    faces = []

    result = detector.process(image_rgb)
    if result.detections:
        for det in result.detections:
            score = float(det.score[0]) if det.score else 0.0
            box = det.location_data.relative_bounding_box
            x1 = int(box.xmin * width)
            y1 = int(box.ymin * height)
            x2 = int((box.xmin + box.width) * width)
            y2 = int((box.ymin + box.height) * height)
            faces.append({"bbox": (x1, y1, x2, y2), "score": score})

    return {
        "count": len(faces),
        "faces": faces,
        "single_face_ok": len(faces) == 1,
        "multi_face": len(faces) > MAX_FACE_COUNT,
    }


def _select_best_insightface_result(results, target_bbox: Tuple[int, int, int, int]):
    if not results:
        return None

    if len(results) == 1:
        return results[0]

    best = None
    best_score = -1.0
    for face in results:
        try:
            face_bbox = tuple(float(x) for x in face.bbox.tolist())
        except Exception:
            continue

        iou = _bbox_iou(face_bbox, target_bbox)
        if iou > best_score:
            best_score = iou
            best = face

    return best if best is not None else results[0]


def _normalize_embedding(embedding: np.ndarray) -> List[float]:
    vec = np.asarray(embedding, dtype=np.float32)
    norm = float(np.linalg.norm(vec))
    if norm <= 0.0:
        return vec.astype(float).tolist()
    return (vec / norm).astype(float).tolist()


def extract_embedding(image_bgr: np.ndarray) -> Dict:
    detection = detect_faces(image_bgr)

    if detection["count"] == 0:
        return {"ok": False, "error": "No face detected.", "embedding": None, "detection": detection}

    if detection["count"] > 1:
        return {"ok": False, "error": "Multiple faces detected. Only one face is allowed.", "embedding": None, "detection": detection}

    target_bbox = detection["faces"][0]["bbox"]

    try:
        crop_bgr = _crop_face(image_bgr, target_bbox)
    except Exception as exc:
        return {"ok": False, "error": f"Face crop failed: {exc}", "embedding": None, "detection": detection}

    app = load_insightface_app()
    results = app.get(crop_bgr)
    if not results:
        results = app.get(image_bgr)

    if not results:
        return {"ok": False, "error": "InsightFace could not extract an embedding.", "embedding": None, "detection": detection}

    selected = _select_best_insightface_result(results, target_bbox)
    if selected is None:
        return {"ok": False, "error": "No valid face embedding found.", "embedding": None, "detection": detection}

    raw_embedding = getattr(selected, "normed_embedding", None)
    if raw_embedding is None:
        raw_embedding = getattr(selected, "embedding", None)

    if raw_embedding is None:
        return {"ok": False, "error": "InsightFace returned no embedding vector.", "embedding": None, "detection": detection}

    embedding = _normalize_embedding(np.asarray(raw_embedding, dtype=np.float32))

    return {
        "ok": True,
        "error": None,
        "embedding": embedding,
        "detection": detection,
        "bbox": target_bbox,
        "face_score": float(detection["faces"][0]["score"]),
    }


def compare_embeddings(
    reference: List[float],
    candidate: List[float],
    threshold: float = FACE_MATCH_THRESHOLD,
) -> Dict:
    ref = np.asarray(reference, dtype=np.float32)
    cand = np.asarray(candidate, dtype=np.float32)

    if ref.size == 0 or cand.size == 0:
        return {"match": False, "similarity": 0.0, "threshold": threshold}

    ref_norm = float(np.linalg.norm(ref))
    cand_norm = float(np.linalg.norm(cand))
    if ref_norm <= 0.0 or cand_norm <= 0.0:
        return {"match": False, "similarity": 0.0, "threshold": threshold}

    similarity = float(np.dot(ref, cand) / (ref_norm * cand_norm))
    return {"match": similarity >= threshold, "similarity": similarity, "threshold": threshold}


def embedding_to_json(embedding: List[float]) -> str:
    return "[" + ",".join(f"{float(x):.8f}" for x in embedding) + "]"


def embedding_from_json(value: str) -> Optional[List[float]]:
    data = safe_json_loads(value, default=None)
    if isinstance(data, list):
        return [float(x) for x in data]
    return None


def image_file_to_bgr(uploaded_file) -> np.ndarray:
    import PIL.Image

    image = PIL.Image.open(uploaded_file).convert("RGB")
    rgb = np.array(image)
    return _to_bgr(rgb)
