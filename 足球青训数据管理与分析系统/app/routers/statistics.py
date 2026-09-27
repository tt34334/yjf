"""数据统计：球队整体统计 + 球员排行榜 + 战绩趋势"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Match, MatchPerformance, Player
from app.schemas import MatchTrendItem, PlayerRankingItem, TeamStatistics

router = APIRouter(prefix="/api/statistics", tags=["数据统计"])


@router.get("/team", response_model=TeamStatistics, summary="球队整体统计（总比赛/胜平负/进球/场均）")
def team_stats(db: Session = Depends(get_db)):
    total = db.execute(select(func.count(Match.id))).scalar() or 0
    wins = db.execute(select(func.count(Match.id)).where(Match.result == "胜")).scalar() or 0
    draws = db.execute(select(func.count(Match.id)).where(Match.result == "平")).scalar() or 0
    losses = db.execute(select(func.count(Match.id)).where(Match.result == "负")).scalar() or 0
    total_goals = db.execute(select(func.coalesce(func.sum(Match.score_our), 0))).scalar() or 0
    total_conceded = db.execute(select(func.coalesce(func.sum(Match.score_opponent), 0))).scalar() or 0
    return TeamStatistics(
        total_matches=total,
        wins=wins,
        draws=draws,
        losses=losses,
        win_rate=round(wins / total * 100, 1) if total else 0.0,
        total_goals=total_goals,
        total_conceded=total_conceded,
        avg_goals=round(total_goals / total, 2) if total else 0.0,
        avg_conceded=round(total_conceded / total, 2) if total else 0.0,
    )


@router.get("/player-ranking", summary="球员排行榜（按进球/助攻/评分/出场时间排序）")
def player_ranking(
    sort_by: str = Query("goals", description="goals/assists/rating/minutes"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    # 按 player_id 聚合表现数据
    rows = db.execute(
        select(
            MatchPerformance.player_id,
            func.sum(MatchPerformance.goals).label("goals"),
            func.sum(MatchPerformance.assists).label("assists"),
            func.sum(MatchPerformance.minutes_played).label("minutes"),
            func.count(MatchPerformance.id).label("matches"),
            func.avg(MatchPerformance.rating).label("avg_rating"),
        ).group_by(MatchPerformance.player_id)
    ).all()
    pids = [r[0] for r in rows]
    players = (
        {p.id: p for p in db.execute(select(Player).where(Player.id.in_(pids))).scalars()}
        if pids
        else {}
    )
    items = []
    for pid, goals, assists, minutes, matches, avg_rating in rows:
        p = players.get(pid)
        if not p:
            continue
        items.append(
            PlayerRankingItem(
                player_id=pid,
                name=p.name,
                position=p.position,
                goals=int(goals or 0),
                assists=int(assists or 0),
                avg_rating=round(float(avg_rating or 0), 2),
                minutes_played=int(minutes or 0),
                matches_played=int(matches or 0),
            )
        )
    sort_key = {
        "goals": "goals",
        "assists": "assists",
        "rating": "avg_rating",
        "minutes": "minutes_played",
    }.get(sort_by, "goals")
    items.sort(key=lambda x: getattr(x, sort_key), reverse=True)
    return items[:limit]


@router.get("/trend", summary="近期战绩趋势（最近N场胜负走势）")
def match_trend(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    rows = (
        db.execute(select(Match).order_by(Match.match_date.desc()).limit(limit))
        .scalars()
        .all()
    )
    rows = list(reversed(rows))  # 按时间正序展示趋势
    return [
        MatchTrendItem(
            match_id=m.id,
            match_date=m.match_date,
            opponent=m.opponent,
            result=m.result,
            score_our=m.score_our,
            score_opponent=m.score_opponent,
        )
        for m in rows
    ]
