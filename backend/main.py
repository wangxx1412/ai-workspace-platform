import os
from datetime import datetime

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Conversation, Message
from schemas import (
    ChatRequest,
    ConversationCreateResponse,
    ConversationDetailResponse,
    ConversationListItem,
    MessageResponse,
)


load_dotenv()

app = FastAPI(title="AI Workspace API")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

DEMO_USER_ID = "local-dev-user"


# Create tables automatically
# Production note:
# In production, use Alembic migrations instead.

# Enable vector extension for pgvector support. 
# In production,should set up the extension manually.
from sqlalchemy import text

with engine.connect() as connection:
    connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    connection.commit()

Base.metadata.create_all(bind=engine)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


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
            print(f"OpenAI streaming error: {error}", flush=True)
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