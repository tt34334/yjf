# File: app/services/knowledge_base.py
"""知识库管理模块：文档上传入库、列表查询、删除（联动清理向量数据）、示例文档导入。"""
import json
import logging
import uuid
from datetime import datetime

from app.config import settings
from app.core import vector_store
from app.services.document_parser import parse_document
from app.services.text_splitter import split_text

logger = logging.getLogger(__name__)


class KnowledgeBaseError(Exception):
    """知识库业务异常（携带用户可读的中文提示）。"""


def _load_registry() -> list[dict]:
    """读取文档元信息登记表（JSON 文件，损坏时视为空）。"""
    if not settings.REGISTRY_PATH.exists():
        return []
    try:
        return json.loads(settings.REGISTRY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("登记表文件损坏，已重置为空：%s", settings.REGISTRY_PATH)
        return []


def _save_registry(registry: list[dict]) -> None:
    """持久化文档元信息登记表。"""
    settings.REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings.REGISTRY_PATH.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def ingest_document(filename: str, data: bytes) -> dict:
    """完整入库流程：解析 -> 分块 -> 向量化 -> 写入 ChromaDB -> 登记文档信息。

    :param filename: 原始文件名
    :param data: 文件二进制内容
    :return: 文档元信息记录
    :raises KnowledgeBaseError: 解析失败 / 内容为空 / 向量库写入失败
    """
    # 1. 解析文本
    try:
        text = parse_document(filename, data).strip()
    except ValueError as e:
        raise KnowledgeBaseError(str(e))
    if not text:
        raise KnowledgeBaseError("文档内容为空，无法入库")

    # 2. 文本分块
    chunks = split_text(text)
    if not chunks:
        raise KnowledgeBaseError("文档切分后未得到有效内容")

    # 3. 写入向量库（失败则中断，避免产生脏数据）
    doc_id = uuid.uuid4().hex
    try:
        vector_store.add_chunks(doc_id, filename, chunks)
    except Exception as e:
        raise KnowledgeBaseError(f"向量库写入失败：{e}")

    # 4. 保存原始文件副本（删除文档时可一并清理）
    file_path = settings.UPLOAD_DIR / f"{doc_id}_{filename}"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(data)

    # 5. 登记文档元信息
    record = {
        "doc_id": doc_id,
        "filename": filename,
        "stored_filename": file_path.name,
        "size_bytes": len(data),
        "chunk_count": len(chunks),
        "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    registry = _load_registry()
    registry.append(record)
    _save_registry(registry)
    logger.info("文档入库成功：%s（%d 块）", filename, len(chunks))
    return record


def list_documents() -> list[dict]:
    """返回全部已上传文档的元信息，按上传时间倒序。"""
    return sorted(_load_registry(), key=lambda d: d.get("uploaded_at", ""), reverse=True)


def count_documents() -> int:
    """返回知识库文档总数。"""
    return len(_load_registry())


def delete_document(doc_id: str) -> dict:
    """删除文档：联动删除向量数据与原始文件副本。

    :param doc_id: 文档唯一 ID
    :return: 删除结果摘要（含删除的向量块数量）
    :raises KnowledgeBaseError: 文档不存在或向量删除失败
    """
    registry = _load_registry()
    record = next((d for d in registry if d["doc_id"] == doc_id), None)
    if record is None:
        raise KnowledgeBaseError(f"文档不存在：{doc_id}")

    # 1. 删除向量库中该文档的全部数据
    try:
        deleted_chunks = vector_store.get_doc_chunk_count(doc_id)
        vector_store.delete_by_doc(doc_id)
    except Exception as e:
        raise KnowledgeBaseError(f"向量数据删除失败：{e}")

    # 2. 删除原始文件副本
    stored = settings.UPLOAD_DIR / record["stored_filename"]
    if stored.exists():
        stored.unlink()

    # 3. 更新登记表
    registry = [d for d in registry if d["doc_id"] != doc_id]
    _save_registry(registry)
    logger.info("文档删除成功：%s（清理 %d 块向量）", record["filename"], deleted_chunks)
    return {
        "doc_id": doc_id,
        "filename": record["filename"],
        "deleted_chunks": deleted_chunks,
    }


def ensure_sample_docs() -> None:
    """启动时自动导入 sample_docs 目录下的示例文档（按文件名去重，已存在则跳过）。"""
    if not settings.SAMPLE_DOCS_DIR.exists():
        return
    existing = {d["filename"] for d in _load_registry()}
    sample_files = sorted(settings.SAMPLE_DOCS_DIR.glob("*.md")) + sorted(
        settings.SAMPLE_DOCS_DIR.glob("*.txt")
    )
    for path in sample_files:
        if path.name in existing:
            continue
        try:
            ingest_document(path.name, path.read_bytes())
            logger.info("示例文档已导入：%s", path.name)
        except Exception as e:
            logger.error("示例文档导入失败：%s，原因：%s", path.name, e)
