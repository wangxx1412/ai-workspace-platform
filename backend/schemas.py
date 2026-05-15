"""
Pydantic schemas
请求/响应数据结构

Schemas define what the API accepts and returns.
Schemas 定义 API 接收什么、返回什么。
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatMessageInput(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    conversation_id: str
    messages: list[ChatMessageInput]


class ConversationCreateResponse(BaseModel):
    id: str
    title: str
    created_at: datetime


class ConversationListItem(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime


class ConversationDetailResponse(BaseModel):
    id: str
    title: str
    messages: list[MessageResponse]