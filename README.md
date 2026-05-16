# AI Workspace Platform

A production-style AI workspace built with **Next.js, FastAPI, PostgreSQL, Docker, OpenAI, pgvector, and AWS**.

The platform supports streaming LLM chat, persistent conversation history, document-based RAG Q&A, async PDF ingestion, citation-aware answers, and cloud deployment on AWS ECS Fargate.

---

## Features

### AI Chat Workspace

- Streaming LLM responses
- Multi-turn conversation context
- Markdown, table, and code block rendering
- Retry last response
- Stop generation with `AbortController`
- Persistent conversations with PostgreSQL
- Conversation sidebar with create/load history

### RAG Document Assistant

- PDF upload
- Text extraction with PyMuPDF
- Chunking with overlap
- OpenAI embeddings
- PostgreSQL + pgvector semantic search
- Document Q&A
- Citation-aware answers with filename, page number, and chunk index
- Async ingestion with document status:
  - `uploaded`
  - `processing`
  - `ready`
  - `failed`

### Reliability / Observability

- Request ID middleware
- Structured-style backend logs
- Request latency logging
- Health check with database connectivity
- OpenAI timeout handling
- Embedding retry logic
- Basic in-memory rate limiting
- CloudWatch-ready stdout logs

---

## Tech Stack

### Frontend

- Next.js
- TypeScript
- Tailwind CSS
- React Markdown
- Vercel

### Backend

- FastAPI
- Python
- SQLAlchemy
- PostgreSQL
- pgvector
- PyMuPDF
- OpenAI SDK

### Infrastructure

- Docker
- Docker Compose
- AWS ECS Fargate
- AWS ECR
- AWS RDS PostgreSQL
- AWS ALB
- AWS CloudWatch
- AWS SSM Parameter Store
- Vercel Rewrite Proxy

---

## Architecture

```text
User
 ↓
Vercel Frontend
 ↓
Vercel Rewrite Proxy
 ↓
AWS Application Load Balancer
 ↓
ECS Fargate FastAPI Backend
 ↓
RDS PostgreSQL + pgvector
 ↓
OpenAI API

CloudWatch collects backend logs.
SSM Parameter Store injects secrets.
```

---

## AI Chat Flow

```text
User sends message
 ↓
Frontend sends conversation_id + messages
 ↓
Backend saves user message
 ↓
Backend calls OpenAI with streaming enabled
 ↓
Backend streams text chunks to frontend
 ↓
Frontend incrementally renders response
 ↓
Backend saves final assistant message
```

---

## RAG Flow

```text
PDF Upload
 ↓
Create document row: uploaded
 ↓
Background ingestion task
 ↓
Extract text
 ↓
Chunk text
 ↓
Create embeddings
 ↓
Store vectors in pgvector
 ↓
User asks question
 ↓
Retrieve top-k chunks
 ↓
Generate grounded answer with citations
```

---

## Database Models

### conversations

Stores AI chat sessions.

```text
id
user_id
title
created_at
updated_at
```

### messages

Stores user and assistant messages.

```text
id
conversation_id
role
content
created_at
```

### documents

Stores uploaded document metadata and ingestion status.

```text
id
user_id
filename
status
error_message
created_at
updated_at
```

### document_chunks

Stores document chunks and embeddings.

```text
id
document_id
content
embedding
chunk_index
page_number
created_at
```

---

## API Endpoints

### Chat

```http
POST /chat
GET /conversations
POST /conversations
GET /conversations/{conversation_id}
```

### Documents / RAG

```http
GET /documents
GET /documents/{document_id}
POST /documents/upload
POST /documents/{document_id}/ask
```

### Health

```http
GET /health
```

---

## Local Development

### 1. Clone and configure

```bash
git clone <repo-url>
cd ai-workspace-platform
cp .env.example .env
```

Update `.env`:

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

### 2. Run with Docker Compose

```bash
docker compose up --build
```

Services:

```text
Frontend: http://localhost:3000
Backend:  http://localhost:8000
Postgres: localhost:5432
```

### 3. Useful commands

```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f postgres
docker compose down
docker compose down -v
```

---

## Cloud Deployment

The app is deployed with:

```text
Frontend: Vercel
Backend: AWS ECS Fargate
Image Registry: AWS ECR
Database: AWS RDS PostgreSQL
Load Balancer: AWS ALB
Logs: AWS CloudWatch
Secrets: AWS SSM Parameter Store
```

The Vercel frontend uses a rewrite proxy:

```text
/browser request: /backend/*
 ↓
Vercel rewrite
 ↓
AWS ALB backend
```

This avoids browser mixed-content issues when the frontend runs on HTTPS and the ALB backend is HTTP.

---

## Environment Variables

### Frontend local

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### Frontend on Vercel

```env
NEXT_PUBLIC_API_BASE_URL=/backend
BACKEND_API_URL=http://your-alb-dns-name
```

### Backend

```env
OPENAI_API_KEY=stored in AWS SSM Parameter Store
OPENAI_MODEL=gpt-4.1-mini
DATABASE_URL=RDS PostgreSQL connection string
FRONTEND_URL=https://your-vercel-domain.vercel.app
```

---

## MVP Tradeoffs

This project intentionally uses a few MVP-friendly decisions:

- Mock user ID instead of full authentication
- FastAPI BackgroundTasks instead of Celery/SQS
- In-memory rate limiting instead of Redis
- SQLAlchemy `create_all` instead of Alembic migrations
- Vercel rewrite proxy instead of full HTTPS custom domain on ALB

Production improvements would include JWT/Auth.js, Redis rate limiting, SQS-based ingestion, Alembic migrations, HTTPS ALB with ACM, Terraform IaC, and CI/CD.

---

## Current Status

Completed:

- Streaming AI chat
- PostgreSQL conversation persistence
- Docker Compose local setup
- RAG document Q&A with pgvector
- Async PDF ingestion
- Citation-aware answers
- Request logging and health checks
- AWS ECS/RDS/ALB/CloudWatch/SSM deployment
- Vercel frontend deployment with rewrite proxy

Next:

- Terraform / IaC skeleton
- Authentication
- S3 document storage
- Redis rate limiting
- CI/CD pipeline
- OpenTelemetry tracing
