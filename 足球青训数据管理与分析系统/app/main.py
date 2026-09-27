"""FastAPI 应用入口：注册路由 / 健康检查 / 启动建表"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时建表（开发期便利，生产应使用 alembic 迁移）
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="足球青训数据管理与分析 API 系统",
    lifespan=lifespan,
)

# 注册路由
from app.routers import matches, opponents, players, schedules, statistics, training  # noqa: E402

app.include_router(players.router)
app.include_router(training.router)
app.include_router(matches.router)
app.include_router(opponents.router)
app.include_router(schedules.router)
app.include_router(statistics.router)


@app.get("/health", tags=["系统"], summary="健康检查")
def health():
    return {"status": "ok", "app": settings.app_name}


@app.get("/", tags=["系统"], summary="根路径")
def root():
    return {
        "app": settings.app_name,
        "docs": "/docs",
        "endpoints": {
            "players": "/api/players",
            "training_statistics": "/api/training/statistics",
            "training_export": "/api/training/export",
        },
    }
