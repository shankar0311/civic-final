# System Port Configuration

This file serves as the **Source of Truth** for all service ports in the Citizen Road Reporting System. 
All code changes and docker reruns MUST adhere to these mappings.

## 🌐 Public Services (Host Ports)

| Service | Host Port | Internal Port | Description |
| :--- | :--- | :--- | :--- |
| **Frontend** | `3005` | `80` | Main User Interface (Vite/Nginx) |
| **Backend API** | `8005` | `8000` | FastAPI Backend |
| **Database** | `5433` | `5432` | PostgreSQL/PostGIS |

## Road Analysis

Road severity analysis now runs inside the backend service itself.
There are no separate analysis services or required AI sidecars in Docker.

## 🛠️ Local Development (Reference)

When running services outside of Docker:
- **Frontend (Vite):** `http://localhost:5173`
- **Backend (Uvicorn):** `http://localhost:8005` (Manually override if running on 8000)

---
*Note: If you change these in `docker-compose.yml`, you MUST update this file and all frontend `.env` or `api.js` configurations.*
