# AI Workspace Platform

A production-style AI chat workspace built with Next.js, FastAPI, and OpenAI.

## Features

- Streaming AI responses
- Multi-turn conversation context
- Markdown rendering
- Code block rendering
- Stop generation
- Retry last response
- Error handling
- FastAPI backend
- Next.js frontend

## Tech Stack

- Frontend: Next.js, TypeScript, Tailwind CSS
- Backend: FastAPI, Python
- AI: OpenAI Responses API
- Future: PostgreSQL, Docker, AWS ECS

## Architecture

User
→ Next.js Chat UI
→ FastAPI /chat endpoint
→ OpenAI Responses API
→ Streaming response
→ Browser stream reader

## Current Status

Day 2 MVP completed.
