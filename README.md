# Citizen Road Reporting System

A full-stack road-issue reporting and triage system focused on potholes and surface damage.

## Features
- **Backend**: FastAPI, SQLAlchemy (Async), PostGIS (Spatial), pgvector (Embeddings).
- **Frontend**: React (Vite), TailwindCSS, Leaflet Maps.
- **Road Analysis**: Deterministic local image, text, and location scoring for road severity.
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
   Copy `.env.example` to `.env` in `backend/`.
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
   - Postgres: localhost:5433

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

## Model Training

The repo now includes a model-training workspace under `ml/` for:

- YOLO road-damage detection
- optional depth-model integration
- optional learned severity scoring

Start with:

```bash
pip install -r backend/requirements-ml.txt
python ml/training/train_detector.py --data ml/config/road_damage.dataset.example.yaml
```

See [`ml/README.md`](/Users/shreyas/Documents/New%20project/hotspot-prioritizer/ml/README.md) for the full step-by-step flow.

## Deployment (Render)

1. Connect your GitHub repository to Render.
2. Create a **Blueprint** using `render.yaml`.
3. Set the `OPENAI_API_KEY` environment variable in the Render dashboard.
4. Ensure the Postgres database is provisioned with PostGIS enabled.

## API Documentation
- Swagger UI: http://localhost:8005/docs
- ReDoc: http://localhost:8005/redoc
