from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database import get_db
from models import Notification
from routers.auth import get_current_user
from models import User

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/")
async def get_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(20)
    )
    notifs = result.scalars().all()
    return [
        {
            "id": n.id,
            "report_id": n.report_id,
            "message": n.message,
            "is_read": bool(n.is_read),
            "created_at": n.created_at.isoformat(),
        }
        for n in notifs
    ]


@router.post("/{notif_id}/read")
async def mark_read(
    notif_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notif_id,
            Notification.user_id == current_user.id,
        )
    )
    notif = result.scalars().first()
    if notif:
        notif.is_read = 1
        await db.commit()
    return {"ok": True}


@router.post("/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read == 0,
        )
    )
    for n in result.scalars().all():
        n.is_read = 1
    await db.commit()
    return {"ok": True}
