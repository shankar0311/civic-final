import base64
import json
import logging
import os
import re
from typing import Optional

import httpx

logger = logging.getLogger("backend.grok")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# AHP weights (must sum to 1.0) — aligned with proposal: Visual 35%, Location 20%, Sentiment 25%, Social 20%
W_IMAGE       = 0.40  # visual
W_LOCATION    = 0.15  # location risk
W_TRAFFIC     = 0.10  # traffic (part of location)
W_UPVOTE      = 0.10  # social
W_DESCRIPTION = 0.25  # sentiment/description

# OSM amenity tag → location risk score (mid-range of each category)
CRITICAL_POI_WEIGHTS = {
    # Healthcare / Emergency
    "hospital": 97,
    "clinic": 62,
    "doctors": 55,
    "pharmacy": 45,
    "ambulance_station": 92,

    # Emergency Services
    "fire_station": 95,
    "police": 77,

    # Education
    "kindergarten": 88,
    "school": 90,
    "college": 77,
    "university": 72,
    "library": 55,

    # Transport Hubs
    "bus_station": 82,
    "bus_stop": 55,
    "taxi": 45,
    "ferry_terminal": 75,

    # Government / Civic
    "townhall": 67,
    "courthouse": 65,
    "post_office": 52,
    "community_centre": 50,

    # Commercial / Market
    "marketplace": 70,
    "fuel": 48,
    "bank": 52,

    # Recreation
    "stadium": 62,
    "sports_centre": 52,
    "place_of_worship": 50,
}

# OSM railway tag → location score
RAILWAY_POI_WEIGHTS = {
    "station": 85,        # Railway / Metro station
    "subway_entrance": 85,
    "halt": 68,
    "tram_stop": 62,
    "platform": 55,
}

# OSM aeroway tag → location score
AEROWAY_POI_WEIGHTS = {
    "terminal": 90,
    "aerodrome": 87,
}

# OSM landuse tag → location score (area-based context)
# "education" is the primary tag for colleges/universities in Indian OSM data
LANDUSE_WEIGHTS = {
    "education": 77,      # College / University campus (very common in India)
    "commercial": 70,
    "retail": 65,
    "industrial": 55,
    "residential": 58,
    "village_green": 35,
    "farmland": 22,
    "forest": 15,
}

# OSM building tag → location score (Indian OSM often tags by building type)
BUILDING_POI_WEIGHTS = {
    "college": 77,
    "university": 72,
    "school": 90,
    "hospital": 97,
    "government": 67,
    "public": 55,
}

# OSM office tag → location score
OFFICE_POI_WEIGHTS = {
    "it": 65,
    "government": 68,
    "company": 52,
}

# OSM highway tag → traffic score (0-100)
ROAD_TRAFFIC_SCORES = {
    "motorway": 100,
    "motorway_link": 90,
    "trunk": 90,
    "trunk_link": 85,
    "primary": 80,
    "primary_link": 75,
    "secondary": 65,
    "secondary_link": 60,
    "tertiary": 45,
    "tertiary_link": 40,
    "unclassified": 30,
    "residential": 20,
    "service": 15,
    "track": 5,
    "path": 5,
}

SEVERITY_LABEL_MAP = {"low": 20, "medium": 45, "high": 70, "critical": 90}
USER_RATING_MAP = {1: 10, 2: 30, 3: 50, 4: 70, 5: 90}


def _grok_api_key() -> Optional[str]:
    return os.getenv("GROK_API_KEY", "").strip() or None


# ── OSM: nearby critical POIs ─────────────────────────────────────────────────

async def query_nearby_pois(latitude: float, longitude: float, radius_m: int = 500) -> dict:
    """Query OSM for all nearby infrastructure within radius_m metres."""
    if latitude is None or longitude is None:
        return {}

    amenities = "|".join(CRITICAL_POI_WEIGHTS.keys())
    railways  = "|".join(RAILWAY_POI_WEIGHTS.keys())
    aeroways  = "|".join(AEROWAY_POI_WEIGHTS.keys())
    landuses  = "|".join(LANDUSE_WEIGHTS.keys())
    offices   = "|".join(OFFICE_POI_WEIGHTS.keys())
    buildings = "|".join(BUILDING_POI_WEIGHTS.keys())

    r = radius_m
    lat, lon = latitude, longitude
    query = f"""
[out:json][timeout:20];
(
  node["amenity"~"{amenities}"](around:{r},{lat},{lon});
  way["amenity"~"{amenities}"](around:{r},{lat},{lon});
  node["railway"~"{railways}"](around:{r},{lat},{lon});
  way["railway"~"{railways}"](around:{r},{lat},{lon});
  node["aeroway"~"{aeroways}"](around:{r},{lat},{lon});
  way["aeroway"~"{aeroways}"](around:{r},{lat},{lon});
  way["landuse"~"{landuses}"](around:{r},{lat},{lon});
  node["office"~"{offices}"](around:{r},{lat},{lon});
  way["office"~"{offices}"](around:{r},{lat},{lon});
  way["building"~"{buildings}"](around:{r},{lat},{lon});
  node["building"~"{buildings}"](around:{r},{lat},{lon});
);
out center 50;
"""
    headers = {"User-Agent": "CityReport/1.0 (road pothole reporting system)"}
    try:
        async with httpx.AsyncClient(timeout=22.0) as client:
            resp = await client.post(OVERPASS_URL, data={"data": query}, headers=headers)
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
    except Exception as exc:
        logger.warning("Overpass POI query failed: %s", exc)
        return {}

    found: dict[str, list[dict]] = {}
    for el in elements:
        tags = el.get("tags", {})
        key = (
            tags.get("amenity")
            or tags.get("railway")
            or tags.get("aeroway")
            or tags.get("landuse")
            or tags.get("office")
            or tags.get("building")
        )
        if not key:
            continue
        # Skip generic building tags that have no scoring value
        all_weights = {**CRITICAL_POI_WEIGHTS, **RAILWAY_POI_WEIGHTS,
                       **AEROWAY_POI_WEIGHTS, **LANDUSE_WEIGHTS,
                       **OFFICE_POI_WEIGHTS, **BUILDING_POI_WEIGHTS}
        if key not in all_weights:
            continue
        name = tags.get("name", key)
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        found.setdefault(key, []).append({"name": name, "lat": lat, "lon": lon})

    return found


