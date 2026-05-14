from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel
import uvicorn
import logging
from PIL import Image
import io

from model_loader import model_loader
from osm_utils import get_location_context

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-ensemble")

app = FastAPI(title="AI Ensemble Severity Analysis")

# AHP weights per proposal
W_VISUAL    = 0.35
W_LOCATION  = 0.20
W_SENTIMENT = 0.25
W_SOCIAL    = 0.20

# Keyword tiers for sentiment scoring (proposal slide 11)
_CRITICAL_KEYWORDS = {"pothole", "crater", "collapse", "dangerous", "accident", "injury"}
_HIGH_KEYWORDS     = {"large", "deep", "severe", "flooding"}
_MEDIUM_KEYWORDS   = {"medium", "moderate", "bump"}

def _sentiment_score(description: str) -> float:
    text = (description or "").lower()
    if any(k in text for k in _CRITICAL_KEYWORDS):
        base = 0.95
    elif any(k in text for k in _HIGH_KEYWORDS):
        base = 0.75
    elif any(k in text for k in _MEDIUM_KEYWORDS):
        base = 0.45
    else:
        base = 0.20
    bonus = 0.10 if sum(1 for k in _HIGH_KEYWORDS if k in text) >= 2 else 0.0
    return min(base + bonus, 1.0)


class AnalysisResult(BaseModel):
    visual_score: float
    sentiment_score: float
    location_score: float
    social_score: float
    final_priority_score: float
    details: dict


@app.on_event("startup")
def startup_event():
    model_loader.load_models()


@app.post("/analyze", response_model=AnalysisResult)
async def analyze_report(
    description: str = Form(...),
    lat: float = Form(...),
    lon: float = Form(...),
    upvotes: int = Form(0),
    image: UploadFile = File(...),
):
    image_bytes = await image.read()
    pil_image = Image.open(io.BytesIO(image_bytes))

    # 1. VISUAL SCORE — YOLOv8 pothole detection
    visual_score = 0.0
    pothole_details = {"count": 0, "max_area_ratio": 0.0, "detections": []}

    try:
        model = model_loader.get_pothole_model()
        results = model(pil_image)
        severity_scores = {"small_pothole": 0.35, "medium_pothole": 0.65, "severe_pothole": 1.0}

        for r in results:
            if not r.boxes:
                continue
            img_area = r.orig_shape[0] * r.orig_shape[1]
            pothole_details["count"] += len(r.boxes)

            for box in r.boxes:
                cls_id = int(box.cls[0].item()) if box.cls is not None else -1
                cls_name = r.names.get(cls_id, "pothole") if hasattr(r, "names") else "pothole"
                confidence = float(box.conf[0].item()) if box.conf is not None else 0.0
                x, y, w, h = [float(v) for v in box.xywh[0].tolist()]
                area_ratio = (w * h) / img_area
                pothole_details["max_area_ratio"] = max(pothole_details["max_area_ratio"], area_ratio)

                # visual score from class or area fallback
                score = severity_scores.get(cls_name)
                if score is None:
                    score = 1.0 if area_ratio > 0.05 else (0.6 if area_ratio > 0.01 else 0.3)
                visual_score = max(visual_score, score)

                pothole_details["detections"].append({
                    "class": cls_name,
                    "confidence": round(confidence, 4),
                    "area_ratio": round(area_ratio, 4),
                })
    except Exception as e:
        logger.error(f"YOLO inference failed: {e}")

    # 2. SENTIMENT SCORE — keyword tiers (no external model needed)
    sentiment = _sentiment_score(description)

    # 3. LOCATION SCORE — OSM critical places
    location_context = get_location_context(lat, lon)
    location_score = location_context["score"]

    # 4. SOCIAL SCORE — upvotes + location bonus
    social_score = min((upvotes / 25.0) + (location_score * 0.2), 1.0)

    # 5. AHP COMPOSITE
    final_score = (
        W_VISUAL    * visual_score +
        W_LOCATION  * location_score +
        W_SENTIMENT * sentiment +
        W_SOCIAL    * social_score
    )

    return AnalysisResult(
        visual_score=round(visual_score, 4),
        sentiment_score=round(sentiment, 4),
        location_score=round(location_score, 4),
        social_score=round(social_score, 4),
        final_priority_score=round(final_score * 100, 2),
        details={"pothole": pothole_details, "location": location_context},
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
