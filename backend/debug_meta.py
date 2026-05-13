from database import AsyncSessionLocal
from models import Report
from sqlalchemy import select, desc
import json
import asyncio

async def check_latest_report():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Report).order_by(desc(Report.created_at)).limit(1))
        report = result.scalars().first()
        if report:
            print(f"Report ID: {report.id}")
            print(f"Title: {report.title}")
            print(f"Location Meta (Raw): {report.location_meta}")
            print(f"Sentiment Meta (Raw): {report.sentiment_meta}")
            print(f"AI Severity: {report.ai_severity_score}")
        else:
            print("No reports found.")

if __name__ == "__main__":
    asyncio.run(check_latest_report())
