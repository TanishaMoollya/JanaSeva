# JANASEVA — Civic Grievance Portal

JANASEVA is a local civic-service prototype for reporting municipal issues and tracking their progress. It uses React/Vite in the browser and FastAPI, SQLAlchemy, and SQLite on the backend. AI recommendations currently use transparent rule-based fallback logic; a provider key is not required.

## What is implemented

- Citizen registration, sign-in, password hashing, and expiring JWTs
- Complaint submission, private citizen listing/detail, generated reference IDs, categories, optional coordinates, priority suggestions, and department suggestions
- Complaint status timeline, guarded status transitions, department assignment API, resolution details, and in-app status notifications
- Department dashboard, administrator statistics API, privacy-rounded public map feed, and Leaflet map
- Restricted JPEG/PNG/WebP uploads with size/content checks, randomized storage names, and authorization on download
- AI classification fallback and advisory guidance data without an external API dependency
- OpenAPI docs at `/docs`

## Not implemented yet

External Gemini calls, email/SMS, multilingual interface, configurable deadlines and escalation, PostgreSQL deployment automation, and production hosting. The department and account controls are local prototype screens. This is not a government-integrated or production-ready system.

## Windows PowerShell setup

Open two VS Code terminals at the project root. Check the tools first:

```powershell
py --version
node --version
npm.cmd --version
git --version
```

If the Python launcher is unavailable, install Python 3.11+ and enable the Python launcher. If `npm` is blocked by PowerShell execution policy, use `npm.cmd` as shown below.

### Backend (Terminal 1)

```powershell
cd C:\Users\Tanisha\Desktop\TANISHA\JanaSeva\backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend\.env`: set `JWT_SECRET` to a long random private value before using accounts beyond a local demo. The local SQLite file is created automatically when the server starts. Create the first administrator through the interactive prompt:

```powershell
python -m app.cli create-admin
```

Start FastAPI:

```powershell
uvicorn app.main:app --reload
```

Visit <http://127.0.0.1:8000/docs> and confirm `/api/health` returns `{"status":"ok"}`. Stop the server with `Ctrl+C`.

### Frontend (Terminal 2)

```powershell
cd C:\Users\Tanisha\Desktop\TANISHA\JanaSeva\frontend
npm.cmd install
npm.cmd run dev
```

Open <http://localhost:5173>. Create a citizen account, submit a fictional issue, then sign in as the administrator. For an official demo account, use the interactive Python shell or add an admin-only official creation workflow before the demo; public registration intentionally cannot create staff accounts.

## Tests and build

With the backend virtual environment active:

```powershell
cd C:\Users\Tanisha\Desktop\TANISHA\JanaSeva\backend
pytest
```

For a frontend production bundle:

```powershell
cd C:\Users\Tanisha\Desktop\TANISHA\JanaSeva\frontend
npm.cmd run build
```

The tests use `backend/test_janaseva.db`, separate from the normal local `janaseva.db`. Stop development servers with `Ctrl+C` in their terminal windows.

## API outline

Auth: `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/users/me`.

Reports: `POST/GET /api/complaints`, `GET /api/complaints/{id}`, `GET /api/complaints/{id}/history`, `PATCH /api/complaints/{id}/status`, `POST /api/complaints/{id}/assign`, `POST/GET /api/complaints/{id}/attachments`.

Public/map and service: `GET /api/map/complaints`, `GET /api/departments`, `GET /api/dashboard/stats`, `GET /api/notifications`, `PATCH /api/notifications/{id}/read`, `POST /api/ai/analyze`, `POST /api/ai/possible-duplicates`, `POST /api/ai/guidance`, and `GET /api/complaints/{id}/resolution-support`.

All protected endpoints require `Authorization: Bearer <token>`. Use `/docs` for the live schema.

## Demo walkthrough

Use fictional details only. Create a citizen account, submit a pothole report, verify its generated reference, and open the map (coordinates are optional). Create an admin interactively; staff accounts/department management UI is a follow-up. The report lifecycle API supports review, assignment, progress, resolution with required details, closure, and reopening. AI category and priority suggestions are advisory. There are no measured service improvements or real municipal integrations.

## Design/deployment notes

The browser calls FastAPI with JSON and JWT bearer authorization. FastAPI validates request bodies using Pydantic, checks role/ownership, and stores records with SQLAlchemy. SQLite is for local development. For deployment, configure a PostgreSQL SQLAlchemy URL, unique production JWT secret, HTTPS, exact frontend CORS origin, persistent private attachment storage, backups, and a real migration workflow. Never commit `.env`, uploaded files, or citizen data. OpenStreetMap tiles require attribution and are subject to the tile service usage policy.
