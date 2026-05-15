# Architecture

## Overview

AI Workspace Platform is a production-style AI chat application built with Next.js, FastAPI, PostgreSQL, Docker, and OpenAI.

The system supports:

- Streaming LLM responses
- Multi-turn conversation context
- Persistent conversation history
- Markdown, table, and code rendering
- Retry and stop generation
- Dockerized local development
- Cloud-ready deployment architecture

---

## High-Level Architecture

```mermaid
graph TD
    User[User] --> Frontend[Next.js Frontend]
    Frontend --> Backend[FastAPI Backend]
    Backend --> OpenAI[OpenAI Responses API]
    Backend --> DB[(PostgreSQL)]
    DB --> Backend
    Backend --> Frontend
```

---

## Streaming Chat Architecture

```mermaid
sequenceDiagram
    participant User
    participant Frontend as Next.js Frontend
    participant Backend as FastAPI Backend
    participant OpenAI as OpenAI Responses API
    participant DB as PostgreSQL

    User->>Frontend: Send message
    Frontend->>Backend: POST /chat with conversation_id + messages
    Backend->>DB: Save user message
    Backend->>OpenAI: Start streaming request
    OpenAI-->>Backend: Text delta chunks
    Backend-->>Frontend: StreamingResponse chunks
    Frontend-->>User: Incrementally render assistant response
    Backend->>DB: Save final assistant message
```

---

## Conversation Persistence Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant DB as PostgreSQL

    User->>Frontend: Open app
    Frontend->>Backend: GET /conversations
    Backend->>DB: Query conversations
    DB-->>Backend: Conversation list
    Backend-->>Frontend: Return conversations

    User->>Frontend: Select conversation
    Frontend->>Backend: GET /conversations/:id
    Backend->>DB: Query messages
    DB-->>Backend: Conversation messages
    Backend-->>Frontend: Return messages
```

---

## Message Persistence Flow

```mermaid
sequenceDiagram
    participant Frontend
    participant Backend
    participant DB as PostgreSQL
    participant OpenAI

    Frontend->>Backend: POST /chat
    Backend->>DB: Save user message
    Backend->>OpenAI: Stream request
    OpenAI-->>Backend: Text chunks
    Backend-->>Frontend: Stream chunks
    Backend->>DB: Save complete assistant message
```

---

## Docker Compose Architecture

```mermaid
graph TD
    Browser[Browser] --> Frontend[Frontend Container: Next.js]
    Frontend --> Backend[Backend Container: FastAPI]
    Backend --> Postgres[(PostgreSQL Container)]
    Backend --> OpenAI[OpenAI API]
```

---

## Local Development Services

| Service  | Technology | Port |
| -------- | ---------- | ---- |
| Frontend | Next.js    | 3000 |
| Backend  | FastAPI    | 8000 |
| Database | PostgreSQL | 5432 |

---

## Database Schema

### conversations

| Column     | Type     | Description            |
| ---------- | -------- | ---------------------- |
| id         | string   | Unique conversation ID |
| user_id    | string   | Mock user ID for MVP   |
| title      | string   | Conversation title     |
| created_at | datetime | Creation timestamp     |
| updated_at | datetime | Last updated timestamp |

### messages

| Column          | Type     | Description            |
| --------------- | -------- | ---------------------- |
| id              | string   | Unique message ID      |
| conversation_id | string   | Parent conversation ID |
| role            | string   | `user` or `assistant`  |
| content         | text     | Message content        |
| created_at      | datetime | Creation timestamp     |

---

## Backend Responsibilities

The FastAPI backend is responsible for:

- Request validation
- OpenAI API orchestration
- Streaming response handling
- Conversation persistence
- Message persistence
- Error handling
- Environment-based configuration

The frontend never calls OpenAI directly. This keeps API keys secure and allows the backend to handle authentication, rate limiting, logging, retrieval, and future provider switching.

---

## Frontend Responsibilities

The Next.js frontend is responsible for:

- Chat UI
- Conversation sidebar
- Streaming response rendering
- Markdown/table/code rendering
- Retry last message
- Stop generation using AbortController
- Loading previous conversations
- Managing active conversation state

---

## Cloud Deployment Architecture

Planned AWS deployment:

```mermaid
graph TD
    User[User] --> Vercel[Vercel or CloudFront Frontend]
    Vercel --> ALB[Application Load Balancer]
    ALB --> ECS[ECS Fargate Backend Service]
    ECS --> RDS[(Amazon RDS PostgreSQL)]
    ECS --> S3[(Amazon S3)]
    ECS --> Secrets[Secrets Manager or SSM Parameter Store]
    ECS --> CloudWatch[CloudWatch Logs]
    ECS --> OpenAI[OpenAI API]
```

---

## AWS Components

| Component                   | Purpose                                 |
| --------------------------- | --------------------------------------- |
| ECR                         | Store backend Docker image              |
| ECS Fargate                 | Run FastAPI backend container           |
| RDS PostgreSQL              | Store conversations and messages        |
| S3                          | Future document storage for RAG         |
| CloudWatch                  | Logs and monitoring                     |
| Secrets Manager / SSM       | Store API keys and database credentials |
| IAM                         | Least-privilege service permissions     |
| ALB                         | Route traffic to backend service        |
| VPC/Subnets/Security Groups | Network isolation and access control    |

---

## Future RAG Architecture

```mermaid
graph TD
    User[User] --> Frontend[Next.js UI]
    Frontend --> Backend[FastAPI Backend]
    Backend --> S3[(S3 Document Storage)]
    Backend --> Worker[Ingestion Worker]
    Worker --> Parser[PDF/Text Parser]
    Parser --> Chunker[Text Chunker]
    Chunker --> Embedding[Embedding Model]
    Embedding --> VectorDB[(PostgreSQL + pgvector)]
    Backend --> Retriever[Semantic Retriever]
    Retriever --> VectorDB
    Retriever --> OpenAI[LLM]
    OpenAI --> Backend
    Backend --> Frontend
```

---

## MVP Tradeoffs

Current MVP tradeoffs:

- Uses a fixed demo user ID instead of real authentication
- Uses PostgreSQL directly without Alembic migrations
- Uses Docker Compose for local production-like setup
- Uses OpenAI as the only LLM provider
- Stores chat history but does not yet support RAG

These are intentional tradeoffs to prioritize the core AI workflow, streaming architecture, and persistence model.

---

## Production Improvements

Future improvements:

- Add real authentication with JWT or Auth.js
- Add Alembic database migrations
- Add Redis-based rate limiting
- Add request IDs and structured logging
- Add OpenTelemetry tracing
- Deploy backend to AWS ECS Fargate
- Use RDS PostgreSQL instead of local PostgreSQL
- Store secrets in AWS Secrets Manager or SSM
- Add Terraform infrastructure as code
- Add RAG with S3, pgvector, and async ingestion pipeline
