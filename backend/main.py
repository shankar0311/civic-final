from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy import text
from database import engine, Base
from routers import auth, reports, analytics, votes, upload, modeling, notifications, user as user_router

app = FastAPI(title="Citizen Road Reporting API")

# Create uploads directory if it doesn't exist
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Mount static files for uploads (must be before other routes)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3005",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router)
app.include_router(reports.router)
app.include_router(votes.router)
app.include_router(analytics.router)
app.include_router(upload.router)
app.include_router(modeling.router)
app.include_router(notifications.router)
app.include_router(user_router.router, prefix="/users", tags=["users"])

@app.on_event("startup")
async def startup():
    # Create extensions in isolated transactions so a failure doesn't poison the whole startup transaction.
    async with engine.connect() as conn:
        for stmt in ("CREATE EXTENSION IF NOT EXISTS postgis;", "CREATE EXTENSION IF NOT EXISTS vector;"):
            try:
                async with conn.begin():
                    await conn.execute(text(stmt))
            except Exception as e:
                # Avoid crashing startup if the extension isn't available (e.g., pgvector not installed)
                print(f"Extension init skipped: {stmt} ({e})")

        async with conn.begin():
            await conn.run_sync(Base.metadata.create_all)

@app.get("/")
def read_root():
    return {"message": "Citizen Road Reporting backend is running"}
