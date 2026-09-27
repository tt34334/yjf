# File: app/core/vector_store.py
"""ChromaDB 向量库封装：文档向量与元数据的持久化存取。

- 本地持久化存储（无需额外部署数据库服务）
- 使用余弦相似度（cosine）作为检索距离度量
"""
from chromadb import PersistentClient
from chromadb.config import Settings as ChromaSettings

from app.config import settings
from app.core.embeddings import embed_query, embed_texts

_client = None
_collection = None


def get_collection():
    """获取 ChromaDB 集合（懒加载单例，持久化到本地磁盘）。"""
    global _client, _collection
    if _collection is None:
        _client = PersistentClient(
            path=str(settings.CHROMA_DIR),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _collection = _client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def add_chunks(doc_id: str, filename: str, chunks: list[str]) -> int:
    """将文档分块向量化后写入 ChromaDB，返回写入的块数。

    每个块携带元数据：doc_id（所属文档）、filename（文档名）、chunk_index（段落序号），
    用于检索后展示引用来源，以及按文档删除向量数据。
    """
    if not chunks:
        return 0
    embeddings = embed_texts(chunks)
    collection = get_collection()
    collection.add(
        ids=[f"{doc_id}::{i}" for i in range(len(chunks))],
        documents=chunks,
        embeddings=embeddings,
        metadatas=[
            {"doc_id": doc_id, "filename": filename, "chunk_index": i}
            for i in range(len(chunks))
        ],
    )
    return len(chunks)


def search(query: str, top_k: int | None = None) -> list[dict]:
    """检索与问题最相关的 Top-K 文档块，返回按相似度降序排列的结果列表。"""
    collection = get_collection()
    total = collection.count()
    if total == 0:
        return []
    top_k = top_k or settings.TOP_K
    result = collection.query(
        query_embeddings=[embed_query(query)],
        n_results=min(top_k, total),
        include=["documents", "metadatas", "distances"],
    )
    hits: list[dict] = []
    for doc, meta, dist in zip(
        result["documents"][0], result["metadatas"][0], result["distances"][0]
    ):
        hits.append(
            {
                "text": doc,
                "doc_id": meta["doc_id"],
                "filename": meta["filename"],
                "chunk_index": meta["chunk_index"],
                # 余弦距离转相似度：similarity = 1 - distance
                "score": round(1.0 - float(dist), 4),
            }
        )
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits


def get_doc_chunk_count(doc_id: str) -> int:
    """统计指定文档在向量库中的块数（删除前用于返回删除数量）。"""
    result = get_collection().get(where={"doc_id": doc_id}, include=["metadatas"])
    return len(result["ids"])


def delete_by_doc(doc_id: str) -> None:
    """按元数据条件删除指定文档的全部向量数据（与文档删除操作联动）。"""
    get_collection().delete(where={"doc_id": doc_id})


def count() -> int:
    """返回向量库中的总块数。"""
    return get_collection().count()
