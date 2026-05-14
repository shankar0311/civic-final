from ultralytics import YOLO
import logging
import os
from pathlib import Path

logger = logging.getLogger("ai-ensemble")

class ModelLoader:
    _instance = None
    _pothole_model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelLoader, cls).__new__(cls)
        return cls._instance

    def load_models(self):
        if self._pothole_model is None:
            logger.info("Loading YOLOv8 Pothole Model...")
            try:
                model_path = os.getenv("POTHOLE_YOLO_MODEL") or os.getenv("ROAD_DETECTOR_WEIGHTS")
                if not model_path:
                    candidate = Path("backend/models/road_detector/best.pt")
                    model_path = str(candidate) if candidate.exists() else "keremberke/yolov8n-pothole-segmentation"
                logger.info("Using pothole model: %s", model_path)
                self._pothole_model = YOLO(model_path)
            except Exception as e:
                logger.error(f"Failed to load YOLO model: {e}")
                raise e
        logger.info("Models loaded successfully.")

    def get_pothole_model(self):
        if self._pothole_model is None:
            self.load_models()
        return self._pothole_model

model_loader = ModelLoader()
