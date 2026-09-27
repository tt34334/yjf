"""后台任务：异步生成训练统计 Excel 报告（功能四）"""
import json
from datetime import date, datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import func, select

from app.cache import task_status_key
from app.config import settings
from app.database import SessionLocal
from app.models import Match, MatchPerformance, Player, TrainingRecord
from app.utils import round2

# 任务状态常量
STATUS_PROCESSING = "processing"
STATUS_DONE = "done"
STATUS_FAILED = "failed"


def _update_task_status(task_id: str, status: str, **extra) -> None:
    """把任务状态写入 Redis（无法连 Redis 时静默降级）"""
    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        meta = {
            "task_id": task_id,
            "status": status,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        meta.update(extra)
        client.set(task_status_key(task_id), json.dumps(meta, ensure_ascii=False), ex=86400)
    except Exception:
        # Redis 故障不应让导出任务失败
        pass


def _gather_data(start: date, end: date) -> dict:
    """聚合统计所需数据"""
    db = SessionLocal()
    try:
        total_sessions = db.scalar(
            select(func.count(TrainingRecord.id)).where(
                TrainingRecord.training_date.between(start, end)
            )
        ) or 0

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
        ).all()

        top_rows = db.execute(
            select(
                Player.id.label("player_id"),
                Player.name.label("name"),
                Player.position.label("position"),
                func.count(TrainingRecord.id).label("attendance"),
                func.round(func.avg(TrainingRecord.distance), 2).label("avg_distance"),
            )
            .join(TrainingRecord, TrainingRecord.player_id == Player.id)
            .where(TrainingRecord.training_date.between(start, end))
            .group_by(Player.id, Player.name, Player.position)
            .order_by(func.count(TrainingRecord.id).desc())
            .limit(10)
        ).all()

        return {
            "total_sessions": total_sessions,
            "position_rows": position_rows,
            "top_rows": top_rows,
        }
    finally:
        db.close()


def export_training_report(task_id: str, start: date, end: date) -> None:
    """生成 Excel 报告并落到服务器本地，更新任务状态"""
    _update_task_status(task_id, STATUS_PROCESSING)
    try:
        data = _gather_data(start, end)

        wb = Workbook()
        ws = wb.active
        ws.title = "训练统计"

        title_font = Font(bold=True, size=14, color="FFFFFF")
        title_fill = PatternFill("solid", fgColor="2E75B6")
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill("solid", fgColor="5B9BD5")
        center = Alignment(horizontal="center", vertical="center")

        ws.merge_cells("A1:D1")
        cell = ws["A1"]
        cell.value = f"足球青训训练统计报表 ({start} ~ {end})"
        cell.font = title_font
        cell.fill = title_fill
        cell.alignment = center
        ws.row_dimensions[1].height = 26

        # 区块 1：总训练次数
        ws["A3"] = "本月总训练次数"
        ws["A3"].font = Font(bold=True)
        ws["B3"] = data["total_sessions"]
        ws["B3"].alignment = center

        # 区块 2：各位置平均跑动距离
        ws["A5"] = "各位置球员训练负荷"
        ws["A5"].font = Font(bold=True, size=12)
        headers = ["位置", "球员数", "平均跑动距离(m)", "平均训练时长(分钟)"]
        for col, h in enumerate(headers, start=1):
            c = ws.cell(row=6, column=col, value=h)
            c.font = header_font
            c.fill = header_fill
            c.alignment = center

        row_idx = 7
        for r in data["position_rows"]:
            ws.cell(row=row_idx, column=1, value=r.position).alignment = center
            ws.cell(row=row_idx, column=2, value=r.player_count).alignment = center
            ws.cell(row=row_idx, column=3, value=round2(r.avg_distance)).alignment = center
            ws.cell(row=row_idx, column=4, value=round2(r.avg_duration)).alignment = center
            row_idx += 1

        # 区块 3：出勤率 Top 球员
        top_start = row_idx + 1
        ws.cell(row=top_start, column=1, value="出勤率 Top 球员").font = Font(bold=True, size=12)
        top_headers = ["球员ID", "姓名", "位置", "出勤次数", "平均跑动距离(m)"]
        for col, h in enumerate(top_headers, start=1):
            c = ws.cell(row=top_start + 1, column=col, value=h)
            c.font = header_font
            c.fill = header_fill
            c.alignment = center

        r_idx = top_start + 2
        for r in data["top_rows"]:
            ws.cell(row=r_idx, column=1, value=r.player_id).alignment = center
            ws.cell(row=r_idx, column=2, value=r.name).alignment = center
            ws.cell(row=r_idx, column=3, value=r.position).alignment = center
            ws.cell(row=r_idx, column=4, value=r.attendance).alignment = center
            ws.cell(row=r_idx, column=5, value=round2(r.avg_distance)).alignment = center
            r_idx += 1

        # 列宽自适应
        for col in range(1, 6):
            ws.column_dimensions[get_column_letter(col)].width = 22

        # 生成文件名
        filename = f"training_report_{start}_{end}_{task_id[:8]}.xlsx"
        file_path = settings.export_path / filename
        wb.save(file_path)

        _update_task_status(
            task_id,
            STATUS_DONE,
            file_path=str(file_path),
            file_name=filename,
        )
    except Exception as e:  # noqa: BLE001  后台任务里必须捕获所有异常
        _update_task_status(task_id, STATUS_FAILED, error=str(e))


