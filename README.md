# AI Workspace Platform

A production-style AI chat workspace built with Next.js, FastAPI, PostgreSQL, Docker, and OpenAI.

This project demonstrates how to build a persistent AI chat system with streaming LLM responses, multi-turn conversation context, markdown rendering, retry/abort handling, Dockerized local setup, and PostgreSQL-backed conversation history.

---

## Screenshots

### Streaming Chat & Conversation History

![Streaming Chat](docs/screenshots/streaming-chat.png)

---

## Features

- Streaming AI responses
- Multi-turn conversation context
- Markdown, table, and code block rendering
- Stop generation with AbortController
- Retry last user message
- Conversation sidebar
- Create and load previous conversations
- PostgreSQL-backed conversation and message persistence
- FastAPI backend orchestration
- OpenAI Responses API integration
- Docker Compose local production setup
- Environment-based configuration
- Basic error handling

---

## Tech Stack

### Frontend

- Next.js
- TypeScript
- Tailwind CSS
- React Markdown
- remark-gfm
- rehype-highlight

### Backend

- FastAPI
- Python
- SQLAlchemy
- PostgreSQL
- OpenAI SDK

### Infrastructure

- Docker
- Docker Compose
- PostgreSQL container

### AI

- OpenAI Responses API
- Streaming text generation
- Multi-turn message context

### Planned Cloud Stack

- AWS ECS Fargate
- Amazon ECR
- Amazon RDS PostgreSQL
- Amazon S3
- AWS CloudWatch
- AWS Secrets Manager or SSM Parameter Store
- Terraform

---

## Architecture

```text
User
 ↓
Next.js Chat UI
 ↓
FastAPI Backend
 ↓
OpenAI Responses API
 ↓
StreamingResponse
 ↓
ReadableStream
 ↓
Incremental UI Rendering

PostgreSQL
 ← conversations
 ← messages
```

See detailed architecture diagrams in:

```text
docs/architecture.md
```

---

## Persistence Flow

```text
User sends a message
 ↓
Frontend checks activeConversationId
 ↓
If no conversation exists, frontend creates one
 ↓
Frontend sends conversation_id + messages to backend
 ↓
Backend saves latest user message to PostgreSQL
 ↓
Backend calls OpenAI with streaming enabled
 ↓
Backend streams text deltas back to frontend
 ↓
Frontend incrementally renders assistant response
 ↓
Backend stores complete assistant message after streaming finishes
 ↓
Frontend refreshes conversation sidebar
```

---

## Database Schema

### conversations

| Column     | Description                                 |
| ---------- | ------------------------------------------- |
| id         | Unique conversation ID                      |
| user_id    | User identifier; currently a mock demo user |
| title      | Conversation title                          |
| created_at | Creation timestamp                          |
| updated_at | Last updated timestamp                      |

### messages

| Column          | Description            |
| --------------- | ---------------------- |
| id              | Unique message ID      |
| conversation_id | Parent conversation ID |
| role            | `user` or `assistant`  |
| content         | Message content        |
| created_at      | Creation timestamp     |

---

## API Endpoints

### Health Check

```http
GET /health
```

Returns backend status.

---

### Create Conversation

```http
POST /conversations
```

Creates a new conversation for the demo user.

---

### List Conversations

```http
GET /conversations
```

Returns all conversations for the demo user.

---

### Get Conversation Detail

```http
GET /conversations/{conversation_id}
```

Returns one conversation and its messages.

---

### Chat

```http
POST /chat
```

Streams an AI response and persists both user and assistant messages.

Example request:

```json
{
  "conversation_id": "conversation-id",
  "messages": [
    {
      "role": "user",
      "content": "Explain RAG in simple terms"
    }
  ]
}
```

---

## Local Development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

---

### Backend Environment Variables

Create `backend/.env`:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4.1-mini
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_workspace
```

---

### PostgreSQL with Docker

```bash
docker run --name ai-workspace-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=ai_workspace \
  -p 5432:5432 \
  -d postgres:16
```

---

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

### Frontend Environment Variables

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

---

## Docker Setup

This project can also be started with Docker Compose.

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Update:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

Start all services:

```bash
docker compose up --build
```

This starts:

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- PostgreSQL: localhost:5432

Stop services:

```bash
docker compose down
```

Stop services and remove database volume:

```bash
docker compose down -v
```

View logs:

```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f postgres
```

Connect to PostgreSQL:

```bash
docker compose exec postgres psql -U postgres -d ai_workspace
```

---

## Environment Variables

Example root `.env` for Docker Compose:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4.1-mini

POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=ai_workspace
POSTGRES_PORT=5432

BACKEND_PORT=8000
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/ai_workspace

FRONTEND_PORT=3000
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Important:

When running backend locally outside Docker:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_workspace
```

When running backend inside Docker Compose:

```env
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/ai_workspace
```

---

## MVP Tradeoff

For the current MVP, this project uses a fixed demo user ID:

```text
local-dev-user
```

This allows the project to focus on the core AI workflow, streaming architecture, and persistence model first.

In a production version, this would be replaced with a real authenticated user ID from JWT, session-based auth, or an identity provider.

---

## Cloud Deployment

The backend is deployed as a containerized FastAPI service on AWS ECS Fargate, with the Docker image hosted in Amazon ECR. PostgreSQL persistence is provided by Amazon RDS, backend logs are collected through CloudWatch, and sensitive configuration such as the OpenAI API key is injected through AWS SSM Parameter Store.

The frontend is deployed on Vercel and uses a rewrite proxy to securely route browser requests to the AWS backend.

## Current Status

### Completed

- Streaming AI chat
- Multi-turn conversation context
- Markdown/table/code rendering
- Stop generation
- Retry last message
- PostgreSQL persistence
- Conversation sidebar
- Create/load previous conversations
- Docker Compose setup

---

## Next Steps

- Add real authentication with JWT or Auth.js
- Add request-level logging and rate limiting
- Add AWS ECS/Fargate deployment
- Add Terraform infrastructure as code
- Add RAG document assistant with pgvector
- Add S3 document storage
- Add observability with CloudWatch/OpenTelemetry
