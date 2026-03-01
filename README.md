# Rhasspy Voice Assistant

Enterprise AI Voice Assistant Platform with 3D Avatar, Multi-Provider LLM Support, and RAG capabilities.

## Features

- **Multi-Provider LLM Support**: OpenAI (GPT-4o, O1, O3), Anthropic (Claude 3.5), and more
- **Knowledge Base / RAG**: Upload documents, chunk, embed, and retrieve for context-aware responses
- **3D Avatar**: Interactive animated avatar using React Three Fiber
- **Streaming Chat**: Real-time SSE streaming responses
- **Tool Integrations**: Extensible tool framework for custom integrations
- **Enterprise Ready**: Multi-tenant, organization-based access control

## Tech Stack

### Backend
- **FastAPI** - Modern async Python web framework
- **PostgreSQL + pgvector** - Database with vector similarity search
- **Redis** - Caching and session management
- **SQLAlchemy 2.0** - Async ORM
- **Celery** - Background task processing
- **Alembic** - Database migrations

### Frontend
- **Next.js 14** - React framework with App Router
- **React Three Fiber** - 3D avatar rendering
- **Tailwind CSS** - Utility-first styling
- **Radix UI** - Accessible components
- **TanStack Query** - Data fetching and caching
- **Zustand** - State management

## Project Structure

```
├── backend/
│   ├── src/
│   │   ├── api/          # API routes
│   │   ├── core/         # Config, security, exceptions
│   │   ├── db/           # Database setup
│   │   ├── llm/          # LLM Gateway & RAG
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # Business logic
│   │   ├── tasks/        # Celery tasks
│   │   └── tools/        # Tool framework
│   ├── alembic/          # Database migrations
│   └── pyproject.toml
├── frontend/
│   ├── app/              # Next.js App Router pages
│   ├── components/       # React components
│   ├── hooks/            # Custom React hooks
│   ├── lib/              # Utilities and API client
│   └── package.json
├── docker/               # Docker configurations
└── docker-compose.yml
```

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Node.js 20+
- Python 3.11+

### Environment Setup

1. Copy the environment file:
```bash
cp backend/.env.example backend/.env
```

2. Configure your API keys in `backend/.env`:
```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
SECRET_KEY=your-secret-key
```

### Running with Docker

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Local Development

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -e .

# Run migrations
alembic upgrade head

# Start server
uvicorn src.main:app --reload
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login and get tokens
- `POST /api/v1/auth/refresh` - Refresh access token
- `GET /api/v1/auth/me` - Get current user

### Assistants
- `GET /api/v1/assistants` - List assistants
- `POST /api/v1/assistants` - Create assistant
- `GET /api/v1/assistants/{id}` - Get assistant
- `PUT /api/v1/assistants/{id}` - Update assistant
- `DELETE /api/v1/assistants/{id}` - Delete assistant

### Knowledge Bases
- `GET /api/v1/knowledge-bases` - List knowledge bases
- `POST /api/v1/knowledge-bases` - Create knowledge base
- `GET /api/v1/knowledge-bases/{id}` - Get knowledge base
- `DELETE /api/v1/knowledge-bases/{id}` - Delete knowledge base

### Files
- `POST /api/v1/files/upload` - Upload file to knowledge base
- `POST /api/v1/files/upload-text` - Upload raw text
- `POST /api/v1/files/upload-url` - Fetch and upload from URL

### Chat
- `POST /api/v1/chat` - Chat with assistant (SSE stream)
- `GET /api/v1/chat/conversations` - List conversations
- `GET /api/v1/chat/conversations/{id}/messages` - Get messages
- `DELETE /api/v1/chat/conversations/{id}` - Delete conversation

### Tools
- `GET /api/v1/tools/available` - List available tools
- `POST /api/v1/tools` - Create custom tool
- `GET /api/v1/tools` - List custom tools
- `POST /api/v1/tools/{id}/test` - Test tool execution

## Architecture

### LLM Gateway

The LLM Gateway provides a unified interface to multiple LLM providers:

```python
from src.llm.gateway import LLMGateway

gateway = LLMGateway()

# Streaming completion
async for delta in gateway.stream(
    provider="openai",
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}],
):
    print(delta.content, end="")
```

### RAG Pipeline

1. **Document Upload** → Extract text from PDF, DOCX, HTML, etc.
2. **Chunking** → Split into overlapping chunks
3. **Embedding** → Generate vector embeddings
4. **Storage** → Store in PostgreSQL with pgvector
5. **Retrieval** → Semantic similarity search
6. **Context Injection** → Inject relevant context into prompts

### Tool Framework

Register custom tools with the decorator pattern:

```python
from src.tools.registry import tool_registry

@tool_registry.register(
    name="get_weather",
    description="Get current weather for a location",
    parameters={
        "type": "object",
        "properties": {
            "location": {"type": "string"}
        },
        "required": ["location"]
    }
)
async def get_weather(location: str) -> dict:
    # Implementation
    return {"temperature": 72, "condition": "sunny"}
```

## Configuration

### Backend Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `SECRET_KEY` | JWT signing key | Required |
| `OPENAI_API_KEY` | OpenAI API key | Optional |
| `ANTHROPIC_API_KEY` | Anthropic API key | Optional |
| `DEBUG` | Enable debug mode | `false` |

### Frontend Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API URL | `http://localhost:8000` |

## License

MIT License
