"""数据库连接：SQLAlchemy 2.0 风格"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False,  # 关闭 SQL 日志打印，避免每个请求的同步 I/O 拖慢响应
    connect_args=connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """ORM 基类"""


def get_db() -> Generator:
    """FastAPI 依赖：每个请求独享一个 session，请求结束自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