def _gather_match_data(start: date, end: date) -> dict:
    """聚合比赛统计所需数据"""
    db = SessionLocal()
    try:
        # 区间内所有比赛
        matches = db.execute(
            select(Match)
            .where(Match.match_date.between(start, end))
            .order_by(Match.match_date)
        ).scalars().all()

        # 胜平负统计
        wins = sum(1 for m in matches if m.result == "胜")
        draws = sum(1 for m in matches if m.result == "平")
        losses = sum(1 for m in matches if m.result == "负")
        total_goals = sum(m.score_our for m in matches)
        total_conceded = sum(m.score_opponent for m in matches)

        # 球员表现汇总：进球/助攻/出场时间/场均评分
        perf_rows = db.execute(
            select(
                Player.id.label("player_id"),
                Player.name.label("name"),
                Player.position.label("position"),
                func.coalesce(func.sum(MatchPerformance.goals), 0).label("total_goals"),
                func.coalesce(func.sum(MatchPerformance.assists), 0).label("total_assists"),
                func.coalesce(func.sum(MatchPerformance.minutes_played), 0).label("total_minutes"),
                func.count(MatchPerformance.id).label("appearances"),
                func.round(func.avg(MatchPerformance.rating), 2).label("avg_rating"),
            )
            .join(MatchPerformance, MatchPerformance.player_id == Player.id)
            .join(Match, Match.id == MatchPerformance.match_id)
            .where(Match.match_date.between(start, end))
            .group_by(Player.id, Player.name, Player.position)
            .order_by(func.sum(MatchPerformance.goals).desc())
        ).all()

        return {
            "matches": matches,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "total_goals": total_goals,
            "total_conceded": total_conceded,
            "perf_rows": perf_rows,
        }
    finally:
        db.close()


