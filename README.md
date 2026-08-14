# EdTech RAG Platform

Turns uploaded PDF documents into an interactive, AI-powered revision space: RAG-based Q&A
with citations, auto-generated summaries/quizzes, and a 6-agent crewAI pipeline
(orchestrator, RAG, pedagogical, generator, evaluation, notification).

Stack: Django + DRF, React (Vite) SPA, PostgreSQL, pgvector/Chroma, crewAI, MinIO (S3-compatible
object storage), djangorestframework-simplejwt, SSE streaming, django.core.mail.

> **Status:** base infrastructure (auth, project structure, docker services) plus the document
> upload/RAG-ingestion pipeline (Step 2). crewAI agents, RAG chat, quiz generation, and
> notifications are still upcoming.

## Prerequisites

Install these locally (none are bundled in this repo):

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (with Docker Compose) — for PostgreSQL only
- [MinIO server for Windows](https://min.io/docs/minio/windows/index.html) (`minio.exe`) — run natively, not via Docker
- Python 3.11+
- Node.js 18+ (with npm)
- **Tesseract OCR** (optional but recommended): [installer for Windows](https://github.com/UB-Mannheim/tesseract/wiki).
  Without it, scanned/image-only PDF pages are simply skipped (no crash) — extractable-text PDFs
  still ingest fully. Install it and make sure `tesseract.exe` is on `PATH` to enable OCR fallback.

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

python manage.py makemigrations accounts documents
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

> `pip install` downloads `torch` (CPU build, ~120 MB) as a dependency of `sentence-transformers`
> — the first install takes a few minutes. The embedding model (`all-MiniLM-L6-v2`, ~90 MB) is
> downloaded from Hugging Face and cached locally the first time it's used (first document
> upload), not at install time.

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

### Document upload & RAG ingestion endpoints

Upload is a 3-step flow: request a presigned MinIO URL, `PUT` the file directly to MinIO, then
confirm — the confirm call runs ingestion **synchronously** (extraction → OCR fallback →
chunking → embeddings → Chroma) and returns the final document status.

| Method | Endpoint                          | Description                                              |
|--------|------------------------------------|------------------------------------------------------------|
| POST   | `/api/documents/upload-url/`      | Validate metadata + quota, return a presigned MinIO PUT URL |
| POST   | `/api/documents/confirm/`         | Confirm upload landed in MinIO, run ingestion, return the `Document` |
| GET    | `/api/documents/`                 | List the current user's documents                          |
| GET    | `/api/documents/<id>/`            | Retrieve one document                                      |
| PATCH  | `/api/documents/<id>/`            | Rename (`filename` is the only writable field)             |
| DELETE | `/api/documents/<id>/`            | Delete — removes the MinIO object, Chroma vectors, and the DB row |
| POST   | `/api/documents/<id>/retry/`      | Re-run ingestion on a `FAILED` document                    |

Business rules enforced server-side: PDF only, ≤ 50 Mo, ≤ 500 pages, per-user quotas
(`max_documents` / `max_storage_mb` on the `User` model — defaults 10 docs / 500 Mo), and
duplicate-content rejection (dedup by the MinIO object's MD5 `ETag`, scoped per owner, ignoring
previously `FAILED` uploads so a failed upload can be retried).

Quick manual test with curl (replace `<access_token>`; on Windows use PowerShell's `curl.exe` or
Git Bash):

```bash
SIZE=$(wc -c < sample.pdf)
curl -X POST http://localhost:8000/api/documents/upload-url/ \
  -H "Authorization: Bearer <access_token>" -H "Content-Type: application/json" \
  -d "{\"filename\":\"sample.pdf\",\"content_type\":\"application/pdf\",\"size_bytes\":$SIZE}"
# -> { upload_url, storage_key, content_type, expires_in }

curl -X PUT "<upload_url>" -H "Content-Type: application/pdf" --data-binary @sample.pdf

curl -X POST http://localhost:8000/api/documents/confirm/ \
  -H "Authorization: Bearer <access_token>" -H "Content-Type: application/json" \
  -d "{\"storage_key\":\"<storage_key>\",\"filename\":\"sample.pdf\"}"
# -> { id, filename, status: "READY", size_bytes, page_count, failure_reason, created_at, updated_at }

curl http://localhost:8000/api/documents/ -H "Authorization: Bearer <access_token>"
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

Once logged in, the dashboard shows a drag-drop/file-picker upload zone and a document table
(name, status badge, size, page count, date). The table polls every 3s while any document is
`UPLOADED`/`PROCESSING`, and supports inline rename (double-click the name or the "Renommer"
button), delete, and "Relancer" (retry) for `FAILED` documents.

## Project structure

```
edtech-rag-platform/
├── backend/
│   ├── config/          # Django project (settings, urls, wsgi/asgi)
│   ├── accounts/        # Custom User model (APPRENANT/ADMINISTRATEUR) + JWT auth
│   ├── documents/       # Upload, quota, extraction/OCR/chunking, ingestion orchestration
│   ├── rag/             # Embeddings (sentence-transformers) + Chroma vector store (shared with the future chat phase)
│   ├── quiz/            # Quiz generation & evaluation (next phase)
│   ├── notifications/   # Email notifications (next phase)
│   ├── chroma_data/     # Chroma's persisted vector DB (gitignored, created on first ingestion)
│   └── manage.py
├── frontend/
│   └── src/
│       ├── api/         # Axios client + auth/document calls
│       ├── context/     # AuthContext (JWT session state)
│       ├── routes/      # ProtectedRoute
│       └── pages/       # Login, Register, Dashboard, DocumentUpload, DocumentList
└── docker-compose.yml   # PostgreSQL only (MinIO runs natively — see above)
```

## Environment files

Three separate `.env` files (never committed — see `.gitignore`):

- `/.env` — docker-compose (Postgres credentials)
- `/backend/.env` — Django settings; must reuse the same Postgres credentials, plus the
  `MINIO_*` vars pointing at the natively-running MinIO instance (`127.0.0.1:9000`)
- `/frontend/.env` — Vite (`VITE_API_BASE_URL`)

## Next phase (not started yet)

The 6 crewAI agents (orchestrator, RAG, pedagogical, generator, evaluation, notification),
SSE-streamed RAG chat with citations, quiz generation/evaluation, and email notifications.

## Notes on this implementation

- **Ingestion runs synchronously** inside the `confirm` request/response cycle (per current
  scope — no task queue yet). The first upload in a process is slower because it loads the
  embedding model into memory; subsequent uploads reuse it.
- **Chunking**: page-by-page, ~500–1000 characters with ~150-character overlap, breaking on
  whitespace near the boundary. Each chunk keeps its source page number.
- **OCR fallback**: pages with no extractable text are rasterized (via `pypdfium2`) and run
  through Tesseract. If Tesseract isn't installed, OCR is skipped silently (logged as a
  warning) rather than failing the whole document — only genuinely text-based PDFs are
  guaranteed to ingest without it.
- **Vector store**: a single persistent Chroma collection (`document_chunks`) with
  `document_id`/`owner_id`/`page_number`/`chunk_index` metadata per vector; deleting a document
  removes its vectors via a metadata filter.
