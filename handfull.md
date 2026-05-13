# CityReport Handoff

Last updated: 2026-05-13

This document is a full project handoff for CityReport, a civic tech platform for citizen road-damage reports. Citizens submit potholes, cracks, and surface-break issues with images and coordinates. The backend stores reports in PostgreSQL/PostGIS, runs AI-assisted severity scoring, and exposes role-protected APIs. The frontend provides separate workflows for citizens, officers, and admins.

## Current Repository State

- Repo path on this machine: `/Users/shreyas/Desktop/hotspot-prioritizer`
- Git branch: `main`
- Remote: `origin -> https://github.com/Shreyas-R-Gowda/hotspot-prioritizer.git`
- Local branch state at handoff: `main` is ahead of `origin/main` by 2 commits.
- Recent local commits:
  - `b4cb910 Add user profile endpoints and report pagination`
  - `10ee3e8 Fix reporting security and profile features`
  - `fd45e32 feat: UI overhaul, AI severity engine, OSM integration` is currently `origin/main`
- Last push attempt failed because GitHub credentials were unavailable in the Codex environment:
  - HTTPS: `could not read Username for 'https://github.com': Device not configured`
  - SSH: `Host key verification failed`
- To push from an authenticated terminal:

```bash
git push origin main
```

There are also unrelated local working-tree changes that were intentionally left alone during recent work:

- `frontend/Dockerfile`
- `frontend/cityreport/package.json`
- `.claude/`

Check before committing:

```bash
git status --short --branch
git diff --stat
```

## Product Summary

CityReport helps a city public works team prioritize road repairs. The product has three user roles:

- `citizen`: reports road issues, views own reports, browses a map, verifies or disputes resolution.
- `officer`: views assigned/open reports and updates repair status.
- `admin`: sees all reports, AI severity scores, analytics, and can trigger re-analysis.

The main business idea is: citizen reports plus image/text/location signals become an AI severity score. That score drives priority so officers can work on the most urgent road damage first.

## Tech Stack

Backend:

- Python 3.11
- FastAPI 0.109
- SQLAlchemy 2.0 async ORM
- asyncpg
- PostgreSQL 15 with PostGIS
- pgvector extension initialized on startup, though vector use is mostly dormant
- Pydantic v2
- JWT auth via `python-jose`
- Password hashing currently uses direct `bcrypt` helper functions in `backend/utils/security.py`
- AI scoring uses Groq/OpenAI-compatible API shape, OSM Overpass enrichment, PIL/NumPy image heuristics, and optional local ML model loaders

Frontend:

- React 18
- Vite 5
- React Router v6
- Axios
- Recharts
- Leaflet, React Leaflet, `leaflet.heat`
- CSS modules/files and CSS custom properties, not Tailwind as a real installed styling system

Infrastructure:

- Docker Compose local stack
- PostGIS Docker image
- Nginx frontend container
- Render blueprint in `render.yaml`

## Local URLs And Ports

Docker Compose:

- Frontend: `http://localhost:3005`
- Backend: `http://localhost:8005`
- Backend Swagger: `http://localhost:8005/docs`
- Backend ReDoc: `http://localhost:8005/redoc`
- Database: `localhost:5433`, container port `5432`

Vite local dev may also use:

- Frontend dev: `http://localhost:5173`

## How To Run

Start the full local stack:

```bash
docker compose up --build
```

Start detached:

```bash
docker compose up -d --build
```

Stop:

```bash
docker compose down
```

Seed test data:

```bash
docker compose exec backend python seed_data.py
```

Run backend locally without Docker, assuming dependencies and database are ready:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8005
```

Run frontend locally:

```bash
cd frontend/cityreport
npm install
npm run dev
```

Build frontend:

```bash
cd frontend/cityreport
npm run build
```

Lint frontend:

```bash
cd frontend/cityreport
npm run lint
```

Note: full frontend lint currently has pre-existing errors in several files. A focused lint of `MapView.jsx` had 0 errors and 1 pre-existing hook dependency warning.

## Environment Variables

Backend:

- `DATABASE_URL`: async SQLAlchemy URL. Docker Compose overrides it to `postgresql+asyncpg://postgres:postgres@db:5432/cityreport`
- `SECRET_KEY`: JWT signing secret. Must be changed for production.
- `ALGORITHM`: usually `HS256`
- `ACCESS_TOKEN_EXPIRE_MINUTES`: default 30
- `GROK_API_KEY`: Groq API key for primary LLM analysis
- `GOOGLE_CLIENT_ID`: Google OAuth client ID
- `GOOGLE_CLIENT_SECRET`: Google OAuth client secret
- `REDIRECT_URI`: Google OAuth callback URL. Recent fix reads this from env, defaulting to localhost.
- `FRONTEND_URL`: OAuth callback destination back to React app
- `ROAD_DETECTOR_WEIGHTS`: optional YOLO weights path
- `ROAD_DEPTH_MODEL`: optional HuggingFace depth model name/path
- `ROAD_SEVERITY_MODEL`: optional joblib severity model path

