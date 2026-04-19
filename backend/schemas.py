from pydantic import BaseModel, EmailStr, Field, validator, field_validator
from typing import Optional, List, Any
from datetime import datetime
from models import UserRole, ReportStatus, ReportSeverity, ReportPriority

# User Schemas
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    name: str
    password: str
    role: UserRole = UserRole.citizen

class UserResponse(UserBase):
    id: int
    name: Optional[str] = None
    role: UserRole
    created_at: datetime

    class Config:
        from_attributes = True

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# Department & Team Schemas
class DepartmentResponse(BaseModel):
    id: int
    name: str
    slug: str
    
    class Config:
        from_attributes = True

class FieldTeamResponse(BaseModel):
    id: int
    name: str
    status: str
    current_lat: Optional[float]
    current_lon: Optional[float]
    department_id: int
    
    class Config:
        from_attributes = True

# Report Schemas
class ReportBase(BaseModel):
    title: str
    description: str
    category: str = "road_issues"
    latitude: float
    longitude: float
    image_url: Optional[str] = None

class ReportCreate(ReportBase):
    pass

class ReportResponse(BaseModel):
    id: int
    title: str
    description: str
    category: str
    status: ReportStatus
    severity: ReportSeverity
    priority: ReportPriority
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    image_url: Optional[str] = None
    upvotes: int
    created_at: datetime
    user_id: int
    department_id: Optional[int]
    assigned_team_id: Optional[int]
    resolution_image_url: Optional[str]
    citizen_feedback: Optional[str]
    
    # AI Scores - Pothole Domain
    pothole_depth_score: Optional[float] = None
    pothole_spread_score: Optional[float] = None

    # AI Scores - Common
    emotion_score: Optional[float] = None
    location_score: Optional[float] = None
    upvote_score: Optional[float] = None
    
    # Final AI Severity
    ai_severity_score: Optional[float] = None
    ai_severity_level: Optional[str] = None
    
    # Metadata for explanations
    location_meta: Optional[str] = None
    sentiment_meta: Optional[str] = None
    
    class Config:
        from_attributes = True

class ReportUpdate(BaseModel):
    status: Optional[ReportStatus] = None
    severity: Optional[ReportSeverity] = None
    title: Optional[str] = None
    description: Optional[str] = None
    resolution_image_url: Optional[str] = None
    citizen_feedback: Optional[str] = None
    assigned_team_id: Optional[int] = None
