from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum, Text, Float, LargeBinary, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
from database import Base
import enum

class UserRole(str, enum.Enum):
    citizen = "citizen"
    admin = "admin"
    officer = "officer"

class ReportStatus(str, enum.Enum):
    pending = "pending"
    assigned = "assigned"
    in_progress = "in_progress"
    resolved = "resolved" # Waiting for citizen verification
    closed = "closed"     # Verified by citizen
    reopened = "reopened" # Rejected by citizen
    rejected = "rejected"

class ReportSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

class ReportPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

class Department(Base):
    __tablename__ = "departments"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True) # e.g., Roads, Drainage
    slug = Column(String, unique=True)
    
    teams = relationship("FieldTeam", back_populates="department")
    reports = relationship("Report", back_populates="department")

class FieldTeam(Base):
    __tablename__ = "field_teams"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    status = Column(String, default="active") # active, busy, offline
    current_lat = Column(Float, nullable=True)
    current_lon = Column(Float, nullable=True)
    
    department_id = Column(Integer, ForeignKey("departments.id"))
    department = relationship("Department", back_populates="teams")
    reports = relationship("Report", back_populates="assigned_team")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(Enum(UserRole), default=UserRole.citizen)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    reports = relationship("Report", back_populates="owner")
    votes = relationship("Vote", back_populates="user")

class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        Index('ix_reports_status', 'status'),
        Index('ix_reports_priority', 'priority'),
        Index('ix_reports_user_id', 'user_id'),
        Index('ix_reports_created_at', 'created_at'),
        Index('ix_reports_category', 'category'),
    )

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    category = Column(String, index=True)
    status = Column(Enum(ReportStatus), default=ReportStatus.pending)
    severity = Column(Enum(ReportSeverity), default=ReportSeverity.medium)
    priority = Column(Enum(ReportPriority), default=ReportPriority.medium, index=True)
    
    image_url = Column(String, nullable=True)
    resolution_image_url = Column(String, nullable=True) # Proof of work
    citizen_feedback = Column(Text, nullable=True) # Reason for reopening
    
    # Spatial column: Point in WGS84 (SRID 4326)
    location = Column(Geometry("POINT", srid=4326))
    
    # Embedding for duplicate detection
    # embedding = Column(Vector(384))
    
    # AI Analysis Scores - Pothole Domain
    # pothole_depth_score removed — unreliable from 2D image without depth model
    pothole_spread_score = Column(Float, nullable=True)  # YOLO area_ratio (0-1)
    
    # AI Analysis Scores - Common
    emotion_score = Column(Float, nullable=True)
    location_score = Column(Float, nullable=True)
    upvote_score = Column(Float, nullable=True)
    
    # AI Explanation Metadata
    location_meta = Column(String, nullable=True) # JSON string: { "schools": 2, "hospitals": 1 }
    sentiment_meta = Column(String, nullable=True) # JSON string: { "keywords": ["urgent", "danger"] }
    
    # Final AI Severity Score (0-100)
    ai_severity_score = Column(Float, nullable=True)
    ai_severity_level = Column(String, nullable=True)  # low, medium, high, critical

    upvotes = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user_id = Column(Integer, ForeignKey("users.id"))
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    assigned_team_id = Column(Integer, ForeignKey("field_teams.id"), nullable=True)
    
    owner = relationship("User", back_populates="reports")
    department = relationship("Department", back_populates="reports")
    assigned_team = relationship("FieldTeam", back_populates="reports")
    votes = relationship("Vote", back_populates="report")

class Vote(Base):
    __tablename__ = "votes"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    report_id = Column(Integer, ForeignKey("reports.id"), primary_key=True)
    value = Column(Integer) # 1 for upvote, -1 for downvote

    user = relationship("User", back_populates="votes")
    report = relationship("Report", back_populates="votes")

class Notification(Base):
    __tablename__ = "notifications"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    report_id  = Column(Integer, ForeignKey("reports.id"), nullable=False)
    message    = Column(String, nullable=False)
    is_read    = Column(Integer, default=0)   # 0 = unread, 1 = read
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user   = relationship("User",   foreign_keys=[user_id])
    report = relationship("Report", foreign_keys=[report_id])


class StoredImage(Base):
    __tablename__ = "stored_images"
    
    id = Column(String, primary_key=True, index=True)
    filename = Column(String)
    content_type = Column(String)
    data = Column(LargeBinary)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
