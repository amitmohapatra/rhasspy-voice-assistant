# Rhasspy Voice Assistant

An open-source AI platform for document intelligence, voice interaction, and conversational AI — with enterprise-grade RAG, multi-provider LLM support, 3D avatar, and multi-cloud deployment.

---

## What It Does

**Rhasspy** is a full-stack AI assistant platform that combines document understanding, knowledge retrieval, and multi-modal interaction into a single deployable system:

- **Document Intelligence** — Upload PDFs, DOCX, PPTX, XLSX, HTML, or Markdown. Docling extracts every element (tables, figures, charts, equations, code, forms, handwriting) with OCR, VLM descriptions, and table structure recognition. A document viewer shows parsed output with bounding box overlays and bidirectional highlighting.

- **RAG Pipeline** — 4-way hybrid retrieval (dense + sparse + BM25 + visual page search) with late chunking, BGE-M3 embeddings, BGE-reranker, and Reciprocal Rank Fusion. Zero LLM calls for indexing — all embedding and chunking is done locally.

- **Multi-Provider Chat** — Stream responses from OpenAI, Anthropic, Google, Cohere, or any OpenAI-compatible API. Tool calling, multi-turn conversations, and knowledge-base-grounded answers.

- **Voice & Avatar** — Text-to-speech, speech-to-text, and an interactive 3D avatar rendered with React Three Fiber. Multiple voice presets and real-time streaming.

- **Multi-Cloud Storage** — Swap between local filesystem, AWS S3, Azure Blob Storage, or Google Cloud Storage with a single environment variable. Cloud emulators included for local development.

---

## Architecture

```
                    ┌──────────────┐
                    │   Frontend   │  Next.js + TypeScript + Tailwind
                    │   :3000      │  3D Avatar, Chat, Document Viewer
                    └──────┬───────┘
                           │
                    ┌──────┴───────┐
                    │   Backend    │  FastAPI + SQLAlchemy async
                    │   :8000      │  Auth, CRUD, SSE Streaming, RAG
                    └──┬───┬───┬──┘
                       │   │   │
            ┌──────────┘   │   └──────────┐
            │              │              │
     ┌──────┴──────┐ ┌────┴────┐  ┌──────┴──────┐
     │  Inference   │ │  Celery │  │  PostgreSQL  │
     │  :8001       │ │  Worker │  │  :5432       │
     │              │ │         │  └──────────────┘
     │  BGE-M3      │ │  Doc    │
     │  Reranker    │ │  Process│  ┌──────────────┐
     │  Docling     │ │  Embed  │  │    Redis      │
     │  img2table   │ │  Index  │  │    :6379      │
     │  ColSmol*    │ └─────────┘  └──────────────┘
     └─────────────┘
                                   ┌──────────────┐
                                   │   Qdrant      │
                                   │   :6333       │
                                   │   Vectors     │
                                   └──────────────┘
```

**Containers:**

| Service | Size | Role |
|---------|------|------|
| **Backend** | ~1.4 GB | FastAPI API, auth, CRUD, SSE streaming, RAG queries |
| **Inference** | ~5-7 GB | ML models: BGE-M3, BGE-reranker, Docling (OCR + VLM), img2table |
| **Celery Worker** | ~1.3 GB | Background document processing (calls inference via HTTP) |
| **Celery Beat** | ~1.3 GB | Scheduled tasks |
| **Frontend** | ~1.1 GB | Next.js dev server with hot reload |
| **PostgreSQL** | ~230 MB | User data, documents, assistants, conversations |
| **Redis** | ~30 MB | Cache, sessions, Celery broker |
| **Qdrant** | ~100 MB | Vector store for chunks and page images |

*ColSmol-256M is optional (~500 MB extra) — visual page retrieval via `COLSMOL_ENABLED=true`*

---

## ML Models (Built Into Inference Container)

All models are pre-downloaded at Docker build time. No network calls at runtime.

