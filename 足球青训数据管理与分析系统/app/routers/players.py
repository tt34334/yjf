"""球员档案：CRUD + 多条件分页查询 + Redis 缓存（功能一 & 功能三）"""
import redis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.cache import (
    cache_delete,
    cache_get,
    cache_set,
    get_redis,
    player_detail_key,
    player_detail_null_key,
)
from app.database import get_db
from app.models import MatchPerformance, Player
from app.schemas import PlayerCreate, PlayerOut, PlayerPage, PlayerUpdate, PlayerMatchHistory
from app.utils import serialize_model

router = APIRouter(prefix="/api/players", tags=["球员管理"])

VALID_POSITIONS = {"前锋", "中场", "后卫"}


@router.get("", response_model=PlayerPage, summary="球员分页查询（多条件动态过滤）")
def list_players(
    name: str | None = Query(None, description="姓名模糊匹配"),
    position: str | None = Query(None, description="位置：前锋/中场/后卫"),
    min_height: int | None = Query(None, ge=100, le=250, description="最小身高"),
    max_height: int | None = Query(None, ge=100, le=250, description="最大身高"),
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    size: int = Query(20, ge=1, le=100, description="每页条数"),
    db=Depends(get_db),
):
    # SQLAlchemy 动态拼接过滤条件
    filters = []
    if name:
        filters.append(Player.name.like(f"%{name}%"))
    if position:
        if position not in VALID_POSITIONS:
            raise HTTPException(status_code=400, detail=f"position 必须是 {VALID_POSITIONS} 之一")
        filters.append(Player.position == position)
    if min_height is not None:
        filters.append(Player.height >= min_height)
    if max_height is not None:
        filters.append(Player.height <= max_height)

    base_query = select(Player)
    if filters:
        base_query = base_query.where(*filters)

    total = db.scalar(select(func.count()).select_from(base_query.subquery()))
    rows = (
        db.execute(base_query.order_by(Player.id.desc()).offset((page - 1) * size).limit(size))
        .scalars()
        .all()
    )
    return PlayerPage(total=total or 0, page=page, size=size, items=[PlayerOut.model_validate(r) for r in rows])


@router.get("/{player_id}", response_model=PlayerOut, summary="球员详情（Redis 缓存加速）")
async def get_player(
    player_id: int,
    db=Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    cache_key = player_detail_key(player_id)
    null_key = player_detail_null_key(player_id)

    # 1) 先查缓存（含空值占位）
    cached = await cache_get(redis_client, cache_key)
    if cached == "__NULL_HIT__":
        raise HTTPException(status_code=404, detail="球员不存在")
    if cached is not None:
        return cached

    # 2) 缓存未命中，查 DB
    player = db.get(Player, player_id)
    if player is None:
        # 防穿透：写入空值短 TTL
        await cache_set(redis_client, null_key, None, base_ttl=60)
        raise HTTPException(status_code=404, detail="球员不存在")

    data = serialize_model(player)
    # 3) 回写缓存（随机 TTL 防雪崩）
    await cache_set(redis_client, cache_key, data)
    return data


@router.post("", response_model=PlayerOut, status_code=status.HTTP_201_CREATED, summary="新增球员")
def create_player(payload: PlayerCreate, db=Depends(get_db)):
    player = Player(**payload.model_dump())
    db.add(player)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"数据冲突：{e.orig}") from e
    db.refresh(player)
    return PlayerOut.model_validate(player)


@router.put("/{player_id}", response_model=PlayerOut, summary="更新球员信息（同步失效缓存）")
async def update_player(
    player_id: int,
    payload: PlayerUpdate,
    db=Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    player = db.get(Player, player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="球员不存在")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="未提供任何更新字段")
    for k, v in update_data.items():
        setattr(player, k, v)
    db.commit()
    db.refresh(player)

    # 同步删除该球员的缓存（含空值占位）
    await cache_delete(redis_client, player_detail_key(player_id), player_detail_null_key(player_id))
    return PlayerOut.model_validate(player)


@router.delete("/{player_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除球员")
async def delete_player(
    player_id: int,
    db=Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    player = db.get(Player, player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="球员不存在")
    db.delete(player)
    db.commit()
    await cache_delete(redis_client, player_detail_key(player_id), player_detail_null_key(player_id))
    return None


@router.get("/{player_id}/match-history", response_model=PlayerMatchHistory, summary="球员历史比赛数据汇总（总进球/助攻/出场/场均评分）")
def player_match_history(player_id: int, db=Depends(get_db)):
    p = db.get(Player, player_id)
    if p is None:
        raise HTTPException(status_code=404, detail="球员不存在")
    rows = (
        db.execute(
            select(MatchPerformance)
            .where(MatchPerformance.player_id == player_id)
            .order_by(MatchPerformance.id.desc())
        )
        .scalars()
        .all()
    )
    if not rows:
        return PlayerMatchHistory(
            player_id=player_id, name=p.name, matches_played=0, total_goals=0,
            total_assists=0, total_minutes=0, avg_rating=0.0, avg_goals=0.0, recent_ratings=[],
        )
    total_goals = sum(r.goals for r in rows)
    total_assists = sum(r.assists for r in rows)
    total_minutes = sum(r.minutes_played for r in rows)
    ratings = [float(r.rating) for r in rows if r.rating is not None]
    return PlayerMatchHistory(
        player_id=player_id,
        name=p.name,
        matches_played=len(rows),
        total_goals=total_goals,
        total_assists=total_assists,
        total_minutes=total_minutes,
        avg_rating=round(sum(ratings) / len(ratings), 2) if ratings else 0.0,
        avg_goals=round(total_goals / len(rows), 2),
        recent_ratings=ratings[:10],
    )

