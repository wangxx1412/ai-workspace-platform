# Architecture

AI Workspace Platform is a production-style AI application with:

- Streaming AI chat
- Persistent conversation history
- RAG document Q&A
- Async PDF ingestion
- Citation-aware answers
- Dockerized local development
- AWS ECS/RDS deployment
- Vercel frontend deployment

---

## High-Level Architecture

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

CloudWatch collects logs.
SSM Parameter Store injects secrets.
```

---

## Cloud Architecture

```mermaid
graph TD
    User[User] --> Vercel[Vercel Frontend]
    Vercel --> Proxy[Vercel Rewrite Proxy]
    Proxy --> ALB[AWS Application Load Balancer]
    ALB --> ECS[ECS Fargate Backend]
    ECS --> RDS[(RDS PostgreSQL + pgvector)]
    ECS --> OpenAI[OpenAI API]
    ECS --> SSM[SSM Parameter Store]
    ECS --> CloudWatch[CloudWatch Logs]
```

---

## Local Docker Architecture

```mermaid
graph TD
    Browser[Browser] --> Frontend[Next.js Frontend Container]
    Frontend --> Backend[FastAPI Backend Container]
    Backend --> Postgres[(PostgreSQL + pgvector Container)]
    Backend --> OpenAI[OpenAI API]
```

---

## AI Chat Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend as Next.js Frontend
    participant Backend as FastAPI Backend
    participant DB as PostgreSQL
    participant OpenAI as OpenAI API

    User->>Frontend: Send message
    Frontend->>Backend: POST /chat with conversation_id + messages
    Backend->>DB: Save user message
    Backend->>OpenAI: Start streaming response
    OpenAI-->>Backend: Text delta chunks
    Backend-->>Frontend: StreamingResponse chunks
    Frontend-->>User: Incrementally render assistant response
    Backend->>DB: Save final assistant message
```

---

## Conversation Persistence

```text
User opens app
 ↓
Frontend calls GET /conversations
 ↓
Backend loads conversations from PostgreSQL
 ↓
User selects conversation
 ↓
Frontend calls GET /conversations/{id}
 ↓
Backend returns messages
 ↓
Frontend restores chat history
```

---

## RAG Ingestion Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant Worker as Background Task
    participant DB as PostgreSQL + pgvector
    participant OpenAI as Embedding API

    User->>Frontend: Upload PDF
    Frontend->>Backend: POST /documents/upload
    Backend->>DB: Create document status=uploaded
    Backend-->>Frontend: Return document_id
    Backend->>Worker: Start background ingestion
    Worker->>DB: Update status=processing
    Worker->>Worker: Extract text with PyMuPDF
    Worker->>Worker: Chunk text with overlap
    Worker->>OpenAI: Create embeddings
    OpenAI-->>Worker: Embedding vectors
    Worker->>DB: Store chunks and vectors
    Worker->>DB: Update status=ready
    Frontend->>Backend: Poll GET /documents/{id}
    Backend-->>Frontend: Return status
```

---

## RAG Question Answering Flow

```mermaid
graph TD
    UserQuestion[User Question] --> QuestionEmbedding[Create Question Embedding]
    QuestionEmbedding --> VectorSearch[pgvector Similarity Search]
    VectorSearch --> TopK[Retrieve Top-K Chunks]
    TopK --> Prompt[Build Citation-aware Prompt]
    Prompt --> LLM[OpenAI LLM]
    LLM --> Answer[Answer with Sources]
```

---

## Reliability and Observability Flow

```mermaid
sequenceDiagram
    participant Client
    participant Backend as FastAPI Backend
    participant Logs as stdout / CloudWatch
    participant DB as PostgreSQL
    participant OpenAI

    Client->>Backend: HTTP Request
    Backend->>Backend: Generate request_id
    Backend->>Logs: request_start
    Backend->>Backend: Rate limit check
    Backend->>DB: Query or persist data
    Backend->>OpenAI: Call OpenAI with timeout
    OpenAI-->>Backend: Response
    Backend->>Logs: request_complete with latency
    Backend-->>Client: Response with X-Request-ID
```

---

## Main Components

| Component           | Responsibility                                               |
| ------------------- | ------------------------------------------------------------ |
| Next.js Frontend    | Chat UI, document UI, streaming rendering, status polling    |
| FastAPI Backend     | API orchestration, OpenAI calls, streaming, RAG, persistence |
| PostgreSQL          | Conversations, messages, documents, chunks                   |
| pgvector            | Vector similarity search for RAG                             |
| OpenAI API          | Chat completions and embeddings                              |
| Docker Compose      | Local development environment                                |
| Vercel              | Frontend hosting and rewrite proxy                           |
| ALB                 | Routes external traffic to ECS backend                       |
| ECS Fargate         | Runs backend container                                       |
| ECR                 | Stores backend Docker image                                  |
| RDS PostgreSQL      | Managed production database                                  |
| CloudWatch          | Backend logs                                                 |
| SSM Parameter Store | Secrets injection                                            |

---

## Database Models

### conversations

```text
id
user_id
title
created_at
updated_at
```

### messages

```text
id
conversation_id
role
content
created_at
```

### documents

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

## MVP Tradeoffs

Current MVP decisions:

- Mock user ID instead of real authentication
- FastAPI BackgroundTasks instead of Celery/SQS
- In-memory rate limiting instead of Redis
- SQLAlchemy `create_all` instead of Alembic migrations
- Vercel rewrite proxy instead of HTTPS custom domain for ALB
- Local Docker Compose before full Terraform automation

---

## Production Improvements

Planned improvements:

- JWT/Auth.js authentication
- Redis-based rate limiting
- SQS or Celery-based ingestion workers
- S3 document storage
- Alembic database migrations
- HTTPS ALB with ACM and Route 53
- Terraform infrastructure as code
- GitHub Actions CI/CD
- OpenTelemetry tracing
