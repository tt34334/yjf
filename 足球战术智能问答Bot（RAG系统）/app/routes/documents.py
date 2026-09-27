# File: app/routes/documents.py
"""知识库文档管理接口：上传入库、列表查询、删除（联动清理向量数据）。"""
import logging
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.models.schemas import (
    DeleteDocumentResponse,
    DocumentInfo,
    DocumentListResponse,
)
from app.services.knowledge_base import (
    KnowledgeBaseError,
    delete_document,
    ingest_document,
    list_documents,
)

router = APIRouter(prefix="/api/documents", tags=["知识库管理"])
logger = logging.getLogger(__name__)


@router.post(
    "/upload",
    response_model=DocumentInfo,
    summary="上传并解析文档",
    description="上传足球战术文档（PDF / TXT / Markdown），自动完成解析、分块、向量化并入库。",
)
async def upload_document(
    file: UploadFile = File(..., description="待上传的文档文件"),
):
    """上传文档：校验格式与大小后执行完整入库流程。"""
    # 1. 校验文件类型
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型「{suffix or '(无后缀)'}」，仅支持：PDF / TXT / Markdown",
        )

    # 2. 校验文件内容与大小
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="上传文件为空")
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大（{len(data) / 1024 / 1024:.1f}MB），最大支持 {settings.MAX_UPLOAD_SIZE_MB}MB",
        )

    # 3. 执行入库
    try:
        record = ingest_document(filename, data)
    except KnowledgeBaseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("文档入库发生未知异常：%s", filename)
        raise HTTPException(status_code=500, detail=f"文档处理失败：{e}")

    return DocumentInfo(**record)


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="获取文档列表",
    description="列出知识库中全部文档及其分块数量。",
)
async def get_documents():
    """查询文档列表。"""
    try:
        docs = list_documents()
    except Exception as e:
        logger.exception("获取文档列表异常")
        raise HTTPException(status_code=500, detail=f"获取文档列表失败：{e}")
    return DocumentListResponse(
        documents=[DocumentInfo(**d) for d in docs], total=len(docs)
    )


@router.delete(
    "/{doc_id}",
    response_model=DeleteDocumentResponse,
    summary="删除文档",
    description="删除指定文档，并联动删除其在向量库中的全部数据。",
)
async def remove_document(doc_id: str):
    """按文档 ID 删除文档及对应向量数据。"""
    try:
        result = delete_document(doc_id)
    except KnowledgeBaseError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("文档删除发生未知异常：%s", doc_id)
        raise HTTPException(status_code=500, detail=f"文档删除失败：{e}")
    return DeleteDocumentResponse(**result, message="删除成功")
