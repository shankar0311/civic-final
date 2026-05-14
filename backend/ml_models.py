import logging
import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image

logger = logging.getLogger("backend.ml")

CLASS_NAMES = {0: "small_pothole", 1: "medium_pothole", 2: "severe_pothole"}
_INPUT_SIZE = 640
_CONF_THRESHOLD = 0.25
_IOU_THRESHOLD = 0.45


@dataclass
class DetectorPrediction:
    boxes: list[dict]
    count: int
    max_area_ratio: float
    source: str


def _letterbox(img: Image.Image) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Resize to 640x640 with letterbox padding; return (array, scale, (pad_left, pad_top))."""
    w, h = img.size
    r = min(_INPUT_SIZE / h, _INPUT_SIZE / w)
    new_w, new_h = int(round(w * r)), int(round(h * r))
    img_r = img.resize((new_w, new_h), Image.BILINEAR)
    pad_w = _INPUT_SIZE - new_w
    pad_h = _INPUT_SIZE - new_h
    left, top = pad_w // 2, pad_h // 2
    canvas = Image.new("RGB", (_INPUT_SIZE, _INPUT_SIZE), (114, 114, 114))
    canvas.paste(img_r, (left, top))
    return np.asarray(canvas, dtype=np.float32) / 255.0, r, (left, top)


def _nms(cx, cy, w, h, scores, iou_thr=_IOU_THRESHOLD):
    x1 = cx - w / 2
    y1 = cy - h / 2
    x2 = cx + w / 2
    y2 = cy + h / 2
    areas = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size:
        i = order[0]
        keep.append(i)
        ix1 = np.maximum(x1[i], x1[order[1:]])
        iy1 = np.maximum(y1[i], y1[order[1:]])
        ix2 = np.minimum(x2[i], x2[order[1:]])
        iy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0, ix2 - ix1) * np.maximum(0, iy2 - iy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
        order = order[1:][iou <= iou_thr]
    return keep


class RoadModelSuite:
    """YOLO pothole detector via ONNX (preferred) or ultralytics fallback."""

    def __init__(self) -> None:
        self.detector_weights = os.getenv("ROAD_DETECTOR_WEIGHTS", "").strip()
        self._session = None
        self._input_name: Optional[str] = None
        self._use_ultralytics = False
        self._detector_error: Optional[str] = None

    def _load_detector(self):
        if self._session is not None or self._detector_error is not None:
            return self._session

        if not self.detector_weights:
            self._detector_error = "ROAD_DETECTOR_WEIGHTS not set"
            return None

        pt_path = Path(self.detector_weights)
        onnx_path = pt_path.with_suffix(".onnx")

        if onnx_path.exists():
            try:
                import onnxruntime as ort
                self._session = ort.InferenceSession(
                    str(onnx_path), providers=["CPUExecutionProvider"]
                )
                self._input_name = self._session.get_inputs()[0].name
                self._use_ultralytics = False
                logger.info("ONNX detector loaded: %s", onnx_path)
                return self._session
            except Exception as exc:
                logger.warning("ONNX load failed, trying ultralytics: %s", exc)

        if pt_path.exists():
            try:
                from ultralytics import YOLO
                self._session = YOLO(str(pt_path))
                self._use_ultralytics = True
                logger.info("Ultralytics detector loaded: %s", pt_path)
                return self._session
            except Exception as exc:
                self._detector_error = f"detector load failed: {exc}"
                logger.warning(self._detector_error)
                return None

        self._detector_error = f"no model file at {pt_path} or {onnx_path}"
        logger.warning(self._detector_error)
        return None

    def status(self) -> dict[str, Any]:
        return {
            "detector_weights": self.detector_weights or None,
            "detector_ready": self._load_detector() is not None,
            "backend": "onnxruntime" if (self._session and not self._use_ultralytics) else (
                "ultralytics" if self._use_ultralytics else None
            ),
            "error": self._detector_error,
        }

    # ------------------------------------------------------------------
    # ONNX inference (YOLOv8 output: [1, 4+nc, 8400])
    # ------------------------------------------------------------------
    def _detect_onnx(self, session, image_bytes: bytes) -> Optional[DetectorPrediction]:
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        orig_w, orig_h = img.size
        total_area = max(orig_w * orig_h, 1)

        arr, scale, (pad_left, pad_top) = _letterbox(img)
        inp = arr.transpose(2, 0, 1)[None]  # NCHW

        raw = session.run(None, {self._input_name: inp})[0]  # [1, 7, 8400]
        pred = raw[0].T  # [8400, 7]

        xy_wh = pred[:, :4]
        class_scores = pred[:, 4:]
        conf = class_scores.max(axis=1)
        mask = conf >= _CONF_THRESHOLD

        if not mask.any():
            return DetectorPrediction(boxes=[], count=0, max_area_ratio=0.0, source="onnx-yolo")

        xy_wh = xy_wh[mask]
        class_scores = class_scores[mask]
        conf = conf[mask]
        cls_ids = class_scores.argmax(axis=1)

        keep = _nms(xy_wh[:, 0], xy_wh[:, 1], xy_wh[:, 2], xy_wh[:, 3], conf)

        boxes = []
        max_area_ratio = 0.0
        for i in keep:
            cx, cy, bw, bh = xy_wh[i]
            # reverse letterbox: remove padding then unscale
            x1 = (cx - bw / 2 - pad_left) / scale
            y1 = (cy - bh / 2 - pad_top) / scale
            x2 = (cx + bw / 2 - pad_left) / scale
            y2 = (cy + bh / 2 - pad_top) / scale
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(orig_w, x2), min(orig_h, y2)
            area_ratio = max(0.0, ((x2 - x1) * (y2 - y1)) / total_area)
            max_area_ratio = max(max_area_ratio, area_ratio)
            cls_id = int(cls_ids[i])
            boxes.append({
                "class_id": cls_id,
                "label": CLASS_NAMES.get(cls_id, str(cls_id)),
                "confidence": round(float(conf[i]), 4),
                "xyxy": [round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)],
                "area_ratio": round(area_ratio, 4),
            })

        return DetectorPrediction(
            boxes=boxes, count=len(boxes), max_area_ratio=float(max_area_ratio), source="onnx-yolo"
        )

    # ------------------------------------------------------------------
    # Ultralytics fallback
    # ------------------------------------------------------------------
    def _detect_ultralytics(self, model, image_bytes: bytes) -> Optional[DetectorPrediction]:
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        orig_w, orig_h = img.size
        total_area = max(orig_w * orig_h, 1)
        results = model.predict(img, verbose=False)
        boxes = []
        max_area_ratio = 0.0
        for result in results:
            if result.boxes is None:
                continue
            names = getattr(result, "names", {}) or getattr(model, "names", {})
            for raw_box in result.boxes:
                cls_id = int(raw_box.cls[0].item()) if raw_box.cls is not None else -1
                conf = float(raw_box.conf[0].item()) if raw_box.conf is not None else 0.0
                x1, y1, x2, y2 = raw_box.xyxy[0].tolist()
                area_ratio = max(((x2 - x1) * (y2 - y1)) / total_area, 0.0)
                max_area_ratio = max(max_area_ratio, area_ratio)
                boxes.append({
                    "class_id": cls_id,
                    "label": str(names.get(cls_id, cls_id)),
                    "confidence": round(conf, 4),
                    "xyxy": [round(v, 2) for v in [x1, y1, x2, y2]],
                    "area_ratio": round(area_ratio, 4),
                })
        return DetectorPrediction(
            boxes=boxes, count=len(boxes), max_area_ratio=float(max_area_ratio), source="ultralytics-yolo"
        )

    def detect_damage(self, image_bytes: bytes) -> Optional[DetectorPrediction]:
        model = self._load_detector()
        if model is None:
            return None
        try:
            if self._use_ultralytics:
                return self._detect_ultralytics(model, image_bytes)
            return self._detect_onnx(model, image_bytes)
        except Exception as exc:
            logger.warning("Detector inference failed: %s", exc)
            return None


road_model_suite = RoadModelSuite()