Frontend:

- `VITE_API_URL`: backend URL for API calls. Defaults to `http://localhost:8005` in `src/api.js`.

## Backend Entry Point

Main file: `backend/main.py`

Responsibilities:

- Creates FastAPI app
- Mounts static uploads at `/uploads`
- Configures CORS
- Includes routers
- On startup, attempts to create PostGIS and pgvector extensions
- Runs `Base.metadata.create_all`

Mounted routers currently include:

- `auth.router`
- `reports.router`
- `votes.router`
- `analytics.router`
- `upload.router`
- `modeling.router`
- `notifications.router`
- `user_router.router` under `/users`

Important caution: there is no Alembic migration flow in active use. Startup uses `create_all`, which is risky for production schema evolution and does not reliably modify existing columns/indexes.

## Data Model Overview

Main file: `backend/models.py`

### User

Current live model fields:

- `id`
- `name`
- `email`
- `hashed_password`
- `role`
- `created_at`

Important mismatch:

- Some project notes refer to `full_name` and `is_active`, but the live model uses `name` and does not define `is_active`.
- The `/users/me` profile endpoint returns API field `full_name` mapped from `User.name`, and defaults `is_active` to `true`.

### Report

Important fields:

- `id`
- `title`
- `description`
- `category`
- `status`
- `severity`
- `priority`
- `image_url`
- `resolution_image_url`
- `citizen_feedback`
- `location`: PostGIS `POINT`, SRID 4326
- AI component scores: `pothole_depth_score`, `pothole_spread_score`, `emotion_score`, `location_score`, `upvote_score`
- AI final scores: `ai_severity_score`, `ai_severity_level`
- AI metadata: `location_meta`, `sentiment_meta`
- `upvotes`
- `created_at`
- `updated_at`
- `user_id`
- `department_id`
- `assigned_team_id`

Recent index definitions were added inside the `Report` model:

- `ix_reports_status`
- `ix_reports_priority`
- `ix_reports_user_id`
- `ix_reports_created_at`
- `ix_reports_category`

Existing column-level indexes also remain on fields like `title`, `category`, and `priority`, so review for duplicate index creation before production migrations.

### Vote

- Composite primary key on `user_id` and `report_id`
- Used for report upvote toggling

### StoredImage

- Stores uploaded images as database blobs
- Used by `/upload/image` endpoints

### Department And FieldTeam

- Exist in schema
- Used lightly for auto-assigning road reports to a Roads department
- Not fully developed into a complete operations workflow

## Auth And Roles

Auth file: `backend/routers/auth.py`

Endpoints:

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`
- `GET /auth/google/login`
- `GET /auth/google/callback`

JWT:

- Token subject is user email
- `get_current_user` decodes JWT, loads `User` by email, and returns the ORM user

Password hashing:

- `backend/utils/security.py` uses direct `bcrypt.hashpw` and `bcrypt.checkpw`
- Requirements still include `passlib[bcrypt]`, but the live code does not use a `pwd_context`

Recent fixes:

- Removed debug print that leaked login email to logs
- `REDIRECT_URI` now reads `os.getenv("REDIRECT_URI", "http://localhost:8005/auth/google/callback")`

## Reports API

File: `backend/routers/reports.py`

Canonical serializer:

- `_serialize_report(report)` converts the ORM `Report` into the API response dictionary
- It extracts lat/lng from the PostGIS geometry
- New endpoints should reuse it for report responses

Important endpoints:

- `POST /reports/`: creates road report, runs AI scoring, stores report
- `GET /reports/mine`: current citizen's reports
- `GET /reports/`: paginated list of road reports
- `GET /reports/{report_id}`: single report detail
- `POST /reports/{report_id}/verify`: citizen verifies resolved work, sets closed
- `POST /reports/{report_id}/reopen`: citizen disputes resolution, sets reopened and stores feedback
- `PATCH /reports/{report_id}/status`: officer/admin status update
- `POST /reports/{report_id}/reanalyze`: admin AI re-analysis
- `DELETE /reports/{report_id}`: admin/citizen owner delete with vote and notification cleanup

Recent pagination behavior for `GET /reports/`:

Query params:

- Existing filters preserved: `lat`, `lon`, `radius`, `category`, `status`, `priority`, `start_date`, `end_date`, `sort_by`, `sort_order`
- New params:
  - `page: int = Query(1, ge=1)`
  - `limit: int = Query(50, ge=1, le=200)`

Response shape:

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "limit": 50
}
```

