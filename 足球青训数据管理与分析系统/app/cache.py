"""Redis 缓存：随机 TTL 防雪崩 + 空值短 TTL 防穿透 + 熔断降级"""
import json
import random
import time
from typing import Any

import redis
from redis.exceptions import RedisError

from app.config import settings

# 设置短超时：Redis 未运行时 0.2 秒快速失败降级，避免拖慢接口（默认无超时会卡 ~8 秒）
pool = redis.ConnectionPool.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=0.2,
    socket_timeout=0.2,
)

# 熔断：Redis 连接失败后 30 秒内跳过所有缓存操作，避免每次请求都反复试连拖慢响应
_CIRCUIT_OPEN_UNTIL = 0.0
_CIRCUIT_RECOVERY_SECONDS = 30


def _cache_available() -> bool:
    """熔断器是否闭合（即允许访问 Redis）"""
    return time.time() >= _CIRCUIT_OPEN_UNTIL


def _trip_circuit() -> None:
    """触发熔断：接下来 30 秒内所有缓存操作直接跳过"""
    global _CIRCUIT_OPEN_UNTIL
    _CIRCUIT_OPEN_UNTIL = time.time() + _CIRCUIT_RECOVERY_SECONDS


def get_redis() -> redis.Redis:
    """FastAPI 依赖：可复用的 Redis 客户端"""
    return redis.Redis(connection_pool=pool)


# 空值占位符：DB 查询为空时写入此标记，避免穿透反复打 DB
NULL_PLACEHOLDER = "__NULL__"


def _ttl(base: int, jitter: int) -> int:
    """基础 TTL + 随机抖动，避免大量 key 同时过期造成缓存雪崩"""
    return base + random.randint(0, jitter)


def _key(*parts: Any) -> str:
    return ":".join(str(p) for p in parts)


def player_detail_key(player_id: int) -> str:
    return _key("player", "detail", player_id)


def player_detail_null_key(player_id: int) -> str:
    return _key("player", "detail", "null", player_id)


async def cache_get(client: redis.Redis, key: str) -> Any | None:
    """读取缓存；命中占位符返回 None 但标识缓存命中；熔断或故障时降级直查 DB"""
    if not _cache_available():
        return None
    try:
        raw = client.get(key)
    except RedisError:
        # Redis 不可用时触发熔断，后续请求直接跳过缓存层
        _trip_circuit()
        return None
    if raw is None:
        return None
    if raw == NULL_PLACEHOLDER:
        # 显式标记为“缓存里的空值”
        return "__NULL_HIT__"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


async def cache_set(client: redis.Redis, key: str, value: Any, base_ttl: int | None = None) -> None:
    if not _cache_available():
        return
    if base_ttl is None:
        base_ttl = settings.cache_player_ttl
    try:
        payload = NULL_PLACEHOLDER if value is None else json.dumps(value, ensure_ascii=False, default=str)
        client.set(key, payload, ex=_ttl(base_ttl, settings.cache_jitter))
    except RedisError:
        _trip_circuit()


async def cache_delete(client: redis.Redis, *keys: str) -> None:
    if not keys:
        return
    if not _cache_available():
        return
    try:
        client.delete(*keys)
    except RedisError:
        _trip_circuit()


# 任务状态缓存命名
def task_status_key(task_id: str) -> str:
    return _key("task", "export", task_id)
