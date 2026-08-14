# EdTech RAG Platform

Turns uploaded PDF documents into an interactive, AI-powered revision space: RAG-based Q&A
with citations, auto-generated summaries/quizzes, and a 6-agent crewAI pipeline
(orchestrator, RAG, pedagogical, generator, evaluation, notification).

Stack: Django + DRF, React (Vite) SPA, PostgreSQL, pgvector/Chroma, crewAI, MinIO (S3-compatible
object storage), djangorestframework-simplejwt, SSE streaming, django.core.mail.

> **Status:** base infrastructure only (this step) — auth, project structure, docker services.
> RAG/crewAI/document-ingestion pipeline is a separate, upcoming phase.

## Prerequisites

Install these locally (none are bundled in this repo):

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (with Docker Compose) — for PostgreSQL only
- [MinIO server for Windows](https://min.io/docs/minio/windows/index.html) (`minio.exe`) — run natively, not via Docker
- Python 3.11+
- Node.js 18+ (with npm)

## 1. Start infrastructure

### PostgreSQL (via docker-compose)

```bash
cp .env.example .env
docker compose up -d
docker compose ps
```

PostgreSQL is reachable at `localhost:5432` (db/user/password from `.env`).

### MinIO (native binary, not Docker)

On this machine MinIO runs as a native Windows binary rather than a container. Start it manually
in its own terminal before running the Django backend:

```bash
minio.exe server C:\minio-data --console-address ":9001"
```

- MinIO API: `http://127.0.0.1:9000`
- MinIO Console: `http://127.0.0.1:9001` (login: `minioadmin` / `minioadmin`)

Leave that process running for the duration of your dev session — the backend's document
upload/RAG phase will depend on it being reachable at `127.0.0.1:9000`.

## 2. Backend (Django + DRF)

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
cp .env.example .env

python manage.py makemigrations accounts
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The API is served at `http://localhost:8000/`. Admin site: `http://localhost:8000/admin/`.

### Auth endpoints

| Method | Endpoint                | Description                          |
|--------|--------------------------|---------------------------------------|
| POST   | `/api/auth/register/`   | Create an account (role defaults to `APPRENANT`) |
| POST   | `/api/auth/login/`      | Obtain JWT access/refresh tokens      |
| POST   | `/api/auth/refresh/`    | Refresh an access token               |
| GET    | `/api/auth/me/`         | Current authenticated user's profile  |

Quick manual test with curl:

```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"test@example.com\",\"password\":\"testpass123\",\"password2\":\"testpass123\",\"first_name\":\"Test\",\"last_name\":\"User\"}"

curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"test@example.com\",\"password\":\"testpass123\"}"

curl http://localhost:8000/api/auth/me/ -H "Authorization: Bearer <access_token>"
```

To promote a user to `ADMINISTRATEUR`, use the Django admin or shell:

```bash
python manage.py shell -c "from accounts.models import User; u = User.objects.get(email='test@example.com'); u.role = User.Role.ADMINISTRATEUR; u.save()"
```

## 3. Frontend (React + Vite)

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Opens at `http://localhost:5173`. Register or log in — the SPA talks to the Django API and
stores the JWT pair in `localStorage`, auto-refreshing the access token on 401s.

## Project structure

```
edtech-rag-platform/
├── backend/
│   ├── config/          # Django project (settings, urls, wsgi/asgi)
│   ├── accounts/        # Custom User model (APPRENANT/ADMINISTRATEUR) + JWT auth
│   ├── documents/       # PDF upload/ingestion (next phase)
│   ├── rag/             # Embeddings, vector store, chat (next phase)
│   ├── quiz/            # Quiz generation & evaluation (next phase)
│   ├── notifications/   # Email notifications (next phase)
│   └── manage.py
├── frontend/
│   └── src/
│       ├── api/         # Axios client + auth calls
│       ├── context/     # AuthContext (JWT session state)
│       ├── routes/      # ProtectedRoute
│       └── pages/       # Login, Register, Dashboard
└── docker-compose.yml   # PostgreSQL only (MinIO runs natively — see above)
```

## Environment files

Three separate `.env` files (never committed — see `.gitignore`):

- `/.env` — docker-compose (Postgres credentials)
- `/backend/.env` — Django settings; must reuse the same Postgres credentials, plus the
  `MINIO_*` vars pointing at the natively-running MinIO instance (`127.0.0.1:9000`)
- `/frontend/.env` — Vite (`VITE_API_BASE_URL`)

## Next phase (not started yet)

Document upload to MinIO via presigned URLs, PDF/OCR text extraction, chunking + embeddings,
pgvector/Chroma indexing, the 6 crewAI agents, SSE-streamed chat, quiz generation/evaluation,
and email notifications.
