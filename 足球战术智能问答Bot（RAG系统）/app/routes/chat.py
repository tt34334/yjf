# File: app/routes/chat.py
"""RAG 问答接口。"""
import logging

from fastapi import APIRouter, HTTPException

from app.models.schemas import ChatRequest, ChatResponse
from app.services.knowledge_base import KnowledgeBaseError
from app.services.llm_client import LLMError
from app.services.rag_service import answer_question

router = APIRouter(prefix="/api/chat", tags=["问答"])
logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=ChatResponse,
    summary="RAG 智能问答",
    description="接收用户问题，从向量库检索 Top-5 相关文档块作为上下文，调用 LLM 生成带引用来源的回答。",
)
async def chat(req: ChatRequest):
    """RAG 问答主接口。"""
    try:
        result = answer_question(req.question)
        return ChatResponse(**result)
    except ValueError as e:
        # 业务校验类错误（如问题为空）
        raise HTTPException(status_code=400, detail=str(e))
    except KnowledgeBaseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LLMError as e:
        # LLM 配置缺失或上游服务异常
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("问答服务发生未知异常")
        raise HTTPException(status_code=500, detail=f"问答服务内部错误：{e}")
