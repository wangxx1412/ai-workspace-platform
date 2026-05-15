"""
Database configuration
数据库配置

This file creates:
1. SQLAlchemy engine
2. SessionLocal for database sessions
3. Base class for ORM models

这个文件负责创建：
1. SQLAlchemy engine
2. 数据库 session
3. ORM model 的 Base 类
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in .env")


# SQLAlchemy engine manages DB connections.
# SQLAlchemy engine 负责管理数据库连接。
engine = create_engine(DATABASE_URL)


# SessionLocal creates a new DB session for each request.
# SessionLocal 用来给每个请求创建一个新的数据库 session。
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# Base is used by SQLAlchemy models.
# 所有 ORM model 都会继承 Base。
Base = declarative_base()


def get_db():
    """
    FastAPI dependency for DB session.
    FastAPI 的数据库 session dependency。

    It opens a DB session for the request,
    then closes it after the request finishes.

    它会为每个请求打开一个数据库 session，
    请求结束后自动关闭。
    """

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()