Important compatibility note:

- Any frontend code still expecting `/reports/` to return an array must read `data.items`.
- `MapView.jsx` currently still calls `data.filter(...)`, so it likely needs a small compatibility fix after pagination.

## User Profile API

File: `backend/routers/user.py`

Mounted in `backend/main.py` with:

```python
app.include_router(user_router.router, prefix="/users", tags=["users"])
```

Endpoints:

- `GET /users/me`
- `PATCH /users/me`
- `POST /users/me/change-password`

Response shape:

```json
{
  "id": 1,
  "email": "person@example.com",
  "full_name": "Person Name",
  "role": "citizen",
  "is_active": true
}
```

Patch body:

```json
{
  "full_name": "Updated Name",
  "email": "new@example.com"
}
```

Password body:

```json
{
  "current_password": "old-password",
  "new_password": "new-password"
}
```

Behavior:

- Email updates check for duplicates and raise `409` if another user has the email.
- Wrong current password raises `400`.
- New password shorter than 8 characters raises `422`.
- API-level `full_name` maps to DB `User.name`.

## Analytics API

File: `backend/routers/analytics.py`

Endpoints:

- `/analytics/status-distribution`
- `/analytics/priority-distribution`
- `/analytics/time-bound-stats`
- `/analytics/heatmap-data`
- `/analytics/trend-analysis`
- `/analytics/predictive-maintenance`
- `/analytics/summary`
- `/analytics/dashboard`

Recent security fixes:

- `/analytics/heatmap-data` validates `status` and `priority` against enums and uses bound SQL parameters.
- `/analytics/trend-analysis` uses a bound `days` parameter and bounds the query param with `ge=1`, `le=365`.

Remaining caution:

- Some analytics endpoints use raw SQL for PostGIS/date aggregation. Review carefully before accepting new query parameters.

## Upload API

File: `backend/routers/upload.py`

Endpoints:

- `POST /upload/image`: stores image as blob in `StoredImage`
- `GET /upload/image/{id}`: returns image response

Frontend utility:

- `frontend/cityreport/src/utils/image.js` resolves image URLs for display

## Votes API

File: `backend/routers/votes.py`

Endpoint:

- `POST /reports/{id}/upvote`

Behavior:

- Toggles vote
- Recalculates AI score using stored component scores
- Does not make a fresh external LLM call

## Notifications API

File: `backend/routers/notifications.py`

Endpoints:

- `GET /notifications/`
- `POST /notifications/{id}/read`
- `POST /notifications/read-all`

Frontend gap:

- There is no dedicated notifications page yet.

## AI Severity Pipeline

Primary entry point: `backend/ai_analysis.py`

Supporting file: `backend/grok_analysis.py`

High-level flow on report creation:

1. Load uploaded image bytes if `image_url` references `/upload/image/{id}`.
2. Try optional local ML model scoring via `RoadModelSuite`.
3. Try Groq/LLM analysis if `GROK_API_KEY` exists and inputs are usable.
4. Query OSM Overpass for nearby critical POIs and road/traffic context where possible.
5. Fall back to local PIL/NumPy image heuristics.
6. Fall back to text keyword heuristics if image analysis fails.
7. Return component scores and metadata.
8. Convert final score into severity and priority.

AHP-ish weights in `grok_analysis.py`:

- Image: `0.40`
- Location: `0.20`
- Traffic: `0.20`
- Upvotes: `0.10`
- Description: `0.10`

Current Groq model constant:

- `meta-llama/llama-4-scout-17b-16e-instruct`

External network dependencies:

- Groq API
- OSM Overpass API

Failure posture:

- The system is designed to degrade gracefully when external APIs or local model weights are missing.

## Optional ML Workspace

Directory: `ml/`

Important files:

- `ml/README.md`
- `ml/training/train_detector.py`
- `ml/training/train_severity.py`
- `ml/tools/create_dataset_dirs.py`
- `ml/tools/validate_yolo_dataset.py`
- `ml/tools/promote_detector_weights.py`
- `ml/config/road_damage.dataset.example.yaml`
- `ml/templates/severity_labels.example.csv`

