"""种子数据：球员/训练/对手/比赛/球员表现/赛程"""
from datetime import date, datetime, timedelta
import random

from sqlalchemy import inspect

from app.database import Base, SessionLocal, engine
from app.models import Match, MatchPerformance, Opponent, Player, Schedule, TrainingRecord

POSITIONS = ["前锋", "中场", "后卫"]
FOOTS = ["左", "右", "双脚"]
NAMES = [
    "李志强", "王浩然", "张俊杰", "陈思远", "刘子轩", "黄铭阳", "周文博",
    "吴俊熙", "徐梓豪", "孙宇辰", "马天佑", "朱泽宇", "胡子睿", "林嘉俊",
    "郭骏杰", "何明轩", "高思聪", "罗梓晨", "梁宇宁", "宋昊然",
]
OPPONENTS_DATA = [
    ("阳光少年队", "中", "传控", "强队，擅长地面配合与中场控制"),
    ("海豹青训", "强", "防反", "防守稳固，反击速度极快"),
    ("星辰体育", "弱", "长传", "身体对抗强，长传冲吊为主"),
    ("雄鹰梯队", "中", "传控", "技术细腻，整体配合默契"),
    ("未来之星", "弱", "防反", "年轻队伍，速度较快但经验不足"),
]
COMPETITIONS = ["友谊赛", "联赛", "杯赛"]


def _need_rebuild() -> bool:
    """检测旧 schema（players 表缺新字段），需重建以加载扩展列"""
    insp = inspect(engine)
    if insp.has_table("players"):
        cols = [c["name"] for c in insp.get_columns("players")]
        if "jersey_number" not in cols:
            return True
    return False


def seed():
    if _need_rebuild():
        print("检测到旧 schema（players 缺扩展字段），重建数据库以加载新表结构...")
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # ---------- 球员 ----------
        if db.query(Player).count() > 0:
            print("球员数据已存在，跳过球员插入。")
        else:
            players = []
            for i, name in enumerate(NAMES):
                p = Player(
                    name=name,
                    position=POSITIONS[i % 3],
                    height=random.randint(165, 188),
                    join_date=date(2024, 1, 1) + timedelta(days=i * 5),
                    jersey_number=i + 1,
                    preferred_foot=random.choice(FOOTS),
                    primary_position=POSITIONS[i % 3],
                    nationality="中国",
                    date_of_birth=date(2010, 3, 1) + timedelta(days=i * 7),
                )
                players.append(p)
            db.add_all(players)
            db.commit()
            for p in players:
                db.refresh(p)
            # 训练记录（2026-08 月）
            records = []
            start = date(2026, 8, 1)
            for p in players:
                days = random.sample(range(31), random.randint(6, 18))
                for d in days:
                    records.append(TrainingRecord(
                        player_id=p.id,
                        training_date=start + timedelta(days=d),
                        distance=round(random.uniform(3500, 11000), 2),
                        duration=random.randint(45, 120),
                    ))
            db.add_all(records)
            db.commit()
            print(f"已插入 {len(players)} 名球员（含扩展字段），{len(records)} 条训练记录。")

        # ---------- 对手 ----------
        if db.query(Opponent).count() == 0:
            opps = [
                Opponent(name=n, strength_level=l, play_style=s, notes=note)
                for n, l, s, note in OPPONENTS_DATA
            ]
            db.add_all(opps)
            db.commit()
            for o in opps:
                db.refresh(o)
            print(f"已插入 {len(opps)} 个对手。")
        else:
            opps = db.query(Opponent).all()
            print(f"对手数据已存在（{len(opps)} 个），跳过。")

        # ---------- 比赛 + 球员表现 ----------
        if db.query(Match).count() == 0:
            opp_names = [o.name for o in opps]
            matches_data = []
            # 8 场过去比赛（有结果）
            past = [
                ("胜", 3, 1), ("胜", 2, 0), ("平", 1, 1), ("胜", 4, 2),
                ("负", 0, 2), ("胜", 3, 2), ("平", 2, 2), ("胜", 2, 1),
            ]
            for i, (res, so, sp) in enumerate(past):
                matches_data.append(Match(
                    opponent=random.choice(opp_names),
                    match_date=date(2026, 5, 10) + timedelta(days=i * 12),
                    venue=random.choice(["主场", "客场"]),
                    score_our=so, score_opponent=sp,
                    result=res, competition=random.choice(COMPETITIONS),
                ))
            # 2 场未来比赛（未赛）
            for i in range(2):
                matches_data.append(Match(
                    opponent=random.choice(opp_names),
                    match_date=date(2026, 9, 15) + timedelta(days=i * 21),
                    venue=random.choice(["主场", "客场"]),
                    score_our=0, score_opponent=0,
                    result=None, competition=random.choice(COMPETITIONS),
                ))
            db.add_all(matches_data)
            db.commit()
            for m in matches_data:
                db.refresh(m)
            print(f"已插入 {len(matches_data)} 场比赛（8 场已赛 + 2 场待赛）。")

            # 球员表现（仅已赛比赛）
            players = db.query(Player).all()
            perfs = []
            for m in matches_data:
                if m.result is None:
                    continue
                squad = random.sample(players, min(11, len(players)))
                for p in squad:
                    perfs.append(MatchPerformance(
                        player_id=p.id, match_id=m.id,
                        goals=random.choices([0, 1, 2, 3], weights=[70, 20, 8, 2])[0],
                        assists=random.choices([0, 1, 2], weights=[75, 20, 5])[0],
                        minutes_played=random.randint(30, 90),
                        rating=round(random.uniform(5.5, 9.5), 1),
                        position_played=p.position,
                    ))
            db.add_all(perfs)
            db.commit()
            print(f"已插入 {len(perfs)} 条球员比赛表现。")
        else:
            print(f"比赛数据已存在（{db.query(Match).count()} 场），跳过。")

        # ---------- 赛程 ----------
        if db.query(Schedule).count() == 0 and opps:
            scheds = []
            for i in range(3):
                scheds.append(Schedule(
                    opponent_id=opps[i % len(opps)].id,
                    match_date=datetime(2026, 9, 15, 10, 0) + timedelta(days=i * 14),
                    venue=random.choice(["主场", "客场"]),
                    status="待赛",
                ))
            db.add_all(scheds)
            db.commit()
            print(f"已插入 {len(scheds)} 条赛程安排。")
        else:
            print(f"赛程数据已存在（{db.query(Schedule).count()} 条），跳过。")

        print("种子数据注入完成！")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
