"""对手管理：CRUD + 历史交锋统计"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Match, Opponent
from app.schemas import HeadToHeadStat, OpponentCreate, OpponentOut, OpponentUpdate
from app.utils import serialize_model

router = APIRouter(prefix="/api/opponents", tags=["对手管理"])


def _get_opponent(db: Session, opponent_id: int) -> Opponent:
    o = db.get(Opponent, opponent_id)
    if not o:
        raise HTTPException(404, "指定的对手不存在")
    return o


@router.get("", summary="获取所有对手列表")
def list_opponents(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = select(Opponent)
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar() or 0
    rows = (
        db.execute(q.order_by(Opponent.id).offset((page - 1) * size).limit(size))
        .scalars()
        .all()
    )
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [serialize_model(o) for o in rows],
    }


@router.post("", status_code=201, summary="新增对手")
def create_opponent(payload: OpponentCreate, db: Session = Depends(get_db)):
    o = Opponent(**payload.model_dump())
    db.add(o)
    db.commit()
    db.refresh(o)
    return serialize_model(o)


@router.get("/{opponent_id}/head-to-head", response_model=HeadToHeadStat, summary="与某对手的历史交锋统计")
def head_to_head(opponent_id: int, db: Session = Depends(get_db)):
    o = _get_opponent(db, opponent_id)
    # 按对手名称匹配 matches 表，计算实际胜平负
    rows = (
        db.execute(
            select(Match)
            .where(Match.opponent == o.name)
            .order_by(Match.match_date.desc())
        )
        .scalars()
        .all()
    )
    wins = sum(1 for r in rows if r.result == "胜")
    draws = sum(1 for r in rows if r.result == "平")
    losses = sum(1 for r in rows if r.result == "负")
    recent = [f"{r.score_our}:{r.score_opponent} {r.result or ''}" for r in rows[:5]]
    return HeadToHeadStat(
        opponent_id=o.id,
        opponent_name=o.name,
        wins=wins,
        draws=draws,
        losses=losses,
        total=len(rows),
        last_meeting=rows[0].match_date if rows else o.last_meeting,
        recent_results=recent,
    )


@router.get("/{opponent_id}", response_model=OpponentOut, summary="获取单个对手详情")
def get_opponent(opponent_id: int, db: Session = Depends(get_db)):
    return serialize_model(_get_opponent(db, opponent_id))


@router.put("/{opponent_id}", response_model=OpponentOut, summary="更新对手信息")
def update_opponent(opponent_id: int, payload: OpponentUpdate, db: Session = Depends(get_db)):
    o = _get_opponent(db, opponent_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(o, field, value)
    db.commit()
    db.refresh(o)
    return serialize_model(o)


@router.delete("/{opponent_id}", status_code=204, summary="删除对手")
def delete_opponent(opponent_id: int, db: Session = Depends(get_db)):
    o = _get_opponent(db, opponent_id)
    db.delete(o)
    db.commit()