| Model | Purpose | Size |
|-------|---------|------|
| **BGE-M3** | Dense + sparse embeddings (1024-dim) | ~2.3 GB |
| **BGE-reranker-v2-m3** | Cross-encoder reranking | ~1.1 GB |
| **Docling** + RapidOCR PP-OCRv5 | Document parsing, OCR (106 languages), table structure (TableFormer) | ~500 MB |
| **PP-DocBee-2B** | VLM image/chart descriptions (injected into Docling) | ~2 GB |
| **img2table** | Borderless table detection (OpenCV) | ~10 MB |
| **ColSmol-256M** *(optional)* | Visual page retrieval (multi-vector MaxSim) | ~500 MB |

---

## Features

### Document Processing (23 Element Types)
Titles, section headers, paragraphs, list items, tables, figures, charts, code blocks, equations, key-value pairs, form fields, captions, footnotes, page headers/footers, references, document indexes, checkboxes (selected/unselected), handwritten text, grading scales.

### RAG Pipeline
- **Chunking**: Docling HybridChunker — layout-aware, respects element boundaries
- **Embedding**: Late chunking with BGE-M3 — document-context-aware, zero LLM calls
- **Retrieval**: 4-way hybrid (dense 0.35 + sparse 0.25 + BM25 0.20 + visual 0.20) with RRF
- **Reranking**: BGE-reranker-v2-m3 cross-encoder
- **Parent-child**: Stored in Qdrant payload for context expansion

### Supported File Formats
| Format | Pipeline |
|--------|----------|
| PDF, Images (PNG/JPG/TIFF) | Full ML: OCR + VLM + table structure + layout |
| DOCX, PPTX, XLSX | Native parsing via Docling SimplePipeline |
| HTML, Markdown | Native parsing |

### Chat & Conversations
- OpenAI Responses API compatible (`/api/v1/responses`)
- SSE streaming for all responses
- Multi-turn via `previous_response_id` chain
- Tool calling with custom and builtin tools
- Knowledge-base-grounded answers

### Voice & Avatar
- Text-to-speech and speech-to-text (OpenAI Whisper/TTS)
- Multiple voice presets
- Interactive 3D avatar (React Three Fiber + GLB models)

### Auth & Security
- JWT authentication (access + refresh tokens)
- bcrypt password hashing
- User-scoped resources (each user sees only their own data)
- No roles, no organizations — simple single-tenant model

---

## Quick Start

### Prerequisites

- **Docker Desktop** with at least **8 GB RAM** and **80 GB disk** allocated
  - The inference container downloads ~5 GB of ML models during the first build
- **Make** (pre-installed on macOS/Linux)
- An **LLM API key** (OpenAI, Anthropic, or Google)

### 1. Clone and Configure

```bash
git clone https://github.com/amitmohapatra/rhasspy-voice-assistant.git
cd rhasspy-voice-assistant
```

Create your local environment file:

```bash
cp backend/.env.example .env.local
```

Edit `.env.local` and add your LLM API key(s):

```env
OPENAI_API_KEY=sk-...
# Optional:
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AI...
```

### 2. Start Services

```bash
make up
```

This starts all 8 containers with local filesystem storage. The first run takes 10-20 minutes to build the inference image and download ML models.

### 3. Open the App

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Qdrant Dashboard**: http://localhost:6333/dashboard

Register a new account at http://localhost:3000/auth/register, then log in.

---

## Running with Cloud Storage

Rhasspy supports four storage backends. For local development, cloud emulators run alongside your services — no real cloud account needed.

### Local Filesystem (Default)

```bash
make up
```

Files are stored in a Docker volume (`backend_storage`). No cloud dependencies.

### AWS (S3 via LocalStack)

```bash
make up-aws
```

