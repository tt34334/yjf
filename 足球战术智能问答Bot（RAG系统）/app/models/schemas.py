# File: app/models/schemas.py
"""Pydantic 请求 / 响应模型定义。"""
from pydantic import BaseModel, Field


# ==================== 文档管理 ====================
class DocumentInfo(BaseModel):
    """文档元信息。"""

    doc_id: str = Field(..., description="文档唯一 ID")
    filename: str = Field(..., description="文档名称")
    size_bytes: int = Field(..., description="文件大小（字节）")
    chunk_count: int = Field(..., description="分块数量")
    uploaded_at: str = Field(..., description="上传时间")


class DocumentListResponse(BaseModel):
    """文档列表响应。"""

    total: int = Field(..., description="文档总数")
    documents: list[DocumentInfo] = Field(..., description="文档列表")


class DeleteDocumentResponse(BaseModel):
    """文档删除响应。"""

    doc_id: str = Field(..., description="被删除的文档 ID")
    filename: str = Field(..., description="被删除的文档名称")
    deleted_chunks: int = Field(..., description="连带删除的向量块数量")
    message: str = Field(..., description="操作结果说明")


# ==================== RAG 问答 ====================
class ChatRequest(BaseModel):
    """问答请求。"""

    question: str = Field(
        ..., min_length=1, max_length=1000, description="用户的足球战术问题"
    )


class SourceInfo(BaseModel):
    """单条引用来源信息。"""

    index: int = Field(..., description="引用编号，与回答中的 [n] 标注对应")
    doc_id: str = Field(..., description="来源文档 ID")
    doc_name: str = Field(..., description="来源文档名称")
    chunk_index: int = Field(..., description="段落在文档中的序号（从 0 开始）")
    snippet: str = Field(..., description="原文片段摘要")
    score: float = Field(..., description="与问题的相似度（0~1，越大越相关）")


class ChatResponse(BaseModel):
    """问答响应。"""

    question: str = Field(..., description="用户问题")
    answer: str = Field(..., description="LLM 生成的回答（内含 [n] 引用标注）")
    sources: list[SourceInfo] = Field(
        default_factory=list, description="回答引用的来源列表"
    )


# ==================== 系统 ====================
class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: str = Field(..., description="运行状态")
    app: str = Field(..., description="应用名称")
    version: str = Field(..., description="应用版本")
    vector_count: int = Field(..., description="向量库总块数")
    document_count: int = Field(..., description="知识库文档总数")
    llm_configured: bool = Field(..., description="是否已配置有效的 LLM API Key")
    llm_mock: bool = Field(..., description="是否处于 Mock 模式（不调用真实 LLM）")
    llm_model: str = Field(..., description="LLM 模型名称")
    embedding_model: str = Field(..., description="Embedding 模型名称")
