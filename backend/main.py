import os
from datetime import datetime
import time
import uuid
from logging_config import setup_logging, logger

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException,File, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pgvector.sqlalchemy import Vector
from collections import defaultdict, deque
from openai import OpenAI
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Conversation, Message, Document, DocumentChunk
from schemas import (
    ChatRequest,
    ConversationCreateResponse,
    ConversationDetailResponse,
    ConversationListItem,
    DocumentDetailResponse,
    MessageResponse,
    DocumentListItem,
    DocumentUploadResponse,
    DocumentAskRequest,
    DocumentAskResponse,
    SourceChunk,
)
from rag import extract_pdf_pages, chunk_text, create_embedding, build_rag_prompt

load_dotenv()

setup_logging()

app = FastAPI(title="AI Workspace API")

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=30.0,
)

DEMO_USER_ID = "local-dev-user"
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 30

request_timestamps: dict[str, deque] = defaultdict(deque)

with engine.connect() as connection:
    connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    connection.commit()

Base.metadata.create_all(bind=engine)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

def check_rate_limit(client_id: str) -> bool:
    """
    Simple in-memory sliding window rate limiter.

    Returns True if allowed.

    MVP tradeoff:
    This works for a single backend instance.
    In production with multiple containers, use Redis.
    """

    now = time.time()
    timestamps = request_timestamps[client_id]

    while timestamps and now - timestamps[0] > RATE_LIMIT_WINDOW_SECONDS:
        timestamps.popleft()

    if len(timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        return False

    timestamps.append(now)
    return True

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request, call_next):
    """
    Add request_id and latency logging for every HTTP request.

    In production, one user action may trigger many logs.
    A request_id lets us connect all logs from the same request.
    """

    request_id = str(uuid.uuid4())
    start_time = time.time()

    request.state.request_id = request_id

    logger.info(
        f"request_start request_id={request_id} "
        f"method={request.method} path={request.url.path}"
    )

    client_host = request.client.host if request.client else "unknown"

    if not check_rate_limit(client_host):
        logger.warning(
            f"rate_limit_exceeded request_id={request_id} client={client_host}"
        )

        return JSONResponse(
            status_code=429,
            content={
                "detail": "Rate limit exceeded. Please try again later.",
                "request_id": request_id,
            },
        )
    try:
        response = await call_next(request)

        latency_ms = round((time.time() - start_time) * 1000, 2)

        logger.info(
            f"request_complete request_id={request_id} "
            f"method={request.method} path={request.url.path} "
            f"status_code={response.status_code} latency_ms={latency_ms}"
        )

        response.headers["X-Request-ID"] = request_id
        return response

    except Exception as error:
        latency_ms = round((time.time() - start_time) * 1000, 2)

        logger.exception(
            f"request_failed request_id={request_id} "
            f"method={request.method} path={request.url.path} "
            f"latency_ms={latency_ms} error={str(error)}"
        )

        raise

@app.get("/health")
def health(db: Session = Depends(get_db)):
    """
    Health check endpoint.

    Checks:
    - API server is running
    - Database connection works
    """

    try:
        db.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "database": "ok",
            "service": "ai-workspace-api",
        }

    except Exception as error:
        logger.exception(f"health_check_failed error={str(error)}")

        raise HTTPException(
            status_code=503,
            detail={
                "status": "error",
                "database": "unavailable",
            },
        )


@app.post("/conversations", response_model=ConversationCreateResponse)
def create_conversation(db: Session = Depends(get_db)):
    """
    Create a new conversation.
    """

    conversation = Conversation(
        user_id=DEMO_USER_ID,
        title="New Chat",
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation


@app.get("/conversations", response_model=list[ConversationListItem])
def list_conversations(db: Session = Depends(get_db)):
    """
    List conversations for demo user.
    """

    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == DEMO_USER_ID)
        .order_by(Conversation.updated_at.desc())
        .all()
    )

    return conversations


@app.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    """
    Load one conversation with messages.
    """

    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == DEMO_USER_ID,
        )
        .first()
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationDetailResponse(
        id=conversation.id,
        title=conversation.title,
        messages=[
            MessageResponse(
                id=message.id,
                role=message.role,
                content=message.content,
                created_at=message.created_at,
            )
            for message in conversation.messages
        ],
    )