Starts a [LocalStack](https://localstack.cloud/) container that emulates S3. The init script (`docker/localstack/init-aws.sh`) automatically creates the bucket.

### Azure (Blob Storage via Azurite)

```bash
make up-azure
```

Starts an [Azurite](https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azurite) container that emulates Azure Blob Storage. After starting:

```bash
make init-azure   # Creates the storage container
```

### GCP (Cloud Storage via fake-gcs-server)

```bash
make up-gcp
```

Starts a [fake-gcs-server](https://github.com/fsouza/fake-gcs-server) container that emulates Google Cloud Storage. After starting:

```bash
make init-gcp     # Creates the storage bucket
```

---

## Production Deployment

For production, replace the local containers with managed cloud services:

| Component | AWS | Azure | GCP |
|-----------|-----|-------|-----|
| Database | RDS PostgreSQL | Azure Database for PostgreSQL | Cloud SQL |
| Cache | ElastiCache Redis | Azure Cache for Redis | Memorystore |
| Storage | S3 | Azure Blob Storage | Cloud Storage |
| Vectors | Qdrant Cloud | Qdrant Cloud | Qdrant Cloud |
| Compute | ECS Fargate / EKS | AKS / Container Apps | Cloud Run / GKE |

Production environment templates are provided:

```bash
# Choose your cloud:
cp .env.production.aws.example .env
cp .env.production.azure.example .env
cp .env.production.gcp.example .env
```

Fill in your managed service endpoints and credentials, then deploy the backend, inference, celery, and frontend containers to your orchestrator.

---

## Useful Commands

```bash
make up              # Start with local storage
make up-aws          # Start with AWS emulation
make up-azure        # Start with Azure emulation
make up-gcp          # Start with GCP emulation
make down            # Stop all services
make logs            # View all logs
make logs-backend    # View backend logs only
make migrate         # Run database migrations
make test            # Run tests
make shell           # Open backend shell
make psql            # Open PostgreSQL shell
make build           # Rebuild all images
make rebuild         # Rebuild and start
make clean           # Stop and remove all volumes
```

### Running E2E Tests

```bash
docker compose exec -e OPENAI_API_KEY=sk-... backend \
  python -m pytest tests/e2e/ -v
```

---

## Project Structure

```
rhasspy-voice-assistant/
├── backend/
│   ├── src/
│   │   ├── api/routes/v1/     # REST + SSE endpoints
│   │   ├── core/              # Config, security, storage backends
│   │   ├── db/                # SQLAlchemy base, seeds, migrations setup
│   │   ├── inference/         # ML inference service (separate container)
│   │   ├── llm/               # LLM Gateway, provider adapters
│   │   ├── models/            # SQLAlchemy models
│   │   ├── rag/               # Chunking, embedding, retrieval, reranking
│   │   ├── schemas/           # Pydantic request/response schemas
│   │   ├── services/          # Business logic layer
│   │   └── tools/             # Tool resolver and adapters
│   ├── alembic/               # Database migrations
│   ├── tests/e2e/             # End-to-end tests (212 tests)
│   ├── Dockerfile             # API container (~1.4 GB)
│   ├── Dockerfile.inference   # ML inference container (~5-7 GB)
│   └── pyproject.toml
├── frontend/
│   ├── app/                   # Next.js App Router pages
│   │   ├── (app)/             # Protected routes (dashboard, assistants, KBs, tools, docs)
│   │   ├── auth/              # Login, register
│   │   ├── chat/              # Chat interface + history
│   │   ├── avatar-chat/       # 3D avatar chat
│   │   └── settings/          # User settings, providers, API keys
│   ├── components/
│   │   ├── document-viewer/   # PDF viewer with bbox overlays
│   │   ├── avatar/            # 3D avatar (React Three Fiber)
│   │   ├── chat/              # Chat components
│   │   ├── layout/            # Navigation, sidebar
│   │   └── ui/                # Radix-based UI primitives
│   ├── hooks/                 # Custom React hooks
│   ├── Dockerfile
│   └── package.json
├── docker/                    # Init scripts for cloud emulators
├── docker-compose.yml         # All services + cloud profiles
├── Makefile                   # Development commands
├── .env.local                 # Local dev config (gitignored)
├── .env.aws                   # AWS/LocalStack config
├── .env.azure                 # Azure/Azurite config
├── .env.gcp                   # GCP/fake-gcs config
└── .env.production.*.example  # Production templates (AWS, Azure, GCP)
```

---

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register new user |
| POST | `/api/v1/auth/login` | Login (returns access + refresh tokens) |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/auth/me` | Get current user |

### Assistants
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/assistants` | List user's assistants |
| POST | `/api/v1/assistants` | Create assistant |
| GET | `/api/v1/assistants/{id}` | Get assistant |
| PUT | `/api/v1/assistants/{id}` | Update assistant |
| DELETE | `/api/v1/assistants/{id}` | Delete assistant |

### Knowledge Bases
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/knowledge-bases` | List knowledge bases |
| POST | `/api/v1/knowledge-bases` | Create knowledge base |
| GET | `/api/v1/knowledge-bases/{id}` | Get knowledge base |
| DELETE | `/api/v1/knowledge-bases/{id}` | Delete knowledge base |

### Files (Decoupled from KBs)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/files/upload` | Upload file (optional KB assignment) |
| POST | `/api/v1/files/{id}/assign` | Assign file to a knowledge base |
| DELETE | `/api/v1/files/{id}/assign/{kb_id}` | Unassign file from KB |
| GET | `/api/v1/files` | List user's files |
| DELETE | `/api/v1/files/{id}` | Delete file |

### Chat (SSE Streaming)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/responses` | Send message (SSE stream) |
| GET | `/api/v1/conversations` | List conversations |
| GET | `/api/v1/conversations/{id}/messages` | Get conversation messages |
| DELETE | `/api/v1/conversations/{id}` | Delete conversation |

### Tools
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/tools` | List custom tools |
| POST | `/api/v1/tools` | Create custom tool |
| DELETE | `/api/v1/tools/{id}` | Delete tool |

### Document Viewer
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/documents/{id}/pages` | Get page images |
| GET | `/api/v1/documents/{id}/pages/{num}` | Get single page image |
| GET | `/api/v1/documents/{id}/enriched` | Get enriched JSON (parsed elements) |

### Vendor Discovery
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/vendor/models` | List available LLM models |
| GET | `/api/v1/vendor/providers` | List configured providers |

---

## Configuration Reference

### Core Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | App secret key | Required |
| `JWT_SECRET_KEY` | JWT signing key | Required |
| `DEBUG` | Enable debug mode | `true` |
| `APP_ENV` | Environment | `development` |

### Database & Cache

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection | `postgresql+asyncpg://rhasspy:rhasspy_secret@postgres:5432/rhasspy` |
| `REDIS_URL` | Redis connection | `redis://redis:6379/0` |
| `CELERY_BROKER_URL` | Celery broker | `redis://redis:6379/1` |

### Storage

| Variable | Description | Default |
|----------|-------------|---------|
| `STORAGE_TYPE` | `local`, `s3`, `azure_blob`, or `gcs` | `local` |
| `S3_BUCKET` | S3 bucket name | — |
| `S3_ENDPOINT_URL` | S3 endpoint (for LocalStack) | — |
| `AZURE_STORAGE_CONNECTION_STRING` | Azure connection string | — |
| `AZURE_STORAGE_CONTAINER` | Azure container name | — |
| `GCP_STORAGE_BUCKET` | GCS bucket name | — |
| `GCP_STORAGE_ENDPOINT_URL` | GCS endpoint (for emulator) | — |

### LLM Providers

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `GOOGLE_API_KEY` | Google AI API key |
| `COHERE_API_KEY` | Cohere API key |
| `VOYAGE_API_KEY` | Voyage AI API key |

### Inference

| Variable | Description | Default |
|----------|-------------|---------|
| `INFERENCE_SERVICE_URL` | ML inference endpoint | `http://inference:8001` |
| `INFERENCE_SERVICE_TIMEOUT` | Request timeout (seconds) | `1200` |
| `COLSMOL_ENABLED` | Enable visual page retrieval | `false` |

---

## Tech Stack

### Backend
- **FastAPI** — Async Python API framework
- **SQLAlchemy 2.0** — Async ORM with PostgreSQL
- **Alembic** — Database migrations
- **Celery** — Background task processing
- **Qdrant** — Vector similarity search
- **Docling** — Document parsing (OCR, VLM, table structure)
- **BGE-M3** — Dense + sparse embeddings
- **RapidOCR PP-OCRv5** — 106-language OCR (ONNX)

### Frontend
- **Next.js 14** — React framework with App Router
- **TypeScript** — Type safety
- **Tailwind CSS** — Utility-first styling
- **Radix UI** — Accessible component primitives
- **React Three Fiber** — 3D avatar rendering
- **Zustand** — State management

### Infrastructure
- **Docker Compose** — Multi-container orchestration
- **PostgreSQL 16** — Relational database
- **Redis 7** — Caching and message broker
- **Qdrant** — Vector database
- **LocalStack / Azurite / fake-gcs-server** — Cloud emulators

---

## License

MIT License
