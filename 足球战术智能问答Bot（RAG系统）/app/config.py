# File: app/config.py
"""全局配置模块：统一管理环境变量、目录路径与 RAG 参数。"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（app/config.py 的上一级）
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """集中配置项，支持通过 .env 文件或环境变量覆盖。"""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------- 应用基础 ----------
    APP_NAME: str = "football-tactics-rag"
    APP_VERSION: str = "1.0.0"

    # ---------- LLM（OpenAI 兼容接口，支持 DeepSeek / 通义千问 / OpenAI 等） ----------
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_MODEL: str = "deepseek-chat"
    LLM_TEMPERATURE: float = 0.3
    LLM_TIMEOUT: int = 60
    LLM_MOCK_MODE: bool = False  # Mock 模式：不调用真实 LLM，返回模拟回答（用于验证问答链路）

    # ---------- Embedding（本地 sentence-transformers 模型，数据不出本机） ----------
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # ---------- RAG 参数 ----------
    CHUNK_SIZE: int = 500      # 分块最大字符数
    CHUNK_OVERLAP: int = 50    # 相邻分块的重叠字符数
    TOP_K: int = 5             # 检索返回的相关文档块数量

    # ---------- 存储路径 ----------
    DATA_DIR: Path = BASE_DIR / "data"

    # ---------- 上传限制 ----------
    MAX_UPLOAD_SIZE_MB: int = 20
    ALLOWED_EXTENSIONS: set[str] = {".pdf", ".txt", ".md"}

    # ---------- ChromaDB ----------
    CHROMA_COLLECTION: str = "football_tactics"

    # ---------- 派生路径 ----------
    @property
    def UPLOAD_DIR(self) -> Path:
        """上传原始文件的保存目录。"""
        return self.DATA_DIR / "uploads"

    @property
    def CHROMA_DIR(self) -> Path:
        """ChromaDB 持久化目录。"""
        return self.DATA_DIR / "chroma"

    @property
    def REGISTRY_PATH(self) -> Path:
        """文档元信息登记表路径。"""
        return self.DATA_DIR / "docs" / "registry.json"

    @property
    def SAMPLE_DOCS_DIR(self) -> Path:
        """预置示例文档目录。"""
        return BASE_DIR / "sample_docs"


settings = Settings()


def ensure_dirs() -> None:
    """初始化所有必需目录（不存在则自动创建）。"""
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    settings.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    settings.REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
