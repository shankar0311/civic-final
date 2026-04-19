from fastapi import APIRouter, Depends, HTTPException

from models import User, UserRole
from routers.auth import get_current_user
from ml_models import road_model_suite

router = APIRouter(prefix="/modeling", tags=["modeling"])


@router.get("/status")
async def model_status(current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    return road_model_suite.status()