def location_score_from_pois(pois: dict) -> tuple[float, str]:
    """
    Returns location_score (0-100) and a human-readable summary.

    Scoring: mean of the top-3 unique-category POI scores.
    - Avoids max() inflating every urban area to 100
    - Avoids mean-of-all diluting critical POIs
    - Single POI gets 85% of its score (slight isolation penalty)
    """
    if not pois:
        return 0.0, "no important infrastructure within 500m"

    all_weights = {
        **CRITICAL_POI_WEIGHTS, **RAILWAY_POI_WEIGHTS,
        **AEROWAY_POI_WEIGHTS, **LANDUSE_WEIGHTS,
        **OFFICE_POI_WEIGHTS, **BUILDING_POI_WEIGHTS,
    }

    # One score per unique category (best item in that category)
    category_scores: list[tuple[float, str]] = []
    for key, items in pois.items():
        weight = all_weights.get(key, 30)
        best_name = items[0]["name"]
        category_scores.append((float(weight), f"{best_name} ({key})"))

    # Sort descending, take top 3
    category_scores.sort(key=lambda x: x[0], reverse=True)
    top3 = category_scores[:3]
    notes = [label for _, label in category_scores[:5]]

    if len(top3) == 1:
        final = top3[0][0] * 0.85          # isolation penalty
    else:
        final = sum(s for s, _ in top3) / len(top3)   # mean of top 3

    return round(min(final, 100.0), 1), ", ".join(notes)


# ── OSM: road traffic density ─────────────────────────────────────────────────

async def query_traffic_density(latitude: float, longitude: float, radius_m: int = 100) -> tuple[float, str]:
    """Returns traffic_score (0-100) and road type label using OSM highway tags."""
    if latitude is None or longitude is None:
        return 30.0, "unknown"

    query = f"""
[out:json][timeout:10];
way["highway"](around:{radius_m},{latitude},{longitude});
out tags 10;
"""
    headers = {"User-Agent": "CityReport/1.0 (road pothole reporting system)"}
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(OVERPASS_URL, data={"data": query}, headers=headers)
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
    except Exception as exc:
        logger.warning("Overpass traffic query failed: %s", exc)
        return 30.0, "unknown"

    if not elements:
        return 50.0, "unknown"

    # Pick the highest-traffic road found nearby
    best_score = 0
    best_label = "unclassified"
    for el in elements:
        highway = el.get("tags", {}).get("highway", "")
        score = ROAD_TRAFFIC_SCORES.get(highway, 25)
        if score > best_score:
            best_score = score
            best_label = highway

    return float(best_score), best_label


# ── Description score ─────────────────────────────────────────────────────────

