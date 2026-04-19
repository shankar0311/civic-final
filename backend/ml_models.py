import logging
import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image

logger = logging.getLogger("backend.ml")


@dataclass
class DetectorPrediction:
    boxes: list[dict]
    count: int
    max_area_ratio: float
    source: str


@dataclass
class DepthPrediction:
    depth_score: float
    source: str
    raw_mean: float


@dataclass
class SeverityPrediction:
    severity_score: float
    source: str


class RoadModelSuite:
    """
    Optional local model stack for road analysis.

    Everything here is best-effort:
    - if a dependency is missing, we log and continue
    - if a weight path is missing, we skip that model
    - backend analysis falls back to heuristics when any model is unavailable
    """

    def __init__(self) -> None:
        self.detector_weights = os.getenv("ROAD_DETECTOR_WEIGHTS", "").strip()
        self.depth_checkpoint = os.getenv("ROAD_DEPTH_MODEL", "").strip()
        self.severity_model_path = os.getenv("ROAD_SEVERITY_MODEL", "").strip()
        self.detector_device = os.getenv("ROAD_MODEL_DEVICE", "").strip() or None

        self._detector = None
        self._depth_pipe = None
        self._severity_model = None
        self._severity_bundle = None

        self._detector_error: Optional[str] = None
        self._depth_error: Optional[str] = None
        self._severity_error: Optional[str] = None

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
        except Exception as exc:  # pragma: no cover - optional dependency path
            self._detector_error = f"detector load failed: {exc}"
            logger.warning(self._detector_error)
            return None

    def _load_depth(self):
        if self._depth_pipe is not None or self._depth_error is not None:
            return self._depth_pipe
        if not self.depth_checkpoint:
            self._depth_error = "ROAD_DEPTH_MODEL not set"
            return None

        try:
            from transformers import pipeline

            self._depth_pipe = pipeline("depth-estimation", model=self.depth_checkpoint)
            return self._depth_pipe
        except Exception as exc:  # pragma: no cover - optional dependency path
            self._depth_error = f"depth model load failed: {exc}"
            logger.warning(self._depth_error)
            return None

    def _load_severity(self):
        if self._severity_model is not None or self._severity_error is not None:
            return self._severity_model
        if not self.severity_model_path:
            self._severity_error = "ROAD_SEVERITY_MODEL not set"
            return None

        model_path = Path(self.severity_model_path)
        if not model_path.exists():
            self._severity_error = f"severity model not found: {model_path}"
            return None

        try:
            import joblib

            bundle = joblib.load(model_path)
            if isinstance(bundle, dict) and "model" in bundle:
                self._severity_bundle = bundle
                self._severity_model = bundle["model"]
            else:
                self._severity_bundle = {"model": bundle}
                self._severity_model = bundle
            return self._severity_model
        except Exception as exc:  # pragma: no cover - optional dependency path
            self._severity_error = f"severity model load failed: {exc}"
            logger.warning(self._severity_error)
            return None

    def status(self) -> dict[str, Any]:
        return {
            "detector_weights": self.detector_weights or None,
            "depth_checkpoint": self.depth_checkpoint or None,
            "severity_model": self.severity_model_path or None,
            "detector_ready": self._load_detector() is not None,
            "depth_ready": self._load_depth() is not None,
            "severity_ready": self._load_severity() is not None,
            "errors": {
                "detector": self._detector_error,
                "depth": self._depth_error,
                "severity": self._severity_error,
            },
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
        except Exception as exc:  # pragma: no cover - optional dependency path
            logger.warning("Detector inference failed: %s", exc)
            return None

    def estimate_depth(self, image_bytes: bytes, region: Optional[list[float]] = None) -> Optional[DepthPrediction]:
        depth_pipe = self._load_depth()
        if depth_pipe is None:
            return None

        try:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            output = depth_pipe(image)
            predicted = output.get("predicted_depth")
            if predicted is None:
                return None

            if hasattr(predicted, "detach"):
                depth_map = predicted.detach().cpu().numpy()
            else:
                depth_map = np.asarray(predicted)

            if depth_map.ndim > 2:
                depth_map = np.squeeze(depth_map)

            if region:
                width, height = image.size
                x1, y1, x2, y2 = region
                sx1 = max(0, min(depth_map.shape[1] - 1, int((x1 / width) * depth_map.shape[1])))
                sx2 = max(sx1 + 1, min(depth_map.shape[1], int((x2 / width) * depth_map.shape[1])))
                sy1 = max(0, min(depth_map.shape[0] - 1, int((y1 / height) * depth_map.shape[0])))
                sy2 = max(sy1 + 1, min(depth_map.shape[0], int((y2 / height) * depth_map.shape[0])))
                roi = depth_map[sy1:sy2, sx1:sx2]
            else:
                roi = depth_map

            if roi.size == 0:
                roi = depth_map

            normalized = (float(roi.mean()) - float(depth_map.min())) / (
                float(depth_map.max() - depth_map.min()) + 1e-6
            )
            return DepthPrediction(
                depth_score=max(0.0, min(1.0, normalized)),
                source=f"transformers:{self.depth_checkpoint}",
                raw_mean=float(roi.mean()),
            )
        except Exception as exc:  # pragma: no cover - optional dependency path
            logger.warning("Depth inference failed: %s", exc)
            return None

    def predict_severity(self, features: list[float]) -> Optional[SeverityPrediction]:
        model = self._load_severity()
        if model is None:
            return None

        try:
            vector = np.asarray([features], dtype=np.float32)
            score = None
            if hasattr(model, "predict_proba"):
                proba = model.predict_proba(vector)[0]
                score = float(np.dot(proba, np.linspace(15.0, 95.0, len(proba))))
            elif hasattr(model, "predict"):
                pred = model.predict(vector)[0]
                if isinstance(pred, str):
                    mapped = {
                        "low": 20.0,
                        "medium": 50.0,
                        "high": 75.0,
                        "critical": 92.0,
                    }
                    score = mapped.get(pred.lower())
                else:
                    score = float(pred)

            if score is None:
                return None

            return SeverityPrediction(
                severity_score=max(0.0, min(100.0, score)),
                source=f"joblib:{Path(self.severity_model_path).name}",
            )
        except Exception as exc:  # pragma: no cover - optional dependency path
            logger.warning("Severity inference failed: %s", exc)
            return None


road_model_suite = RoadModelSuite()
