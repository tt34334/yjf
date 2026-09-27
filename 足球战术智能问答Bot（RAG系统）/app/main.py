# File: app/main.py
"""FastAPI 应用入口：注册路由、初始化存储、启动时自动导入示例文档。

启动方式（项目根目录执行）：
    uvicorn app.main:app --host 0.0.0.0 --port 8000
    python -m app.main
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import ensure_dirs, settings
from app.core import vector_store
from app.models.schemas import HealthResponse
from app.routes.chat import router as chat_router
from app.routes.documents import router as documents_router
from app.services.knowledge_base import count_documents, ensure_sample_docs

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化目录、向量库与示例文档，关闭时释放资源。"""
    ensure_dirs()
    vector_store.get_collection()  # 触发 ChromaDB 初始化
    ensure_sample_docs()  # 首次启动自动导入示例文档
    logger.info("应用启动完成：知识库共 %d 篇文档、%d 个向量块", count_documents(), vector_store.count())
    yield
    logger.info("应用已关闭")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="⚽ 足球战术智能问答 RAG 系统 API（FastAPI + ChromaDB + 本地 Embedding）",
    lifespan=lifespan,
)

# 跨域配置：允许前端 / 调试工具直接访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(documents_router)
app.include_router(chat_router)


def _llm_configured() -> bool:
    """判断是否配置了真实可用的 API Key（排除空值与 .env.example 的占位符）。"""
    key = settings.OPENAI_API_KEY.strip()
    return bool(key) and "your-api-key" not in key


@app.get("/api/health", response_model=HealthResponse, tags=["系统"], summary="健康检查")
async def health():
    """返回系统运行状态与配置摘要，供前端与运维探活使用。"""
    return HealthResponse(
        status="ok",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        vector_count=vector_store.count(),
        document_count=count_documents(),
        llm_configured=_llm_configured(),
        llm_mock=settings.LLM_MOCK_MODE,
        llm_model=settings.LLM_MODEL,
        embedding_model=settings.EMBEDDING_MODEL,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
