"""Pydantic 数据校验模型"""
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


# ==================== 球员 ====================
class PlayerBase(BaseModel):
    name: str = Field(min_length=1, max_length=64, examples=["张三"])
    position: str = Field(min_length=1, max_length=16, examples=["前锋"])
    height: int = Field(ge=100, le=250, description="身高(cm)")
    join_date: date
    # 扩展字段
    jersey_number: int | None = Field(None, ge=1, le=99, description="球衣号码")
    preferred_foot: str | None = Field(None, description="惯用脚：左/右/双脚")
    primary_position: str | None = Field(None, max_length=20, description="主要位置")
    date_of_birth: date | None = None
    nationality: str | None = Field(None, max_length=50, description="国籍")

    @field_validator("position")
    @classmethod
    def check_position(cls, v: str) -> str:
        allowed = {"前锋", "中场", "后卫"}
        v = v.strip()
        if v not in allowed:
            raise ValueError(f"position 必须是 {allowed} 之一")
        return v

    @field_validator("preferred_foot")
    @classmethod
    def check_foot(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = {"左", "右", "双脚"}
        v = v.strip()
        if v not in allowed:
            raise ValueError(f"preferred_foot 必须是 {allowed} 之一")
        return v


class PlayerCreate(PlayerBase):
    pass


class PlayerUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64)
    position: str | None = Field(None, min_length=1, max_length=16)
    height: int | None = Field(None, ge=100, le=250)
    join_date: date | None = None
    jersey_number: int | None = Field(None, ge=1, le=99)
    preferred_foot: str | None = None
    primary_position: str | None = Field(None, max_length=20)
    date_of_birth: date | None = None
    nationality: str | None = Field(None, max_length=50)

    @field_validator("position")
    @classmethod
    def check_position(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = {"前锋", "中场", "后卫"}
        v = v.strip()
        if v not in allowed:
            raise ValueError(f"position 必须是 {allowed} 之一")
        return v

    @field_validator("preferred_foot")
    @classmethod
    def check_foot(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = {"左", "右", "双脚"}
        v = v.strip()
        if v not in allowed:
            raise ValueError(f"preferred_foot 必须是 {allowed} 之一")
        return v


class PlayerOut(PlayerBase):
    id: int
    updated_at: datetime

    model_config = {"from_attributes": True}


# ==================== 分页 ====================
class Page(BaseModel):
    total: int
    page: int
    size: int
    items: list


class PlayerPage(Page):
    items: list[PlayerOut]


# ==================== 训练记录 ====================
class TrainingRecordCreate(BaseModel):
    player_id: int
    training_date: date
    distance: float = Field(ge=0, description="跑动距离(米)")
    duration: int = Field(ge=0, le=600, description="训练时长(分钟)")


class TrainingRecordUpdate(BaseModel):
    player_id: int | None = None
    training_date: date | None = None
    distance: float | None = Field(None, ge=0)
    duration: int | None = Field(None, ge=0, le=600)


class TrainingRecordOut(TrainingRecordCreate):
    id: int
    model_config = {"from_attributes": True}


class TrainingRecordPage(BaseModel):
    total: int
    page: int
    size: int
    items: list[TrainingRecordOut]


# ==================== 对手 ====================
class OpponentBase(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["阳光少年队"])
    strength_level: str | None = Field(None, description="实力等级：强/中/弱")
    play_style: str | None = Field(None, max_length=50, description="风格：传控/防反/长传等")
    head_to_head_wins: int = Field(0, ge=0)
    head_to_head_draws: int = Field(0, ge=0)
    head_to_head_losses: int = Field(0, ge=0)
    last_meeting: date | None = None
    notes: str | None = None

    @field_validator("strength_level")
    @classmethod
    def check_level(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = {"强", "中", "弱"}
        v = v.strip()
        if v not in allowed:
            raise ValueError(f"strength_level 必须是 {allowed} 之一")
        return v


class OpponentCreate(OpponentBase):
    pass


class OpponentUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    strength_level: str | None = None
    play_style: str | None = Field(None, max_length=50)
    head_to_head_wins: int | None = Field(None, ge=0)
    head_to_head_draws: int | None = Field(None, ge=0)
    head_to_head_losses: int | None = Field(None, ge=0)
    last_meeting: date | None = None
    notes: str | None = None


class OpponentOut(OpponentBase):
    id: int
    model_config = {"from_attributes": True}


class HeadToHeadStat(BaseModel):
    opponent_id: int
    opponent_name: str
    wins: int
    draws: int
    losses: int
    total: int
    last_meeting: date | None
    recent_results: list[str]  # 如 ["3:1 胜", "0:2 负"]


# ==================== 比赛 ====================
class MatchCreate(BaseModel):
    opponent: str = Field(min_length=1, max_length=100, examples=["阳光少年队"])
    match_date: date
    venue: str | None = Field(None, max_length=50, description="主场/客场")
    score_our: int = Field(0, ge=0)
    score_opponent: int = Field(0, ge=0)
    result: str | None = Field(None, description="胜/平/负")
    competition: str | None = Field(None, max_length=50, description="赛事：友谊赛/联赛/杯赛")
    notes: str | None = None

    @field_validator("result")
    @classmethod
    def check_result(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = {"胜", "平", "负"}
        v = v.strip()
        if v not in allowed:
            raise ValueError(f"result 必须是 {allowed} 之一")
        return v


class MatchUpdate(BaseModel):
    opponent: str | None = Field(None, min_length=1, max_length=100)
    match_date: date | None = None
    venue: str | None = None
    score_our: int | None = Field(None, ge=0)
    score_opponent: int | None = Field(None, ge=0)
    result: str | None = None
    competition: str | None = None
    notes: str | None = None

    @field_validator("result")
    @classmethod
    def check_result(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = {"胜", "平", "负"}
        v = v.strip()
        if v not in allowed:
            raise ValueError(f"result 必须是 {allowed} 之一")
        return v


class MatchOut(BaseModel):
    id: int
    opponent: str
    match_date: date
    venue: str | None
    score_our: int
    score_opponent: int
    result: str | None
    competition: str | None
    notes: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


# 球员单场表现
class PerformanceIn(BaseModel):
    """批量录入时单条球员表现"""
    player_id: int
    goals: int = Field(0, ge=0)
    assists: int = Field(0, ge=0)
    minutes_played: int = Field(0, ge=0, le=300)
    rating: float | None = Field(None, ge=0, le=10, description="评分1-10")
    position_played: str | None = Field(None, max_length=20)


class PerformanceBatch(BaseModel):
    """批量录入某场比赛所有球员表现"""
    performances: list[PerformanceIn] = Field(default_factory=list)


class MatchPerformanceOut(BaseModel):
    id: int
    player_id: int
    match_id: int
    goals: int
    assists: int
    minutes_played: int
    rating: float | None
    position_played: str | None
    player_name: str | None = None  # 关联球员姓名（详情接口用）
    model_config = {"from_attributes": True}


class MatchDetail(MatchOut):
    """比赛详情：含该场所有球员表现"""
    performances: list[MatchPerformanceOut] = []


class MatchPage(Page):
    items: list[MatchOut]


# ==================== 赛程 ====================
class ScheduleCreate(BaseModel):
    opponent_id: int
    match_date: datetime
    venue: str | None = Field(None, max_length=50)
    status: str = Field("待赛", description="待赛/已赛/已取消")

    @field_validator("status")
    @classmethod
    def check_status(cls, v: str) -> str:
        allowed = {"待赛", "已赛", "已取消"}
        v = v.strip()
        if v not in allowed:
            raise ValueError(f"status 必须是 {allowed} 之一")
        return v


class ScheduleUpdate(BaseModel):
    opponent_id: int | None = None
    match_date: datetime | None = None
    venue: str | None = Field(None, max_length=50)
    status: str | None = None

    @field_validator("status")
    @classmethod
    def check_status(cls, v: str | None) -> str | None:
        if v is None:
            return None
        allowed = {"待赛", "已赛", "已取消"}
        v = v.strip()
        if v not in allowed:
            raise ValueError(f"status 必须是 {allowed} 之一")
        return v


class ScheduleOut(BaseModel):
    id: int
    opponent_id: int
    match_date: datetime
    venue: str | None
    status: str
    opponent_name: str | None = None
    model_config = {"from_attributes": True}


# ==================== 统计 ====================
class PositionStat(BaseModel):
    position: str
    avg_distance: float
    avg_duration: float
    player_count: int


class TopPlayer(BaseModel):
    player_id: int
    name: str
    position: str
    attendance: int


class TrainingStatistics(BaseModel):
    start: date
    end: date
    total_sessions: int
    position_stats: list[PositionStat]
    top3_attendance: list[TopPlayer]


# 球队整体统计
class TeamStatistics(BaseModel):
    total_matches: int
    wins: int
    draws: int
    losses: int
    win_rate: float
    total_goals: int
    total_conceded: int
    avg_goals: float
    avg_conceded: float


# 球员排行榜
class PlayerRankingItem(BaseModel):
    player_id: int
    name: str
    position: str
    goals: int
    assists: int
    avg_rating: float
    minutes_played: int
    matches_played: int


# 战绩趋势
class MatchTrendItem(BaseModel):
    match_id: int
    match_date: date
    opponent: str
    result: str | None
    score_our: int
    score_opponent: int


# 球员历史比赛汇总
class PlayerMatchHistory(BaseModel):
    player_id: int
    name: str
    matches_played: int
    total_goals: int
    total_assists: int
    total_minutes: int
    avg_rating: float
    avg_goals: float
    recent_ratings: list[float]  # 近期评分趋势


# ==================== 导出任务 ====================
class ExportTaskCreate(BaseModel):
    start: date | None = None
    end: date | None = None
    report_type: str = Field("training", description="training/match")


class ExportTaskOut(BaseModel):
    task_id: str
    status: str
    created_at: datetime


class ExportTaskResult(BaseModel):
    task_id: str
    status: str
    file_path: str | None = None
    error: str | None = None
    created_at: datetime
