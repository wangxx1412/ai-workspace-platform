"""
Database models
1. Conversation
2. Message
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from database import Base


def generate_uuid():
    """
    Generate UUID string.
    生成 UUID 字符串。
    """

    return str(uuid.uuid4())


class Conversation(Base):
    """
    Conversation table.
    对话表。

    One conversation contains many messages.
    一个 conversation 包含多条 messages。
    """

    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=generate_uuid)

    # For Day 3, we use a fixed demo user id.
    # Day 3 暂时用固定 demo user id。
    user_id = Column(String, nullable=False, index=True)

    title = Column(String, nullable=False, default="New Chat")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    """
    Message table.
    消息表。

    Each message belongs to one conversation.
    每条 message 属于一个 conversation。
    """

    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=generate_uuid)

    conversation_id = Column(
        String,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # role can be "user" or "assistant"
    # role 可以是 "user" 或 "assistant"
    role = Column(String, nullable=False)

    content = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship(
        "Conversation",
        back_populates="messages",
    )

class Document(Base):
    """
    Document table.

    One uploaded PDF creates one document record.
    """

    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid)

    user_id = Column(String, nullable=False, index=True)

    filename = Column(String, nullable=False)

    status = Column(String, nullable=False, default="ready")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
    )


class DocumentChunk(Base):
    """
    Document chunk table.

    Each chunk stores:
    - text content
    - embedding vector
    - metadata such as page number and chunk index
    """

    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True, default=generate_uuid)

    document_id = Column(
        String,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    content = Column(Text, nullable=False)

    chunk_index = Column(String, nullable=False)

    page_number = Column(String, nullable=True)

    # text-embedding-3-small returns 1536 dimensions.
    # text-embedding-3-small 返回 1536 维向量。
    embedding = Column(Vector(1536), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship(
        "Document",
        back_populates="chunks",
    )