Backend optional loader:

- `backend/ml_models.py`

The model suite should fail gracefully when model artifacts are absent.

## Frontend Routing

Entry point: `frontend/cityreport/src/main.jsx`

Router file: `frontend/cityreport/src/App.jsx`

Public routes:

- `/`
- `/login`
- `/signup`
- `/auth/callback`

Citizen routes:

- `/citizen/dashboard`
- `/citizen/report/new`
- `/citizen/report/:id`
- `/citizen/map`
- `/citizen/reports`

Officer routes:

- `/officer/dashboard`
- `/officer/report/:id`

Admin routes:

- `/admin/dashboard`
- `/admin/reports`
- `/admin/reports/:id`
- `/admin/analytics`

Recent frontend route fix:

- `Analytics.jsx` is now imported and reachable at `/admin/analytics`.

## Frontend Auth

File: `frontend/cityreport/src/contexts/AuthContext.jsx`

Behavior:

- Stores `token` and `user` in localStorage
- Login submits `application/x-www-form-urlencoded` to FastAPI OAuth2 endpoint
- After login, fetches `/auth/me`
- Axios interceptor in `src/api.js` attaches the latest token to every request

Potential improvement:

- Add token expiry handling and refresh flow.
- Add global 401 handling to logout or redirect cleanly.

## Citizen Map

File: `frontend/cityreport/src/pages/citizen/MapView.jsx`

Recent marker/status fixes:

- `pending`: red
- `in_progress`: amber
- `resolved`: green
- `reopened`: purple
- `closed`: gray

Status badge mapping:

- `reopened` returns `danger`
- `closed` returns `success`

Filter chips now include:

- Pending
- In Progress
- Resolved
- Reopened
- Closed

Important immediate bug after report pagination:

- `MapView.jsx` currently fetches `/reports/` and assumes the response is an array.
- Because `/reports/` now returns `{ items, total, page, limit }`, update map fetching to something like:

```js
api.get('/reports/', { params: { limit: 200 } })
  .then(({ data }) => {
    const rows = Array.isArray(data) ? data : data.items || [];
    const valid = rows.filter(r => r.latitude && r.longitude);
    ...
  });
```

Do this carefully without changing `HeatmapLayer`, `LocateController`, or `MapContainer` logic unless specifically asked.

## Admin Frontend

Files:

- `frontend/cityreport/src/pages/admin/Dashboard.jsx`
- `frontend/cityreport/src/pages/admin/AdminReports.jsx`
- `frontend/cityreport/src/pages/admin/Analytics.jsx`

Admin functionality:

- Dashboard overview through `/analytics/dashboard`
- Reports grid
- Analytics charts using Recharts
- Report details route reuses citizen `ReportDetail.jsx`

Potential issue:

- Admin/officer report detail reuse may show citizen-oriented actions or hide officer/admin-specific AI details. Review UX role branching.

## Officer Frontend

File:

- `frontend/cityreport/src/pages/officer/Dashboard.jsx`

Current scope:

- Table/list view
- Status update actions

Missing:

- Dedicated officer report detail UI with full AI breakdown and repair workflow context

## Styling

Styles are plain CSS files and shared component CSS:

- `src/index.css`
- `src/App.css`
- `src/components/shared/*.css`
- Page-specific CSS files

There are utility-like class names in JSX, but this project does not appear to have a real Tailwind setup in `frontend/cityreport/package.json`.

## Deployment Notes

Docker Compose:

- DB name is `cityreport`
- Backend exposed as `localhost:8005`
- Frontend exposed as `localhost:3005`
- Backend command still uses `--reload`, which is fine for local Docker dev but not production

Render:

- `render.yaml` backend command no longer uses `--reload`
- Render database is named `citizen_ai`, while Docker app database is `cityreport`
- Confirm whether this mismatch is intentional before production
- `VITE_API_URL` is set from the backend service URL in Render

Production readiness risks:

- `create_all` on startup instead of migrations
- Secret defaults are unsafe
- No CI/CD pipeline
- No health endpoint
- No rate limiting
- No formal test suite covering role/permission flows

## Verification Commands Used Recently

