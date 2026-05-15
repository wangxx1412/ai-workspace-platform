# AI Workspace Platform

A production-style AI chat workspace built with Next.js, FastAPI, PostgreSQL, and OpenAI.

This project demonstrates how to build a persistent AI chat system with streaming LLM responses, multi-turn conversation context, markdown rendering, retry/abort handling, and PostgreSQL-backed conversation history.

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
- Basic error handling
- Environment-based API configuration

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

### AI

- OpenAI Responses API
- Streaming text generation
- Multi-turn message context

### Future Infrastructure

- Docker
- Docker Compose
- AWS ECS Fargate
- ECR
- CloudWatch

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
