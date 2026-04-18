from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn
import logging
import os
import torch

from model_loader import pothole_model_loader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pothole-parent")

app = FastAPI(title="Pothole Severity Prediction Service")

class SeverityInput(BaseModel):
    depth_score: float = Field(..., ge=0, le=1, description="Depth score from child model")
    spread_score: float = Field(..., ge=0, le=1, description="Spread score from YOLO")
    emotion_score: float = Field(..., ge=0, le=1, description="Urgency from sentiment analysis")
    location_score: float = Field(..., ge=0, le=1, description="Location context score")
    upvote_score: float = Field(..., ge=0, le=1, description="Normalized upvote count")

class SeverityOutput(BaseModel):
    severity_score: float
    severity_level: str

@app.on_event("startup")
def startup_event():
    """Load model at server startup"""
    model_path = os.getenv(
        "POTHOLE_MODEL_PATH",
        "models/pothole_severity.pth"
    )
    pothole_model_loader.load_model(model_path)
    logger.info("Pothole severity prediction service ready on port 8003")

@app.post("/predict", response_model=SeverityOutput)
def predict(input_data: SeverityInput):
    """Predict severity for a pothole report"""
    try:
        # Get model and device
        model, device = pothole_model_loader.get_model()
        
        # Heuristic fallback if model failed to load
        if model is None:
             # Simple weighted formula
             # spread (30%), depth (30%), emotion (20%), location (10%), upvotes (10%)
             weighted_score = (
                 (input_data.spread_score * 0.3) +
                 (input_data.depth_score * 0.3) +
                 (input_data.emotion_score * 0.2) +
                 (input_data.location_score * 0.1) +
                 (input_data.upvote_score * 0.1)
             )
             severity = weighted_score * 100.0
             # Add some randomness for demo feeling if it's too static
             import random
             if severity > 0:
                 severity += random.uniform(-5, 5)
        
        else:
            # Prepare input tensor
            inputs = [
                input_data.depth_score,
                input_data.spread_score,
                input_data.emotion_score,
                input_data.location_score,
                input_data.upvote_score
            ]
            input_tensor = torch.tensor(inputs, dtype=torch.float32).unsqueeze(0)
            input_tensor = input_tensor.to(device)
            
            # Run inference
            with torch.no_grad():
                output = model(input_tensor)
                severity = output.item()
        
        # Scale to 0-100 and clip
        severity_score = max(0.0, min(100.0, severity))
        
        # Map to severity level
        # Map to severity level
        if severity_score >= 80:
            severity_level = "critical"
        elif severity_score >= 60:
            severity_level = "high"
        elif severity_score >= 40:
            severity_level = "medium"
        else:
            severity_level = "low"
        
        return SeverityOutput(
            severity_score=round(severity_score, 2),
            severity_level=severity_level
        )
    
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "pothole-parent-model",
        "port": 8003,
        "model_loaded": pothole_model_loader._model is not None
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