def description_score(description: str, citizen_severity: str) -> float:
    """Combines text cues + citizen severity rating into a 0-100 score."""
    text = (description or "").lower()
    severity_base = SEVERITY_LABEL_MAP.get(citizen_severity, 45)

    urgency_terms = {
        "dangerous": 20, "accident": 22, "emergency": 25, "injury": 22,
        "critical": 20, "urgent": 18, "deep": 15, "large": 12,
        "huge": 15, "massive": 18, "crater": 20, "wide": 10,
        "multiple": 8, "night": 8, "rain": 8, "school bus": 15,
    }
    boost = sum(v for k, v in urgency_terms.items() if k in text)
    return min(severity_base + boost, 100.0)


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(
    description: str,
    citizen_severity: str,
    upvote_score: float,
    latitude: Optional[float],
    longitude: Optional[float],
    poi_summary: str,
    location_score: float,
    traffic_score: float,
    traffic_label: str,
    desc_score: float,
) -> str:
    coord_str = f"{latitude:.5f}, {longitude:.5f}" if latitude and longitude else "not provided"
    upvote_display = round(upvote_score * 100)

    return f"""You are an intelligent road infrastructure assessment system.

Your task is to analyze a reported road issue and compute a final severity score (0–100) using a weighted multi-factor model inspired by AHP (Analytic Hierarchy Process) and MCDM principles.

### INPUTS:

* Image analysis score (0–100): [Analyze the attached image and produce this score yourself]
* Citizen description: "{description or 'No description provided'}"
* Citizen severity rating: {citizen_severity}
* Upvotes (normalized 0–100): {upvote_display}
* Location coordinates: {coord_str}
* Nearby critical locations: {poi_summary}
* Traffic severity (0–100): {round(traffic_score)} ({traffic_label} road)

### PRE-COMPUTED CONTEXT SCORES (use these directly):
* Location Score: {round(location_score)} / 100
* Traffic Score: {round(traffic_score)} / 100
* User Description Score: {round(desc_score)} / 100
* Upvote Score: {upvote_display} / 100

---

### STEP 1: Interpret the Image
Analyze the image carefully and produce an Image Score (0–100) representing physical damage severity (depth, size, surface area, safety risk).

---

### STEP 2: Apply AHP Weights

Use EXACTLY these weights:
* Image Score → 0.40
* User Description Score → 0.25
* Location Score → 0.15
* Traffic Severity → 0.10
* Upvote Score → 0.10

Final Score = (0.40 × Image Score) + (0.25 × {round(desc_score)}) + (0.15 × {round(location_score)}) + (0.10 × {round(traffic_score)}) + (0.10 × {upvote_display})

---

### STEP 3: Classify

* 0–25 → Low
* 26–50 → Medium
* 51–75 → High
* 76–100 → Critical

---

### STEP 4: Return STRICT JSON only — no markdown, no explanation outside JSON.

{{
  "image_score": <0-100>,
  "final_severity_score": <0-100>,
  "damage_type": "<pothole|longitudinal_crack|transverse_crack|alligator_crack|surface_failure|waterlogging|debris|other>",
  "severity_level": "<low|medium|high|critical>",
  "priority": "<low|medium|high|critical>",
  "explanation": "<2-3 sentences referencing the dominant factors>",
  "confidence": <0.0-1.0>
}}"""


# ── Main entry point ──────────────────────────────────────────────────────────

async def analyze_with_grok(
    image_bytes: Optional[bytes],
    description: str,
    citizen_severity: str,
    latitude: Optional[float],
    longitude: Optional[float],
    upvotes: int = 0,
    pois: Optional[dict] = None,
    traffic_score: Optional[float] = None,
    traffic_label: Optional[str] = None,
) -> Optional[dict]:
    api_key = _grok_api_key()
    if not api_key:
        return None

    # Gather context in parallel-ish (sequential is fine given async)
    if pois is None:
        pois = await query_nearby_pois(latitude, longitude) if latitude and longitude else {}

    if traffic_score is None:
        traffic_score, traffic_label = await query_traffic_density(latitude, longitude) if latitude and longitude else (30.0, "unknown")

    loc_score, poi_summary = location_score_from_pois(pois)
    desc_sc = description_score(description, citizen_severity)
    upvote_sc = min((upvotes or 0) / 25.0, 1.0)

    prompt = _build_prompt(
        description=description,
        citizen_severity=citizen_severity,
        upvote_score=upvote_sc,
        latitude=latitude,
        longitude=longitude,
        poi_summary=poi_summary,
        location_score=loc_score,
        traffic_score=traffic_score,
        traffic_label=traffic_label or "unknown",
        desc_score=desc_sc,
    )

    messages_content: list[dict] = [{"type": "text", "text": prompt}]
    if image_bytes:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        messages_content.insert(0, {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })

    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": messages_content}],
        "temperature": 0.1,
        "max_tokens": 1024,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            if not resp.is_success:
                logger.warning("Groq HTTP %s: %s", resp.status_code, resp.text[:300])
                return None

            raw_content = resp.json()["choices"][0]["message"]["content"] or ""
            content = raw_content.strip()

        if not content:
            logger.warning("Groq returned empty content")
            return None

        logger.info("Groq raw response: %s", content[:400])

        # Extract JSON: handle ```json ... ```, ``` ... ```, or bare JSON
        json_match = re.search(r'\{[\s\S]*\}', content)
        if not json_match:
            logger.warning("Groq: no JSON object found in response: %s", content[:200])
            return None
        content = json_match.group(0)

        result = json.loads(content)
        result["_location_score"] = loc_score
        result["_traffic_score"] = traffic_score
        result["_traffic_label"] = traffic_label
        result["_desc_score"] = desc_sc
        result["_upvote_score"] = round(upvote_sc * 100)
        result["_poi_summary"] = poi_summary
        result["_nearby_pois"] = {k: [p["name"] for p in v[:3]] for k, v in pois.items()}
        result["_source"] = "groq-vision-ahp"
        return result

    except json.JSONDecodeError as exc:
        logger.warning("Groq JSON parse failed: %s | content: %s", exc, content[:200])
        return None
    except Exception as exc:
        logger.warning("Groq API call failed: %s", exc)
        return None
