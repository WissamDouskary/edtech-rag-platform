# EdTech RAG Platform

Turns uploaded PDF documents into an interactive, AI-powered revision space: RAG-based Q&A
with citations, auto-generated summaries/quizzes, and a 6-agent crewAI pipeline
(orchestrator, RAG, pedagogical, generator, evaluation, notification).

Stack: Django + DRF, React (Vite) SPA, PostgreSQL, pgvector/Chroma, crewAI, MinIO (S3-compatible
object storage), djangorestframework-simplejwt, SSE streaming, django.core.mail.

> **Status:** base infrastructure, document upload/RAG-ingestion (Step 2), and the multi-agent
> RAG chat (Step 3 — orchestrateur/RAG/pédagogique agents, SSE streaming, citations) are done.
> Quiz generation/evaluation and email notifications are still upcoming.

> **On "crewAI":** the `crewai` PyPI package requires Python `<3.14`; this project's environment
> runs Python 3.14, and even crewAI's oldest release pulls in a pinned `numpy` with no 3.14 wheel
> (it tries to compile from source, which fails with no C compiler present). The 6 agents are
> therefore implemented as a lightweight, dependency-free Agent/Task pattern (role, goal,
> backstory + a `run()` callable) in [`backend/rag/services/agents.py`](backend/rag/services/agents.py)
> — structurally the same idea crewAI wraps, just without the package. If your grading requires
> the literal `crewai` import, this needs a Python 3.11–3.13 venv; ask before assuming either way.

## Prerequisites

