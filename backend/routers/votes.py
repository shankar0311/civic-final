from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.shape import to_shape
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database import get_db
from models import Report, User, Vote
from routers.auth import get_current_user

router = APIRouter(prefix="/reports", tags=["votes"])


@router.post("/{report_id}/upvote")
async def upvote_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalars().first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    vote_result = await db.execute(
        select(Vote).where(
            Vote.user_id == current_user.id,
            Vote.report_id == report_id,
        )
    )
    existing_vote = vote_result.scalars().first()

    if existing_vote:
        if existing_vote.value == 1:
            await db.delete(existing_vote)
            report.upvotes = max(0, report.upvotes - 1)
        else:
            existing_vote.value = 1
            report.upvotes += 1
    else:
        db.add(Vote(user_id=current_user.id, report_id=report_id, value=1))
        report.upvotes += 1

    await db.commit()
    await db.refresh(report)
    updated = await recalculate_ai_score(report, db)

    return {"message": "Vote recorded", "upvotes": report.upvotes, **updated}


@router.post("/{report_id}/downvote")
async def downvote_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalars().first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    vote_result = await db.execute(
        select(Vote).where(
            Vote.user_id == current_user.id,
            Vote.report_id == report_id,
        )
    )
    existing_vote = vote_result.scalars().first()

    if existing_vote:
        if existing_vote.value == -1:
            await db.delete(existing_vote)
        else:
            existing_vote.value = -1
            report.upvotes = max(0, report.upvotes - 1)
    else:
        db.add(Vote(user_id=current_user.id, report_id=report_id, value=-1))

    await db.commit()
    await db.refresh(report)
    updated = await recalculate_ai_score(report, db)

    return {"message": "Vote recorded", "upvotes": report.upvotes, **updated}


async def recalculate_ai_score(report: Report, db: AsyncSession) -> dict:
    """Fast AHP re-score using stored component scores — no Groq/OSM calls."""
    import json

    if not report.ai_severity_score:
        return {}

    try:
        sentiment = json.loads(report.sentiment_meta or "{}")
        location = json.loads(report.location_meta or "{}")

        image_score    = float(sentiment.get("image_score") or 0)
        desc_score     = float(sentiment.get("description_score") or (report.emotion_score or 0) * 100)
        location_score = float(sentiment.get("location_score") or location.get("location_score") or (report.location_score or 0) * 100)
        traffic_score  = float(location.get("traffic_score") or sentiment.get("traffic_score") or 0)

        upvote_ratio = min((report.upvotes or 0) / 25.0, 1.0)
        upvote_score = round(upvote_ratio * 100)

        # Weights: Image 40%, Description 25%, Location 15%, Traffic 10%, Upvotes 10%
        final = round(min(
            0.40 * image_score +
            0.25 * desc_score +
            0.15 * location_score +
            0.10 * traffic_score +
            0.10 * upvote_score,
            100.0
        ), 1)

        if final >= 76:
            level = "critical"
        elif final >= 51:
            level = "high"
        elif final >= 26:
            level = "medium"
        else:
            level = "low"

        sentiment["upvote_score"] = upvote_score
        report.upvote_score = upvote_ratio
        report.ai_severity_score = final
        report.ai_severity_level = level
        report.sentiment_meta = json.dumps(sentiment)

        await db.commit()
        return {"ai_severity_score": final, "ai_severity_level": level, "upvote_score": upvote_score}

    except Exception:
        return {}
