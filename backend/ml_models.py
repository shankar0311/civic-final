import logging
import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from PIL import Image

logger = logging.getLogger("backend.ml")


@dataclass
class DetectorPrediction:
    boxes: list[dict]
    count: int
    max_area_ratio: float
    source: str


class RoadModelSuite:
    """
    Optional YOLO-based pothole detector.
    Falls back gracefully when weights are missing or ultralytics is not installed.
    """

    def __init__(self) -> None:
        self.detector_weights = os.getenv("ROAD_DETECTOR_WEIGHTS", "").strip()
        self.detector_device = os.getenv("ROAD_MODEL_DEVICE", "").strip() or None
        self._detector = None
        self._detector_error: Optional[str] = None

    def _load_detector(self):
        if self._detector is not None or self._detector_error is not None:
            return self._detector
        if not self.detector_weights:
            self._detector_error = "ROAD_DETECTOR_WEIGHTS not set"
            return None

        weights_path = Path(self.detector_weights)
        if not weights_path.exists():
            self._detector_error = f"detector weights not found: {weights_path}"
            return None

        try:
            from ultralytics import YOLO
            self._detector = YOLO(str(weights_path))
            return self._detector
        except Exception as exc:
            self._detector_error = f"detector load failed: {exc}"
            logger.warning(self._detector_error)
            return None

    def status(self) -> dict[str, Any]:
        return {
            "detector_weights": self.detector_weights or None,
            "detector_ready": self._load_detector() is not None,
            "error": self._detector_error,
        }

    def detect_damage(self, image_bytes: bytes) -> Optional[DetectorPrediction]:
        model = self._load_detector()
        if model is None:
            return None

        try:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            width, height = image.size
            total_area = max(width * height, 1)
            results = model.predict(image, verbose=False, device=self.detector_device)
            boxes: list[dict] = []
            max_area_ratio = 0.0

            for result in results:
                if result.boxes is None:
                    continue
                names = getattr(result, "names", {}) or getattr(model, "names", {})
                for raw_box in result.boxes:
                    cls_id = int(raw_box.cls[0].item()) if raw_box.cls is not None else -1
                    conf = float(raw_box.conf[0].item()) if raw_box.conf is not None else 0.0
                    xyxy = raw_box.xyxy[0].tolist()
                    x1, y1, x2, y2 = xyxy
                    area_ratio = max(((x2 - x1) * (y2 - y1)) / total_area, 0.0)
                    max_area_ratio = max(max_area_ratio, area_ratio)
                    boxes.append(
                        {
                            "class_id": cls_id,
                            "label": str(names.get(cls_id, cls_id)),
                            "confidence": round(conf, 4),
                            "xyxy": [round(v, 2) for v in xyxy],
                            "area_ratio": round(area_ratio, 4),
                        }
                    )

            return DetectorPrediction(
                boxes=boxes,
                count=len(boxes),
                max_area_ratio=float(max_area_ratio),
                source="ultralytics-yolo",
            )
        except Exception as exc:
            logger.warning("Detector inference failed: %s", exc)
            return None


road_model_suite = RoadModelSuite()
