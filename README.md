# Citizen AI System

A full-stack Citizen Issue Reporting & Management System with AI capabilities.

## Features
- **Backend**: FastAPI, SQLAlchemy (Async), PostGIS (Spatial), pgvector (Embeddings).
- **Frontend**: React (Vite), TailwindCSS, Leaflet Maps.
- **AI Services**:
  - `ai-duplicate`: Duplicate detection using Sentence Transformers.
  - `ai-llm`: Summarization and Text-to-SQL using OpenAI/LLMs.
- **Infrastructure**: Docker Compose, Nginx, Render Deployment.

## Prerequisites
- Docker & Docker Compose
- Node.js 18+ (for local frontend dev)
- Python 3.11+ (for local backend dev)

## Quick Start (Docker)

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd citizen-ai-system
   ```

2. **Environment Setup**
   Copy `.env.example` to `.env` in `backend/` and `ai-llm/`.
   ```bash
   cp backend/.env.example backend/.env
   # Edit backend/.env to set your secrets
   ```

3. **Run with Docker Compose**
   ```bash
   docker compose up --build
   ```
   This starts the core stack:
   - Frontend: http://localhost:3005
   - Backend: http://localhost:8005
   - Postgres: localhost:5432

   To also build/run the (optional) AI services, run:
   ```bash
   docker compose --profile ai up --build
   ```
   AI services are heavy (PyTorch / transformers) and are disabled by default.

4. **Seed Data**
   To populate the database with synthetic reports:
   ```bash
   docker compose exec backend python seed_data.py
   ```

## Development

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend/cityreport
npm install
npm run dev
```

## Deployment (Render)

1. Connect your GitHub repository to Render.
2. Create a **Blueprint** using `render.yaml`.
3. Set the `OPENAI_API_KEY` environment variable in the Render dashboard.
4. Ensure the Postgres database is provisioned with PostGIS and pgvector extensions.
   - You may need to run `CREATE EXTENSION vector;` manually if the image doesn't auto-enable it, but `ankane/pgvector` should handle it.

## API Documentation
- Swagger UI: http://localhost:8005/docs
- ReDoc: http://localhost:8005/redoc
