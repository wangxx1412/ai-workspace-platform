"""
AI Workspace Backend
后端入口文件

This FastAPI backend exposes a /chat endpoint.
It receives a user message from the frontend, sends it to OpenAI,
and streams the AI response back to the browser.

这个 FastAPI 后端提供 /chat 接口。
它接收前端传来的用户消息，调用 OpenAI API，
并把 AI 的回复以 streaming 的方式返回给浏览器。
"""

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel


# Load environment variables from .env file
# 从 .env 文件加载环境变量，比如 OPENAI_API_KEY
load_dotenv()


# Create FastAPI app instance
# 创建 FastAPI 应用实例
app = FastAPI()


# Create OpenAI client
# 创建 OpenAI 客户端
#
# Important:
# Never put your API key in frontend code.
# The API key should only exist on the backend/server side.
#
# 重要：
# 永远不要把 API key 放到前端代码里。
# API key 只能放在后端/server 端。
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


# Allow frontend app to call backend API
# 允许前端应用访问后端 API
#
# Browser has CORS protection.
# Since frontend runs on localhost:3000 and backend runs on localhost:8000,
# we need to explicitly allow frontend origin.
#
# 浏览器有 CORS 跨域保护。
# 因为前端运行在 localhost:3000，后端运行在 localhost:8000，
# 所以我们需要明确允许前端 origin。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL / 前端地址
    allow_methods=["*"],                      # Allow all HTTP methods / 允许所有 HTTP 方法
    allow_headers=["*"],                      # Allow all headers / 允许所有请求头
)


class ChatRequest(BaseModel):
    """
    Request body schema for /chat endpoint.
    /chat 接口的请求体结构。

    Example request JSON:
    示例请求 JSON:

    {
        "message": "Explain RAG in simple terms"
    }
    """

    message: str


@app.get("/health")
def health():
    """
    Health check endpoint.
    健康检查接口。

    You can open http://localhost:8000/health
    to verify that the backend server is running.

    你可以打开 http://localhost:8000/health
    来确认后端服务是否正常运行。
    """

    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest):
    """
    Chat endpoint with streaming response.
    带 streaming 的聊天接口。

    Frontend sends a user message here.
    Backend sends the message to OpenAI.
    OpenAI streams response chunks back.
    Backend forwards those chunks to the frontend immediately.

    前端把用户消息发到这里。
    后端把消息转发给 OpenAI。
    OpenAI 以 chunk 的形式流式返回回复。
    后端再把这些 chunk 立即转发给前端。
    """

    def stream():
        """
        Generator function for streaming text chunks.
        用于流式返回文本片段的生成器函数。

        Why generator?
        为什么用 generator？

        Because we do not want to wait for the full AI answer.
        We want to yield each small piece as soon as it arrives.

        因为我们不想等 AI 完整回答生成完再返回。
        我们希望每生成一小段，就立刻发给前端。
        """

        # Call OpenAI Responses API with streaming enabled.
        # 调用 OpenAI Responses API，并开启 streaming。
        #
        # model:
        # Use a cheaper model for development if possible.
        # 开发阶段建议使用便宜的模型。
        #
        # input:
        # For Day 1, we only send the latest user message.
        # Later, we will upgrade this to send full conversation history.
        #
        # Day 1 阶段，我们只发送用户最新的一条消息。
        # 后面会升级成发送完整对话上下文。
        with client.responses.stream(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            input=req.message,
        ) as response:

            # OpenAI streaming returns many event types.
            # OpenAI streaming 会返回多种事件类型。
            #
            # We only care about text delta events here.
            # 这里我们只关心文本增量事件。
            for event in response:
                # Each delta is a small piece of the assistant response.
                # 每个 delta 都是 AI 回复的一小段文本。
                if event.type == "response.output_text.delta":
                    yield event.delta

    # Return streaming response to frontend.
    # 把流式响应返回给前端。
    #
    # media_type="text/plain" means we are streaming plain text.
    # media_type="text/plain" 表示我们返回的是普通文本流。
    return StreamingResponse(stream(), media_type="text/plain")