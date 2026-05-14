from ultralytics import YOLO
from transformers import pipeline
import logging
import os
from pathlib import Path

logger = logging.getLogger("ai-ensemble")

class ModelLoader:
    _instance = None
    _pothole_model = None
    _depth_pipeline = None
    _sentiment_pipeline = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelLoader, cls).__new__(cls)
        return cls._instance

    def load_models(self):
        """Loads models if they aren't already loaded."""
        if self._pothole_model is None:
            logger.info("Loading YOLOv8 Pothole Model...")
            try:
                model_path = os.getenv("POTHOLE_YOLO_MODEL") or os.getenv("ROAD_DETECTOR_MODEL")
                if not model_path:
                    candidate = Path("backend/models/road_detector/best.pt")
                    model_path = str(candidate) if candidate.exists() else "keremberke/yolov8m-pothole-segmentation"
                logger.info("Using pothole model: %s", model_path)
                self._pothole_model = YOLO(model_path)
            except Exception as e:
                logger.error(f"Failed to load YOLO model: {e}")
                raise e
        
        if self._depth_pipeline is None:
            logger.info("Loading Depth Analysis Model (Depth Anything)...")
            try:
                self._depth_pipeline = pipeline(
                    task="depth-estimation",
                    model="LiheYoung/depth-anything-small-hf"
                )
            except Exception as e:
                logger.error(f"Failed to load Depth model: {e}")
                # We might continue without depth if strictly necessary, but better to fail early for now
                raise e

        if self._sentiment_pipeline is None:
            logger.info("Loading Sentiment Analysis Pipeline...")
            try:
                self._sentiment_pipeline = pipeline(
                    "sentiment-analysis",
                    model="distilbert-base-uncased-finetuned-sst-2-english"
                )
            except Exception as e:
                logger.error(f"Failed to load Sentiment model: {e}")
                raise e
        
        logger.info("All models loaded successfully.")

    def get_pothole_model(self):
        if self._pothole_model is None:
            self.load_models()
        return self._pothole_model

    def get_depth_pipeline(self):
        if self._depth_pipeline is None:
            self.load_models()
        return self._depth_pipeline

    def get_sentiment_pipeline(self):
        if self._sentiment_pipeline is None:
            self.load_models()
        return self._sentiment_pipeline

model_loader = ModelLoader()
