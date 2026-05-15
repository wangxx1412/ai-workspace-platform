"""
Database models
数据库模型

Day 3 models:
1. Conversation
2. Message

Day 3 暂时不做真正 User 表。
我们使用 demo_user_id 来模拟用户。
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

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