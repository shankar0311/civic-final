import json
import logging
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional

import numpy as np
from PIL import Image
from ml_models import road_model_suite
from grok_analysis import (
    analyze_with_grok,
    query_nearby_pois,
    query_traffic_density,
    location_score_from_pois,
    description_score,
)

logger = logging.getLogger("backend")


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _severity_level_from_score(score: float) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 40:
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


def _visual_scores_from_text(description: str) -> tuple[float, float, dict]:
    text = (description or "").lower()

    depth_terms = {
        "deep": 0.28,
        "crater": 0.32,
        "sunken": 0.22,
        "dangerous": 0.14,
        "accident": 0.10,
        "6 inch": 0.22,
        "8 inch": 0.28,
    }
    spread_terms = {
        "wide": 0.26,
        "large": 0.18,
        "huge": 0.24,
        "massive": 0.28,
        "2 feet": 0.20,
        "3 feet": 0.26,
        "lane": 0.12,
        "multiple": 0.16,
    }

    matched_depth = [term for term in depth_terms if term in text]
    matched_spread = [term for term in spread_terms if term in text]

    depth_score = _clip01(0.18 + sum(depth_terms[term] for term in matched_depth))
    spread_score = _clip01(0.20 + sum(spread_terms[term] for term in matched_spread))

    return depth_score, spread_score, {
        "mode": "text-only",
        "matched_depth_terms": matched_depth,
        "matched_spread_terms": matched_spread,
    }


def _visual_scores_from_image(image_bytes: bytes, description: str) -> tuple[float, float, dict]:
    try:
        image = Image.open(BytesIO(image_bytes)).convert("L").resize((256, 256))
    except Exception as exc:
        logger.warning("Image decoding failed during road analysis: %s", exc)
        depth_score, spread_score, meta = _visual_scores_from_text(description)
        meta["image_available"] = False
        meta["decode_failed"] = True
        return depth_score, spread_score, meta

    gray = np.asarray(image, dtype=np.float32) / 255.0
    center = gray[64:192, 64:192]
    border = np.concatenate(
        [
            gray[:64, :].ravel(),
            gray[192:, :].ravel(),
            gray[64:192, :64].ravel(),
            gray[64:192, 192:].ravel(),
        ]
    )

    center_darkness = 1.0 - float(center.mean())
    border_darkness = 1.0 - float(border.mean())
    depression_score = _clip01((center_darkness - border_darkness + 0.10) / 0.45)

    center_std = float(center.std())
    texture_score = _clip01(center_std * 3.2)
    edge_strength = (
        float(np.abs(np.diff(center, axis=0)).mean()) +
        float(np.abs(np.diff(center, axis=1)).mean())
    ) / 2.0
    edge_score = _clip01(edge_strength * 4.8)
    dark_ratio = float(np.mean(center < 0.42))
    shadow_ratio = float(np.mean(center < 0.30))

    text_depth, text_spread, text_meta = _visual_scores_from_text(description)

    spread_score = _clip01(
        0.12 +
        (dark_ratio * 0.42) +
        (texture_score * 0.18) +
        (edge_score * 0.14) +
        (depression_score * 0.12)
    )
    depth_score = _clip01(
        0.10 +
        (depression_score * 0.42) +
        (shadow_ratio * 0.18) +
        (texture_score * 0.16) +
        (edge_score * 0.10)
    )

    spread_score = _clip01(max(spread_score, text_spread * 0.8))
    depth_score = _clip01(max(depth_score, text_depth * 0.8))

    return depth_score, spread_score, {
        "mode": "local-image-heuristic",
        "image_available": True,
        "features": {
            "center_darkness": round(center_darkness, 3),
            "border_darkness": round(border_darkness, 3),
            "depression_score": round(depression_score, 3),
            "texture_score": round(texture_score, 3),
            "edge_score": round(edge_score, 3),
            "dark_ratio": round(dark_ratio, 3),
            "shadow_ratio": round(shadow_ratio, 3),
        },
        "text_support": text_meta,
    }


def _sentiment_score(description: str) -> tuple[float, dict]:
    text = (description or "").lower()
    weights = {
        "urgent": 0.20,
        "danger": 0.22,
        "dangerous": 0.22,
        "accident": 0.24,
        "injury": 0.26,
        "emergency": 0.28,
        "critical": 0.28,
        "immediately": 0.18,
        "school bus": 0.20,
        "vehicle damage": 0.16,
        "night": 0.10,
        "rain": 0.10,
    }
    matched = [term for term in weights if term in text]
    score = _clip01(0.18 + sum(weights[term] for term in matched))
    label = "urgent" if score >= 0.65 else "moderate" if score >= 0.35 else "routine"
    return score, {
        "mode": "local-keyword-analysis",
        "label": label,
        "keywords": matched,
    }


def _location_score(description: str, latitude: float, longitude: float) -> tuple[float, dict]:
    text = (description or "").lower()
    weights = {
        "intersection": 0.18,
        "main road": 0.16,
        "highway": 0.22,
        "junction": 0.14,
        "bridge": 0.12,
        "school": 0.18,
        "hospital": 0.20,
        "market": 0.10,
        "bus": 0.08,
        "traffic": 0.12,
    }
    matched = [term for term in weights if term in text]

    has_coordinates = latitude is not None and longitude is not None
    score = 0.22 + (0.05 if has_coordinates else 0.0) + sum(weights[term] for term in matched)

    return _clip01(score), {
        "mode": "local-road-context",
        "geospatial_enrichment": False,
        "matched_keywords": matched,
        "coordinates_supplied": has_coordinates,
        "latitude": latitude,
        "longitude": longitude,
    }