@app.post("/chat")
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    """
    Stream AI response and persist both user and assistant messages.
    """

    if not req.messages:
        raise HTTPException(status_code=400, detail="Messages cannot be empty.")

    latest_message = req.messages[-1]

    if latest_message.role != "user":
        raise HTTPException(
            status_code=400,
            detail="The last message must be from the user.",
        )

    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == req.conversation_id,
            Conversation.user_id == DEMO_USER_ID,
        )
        .first()
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Save latest user message before calling OpenAI.
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=latest_message.content,
    )

    db.add(user_message)

    # If this is the first real user message, use it as conversation title.
    existing_user_message_count = (
        db.query(Message)
        .filter(
            Message.conversation_id == conversation.id,
            Message.role == "user",
        )
        .count()
    )

    if existing_user_message_count == 0:
        conversation.title = latest_message.content[:50]

    conversation.updated_at = datetime.utcnow()
    db.commit()

    def stream():
        """
        Stream AI response and save assistant message at the end.
        """

        assistant_content_parts: list[str] = []

        try:
            with client.responses.stream(
                model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                input=[
                    {
                        "role": message.role,
                        "content": message.content,
                    }
                    for message in req.messages
                ],
            ) as response:
                for event in response:
                    if event.type == "response.output_text.delta":
                        assistant_content_parts.append(event.delta)
                        yield event.delta

            assistant_content = "".join(assistant_content_parts).strip()

            if assistant_content:
                # Important:
                # We create a new DB session inside generator context.
                from database import SessionLocal

                stream_db = SessionLocal()

                try:
                    assistant_message = Message(
                        conversation_id=conversation.id,
                        role="assistant",
                        content=assistant_content,
                    )

                    stream_conversation = (
                        stream_db.query(Conversation)
                        .filter(Conversation.id == conversation.id)
                        .first()
                    )

                    if stream_conversation:
                        stream_conversation.updated_at = datetime.utcnow()

                    stream_db.add(assistant_message)
                    stream_db.commit()

                finally:
                    stream_db.close()

        except Exception as error:
            logger.exception(f"openai_streaming_failed error={str(error)}")
            yield "\n\n[Error] The AI service failed while generating a response."

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

def process_document_in_background(
    document_id: str,
    file_bytes: bytes,
):
    """
    Process uploaded PDF in the background.
    """
    logger.info(f"document_ingestion_start document_id={document_id}")

    from database import SessionLocal

    background_db = SessionLocal()

    try:
        document = (
            background_db.query(Document)
            .filter(Document.id == document_id)
            .first()
        )

        if not document:
            return

        document.status = "processing"
        document.error_message = None
        document.updated_at = datetime.utcnow()
        background_db.commit()

        pages = extract_pdf_pages(file_bytes)

        chunk_index = 0

        for page in pages:
            page_number = page["page_number"]
            page_text = page["text"]

            chunks = chunk_text(page_text)

            for chunk in chunks:
                embedding = create_embedding(client, chunk)

                document_chunk = DocumentChunk(
                    document_id=document.id,
                    content=chunk,
                    chunk_index=chunk_index,
                    page_number=page_number,
                    embedding=embedding,
                )

                background_db.add(document_chunk)
                chunk_index += 1

        document.status = "ready"
        document.updated_at = datetime.utcnow()
        logger.info(
            f"document_ingestion_complete document_id={document_id} chunks={chunk_index}"
        )
        background_db.commit()

    except Exception as error:
        logger.exception(f"document_ingestion_failed document_id={document_id} error={str(error)}")

        document = (
            background_db.query(Document)
            .filter(Document.id == document_id)
            .first()
        )

        if document:
            document.status = "failed"
            document.error_message = str(error)[:1000]
            document.updated_at = datetime.utcnow()
            background_db.commit()

    finally:
        background_db.close()

@app.get("/documents", response_model=list[DocumentListItem])
def list_documents(db: Session = Depends(get_db)):
    """
    List uploaded documents.
    """

    documents = (
        db.query(Document)
        .filter(Document.user_id == DEMO_USER_ID)
        .order_by(Document.created_at.desc())
        .all()
    )

    return documents

@app.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload PDF, extract text, chunk it, create embeddings, and store chunks.
    """

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_bytes = await file.read()

    document = Document(
        user_id=DEMO_USER_ID,
        filename=file.filename,
        status="uploaded",
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    background_tasks.add_task(
        process_document_in_background,
        document.id,
        file_bytes,
    )

    return DocumentUploadResponse(
        id=document.id,
        filename=document.filename,
        status=document.status,
    )

@app.post("/documents/{document_id}/ask", response_model=DocumentAskResponse)
def ask_document(
    document_id: str,
    req: DocumentAskRequest,
    db: Session = Depends(get_db),
):
    """
    Ask a question about one document using RAG.
    """

    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == DEMO_USER_ID,
        )
        .first()
    )

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not ready. Current status: {document.status}",
        )

    question_embedding = create_embedding(client, req.question)

    # pgvector cosine distance query.
    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.embedding.cosine_distance(question_embedding))
        .limit(req.top_k)
        .all()
    )

    if not chunks:
        raise HTTPException(status_code=404, detail="No chunks found for document")

    context_chunks = [
        {
            "source_id": index + 1,
            "filename": document.filename,
            "page_number": chunk.page_number,
            "content": chunk.content,
        }
        for index, chunk in enumerate(chunks)
    ]

    prompt = build_rag_prompt(req.question, context_chunks)

    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        input=prompt,
    )

    answer = response.output_text

    return DocumentAskResponse(
        answer=answer,
        sources=[
            SourceChunk(
                chunk_id=chunk.id,
                filename=document.filename,
                content=chunk.content[:500],
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
            )
            for chunk in chunks
        ],
    )

@app.get("/documents/{document_id}", response_model=DocumentDetailResponse)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
):
    """
    Get document status and metadata.
    """

    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == DEMO_USER_ID,
        )
        .first()
    )

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    chunk_count = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document.id)
        .count()
    )

    return DocumentDetailResponse(
        id=document.id,
        filename=document.filename,
        status=document.status,
        error_message=document.error_message,
        created_at=document.created_at,
        updated_at=document.updated_at,
        chunk_count=chunk_count,
    )
