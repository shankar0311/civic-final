import json
import logging
from pathlib import Path
from typing import Dict, Optional

from ml_models import road_model_suite
from grok_analysis import (
    analyze_with_grok,
    query_nearby_pois,
    query_traffic_density,
    location_score_from_pois,
    description_score,
)

logger = logging.getLogger("backend")

# AHP weights per proposal
W_VISUAL    = 0.35
W_LOCATION  = 0.20
W_SENTIMENT = 0.25
W_SOCIAL    = 0.20

# YOLO class → visual score
YOLO_CLASS_SCORES = {
    "small_pothole":  0.35,
    "medium_pothole": 0.65,
    "severe_pothole": 1.00,
}


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _severity_level_from_score(score: float) -> str:
    if score >= 75:
        return "critical"
    if score >= 50:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def _load_local_image_bytes(image_url: str, image_bytes: Optional[bytes]) -> Optional[bytes]:
    if image_bytes:
        return image_bytes
    if not image_url or not image_url.startswith("/uploads/"):
        return None
    file_path = Path("uploads") / image_url.replace("/uploads/", "")
    if not file_path.exists():
        logger.warning("Local upload not found for analysis: %s", file_path)
        return None
    return file_path.read_bytes()


def _sentiment_score(description: str) -> float:
    """Keyword tier scoring per proposal slide 11."""
    text = (description or "").lower()
    critical = {"pothole", "crater", "collapse", "dangerous", "accident", "injury"}
    high     = {"large", "deep", "severe", "flooding"}
    medium   = {"medium", "moderate", "bump"}

    if any(k in text for k in critical):
        base = 0.95
    elif any(k in text for k in high):
        base = 0.75
    elif any(k in text for k in medium):
        base = 0.45
    else:
        base = 0.20

    bonus = 0.10 if sum(1 for k in high if k in text) >= 2 else 0.0
    return min(base + bonus, 1.0)


def _yolo_visual_score(image_bytes: bytes) -> tuple[float, float, dict]:
    """
    Returns (visual_score, spread_score, meta).
    visual_score — from YOLO class label (small/medium/severe)
    spread_score — largest detected box area as % of image (0-1)
    """
    detector_result = road_model_suite.detect_damage(image_bytes)
    if detector_result is None or detector_result.count == 0:
        return 0.0, 0.0, {"source": "yolo-unavailable", "count": 0}

    visual_score = 0.0
    for box in detector_result.boxes:
        cls_score = YOLO_CLASS_SCORES.get(box["label"])
        if cls_score is None:
            # area-based fallback if class not recognised
            area = box["area_ratio"]
            cls_score = 1.0 if area > 0.05 else (0.6 if area > 0.01 else 0.3)
        visual_score = max(visual_score, cls_score)

    spread_score = _clip01(detector_result.max_area_ratio)

    return visual_score, spread_score, {
        "source": detector_result.source,
        "count": detector_result.count,
        "max_area_ratio": round(detector_result.max_area_ratio, 4),
        "top_class": detector_result.boxes[0]["label"] if detector_result.boxes else None,
        "boxes": detector_result.boxes[:5],
    }


async def analyze_pothole_report(
    image_url: str,
    description: str,
    latitude: float,
    longitude: float,
    upvotes: int,
    image_bytes: Optional[bytes] = None,
    citizen_severity: str = "medium",
) -> Dict:
    loaded_image = _load_local_image_bytes(image_url, image_bytes)

    has_coords = bool(latitude and longitude)
    pois = await query_nearby_pois(latitude, longitude) if has_coords else {}
    traffic_score, traffic_label = await query_traffic_density(latitude, longitude) if has_coords else (30.0, "unknown")
    loc_score, poi_summary = location_score_from_pois(pois)
    desc_sc = description_score(description, citizen_severity)
    upvote_score = _clip01((upvotes or 0) / 25.0)

    # --- Groq path (primary) ---
    groq_result = await analyze_with_grok(
        image_bytes=loaded_image,
        description=description,
        citizen_severity=citizen_severity,
        latitude=latitude,
        longitude=longitude,
        upvotes=upvotes,
        pois=pois,
        traffic_score=traffic_score,
        traffic_label=traffic_label,
    )

    if groq_result:
        final_score = float(groq_result.get("final_severity_score", 50))
        severity_level = groq_result.get("severity_level", _severity_level_from_score(final_score))
        image_score = float(groq_result.get("image_score", 50))

        return {
            "pothole_spread_score": round(image_score / 100.0, 3),
            "emotion_score": round(desc_sc / 100.0, 3),
            "location_score": round(loc_score / 100.0, 3),
            "upvote_score": round(upvote_score, 3),
            "ai_severity_score": round(min(final_score, 100.0), 2),
            "ai_severity_level": severity_level,
            "location_meta": json.dumps({
                "mode": "groq-ahp",
                "geospatial_enrichment": True,
                "latitude": latitude,
                "longitude": longitude,
                "location_score": loc_score,
                "traffic_score": traffic_score,
                "traffic_label": traffic_label,
                "nearby_critical_places": poi_summary,
            }),
            "sentiment_meta": json.dumps({
                "source": "groq-vision-ahp",
                "damage_type": groq_result.get("damage_type"),
                "image_score": image_score,
                "description_score": desc_sc,
                "location_score": loc_score,
                "upvote_score": round(upvote_score * 100),
                "final_severity_score": final_score,
                "explanation": groq_result.get("explanation"),
                "confidence": groq_result.get("confidence"),
            }),
        }

    # --- Heuristic fallback (no Groq) ---
    # Visual: YOLO class score + spread, else 0
    if loaded_image:
        visual_score, spread_score, yolo_meta = _yolo_visual_score(loaded_image)
    else:
        visual_score, spread_score, yolo_meta = 0.0, 0.0, {"source": "no-image"}

    sentiment = _sentiment_score(description)
    social_score = min((upvotes / 25.0) + (loc_score / 100.0 * 0.2), 1.0)

    # AHP: Visual 35% + Location 20% + Sentiment 25% + Social 20%
    severity = (
        W_VISUAL    * visual_score * 100 +
        W_LOCATION  * loc_score +
        W_SENTIMENT * sentiment * 100 +
        W_SOCIAL    * social_score * 100
    )

    return {
        "pothole_spread_score": round(spread_score, 3),
        "emotion_score": round(sentiment, 3),
        "location_score": round(loc_score / 100.0, 3),
        "upvote_score": round(upvote_score, 3),
        "ai_severity_score": round(_clip01(severity / 100.0) * 100.0, 2),
        "ai_severity_level": _severity_level_from_score(severity),
        "location_meta": json.dumps({
            "mode": "ahp-heuristic",
            "geospatial_enrichment": has_coords,
            "latitude": latitude,
            "longitude": longitude,
            "location_score": loc_score,
            "traffic_score": traffic_score,
            "traffic_label": traffic_label,
            "nearby_critical_places": poi_summary,
        }),
        "sentiment_meta": json.dumps({
            "source": "ahp-heuristic",
            "visual_score": round(visual_score, 3),
            "spread_score": round(spread_score, 3),
            "sentiment_score": round(sentiment, 3),
            "social_score": round(social_score, 3),
            "yolo": yolo_meta,
        }),
    }
