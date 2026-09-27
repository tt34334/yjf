"""训练记录：复杂聚合统计（功能二）+ 异步 Excel 导出（功能四）"""
import json
import uuid
from datetime import date, datetime, timedelta

import redis
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select, text

from app.cache import get_redis, task_status_key
from app.database import SessionLocal, get_db
from app.models import Player, TrainingRecord
from app.schemas import (
    ExportTaskCreate,
    ExportTaskOut,
    ExportTaskResult,
    TrainingRecordCreate,
    TrainingRecordOut,
    TrainingRecordPage,
    TrainingRecordUpdate,
    TrainingStatistics,
)
from app.tasks import export_match_report, export_training_report
from app.utils import round2

router = APIRouter(prefix="/api/training", tags=["训练管理"])


@router.post("/records", response_model=TrainingRecordOut, status_code=201, summary="新增训练记录")
def create_record(payload: TrainingRecordCreate, db=Depends(get_db)):
    if db.get(Player, payload.player_id) is None:
        raise HTTPException(status_code=404, detail="指定的球员不存在")
    record = TrainingRecord(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return TrainingRecordOut.model_validate(record)


@router.get("/records", response_model=TrainingRecordPage, summary="训练记录列表")
def list_records(
    player_id: int | None = Query(None, description="球员ID"),
    start: date | None = Query(None, description="起始日期"),
    end: date | None = Query(None, description="结束日期"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    db=Depends(get_db),
):
    q = select(TrainingRecord)
    if player_id is not None:
        q = q.where(TrainingRecord.player_id == player_id)
    if start is not None:
        q = q.where(TrainingRecord.training_date >= start)
    if end is not None:
        q = q.where(TrainingRecord.training_date <= end)
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar() or 0
    rows = db.execute(
        q.order_by(TrainingRecord.training_date.desc(), TrainingRecord.id.desc())
        .offset((page - 1) * size).limit(size)
    ).scalars().all()
    return TrainingRecordPage(
        total=total, page=page, size=size,
        items=[TrainingRecordOut.model_validate(r) for r in rows],
    )


@router.get("/records/avg_sql", summary="原生 SQL 演示：按位置聚合")
def avg_by_position_sql(db=Depends(get_db)):
    """展示原生 SQL 执行能力（ORM 之外的补充技能点）"""
    sql = text(
        """
        SELECT p.position,
               ROUND(AVG(tr.distance), 2) AS avg_distance,
               ROUND(AVG(tr.duration), 2) AS avg_duration,
               COUNT(DISTINCT p.id)            AS player_count
        FROM players p
        JOIN training_records tr ON tr.player_id = p.id
        GROUP BY p.position
        HAVING COUNT(tr.id) > 0
        """
    )
    rows = db.execute(sql).mappings().all()
    return {"items": [dict(r) for r in rows]}


@router.get("/records/{record_id}", response_model=TrainingRecordOut, summary="单条训练记录详情")
def get_record(record_id: int, db=Depends(get_db)):
    r = db.get(TrainingRecord, record_id)
    if not r:
        raise HTTPException(404, "指定的训练记录不存在")
    return TrainingRecordOut.model_validate(r)


@router.put("/records/{record_id}", response_model=TrainingRecordOut, summary="更新训练记录")
def update_record(record_id: int, payload: TrainingRecordUpdate, db=Depends(get_db)):
    r = db.get(TrainingRecord, record_id)
    if not r:
        raise HTTPException(404, "指定的训练记录不存在")
    data = payload.model_dump(exclude_unset=True)
    if "player_id" in data and data["player_id"] is not None:
        if db.get(Player, data["player_id"]) is None:
            raise HTTPException(404, "指定的球员不存在")
    for field, value in data.items():
        if value is not None:
            setattr(r, field, value)
    db.commit()
    db.refresh(r)
    return TrainingRecordOut.model_validate(r)


@router.delete("/records/{record_id}", status_code=204, summary="删除训练记录")
def delete_record(record_id: int, db=Depends(get_db)):
    r = db.get(TrainingRecord, record_id)
    if not r:
        raise HTTPException(404, "指定的训练记录不存在")
    db.delete(r)
    db.commit()


@router.get("/statistics", response_model=TrainingStatistics, summary="复杂业务统计（聚合查询）")
def training_statistics(
    start: date = Query(..., description="起始日期，例如 2026-08-01"),
    end: date = Query(..., description="结束日期，例如 2026-08-31"),
    db=Depends(get_db),
):
    if start > end:
        raise HTTPException(status_code=400, detail="起始日期不能晚于结束日期")

    # 1) 本月总训练次数（在日期范围内的训练记录总数）
    total_sessions = db.scalar(
        select(func.count(TrainingRecord.id)).where(
            TrainingRecord.training_date.between(start, end)
        )
    ) or 0

    # 2) 各位置球员平均跑动距离（players JOIN training_records + group_by position）
    #    having 子句：仅保留有训练记录的位置
    position_rows = db.execute(
        select(
            Player.position.label("position"),
            func.round(func.avg(TrainingRecord.distance), 2).label("avg_distance"),
            func.round(func.avg(TrainingRecord.duration), 2).label("avg_duration"),
            func.count(func.distinct(Player.id)).label("player_count"),
        )
        .join(TrainingRecord, TrainingRecord.player_id == Player.id)
        .where(TrainingRecord.training_date.between(start, end))
        .group_by(Player.position)
        .having(func.count(TrainingRecord.id) > 0)
    ).all()

    # 3) 出勤率最高的前 3 名球员（训练次数降序）
    top3_rows = db.execute(
        select(
            Player.id.label("player_id"),
            Player.name.label("name"),
            Player.position.label("position"),
            func.count(TrainingRecord.id).label("attendance"),
        )
        .join(TrainingRecord, TrainingRecord.player_id == Player.id)
        .where(TrainingRecord.training_date.between(start, end))
        .group_by(Player.id, Player.name, Player.position)
        .order_by(func.count(TrainingRecord.id).desc())
        .limit(3)
    ).all()

    return TrainingStatistics(
        start=start,
        end=end,
        total_sessions=total_sessions,
        position_stats=[
            {
                "position": r.position,
                "avg_distance": round2(r.avg_distance),
                "avg_duration": round2(r.avg_duration),
                "player_count": r.player_count,
            }
            for r in position_rows
        ],
        top3_attendance=[
            {
                "player_id": r.player_id,
                "name": r.name,
                "position": r.position,
                "attendance": r.attendance,
            }
            for r in top3_rows
        ],
    )


@router.get("/daily_trend", summary="每日训练趋势（供前端折线图）")
def training_daily_trend(
    start: date = Query(..., description="起始日期，例如 2026-08-01"),
    end: date = Query(..., description="结束日期，例如 2026-08-31"),
    db=Depends(get_db),
):
    if start > end:
        raise HTTPException(status_code=400, detail="起始日期不能晚于结束日期")
    rows = db.execute(
        select(
            TrainingRecord.training_date.label("date"),
            func.count(TrainingRecord.id).label("sessions"),
            func.round(func.sum(TrainingRecord.distance), 2).label("total_distance"),
        )
        .where(TrainingRecord.training_date.between(start, end))
        .group_by(TrainingRecord.training_date)
        .order_by(TrainingRecord.training_date)
    ).all()
    return [
        {"date": str(r.date), "sessions": r.sessions, "total_distance": float(r.total_distance or 0)}
        for r in rows
    ]


@router.post("/export", response_model=ExportTaskOut, status_code=202, summary="异步导出 Excel 报告")
async def export_report(
    background_tasks: BackgroundTasks,
    payload: ExportTaskCreate | None = None,
    redis_client: redis.Redis = Depends(get_redis),
):
    today = date.today()
    end = (payload and payload.end) or today
    start = (payload and payload.start) or (end - timedelta(days=30))
    report_type = (payload and payload.report_type) or "training"

    task_id = uuid.uuid4().hex
    meta = {
        "task_id": task_id,
        "status": "processing",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    # Redis 不可用时降级：仍接受任务并交给后台执行，仅状态查询会失效
    try:
        redis_client.set(task_status_key(task_id), json.dumps(meta, ensure_ascii=False), ex=86400)
    except redis.RedisError:
        pass

    # 把任务交给 FastAPI 的 BackgroundTasks 执行（异步导出 Excel）
    if report_type == "match":
        background_tasks.add_task(export_match_report, task_id, start, end)
    else:
        background_tasks.add_task(export_training_report, task_id, start, end)
    return ExportTaskOut(**meta)


@router.get("/export/{task_id}", response_model=ExportTaskResult, summary="查询导出任务状态/结果")
def export_status(task_id: str, redis_client: redis.Redis = Depends(get_redis)):
    try:
        raw = redis_client.get(task_status_key(task_id))
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="缓存服务不可用，无法查询任务状态")
    if raw is None:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return ExportTaskResult(**json.loads(raw))
