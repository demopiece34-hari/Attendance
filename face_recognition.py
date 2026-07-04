from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np
import streamlit as st
import torch
from facenet_pytorch import InceptionResnetV1

from config import FACE_MATCH_THRESHOLD, MAX_FACE_COUNT
from utils import safe_json_loads

_MP_FACE_DETECTION = mp.solutions.face_detection


@st.cache_resource(show_spinner=False)
def load_embedding_model():
    model = InceptionResnetV1(pretrained="vggface2").eval()
    return model


def _to_rgb(image_bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)


def _crop_face(image_rgb: np.ndarray, bbox: Tuple[int, int, int, int], out_size: int = 160) -> np.ndarray:
    x1, y1, x2, y2 = bbox
    h, w = image_rgb.shape[:2]
    x1 = max(0, min(w - 1, x1))
    y1 = max(0, min(h - 1, y1))
    x2 = max(1, min(w, x2))
    y2 = max(1, min(h, y2))
    crop = image_rgb[y1:y2, x1:x2]
    if crop.size == 0:
        raise ValueError("Face crop is empty.")
    return cv2.resize(crop, (out_size, out_size), interpolation=cv2.INTER_AREA)


def detect_faces(image_bgr: np.ndarray) -> Dict:
    image_rgb = _to_rgb(image_bgr)
    h, w = image_rgb.shape[:2]
    faces = []

    with _MP_FACE_DETECTION.FaceDetection(model_selection=0, min_detection_confidence=0.6) as detector:
        result = detector.process(image_rgb)
        if result.detections:
            for det in result.detections:
                score = float(det.score[0]) if det.score else 0.0
                box = det.location_data.relative_bounding_box
                x1 = int(box.xmin * w)
                y1 = int(box.ymin * h)
                x2 = int((box.xmin + box.width) * w)
                y2 = int((box.ymin + box.height) * h)
                faces.append({"bbox": (x1, y1, x2, y2), "score": score})

    return {
        "count": len(faces),
        "faces": faces,
        "single_face_ok": len(faces) == 1,
        "multi_face": len(faces) > MAX_FACE_COUNT,
    }


def extract_embedding(image_bgr: np.ndarray) -> Dict:
    detection = detect_faces(image_bgr)
    if detection["count"] == 0:
        return {"ok": False, "error": "No face detected.", "embedding": None, "detection": detection}
    if detection["count"] > 1:
        return {"ok": False, "error": "Multiple faces detected. Only one face is allowed.", "embedding": None, "detection": detection}

    bbox = detection["faces"][0]["bbox"]
    image_rgb = _to_rgb(image_bgr)
    face_chip = _crop_face(image_rgb, bbox, out_size=160)

    face = torch.from_numpy(face_chip).permute(2, 0, 1).float() / 255.0
    face = (face - 0.5) / 0.5
    face = face.unsqueeze(0)

    model = load_embedding_model()
    with torch.no_grad():
        emb = model(face).cpu().numpy()[0].astype(float).tolist()

    return {
        "ok": True,
        "error": None,
        "embedding": emb,
        "detection": detection,
        "bbox": bbox,
        "face_score": detection["faces"][0]["score"],
    }


def compare_embeddings(reference: List[float], candidate: List[float], threshold: float = FACE_MATCH_THRESHOLD) -> Dict:
    ref = np.asarray(reference, dtype=np.float32)
    cand = np.asarray(candidate, dtype=np.float32)

    if ref.size == 0 or cand.size == 0:
        return {"match": False, "similarity": 0.0, "threshold": threshold}

    ref_norm = np.linalg.norm(ref)
    cand_norm = np.linalg.norm(cand)
    if ref_norm == 0.0 or cand_norm == 0.0:
        return {"match": False, "similarity": 0.0, "threshold": threshold}

    similarity = float(np.dot(ref, cand) / (ref_norm * cand_norm))
    return {
        "match": similarity >= threshold,
        "similarity": similarity,
        "threshold": threshold,
    }


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
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
