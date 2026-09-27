"""比赛管理：CRUD + 球员表现批量录入"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Match, MatchPerformance, Player
from app.schemas import (
    MatchCreate,
    MatchDetail,
    MatchOut,
    MatchPage,
    MatchUpdate,
    MatchPerformanceOut,
    PerformanceBatch,
)
from app.utils import serialize_model

router = APIRouter(prefix="/api/matches", tags=["比赛管理"])


def _get_match(db: Session, match_id: int) -> Match:
    m = db.get(Match, match_id)
    if not m:
        raise HTTPException(404, "指定的比赛不存在")
    return m


@router.get("", response_model=MatchPage, summary="比赛列表（支持日期/对手/赛事/结果筛选与分页）")
def list_matches(
    start: date | None = None,
    end: date | None = None,
    opponent: str | None = None,
    competition: str | None = None,
    result: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = select(Match)
    if start:
        q = q.where(Match.match_date >= start)
    if end:
        q = q.where(Match.match_date <= end)
    if opponent:
        q = q.where(Match.opponent.like(f"%{opponent}%"))
    if competition:
        q = q.where(Match.competition == competition)
    if result:
        q = q.where(Match.result == result)
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar() or 0
    rows = (
        db.execute(q.order_by(Match.match_date.desc()).offset((page - 1) * size).limit(size))
        .scalars()
        .all()
    )
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [MatchOut.model_validate(r) for r in rows],
    }


@router.get("/upcoming", summary="获取下一场比赛（最近的未来比赛）")
def upcoming(db: Session = Depends(get_db)):
    today = date.today()
    m = (
        db.execute(
            select(Match)
            .where(Match.match_date >= today)
            .order_by(Match.match_date.asc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    if not m:
        return {"upcoming": None}
    return {"upcoming": serialize_model(m)}


@router.get("/{match_id}", response_model=MatchDetail, summary="比赛详情（含该场所有球员表现）")
def get_match(match_id: int, db: Session = Depends(get_db)):
    m = _get_match(db, match_id)
    # 关联查询球员表现 + 球员姓名
    perfs = db.execute(
        select(MatchPerformance, Player.name)
        .join(Player, MatchPerformance.player_id == Player.id)
        .where(MatchPerformance.match_id == match_id)
    ).all()
    perf_list = []
    for p, pname in perfs:
        d = MatchPerformanceOut.model_validate(p)
        d.player_name = pname
        perf_list.append(d)
    detail = MatchDetail.model_validate(m)
    detail.performances = perf_list
    return detail


@router.post("", response_model=MatchOut, status_code=201, summary="创建比赛")
def create_match(payload: MatchCreate, db: Session = Depends(get_db)):
    m = Match(**payload.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    return MatchOut.model_validate(m)


@router.put("/{match_id}", response_model=MatchOut, summary="更新比赛信息")
def update_match(match_id: int, payload: MatchUpdate, db: Session = Depends(get_db)):
    m = _get_match(db, match_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)
    return MatchOut.model_validate(m)


@router.delete("/{match_id}", status_code=204, summary="删除比赛")
def delete_match(match_id: int, db: Session = Depends(get_db)):
    m = _get_match(db, match_id)
    db.delete(m)
    db.commit()


@router.post("/{match_id}/performances", summary="批量录入/更新该场比赛球员表现（全量覆盖）")
def set_performances(match_id: int, payload: PerformanceBatch, db: Session = Depends(get_db)):
    _get_match(db, match_id)
    pids = {p.player_id for p in payload.performances}
    if pids:
        exist = set(db.execute(select(Player.id).where(Player.id.in_(pids))).scalars().all())
        missing = pids - exist
        if missing:
            raise HTTPException(400, f"球员ID不存在: {missing}")
    # 全量覆盖：先删除该场所有表现，再批量插入
    db.execute(delete(MatchPerformance).where(MatchPerformance.match_id == match_id))
    for p in payload.performances:
        d = p.model_dump()
        d["match_id"] = match_id
        db.add(MatchPerformance(**d))
    db.commit()
    return {"match_id": match_id, "saved": len(payload.performances)}
