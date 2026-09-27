"""赛程管理：列表 + 创建 + 编辑 + 删除"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Opponent, Schedule
from app.schemas import ScheduleCreate, ScheduleOut, ScheduleUpdate
from app.utils import serialize_model

router = APIRouter(prefix="/api/schedules", tags=["赛程管理"])


def _get_schedule(db: Session, schedule_id: int) -> Schedule:
    s = db.get(Schedule, schedule_id)
    if not s:
        raise HTTPException(404, "指定的赛程不存在")
    return s


@router.get("", summary="赛程列表（按日期排序，含对手名称）")
def list_schedules(
    status: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = select(Schedule, Opponent.name).join(Opponent, Schedule.opponent_id == Opponent.id)
    if status:
        q = q.where(Schedule.status == status)
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar() or 0
    rows = (
        db.execute(q.order_by(Schedule.match_date.asc()).offset((page - 1) * size).limit(size))
        .all()
    )
    items = []
    for s, oname in rows:
        d = serialize_model(s)
        d["opponent_name"] = oname
        items.append(d)
    return {"total": total, "page": page, "size": size, "items": items}


@router.post("", status_code=201, summary="创建赛程安排")
def create_schedule(payload: ScheduleCreate, db: Session = Depends(get_db)):
    if not db.get(Opponent, payload.opponent_id):
        raise HTTPException(400, "指定的对手不存在")
    s = Schedule(**payload.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return serialize_model(s)


@router.get("/{schedule_id}", response_model=ScheduleOut, summary="获取单条赛程")
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    s = _get_schedule(db, schedule_id)
    d = serialize_model(s)
    opp = db.get(Opponent, s.opponent_id)
    d["opponent_name"] = opp.name if opp else None
    return d


@router.put("/{schedule_id}", response_model=ScheduleOut, summary="更新赛程")
def update_schedule(schedule_id: int, payload: ScheduleUpdate, db: Session = Depends(get_db)):
    s = _get_schedule(db, schedule_id)
    data = payload.model_dump(exclude_unset=True)
    if "opponent_id" in data and data["opponent_id"] is not None:
        if not db.get(Opponent, data["opponent_id"]):
            raise HTTPException(400, "指定的对手不存在")
    for field, value in data.items():
        if value is not None:
            setattr(s, field, value)
    db.commit()
    db.refresh(s)
    d = serialize_model(s)
    opp = db.get(Opponent, s.opponent_id)
    d["opponent_name"] = opp.name if opp else None
    return d


@router.delete("/{schedule_id}", status_code=204, summary="删除赛程")
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    s = _get_schedule(db, schedule_id)
    db.delete(s)
    db.commit()