Install these locally (none are bundled in this repo):

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (with Docker Compose) — for PostgreSQL only
- [MinIO server for Windows](https://min.io/docs/minio/windows/index.html) (`minio.exe`) — run natively, not via Docker
- Python 3.11+
- Node.js 18+ (with npm)
- **Tesseract OCR** (optional but recommended): [installer for Windows](https://github.com/UB-Mannheim/tesseract/wiki).
  Without it, scanned/image-only PDF pages are simply skipped (no crash) — extractable-text PDFs
  still ingest fully. Install it and make sure `tesseract.exe` is on `PATH` to enable OCR fallback.
- **Gemini API key** (free tier) — powers the multi-agent RAG chat. Get one at
  [aistudio.google.com/apikey](https://aistudio.google.com/apikey) (Google account, no credit
  card). See "Why Gemini" below.

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

### Multi-agent RAG chat (crewAI-pattern) + SSE streaming

**Why Gemini:** free tier with no credit card, official Python SDK (`google-genai`) with clean
streaming support, and generous-enough rate limits for a school project. (Originally chose Groq
for its very fast token generation, but switched to Gemini per your preference — you already had
a key ready and didn't want to sign up for another service before the deadline.)

Two Gemini models are used, both under `gemini-*-latest` aliases so they keep resolving to a
currently-supported model instead of hitting hard deprecation 404s (dated model names like
`gemini-2.5-flash` returned "no longer available to new users" during testing):

- `GEMINI_ORCHESTRATOR_MODEL` (default `gemini-flash-lite-latest`) — fast intent classification.
- `GEMINI_PEDAGOGICAL_MODEL` (default `gemini-flash-lite-latest`) — the streamed answer. The
  heavier `gemini-flash-latest` tier returned frequent `503 UNAVAILABLE` ("high demand") during
  testing; the lite tier was fast (<1s to first token) and reliable, so it's the default for
  both agents. If you want the beefier model and can tolerate occasional retries, set
  `GEMINI_PEDAGOGICAL_MODEL=gemini-flash-latest` in `backend/.env`.

**The 6 agents** (`backend/rag/services/agents.py`) — orchestrateur, RAG, and pédagogique are
fully functional; générateur/évaluation/notification are declared with their real
role/goal/backstory but only return a `{"status": "not_implemented", ...}` stub for now:

1. **Orchestrateur** — classifies intent (`question_factuelle` / `explication` /
   `demande_de_quiz` / `demande_de_resume` / `autre`) and rewrites the question into a
   standalone search query using recent conversation history (resolves "it"/"that" style
   references). Non-streaming Gemini call, JSON output.
2. **Agent RAG** — embeds the enriched query (same local `sentence-transformers` model as
   ingestion) and does a top-k similarity search against Chroma, scoped to the conversation's
   documents (or the whole workspace).
3. **Agent pédagogique** — streams the answer via Gemini, instructed to answer **only** from the
   retrieved passages (to limit hallucination) at the conversation's vulgarization level
   (`SIMPLE`/`INTERMEDIATE`/`EXPERT`), with numbered citations `[1]`, `[2]` matching the passage
   order. If intent is `demande_de_quiz`, it still answers helpfully but notes that full quiz
   generation is coming in a later phase.
4–6. **Générateur / Évaluation / Notification** — stubs, to be implemented in the quiz and
   notification phases.

**Citations, precisely:** rather than trust the LLM to output structured citation JSON (unreliable
under streaming), the backend already knows exactly which retrieved passage each `[n]` refers to
(it built the prompt that way). After streaming finishes, it regex-scans the assembled text for
`[n]` markers actually used and returns only those, each with `document_id`, `document_filename`,
`page_number`, `chunk_id`, and a short excerpt.

**Citation click-through — the trade-off:** true in-browser PDF highlighting needs a pdf.js-based
viewer with text-layer coordinate mapping — heavy for this phase. Instead, clicking a citation
chip does two lighter-weight things: (1) shows the exact excerpt inline, expandable under the
message, and (2) offers an "Ouvrir le PDF à la page N" button that fetches a presigned MinIO GET
URL and opens `<url>#page=N` in a new tab — Chrome/Edge/Firefox's built-in PDF viewer jumps to
that page automatically via the URL fragment (not exact-passage highlighting, but page-accurate
and zero extra dependencies).

| Method | Endpoint                                        | Description                                    |
|--------|--------------------------------------------------|--------------------------------------------------|
| POST   | `/api/rag/conversations/`                       | Create a conversation (`scope`, `document_ids`, `vulgarization_level`) |
| GET    | `/api/rag/conversations/`                       | List the current user's conversations           |
| GET    | `/api/rag/conversations/<id>/`                  | Retrieve one conversation with its full message history |
| DELETE | `/api/rag/conversations/<id>/`                  | Delete a conversation                            |
| POST   | `/api/rag/conversations/<id>/messages/`         | Send a message — **`text/event-stream` response** |
| GET    | `/api/documents/<id>/download-url/`             | Presigned GET URL for a `READY` document (citation click-through) |

`scope` is `DOCUMENT` (exactly one `document_ids` entry), `DOCUMENTS` (one or more), or
`WORKSPACE` (searches all of the owner's `READY` documents; `document_ids` ignored).

The message endpoint streams Server-Sent Events — note this is **not** a plain `EventSource`
(which can't send an `Authorization` header), the frontend uses `fetch` + manual SSE parsing
instead. Event types: `intent` (classification result, fires once early), `token` (one text
delta per event), `done` (final `message_id` + `citations`), `error`.

Quick manual test with curl (`-N` disables buffering so you see events as they arrive):

```bash
curl -N -X POST http://localhost:8000/api/rag/conversations/ \
  -H "Authorization: Bearer <access_token>" -H "Content-Type: application/json" \
  -d '{"scope":"WORKSPACE","vulgarization_level":"SIMPLE"}'
# -> {"id": 1, ...}

curl -N -X POST http://localhost:8000/api/rag/conversations/1/messages/ \
  -H "Authorization: Bearer <access_token>" -H "Content-Type: application/json" \
  -d '{"content":"Explique-moi ce concept simplement"}'
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
button), delete, and "Relancer" (retry) for `FAILED` documents. Each `READY` row has a
"Discuter" button.

**Chat** (`/chat`, or "Discuter avec mes documents" in the top bar): a sidebar lists your
conversations; "+ Nouvelle conversation" opens a form to pick scope (one document / several /
whole workspace) and vulgarization level. Arriving via a document's "Discuter" button
pre-fills scope=one-document for that document. The message thread renders the streamed answer
live, `[n]` citation markers become clickable chips (excerpt + "open PDF at page N"), and each
assistant reply gets "Approfondir" / "Simplifier" / "Générer un quiz sur ce point" buttons that
resend a canned follow-up prompt into the same conversation (relying on conversation memory —
no special backend logic).

## Project structure

```
edtech-rag-platform/
├── backend/
│   ├── config/          # Django project (settings, urls, wsgi/asgi)
│   ├── accounts/        # Custom User model (APPRENANT/ADMINISTRATEUR) + JWT auth
│   ├── documents/       # Upload, quota, extraction/OCR/chunking, ingestion orchestration
│   ├── rag/             # Conversation/Message models, the 6 agents, Gemini client,
│   │                    # embeddings + Chroma vector store, SSE chat endpoint
│   ├── quiz/            # Quiz generation & evaluation (next phase)
│   ├── notifications/   # Email notifications (next phase)
│   ├── chroma_data/     # Chroma's persisted vector DB (gitignored, created on first ingestion)
│   └── manage.py
├── frontend/
│   └── src/
│       ├── api/         # Axios client + auth/document/chat (SSE) calls
│       ├── context/     # AuthContext (JWT session state)
│       ├── routes/      # ProtectedRoute
│       └── pages/       # Login, Register, Dashboard, DocumentUpload, DocumentList, ChatPage
└── docker-compose.yml   # PostgreSQL only (MinIO runs natively — see above)
```

## Environment files

Three separate `.env` files (never committed — see `.gitignore`):

- `/.env` — docker-compose (Postgres credentials)
- `/backend/.env` — Django settings; must reuse the same Postgres credentials, plus the
  `MINIO_*` vars pointing at the natively-running MinIO instance (`127.0.0.1:9000`) and
  `GEMINI_API_KEY` for the chat
- `/frontend/.env` — Vite (`VITE_API_BASE_URL`)

## Next phase (not started yet)

Quiz generation (agent générateur) and evaluation (agent d'évaluation) — QCM/Vrai-Faux/open
questions, exact-match + LLM-assisted semantic grading — and email notifications
(agent de notification) via `django.core.mail`.

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
- **Chat streaming is synchronous within the request** too: the orchestrateur and RAG-retrieval
  steps run before the `StreamingHttpResponse` starts sending, then the pédagogique agent's
  tokens are yielded as SSE events as they arrive from Gemini. The assistant `Message` (full
  text + citations) is saved to Postgres only after the stream completes; if generation fails
  partway, the user's message is still saved (so nothing is silently lost) but no assistant
  message is created — the frontend surfaces an error banner.
- **No crewAI package** — see the callout near the top of this file for why, and where the
  agent pattern lives instead.
- **Model availability shifts fast on Gemini's free tier**: dated model names (e.g.
  `gemini-2.5-flash`) got hard-deprecated ("no longer available to new users") between when this
  was written and tested; the `-latest` aliases used here are meant to absorb that churn, but if
  you hit a `404 NOT_FOUND` again, run this to see what your key currently has access to:
  ```bash
  python manage.py shell -c "from rag.services.llm import get_gemini_client; [print(m.name) for m in get_gemini_client().models.list() if 'generateContent' in (m.supported_actions or [])]"
  ```
