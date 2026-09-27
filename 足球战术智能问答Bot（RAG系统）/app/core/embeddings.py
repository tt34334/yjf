# File: app/core/embeddings.py
"""本地 Embedding 模型封装（sentence-transformers）。

模型在本地运行、数据不上传，保证隐私安全。
"""
import os

# 国内网络默认使用 HuggingFace 镜像站加速模型下载（可用环境变量覆盖）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from sentence_transformers import SentenceTransformer  # noqa: E402

from app.config import settings  # noqa: E402

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """懒加载并缓存本地 Embedding 模型（进程内单例，避免重复加载）。"""
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.EMBEDDING_MODEL, device="cpu")
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量将文本转换为向量（做归一化，配合余弦相似度检索）。"""
    if not texts:
        return []
    model = get_embedding_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]


def embed_query(text: str) -> list[float]:
    """将单条查询语句转换为向量。"""
    return embed_texts([text])[0]
