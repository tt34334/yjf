"""ORM 模型：players / training_records / matches / match_performances / opponents / schedules"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), comment="球员姓名")
    position: Mapped[str] = mapped_column(String(16), comment="位置：前锋/中场/后卫")
    height: Mapped[int] = mapped_column(comment="身高(cm)")
    join_date: Mapped[date] = mapped_column(comment="入队日期")
    # 扩展字段（青训球员档案）
    jersey_number: Mapped[int | None] = mapped_column(comment="球衣号码", nullable=True)
    preferred_foot: Mapped[str | None] = mapped_column(String(10), comment="惯用脚：左/右/双脚", nullable=True)
    primary_position: Mapped[str | None] = mapped_column(String(20), comment="主要位置", nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(comment="出生日期", nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(50), comment="国籍", nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    training_records: Mapped[list["TrainingRecord"]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )
    match_performances: Mapped[list["MatchPerformance"]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_players_position", "position"),)


class TrainingRecord(Base):
    __tablename__ = "training_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), comment="球员ID")
    training_date: Mapped[date] = mapped_column(comment="训练日期")
    distance: Mapped[float] = mapped_column(comment="跑动距离(米)")
    duration: Mapped[int] = mapped_column(comment="训练时长(分钟)")

    player: Mapped["Player"] = relationship(back_populates="training_records")

    __table_args__ = (
        Index("idx_training_player_date", "player_id", "training_date"),
        Index("idx_training_date", "training_date"),
    )


class Opponent(Base):
    """对手球队库：记录实力等级、风格特点、历史交锋战绩"""
    __tablename__ = "opponents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), comment="球队名称")
    strength_level: Mapped[str | None] = mapped_column(String(20), comment="实力等级：强/中/弱", nullable=True)
    play_style: Mapped[str | None] = mapped_column(String(50), comment="风格特点：传控/防反/长传等", nullable=True)
    head_to_head_wins: Mapped[int] = mapped_column(default=0, comment="历史交锋胜场")
    head_to_head_draws: Mapped[int] = mapped_column(default=0, comment="历史交锋平场")
    head_to_head_losses: Mapped[int] = mapped_column(default=0, comment="历史交锋负场")
    last_meeting: Mapped[date | None] = mapped_column(comment="上次交锋日期", nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, comment="备注", nullable=True)

    schedules: Mapped[list["Schedule"]] = relationship(back_populates="opponent")

    __table_args__ = (Index("idx_opponents_name", "name"),)


class Match(Base):
    """比赛记录：对手、比分、结果、赛事"""
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    opponent: Mapped[str] = mapped_column(String(100), comment="对手球队名称")
    match_date: Mapped[date] = mapped_column(comment="比赛日期")
    venue: Mapped[str | None] = mapped_column(String(50), comment="主场/客场", nullable=True)
    score_our: Mapped[int] = mapped_column(default=0, comment="我方进球数")
    score_opponent: Mapped[int] = mapped_column(default=0, comment="对方进球数")
    result: Mapped[str | None] = mapped_column(String(10), comment="胜/平/负", nullable=True)
    competition: Mapped[str | None] = mapped_column(String(50), comment="赛事名称：友谊赛/联赛/杯赛", nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, comment="比赛备注", nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    performances: Mapped[list["MatchPerformance"]] = relationship(
        back_populates="match", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_matches_date", "match_date"),
        Index("idx_matches_opponent", "opponent"),
    )


class MatchPerformance(Base):
    """球员单场比赛表现：进球、助攻、出场时间、评分"""
    __tablename__ = "match_performances"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), comment="球员ID")
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), comment="比赛ID")
    goals: Mapped[int] = mapped_column(default=0, comment="进球数")
    assists: Mapped[int] = mapped_column(default=0, comment="助攻数")
    minutes_played: Mapped[int] = mapped_column(default=0, comment="出场分钟数")
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), comment="评分1-10", nullable=True)
    position_played: Mapped[str | None] = mapped_column(String(20), comment="本场位置", nullable=True)

    player: Mapped["Player"] = relationship(back_populates="match_performances")
    match: Mapped["Match"] = relationship(back_populates="performances")

    __table_args__ = (
        Index("idx_perf_player", "player_id"),
        Index("idx_perf_match", "match_id"),
    )


class Schedule(Base):
    """赛程安排：未来比赛计划"""
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    opponent_id: Mapped[int] = mapped_column(ForeignKey("opponents.id", ondelete="CASCADE"), comment="对手ID")
    match_date: Mapped[datetime] = mapped_column(comment="比赛时间")
    venue: Mapped[str | None] = mapped_column(String(50), comment="主场/客场", nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="待赛", comment="待赛/已赛/已取消")

    opponent: Mapped["Opponent"] = relationship(back_populates="schedules")

    __table_args__ = (Index("idx_schedules_date", "match_date"),)
