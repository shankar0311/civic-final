# System Port Configuration

This file serves as the **Source of Truth** for all service ports in the Citizen AI System. 
All code changes and docker reruns MUST adhere to these mappings.

## 🌐 Public Services (Host Ports)

| Service | Host Port | Internal Port | Description |
| :--- | :--- | :--- | :--- |
| **Frontend** | `3005` | `80` | Main User Interface (Vite/Nginx) |
| **Backend API** | `8005` | `8000` | FastAPI Backend |
| **Database** | `5432` | `5432` | PostgreSQL/PostGIS |

## 🤖 AI Services (Internal/Docker Network)

These are used for inter-service communication within Docker.

AI services are disabled by default in `docker-compose.yml` (they are heavy) and are only started when running with the `ai` profile:
`docker compose --profile ai up --build`.

| Service | Port | Endpoint |
| :--- | :--- | :--- |
| **AI Duplicate** | `9001` | `http://ai-duplicate:9001` |
| **Pothole Child** | `8001` | `http://ai-pothole-child:8001` |
| **Pothole Parent** | `8003` | `http://ai-pothole-parent:8003` |
| **Garbage Child** | `8002` | `http://ai-garbage-child:8002` |
| **Garbage Parent** | `8004` | `http://ai-garbage-parent:8004` |

## 🛠️ Local Development (Reference)

When running services outside of Docker:
- **Frontend (Vite):** `http://localhost:5173`
- **Backend (Uvicorn):** `http://localhost:8005` (Manually override if running on 8000)

---
*Note: If you change these in `docker-compose.yml`, you MUST update this file and all frontend `.env` or `api.js` configurations.*