def _visual_scores_from_models(image_bytes: bytes, description: str) -> tuple[Optional[float], Optional[float], dict]:
    detector_result = road_model_suite.detect_damage(image_bytes)
    if detector_result is None or detector_result.count == 0:
        return None, None, {"mode": "model-unavailable"}

    spread_score = _clip01((detector_result.max_area_ratio / 0.22) + min(detector_result.count, 4) * 0.05)
    depth_score, _, text_meta = _visual_scores_from_text(description)

    return depth_score, spread_score, {
        "mode": "model-assisted",
        "detector": {
            "source": detector_result.source,
            "count": detector_result.count,
            "max_area_ratio": round(detector_result.max_area_ratio, 4),
            "boxes": detector_result.boxes[:10],
        },
        "depth": {"source": "text-fallback", "text_support": text_meta},
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

    # Fetch OSM context (used by both Groq and heuristic paths)
    has_coords = bool(latitude and longitude)
    pois = await query_nearby_pois(latitude, longitude) if has_coords else {}
    traffic_score, traffic_label = await query_traffic_density(latitude, longitude) if has_coords else (30.0, "unknown")
    loc_score, poi_summary = location_score_from_pois(pois)
    desc_sc = description_score(description, citizen_severity)
    upvote_score = _clip01((upvotes or 0) / 25.0)

    # --- Groq AHP vision path (primary) ---
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

        location_meta = {
            "mode": "osm-overpass-ahp",
            "geospatial_enrichment": True,
            "coordinates_supplied": has_coords,
            "latitude": latitude,
            "longitude": longitude,
            "location_score": loc_score,
            "traffic_score": traffic_score,
            "traffic_label": traffic_label,
            "nearby_critical_places": poi_summary,
            "nearby_pois": groq_result.get("_nearby_pois", {}),
        }
        sentiment_meta = {
            "source": "groq-vision-ahp",
            "damage_type": groq_result.get("damage_type"),
            "image_score": image_score,
            "description_score": desc_sc,
            "location_score": loc_score,
            "traffic_score": traffic_score,
            "upvote_score": round(upvote_score * 100),
            "final_severity_score": final_score,
            "explanation": groq_result.get("explanation"),
            "priority": groq_result.get("priority"),
            "confidence": groq_result.get("confidence"),
        }

        return {
            "pothole_depth_score": round(image_score / 100.0 * 0.6, 3),
            "pothole_spread_score": round(image_score / 100.0 * 0.8, 3),
            "emotion_score": round(desc_sc / 100.0, 3),
            "location_score": round(loc_score / 100.0, 3),
            "upvote_score": round(upvote_score, 3),
            "ai_severity_score": round(min(final_score, 100.0), 2),
            "ai_severity_level": severity_level,
            "location_meta": json.dumps(location_meta),
            "sentiment_meta": json.dumps(sentiment_meta),
        }

    # --- Heuristic fallback (AHP weights, no Groq) ---
    if loaded_image:
        model_depth, model_spread, model_meta = _visual_scores_from_models(loaded_image, description)
        if model_depth is not None and model_spread is not None:
            depth_score, spread_score, visual_meta = model_depth, model_spread, model_meta
        else:
            depth_score, spread_score, visual_meta = _visual_scores_from_image(loaded_image, description)
    else:
        depth_score, spread_score, visual_meta = _visual_scores_from_text(description)
        visual_meta["image_available"] = False

    image_score_h = (depth_score * 0.5 + spread_score * 0.5) * 100.0

    # AHP weights: image 0.40, location 0.20, traffic 0.20, upvote 0.10, desc 0.10
    heuristic_severity = (
        (image_score_h * 0.40) +
        (loc_score * 0.20) +
        (traffic_score * 0.20) +
        (upvote_score * 100.0 * 0.10) +
        (desc_sc * 0.10)
    )

    severity = heuristic_severity

    location_meta = {
        "mode": "osm-overpass-heuristic",
        "geospatial_enrichment": has_coords,
        "coordinates_supplied": has_coords,
        "latitude": latitude,
        "longitude": longitude,
        "location_score": loc_score,
        "traffic_score": traffic_score,
        "traffic_label": traffic_label,
        "nearby_critical_places": poi_summary,
        "nearby_pois": {k: [p["name"] for p in v[:3]] for k, v in pois.items()},
    }
    sentiment_meta = {
        "source": "ahp-heuristic",
        "image_score": round(image_score_h, 2),
        "description_score": round(desc_sc, 2),
        "location_score": round(loc_score, 2),
        "traffic_score": round(traffic_score, 2),
        "upvote_score": round(upvote_score * 100, 2),
        "heuristic_severity": round(heuristic_severity, 2),
        "visual_meta": visual_meta,
    }

    return {
        "pothole_depth_score": round(depth_score, 3),
        "pothole_spread_score": round(spread_score, 3),
        "emotion_score": round(desc_sc / 100.0, 3),
        "location_score": round(loc_score / 100.0, 3),
        "upvote_score": round(upvote_score, 3),
        "ai_severity_score": round(_clip01(severity / 100.0) * 100.0, 2),
        "ai_severity_level": _severity_level_from_score(severity),
        "location_meta": json.dumps(location_meta),
        "sentiment_meta": json.dumps(sentiment_meta),
    }
