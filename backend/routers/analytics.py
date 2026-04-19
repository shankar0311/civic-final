from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, func
from sqlalchemy.future import select
from database import get_db
from models import User, UserRole, Report, ReportStatus, ReportPriority
from routers.auth import get_current_user
from typing import List, Dict, Optional
from datetime import datetime, timedelta

router = APIRouter(prefix="/analytics", tags=["analytics"])
ROAD_FILTER = Report.category == "road_issues"

@router.get("/status-distribution")
async def get_status_distribution(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get count of reports by status"""
    query = select(
        Report.status,
        func.count(Report.id).label('count')
    ).where(ROAD_FILTER).group_by(Report.status)
    
    result = await db.execute(query)
    rows = result.all()
    
    distribution = {row.status.value: row.count for row in rows}
    
    return {"status_distribution": distribution}

@router.get("/priority-distribution")
async def get_priority_distribution(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get count of reports by priority"""
    query = select(
        Report.priority,
        func.count(Report.id).label('count')
    ).where(ROAD_FILTER).group_by(Report.priority)
    
    result = await db.execute(query)
    rows = result.all()
    
    distribution = {row.priority.value: row.count for row in rows}
    
    return {"priority_distribution": distribution}

@router.get("/time-bound-stats")
async def get_time_bound_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get resolution statistics within time bounds
    Categories: < 24h, < 7d, < 30d, > 30d
    """
    # Query for resolved/closed reports with resolution time
    query = text("""
        SELECT 
            CASE
                WHEN updated_at - created_at < INTERVAL '1 day' THEN 'under_24h'
                WHEN updated_at - created_at < INTERVAL '7 days' THEN 'under_7d'
                WHEN updated_at - created_at < INTERVAL '30 days' THEN 'under_30d'
                ELSE 'over_30d'
            END as time_category,
            COUNT(*) as count
        FROM reports
        WHERE category = 'road_issues'
        AND status IN ('resolved', 'closed')
        AND updated_at IS NOT NULL
        GROUP BY time_category
    """)
    
    result = await db.execute(query)
    rows = result.all()
    
    stats = {row.time_category: row.count for row in rows}
    
    # Ensure all categories exist
    for category in ['under_24h', 'under_7d', 'under_30d', 'over_30d']:
        if category not in stats:
            stats[category] = 0
    
    return {"time_bound_stats": stats}

@router.get("/heatmap-data")
async def get_heatmap_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    status: Optional[str] = None,
    priority: Optional[str] = None
):
    """
    Get geographic data for heatmap visualization
    Returns lat/lon coordinates with intensity (report count)
    """
    # Build query with optional filters
    conditions = []
    if status:
        conditions.append(f"status = '{status}'")
    if priority:
        conditions.append(f"priority = '{priority}'")
    
    conditions.insert(0, "category = 'road_issues'")
    where_clause = f"WHERE {' AND '.join(conditions)}"
    
    query = text(f"""
        SELECT 
            ST_Y(location::geometry) as latitude,
            ST_X(location::geometry) as longitude,
            COUNT(*) as intensity,
            priority,
            status
        FROM reports
        {where_clause}
        GROUP BY ST_Y(location::geometry), ST_X(location::geometry), priority, status
        ORDER BY intensity DESC
        LIMIT 500
    """)
    
    result = await db.execute(query)
    rows = result.all()
    
    heatmap_points = [
        {
            "latitude": row.latitude,
            "longitude": row.longitude,
            "intensity": row.intensity,
            "priority": row.priority,
            "status": row.status
        }
        for row in rows
    ]
    
    return {"heatmap_data": heatmap_points}

@router.get("/trend-analysis")
async def get_trend_analysis(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, description="Number of days to analyze")
):
    """Get report trends over time"""
    query = text(f"""
        SELECT 
            DATE(created_at) as date,
            COUNT(*) as count,
            status
        FROM reports
        WHERE category = 'road_issues'
        AND created_at >= NOW() - INTERVAL '{days} days'
        GROUP BY DATE(created_at), status
        ORDER BY date DESC
    """)
    
    result = await db.execute(query)
    rows = result.all()
    
    # Group by date
    trends = {}
    for row in rows:
        date_str = row.date.isoformat()
        if date_str not in trends:
            trends[date_str] = {}
        trends[date_str][row.status] = row.count
    
    return {"trend_data": trends, "days": days}

@router.get("/predictive-maintenance")
async def predictive_maintenance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Identify hotspots for predictive maintenance.
    Aggregates reports by location and category to find recurring issues.
    """
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Query to find clusters of reports
    query = text("""
        SELECT 
            COUNT(*) as count,
            AVG(ST_X(location::geometry)) as avg_lon,
            AVG(ST_Y(location::geometry)) as avg_lat,
            priority
        FROM reports
        WHERE category = 'road_issues'
        AND created_at > NOW() - INTERVAL '30 days'
        GROUP BY priority
        HAVING COUNT(*) > 2
        ORDER BY count DESC, priority DESC
    """)
    
    result = await db.execute(query)
    hotspots = []
    for row in result:
        hotspots.append({
            "category": "road_issues",
            "report_count": row.count,
            "location": {"lat": row.avg_lat, "lon": row.avg_lon},
            "priority": row.priority,
            "recommendation": "Schedule preventive road maintenance in this area."
        })
        
    return {"hotspots": hotspots}

@router.get("/summary")
async def get_summary_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get overall summary statistics"""
    total_query = select(func.count(Report.id)).where(ROAD_FILTER)
    total_result = await db.execute(total_query)
    total_reports = total_result.scalar()

    pending_query = select(func.count(Report.id)).where(ROAD_FILTER, Report.status == ReportStatus.pending)
    pending_result = await db.execute(pending_query)
    pending_reports = pending_result.scalar()

    resolved_query = select(func.count(Report.id)).where(
        ROAD_FILTER,
        Report.status.in_([ReportStatus.resolved, ReportStatus.closed]),
    )
    resolved_result = await db.execute(resolved_query)
    resolved_reports = resolved_result.scalar()

    critical_query = select(func.count(Report.id)).where(ROAD_FILTER, Report.priority == ReportPriority.critical)
    critical_result = await db.execute(critical_query)
    critical_reports = critical_result.scalar()

    return {
        "total_reports": total_reports,
        "pending_reports": pending_reports,
        "resolved_reports": resolved_reports,
        "critical_reports": critical_reports,
        "resolution_rate": (resolved_reports / total_reports * 100) if total_reports > 0 else 0
    }


@router.get("/dashboard")
async def get_dashboard_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Single endpoint for admin dashboard: stats + severity breakdown + monthly trends + user count"""

    # ── Stats ──────────────────────────────────────────────────────────────
    total_q   = await db.execute(select(func.count(Report.id)))
    total     = total_q.scalar() or 0

    resolved_q = await db.execute(
        select(func.count(Report.id)).where(
            Report.status.in_([ReportStatus.resolved, ReportStatus.closed])
        )
    )
    resolved = resolved_q.scalar() or 0

    users_q  = await db.execute(select(func.count(User.id)).where(User.role == UserRole.citizen))
    users    = users_q.scalar() or 0

    rate = round(resolved / total * 100) if total > 0 else 0

    # ── Severity distribution (pie chart) ──────────────────────────────────
    sev_q = await db.execute(
        select(Report.ai_severity_level, func.count(Report.id).label("cnt"))
        .where(Report.ai_severity_level.isnot(None))
        .group_by(Report.ai_severity_level)
    )
    severity_dist = [{"name": row.ai_severity_level.capitalize(), "value": row.cnt} for row in sev_q.all()]

    # fallback: use severity enum if no AI scores
    if not severity_dist:
        sev_q2 = await db.execute(
            select(Report.severity, func.count(Report.id).label("cnt"))
            .group_by(Report.severity)
        )
        severity_dist = [{"name": row.severity.value.capitalize(), "value": row.cnt} for row in sev_q2.all()]

    # ── Monthly trends (last 6 months) ─────────────────────────────────────
    monthly_q = await db.execute(text("""
        SELECT
            TO_CHAR(created_at, 'Mon') AS month,
            EXTRACT(YEAR  FROM created_at) AS yr,
            EXTRACT(MONTH FROM created_at) AS mo,
            COUNT(*) AS total,
            SUM(CASE WHEN status IN ('resolved','closed') THEN 1 ELSE 0 END) AS resolved
        FROM reports
        WHERE created_at >= NOW() - INTERVAL '6 months'
        GROUP BY month, yr, mo
        ORDER BY yr, mo
    """))
    monthly = [
        {"month": row.month, "reports": int(row.total), "resolved": int(row.resolved)}
        for row in monthly_q.all()
    ]

    return {
        "total_reports":    total,
        "active_users":     users,
        "resolved_reports": resolved,
        "resolution_rate":  rate,
        "severity_dist":    severity_dist,
        "monthly_trends":   monthly,
    }
