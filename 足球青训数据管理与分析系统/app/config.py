"""应用配置：通过环境变量注入，方便 Docker 化部署"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "足球青训数据管理 API"
    debug: bool = True

    # 默认使用 SQLite，方便本地零依赖调试；Docker compose 会覆盖为 MySQL
    database_url: str = "sqlite:///./academy.db"
    redis_url: str = "redis://localhost:6379/0"

    # 导出文件目录
    export_dir: str = "./exports"

    # 缓存：基础过期时间 30 分钟，叠加随机抖动防止缓存雪崩
    cache_player_ttl: int = 1800
    cache_jitter: int = 120

    @property
    def export_path(self) -> Path:
        path = Path(self.export_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