Backend syntax checks:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/codex_pycache python3 -m compileall backend
PYTHONPYCACHEPREFIX=/private/tmp/codex_pycache python3 -m py_compile backend/routers/reports.py
PYTHONPYCACHEPREFIX=/private/tmp/codex_pycache python3 -m py_compile backend/models.py
PYTHONPYCACHEPREFIX=/private/tmp/codex_pycache python3 -m py_compile backend/routers/user.py backend/main.py
```

Frontend checks:

```bash
cd frontend/cityreport
npm run build
npx eslint src/App.jsx
npx eslint src/pages/citizen/MapView.jsx
```

Known lint status:

- `npm run build` passed recently.
- `npx eslint src/App.jsx` passed.
- `npx eslint src/pages/citizen/MapView.jsx` passed with 0 errors and 1 pre-existing hook dependency warning.
- Full `npm run lint` fails due to existing lint issues in multiple components.

Examples of existing lint issues seen:

- Unused variables in `ReportForm.jsx`, `ReportCard.jsx`, `AuthCallback.jsx`, `Dashboard.jsx`, `MyReports.jsx`, `NewReport.jsx`, officer dashboard
- React hook warnings in `LocationPicker.jsx`, `AuthContext.jsx`, `MapView.jsx`, `ReportDetail.jsx`
- `AdminReports.jsx` has a hook/immutability lint complaint around `fetchReports`

## Recent Changes Summary

Security and API fixes:

- Fixed SQL injection risk in analytics heatmap filters.
- Parameterized analytics trend days.
- Removed auth debug email print.
- Made OAuth `REDIRECT_URI` configurable.
- Fixed `debug_meta.py` broken `SessionLocal` import to `AsyncSessionLocal`.
- Removed unused Pydantic v1 `validator` import.

Feature/API changes:

- Added `/users/me` profile endpoints.
- Added password change endpoint.
- Added pagination wrapper to `GET /reports/`.
- Added total count query with same filters as report list.
- Added report indexes in `Report.__table_args__`.

Frontend changes:

- Routed admin analytics page.
- Added reopened/closed map marker colors, labels, badge variants, and filter chips.

## High Priority Next Steps

1. Push local commits to GitHub from an authenticated terminal.

```bash
git push origin main
```

2. Fix frontend callers for paginated `/reports/`.

Likely files:

- `frontend/cityreport/src/pages/citizen/MapView.jsx`
- `frontend/cityreport/src/pages/admin/AdminReports.jsx`
- Any other component using `api.get('/reports/')`

Search:

```bash
rg "api\\.get\\('/reports/|api\\.get\\(\"/reports/" frontend/cityreport/src
```

3. Add Alembic migrations.

This is important because recently added indexes in `models.py` will not automatically appear in existing production databases unless migrations are run or the DB is rebuilt.

4. Add health endpoint.

Recommended:

- `GET /health`
- Return app status, DB connectivity, and maybe extension availability

5. Add rate limiting.

Start with:

- `/auth/login`
- `POST /reports/`
- image upload endpoint

6. Fix full frontend lint.

This will make future changes much easier to trust.

## Medium Priority Backlog

- Comments API and UI
- Notifications page
- User profile page in frontend using `/users/me`
- Officer report detail page
- JWT refresh token flow
- Better role-specific report detail behavior
- Pagination UI for admin reports
- Pagination/infinite loading for map
- Add reopened/closed markers to any legend outside `MapView.jsx`, if one exists later
- Multiple image upload support on report submission
- Add indexes/migrations for status, priority, user ID, category, created date, and possibly geospatial query patterns
- Add DB constraints around enum/status transitions
- Add audit trail for officer status changes
- Add assignment workflow for departments and field teams

## Known Mismatches And Watch-Outs

- Project docs and code sometimes say `GROK_API_KEY`, but the provider/model is Groq. Confirm naming before deployment.
- Some old docs mention OpenAI API key in Render instructions, but current scoring uses `GROK_API_KEY`.
- Live user model has `name`, not `full_name`.
- Live user model has no `is_active`.
- `reports.category` and `reports.priority` already had some column-level indexes before `__table_args__`; avoid duplicate migration definitions later.
- `GET /reports/` response shape changed from array to wrapper object.
- `create_all` does not equal migrations.
- Docker backend command uses `--reload`.
- Render DB name is `citizen_ai`; Docker DB name is `cityreport`.
- There are several AI microservice folders (`ai-pothole-child`, `ai-pothole-parent`, `ai-duplicate`, `ai-ensemble`, `ai-llm`) that appear historical or experimental. The main backend currently uses `backend/ai_analysis.py`, `backend/grok_analysis.py`, and `backend/ml_models.py`.

## Suggested Smoke Test Flow

After starting Docker:

1. Open backend docs:

```text
http://localhost:8005/docs
```

2. Register users:

- Citizen
- Officer
- Admin

3. Login as citizen.

4. Upload image through `/upload/image`.

5. Create report through `/reports/`.

6. Confirm:

- Report appears in `/reports/mine`
- Report appears in `/reports/?page=1&limit=50`
- Response has `items`, `total`, `page`, `limit`
- Report has lat/lng after serialization
- AI score fields are present

7. Login as officer.

8. Update report status:

- `pending`
- `in_progress`
- `resolved`

9. Login as citizen.

10. Verify resolution to close, or reopen with feedback.

11. Check map markers:

- `pending` red
- `in_progress` amber
- `resolved` green
- `reopened` purple
- `closed` gray

12. Login as admin.

13. Visit:

- `/admin/dashboard`
- `/admin/reports`
- `/admin/analytics`

14. Trigger re-analysis on a report if available.

## Suggested Test Coverage

Backend tests to add:

- Auth login/register happy path
- Auth bad password
- `/users/me` get/update/change-password
- Duplicate email update returns 409
- Short password returns 422
- Wrong current password returns 400
- `GET /reports/` pagination defaults
- `GET /reports/` filters and total count
- `GET /reports/` invalid status/priority behavior stays compatible
- Analytics heatmap rejects invalid filters
- Analytics heatmap parameterization does not interpolate raw strings
- Vote toggle recalculates score
- Report delete cascades votes/notifications

Frontend tests to add:

- AuthContext login flow
- ProtectedRoute role redirects
- Admin analytics route renders
- Map status labels and filters include reopened/closed
- Report list handles paginated response wrapper
- AdminReports handles paginated response wrapper

## File Map

Backend:

- `backend/main.py`: FastAPI app setup and router mounting
- `backend/database.py`: async engine/session setup
- `backend/models.py`: SQLAlchemy models
- `backend/schemas.py`: Pydantic schemas
- `backend/routers/auth.py`: auth and OAuth
- `backend/routers/reports.py`: report CRUD and status lifecycle
- `backend/routers/user.py`: profile and password endpoints
- `backend/routers/votes.py`: upvote toggle and score recalculation
- `backend/routers/analytics.py`: admin/dashboard analytics
- `backend/routers/upload.py`: image blob storage
- `backend/routers/notifications.py`: notification reads
- `backend/routers/modeling.py`: model status
- `backend/routers/comments.py`: currently empty
- `backend/ai_analysis.py`: AI scoring orchestrator
- `backend/grok_analysis.py`: Groq and OSM scoring helpers
- `backend/ml_models.py`: optional local model suite
- `backend/utils/security.py`: JWT/password helpers

Frontend:

- `frontend/cityreport/src/App.jsx`: routes
- `frontend/cityreport/src/api.js`: Axios client
- `frontend/cityreport/src/contexts/AuthContext.jsx`: auth state
- `frontend/cityreport/src/pages/auth/*`: login/signup/OAuth callback
- `frontend/cityreport/src/pages/citizen/*`: citizen UI
- `frontend/cityreport/src/pages/officer/Dashboard.jsx`: officer UI
- `frontend/cityreport/src/pages/admin/*`: admin UI and analytics
- `frontend/cityreport/src/components/shared/*`: shared UI components
- `frontend/cityreport/src/utils/image.js`: image URL helper

Infrastructure:

- `docker-compose.yml`: local services
- `backend/Dockerfile`: backend container
- `frontend/Dockerfile`: frontend build/container
- `frontend/nginx.conf`: frontend Nginx config
- `render.yaml`: Render deployment blueprint

## Recommended Development Style

- Keep backend DB operations async.
- Use `Depends(get_db)` for DB session injection.
- Use `Depends(get_current_user)` for protected endpoints.
- Check roles explicitly where needed.
- Use `_serialize_report()` for report API responses.
- Use `src/api.js` for frontend API calls.
- Preserve role-specific route protection in React.
- Prefer migrations over relying on `create_all`.
- Keep route response shapes stable once frontend is updated.

## Immediate Handoff Warning

The most important thing for the next developer: recent backend pagination changed `/reports/` from returning a raw list to returning a wrapper object. That is the right API direction, but the frontend still has at least one likely incompatible caller. Fix that before demoing the map or admin reports.

Second most important thing: local commits are not on GitHub yet because the Codex environment did not have GitHub credentials. Push from an authenticated terminal before handing the repo to anyone else.