def export_match_report(task_id: str, start: date, end: date) -> None:
    """生成比赛数据 Excel 报告并落到服务器本地，更新任务状态"""
    _update_task_status(task_id, STATUS_PROCESSING)
    try:
        data = _gather_match_data(start, end)

        wb = Workbook()
        ws = wb.active
        ws.title = "比赛统计"

        title_font = Font(bold=True, size=14, color="FFFFFF")
        title_fill = PatternFill("solid", fgColor="2E7D32")
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill("solid", fgColor="43A047")
        center = Alignment(horizontal="center", vertical="center")

        ws.merge_cells("A1:G1")
        cell = ws["A1"]
        cell.value = f"足球青训比赛数据报表 ({start} ~ {end})"
        cell.font = title_font
        cell.fill = title_fill
        cell.alignment = center
        ws.row_dimensions[1].height = 26

        # 区块 1：战绩汇总
        total = len(data["matches"])
        ws["A3"] = "比赛场次"
        ws["B3"] = total
        ws["A4"] = "胜/平/负"
        ws["B4"] = f"{data['wins']} / {data['draws']} / {data['losses']}"
        ws["A5"] = "总进球"
        ws["B5"] = data["total_goals"]
        ws["A6"] = "总失球"
        ws["B6"] = data["total_conceded"]
        ws["A7"] = "胜率"
        ws["B7"] = f"{(data['wins'] / total * 100):.1f}%" if total else "0%"
        for r in range(3, 8):
            ws.cell(row=r, column=1).font = Font(bold=True)
            ws.cell(row=r, column=2).alignment = center

        # 区块 2：比赛明细
        ws["A9"] = "比赛明细"
        ws["A9"].font = Font(bold=True, size=12)
        match_headers = ["日期", "对手", "场地", "我方比分", "对方比分", "结果", "赛事"]
        for col, h in enumerate(match_headers, start=1):
            c = ws.cell(row=10, column=col, value=h)
            c.font = header_font
            c.fill = header_fill
            c.alignment = center

        row_idx = 11
        for m in data["matches"]:
            ws.cell(row=row_idx, column=1, value=str(m.match_date)).alignment = center
            ws.cell(row=row_idx, column=2, value=m.opponent).alignment = center
            ws.cell(row=row_idx, column=3, value=m.venue or "").alignment = center
            ws.cell(row=row_idx, column=4, value=m.score_our).alignment = center
            ws.cell(row=row_idx, column=5, value=m.score_opponent).alignment = center
            ws.cell(row=row_idx, column=6, value=m.result or "").alignment = center
            ws.cell(row=row_idx, column=7, value=m.competition or "").alignment = center
            row_idx += 1

        # 区块 3：球员表现汇总
        perf_start = row_idx + 2
        ws.cell(row=perf_start, column=1, value="球员表现汇总").font = Font(bold=True, size=12)
        perf_headers = ["球员ID", "姓名", "位置", "出场次数", "总进球", "总助攻", "总出场时间", "场均评分"]
        for col, h in enumerate(perf_headers, start=1):
            c = ws.cell(row=perf_start + 1, column=col, value=h)
            c.font = header_font
            c.fill = header_fill
            c.alignment = center

        r_idx = perf_start + 2
        for r in data["perf_rows"]:
            ws.cell(row=r_idx, column=1, value=r.player_id).alignment = center
            ws.cell(row=r_idx, column=2, value=r.name).alignment = center
            ws.cell(row=r_idx, column=3, value=r.position).alignment = center
            ws.cell(row=r_idx, column=4, value=r.appearances).alignment = center
            ws.cell(row=r_idx, column=5, value=int(r.total_goals)).alignment = center
            ws.cell(row=r_idx, column=6, value=int(r.total_assists)).alignment = center
            ws.cell(row=r_idx, column=7, value=int(r.total_minutes)).alignment = center
            ws.cell(row=r_idx, column=8, value=round2(r.avg_rating) if r.avg_rating else "").alignment = center
            r_idx += 1

        # 列宽自适应
        for col in range(1, 9):
            ws.column_dimensions[get_column_letter(col)].width = 18

        filename = f"match_report_{start}_{end}_{task_id[:8]}.xlsx"
        file_path = settings.export_path / filename
        wb.save(file_path)

        _update_task_status(
            task_id,
            STATUS_DONE,
            file_path=str(file_path),
            file_name=filename,
        )
    except Exception as e:  # noqa: BLE001
        _update_task_status(task_id, STATUS_FAILED, error=str(e))
