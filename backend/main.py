"""
AI Workspace Backend - Day 2 Version
AI Workspace 后端 - Day 2 版本

Main upgrades:
主要升级：

1. Accept full conversation history
   接收完整对话上下文

2. Stream assistant response
   流式返回 assistant 回复

3. Basic input validation
   基础输入校验

4. Safer error handling
   更安全的错误处理
"""

import os
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel, Field


load_dotenv()

app = FastAPI(title="AI Workspace API")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    """
    One chat message.
    一条聊天消息。

    role:
    - user: message from human
    - assistant: message from AI

    role:
    - user: 用户消息
    - assistant: AI 消息
    """

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    """
    Request body for /chat.
    /chat 接口请求体。

    Instead of sending only the latest message,
    we now send the full conversation history.

    现在不只发送最新消息，
    而是发送完整对话上下文。
    """

    messages: list[ChatMessage]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest):
    """
    Stream AI response based on full conversation history.
    基于完整对话上下文流式返回 AI 回复。
    """

    if not req.messages:
        raise HTTPException(status_code=400, detail="Messages cannot be empty.")

    latest_message = req.messages[-1]

    if latest_message.role != "user":
        raise HTTPException(
            status_code=400,
            detail="The last message must be from the user.",
        )

    def stream():
        """
        Stream response chunks from OpenAI to frontend.
        从 OpenAI 向前端流式传输回复片段。
        """

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
                        yield event.delta

        except Exception as error:
            """
            In a real production system, we would log this error
            using structured logging.

            在真实生产系统中，我们会用 structured logging
            记录这个错误。
            """

            print(f"OpenAI streaming error: {error}")
            yield "\n\n[Error] The AI service failed while generating a response."

    return StreamingResponse(stream(), media_type="text/plain")