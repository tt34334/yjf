import os
import time
import random
from pathlib import Path
import requests
import pandas as pd
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 项目根目录（本文件位于：项目根目录/可运行的程序（用PyCharm运行打开）/球员数据代码/本文件）
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ================== 配置区 ==================
TEAM_ID = "50117905"
SEASON = "2024"
PROXY = None
# 生成的球员数据保存到项目 outputs 目录（数据集目录中自带一份已生成好的样例数据）
OUTPUT_PATH = str(PROJECT_ROOT / "outputs" / "玉昆队_大数据.csv")
REQUEST_DELAY = (1, 3)
MAX_RETRIES = 3

# 数据生成参数
SIM_MATCHES = 30  # 模拟比赛场次
PLAYERS_PER_MATCH = 11  # 每场球员数

# 扩展版城市海拔数据库
CITY_ALTITUDE = {
    "玉溪": 1650,
    "北京": 43.5, "上海": 4.0, "广州": 11.0,
    "成都": 500, "济南": 58, "青岛": 76.6,
    "武汉": 23.3, "南京": 20, "大连": 93,
    "长春": 236, "深圳": 76, "天津": 5,
    "重庆": 237, "苏州": 5, "郑州": 110,
    "西安": 400, "长沙": 45, "贵阳": 1071,
    "石家庄": 83, "哈尔滨": 150
}

# ================== 请求会话配置 ==================
session = requests.Session()
retry_strategy = Retry(
    total=MAX_RETRIES,
    status_forcelist=[500, 502, 503, 504, 429],
    allowed_methods=["GET"]
)
session.mount('https://', HTTPAdapter(max_retries=retry_strategy))


# ================== 新增缺失函数 ==================
def get_real_matches():
    """获取实时比赛数据"""
    print("\n[获取实时数据]")
    url = "https://www.dongqiudi.com/team/50117905.html"

    try:
        response = session.get(
            url,
            headers={
                'User-Agent': random.choice([
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0'
                ])
            },
            timeout=15
        )
        response.raise_for_status()

        data = response.json()
        matches = [m for m in data.get('data', [])
                   if str(m.get('season')) == SEASON]
        print(f"获取到{len(matches)}场实时比赛")
        return matches

    except Exception as e:
        print(f"实时数据获取失败: {str(e)}")
        return []


def get_player_stats(match_id):
    """获取比赛球员数据"""
    url = f"https://api.dongqiudi.com/matches/{match_id}/stats.json"

    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        return response.json().get('data')
    except Exception as e:
        print(f"获取比赛{match_id}数据失败: {str(e)}")
        return None



# ================== 增强版数据处理 ==================
def process_data(real_matches):
    """混合处理实时与模拟数据"""
    all_data = []

    # 处理实时比赛 (添加异常处理)
    if real_matches:
        print("\n[处理实时比赛]")
        for match in real_matches:
            try:
                if stats := get_player_stats(match.get('id')):
                    is_home = str(match.get('home_team', {}).get('id')) == TEAM_ID
                    city = "玉溪" if is_home else random.choice([c for c in CITY_ALTITUDE if c != "玉溪"])

                    # 确保获取到球员列表
                    players = stats.get('home' if is_home else 'away', {}).get('players', [])
                    if not players:
                        print(f"比赛{match.get('id')}无球员数据")
                        continue

                    for player in players[:PLAYERS_PER_MATCH]:
                        try:
                            # 统一日期字段处理
                            match_date = datetime.strptime(
                                match.get('start_time', '2024-01-01 00:00:00'),  # 默认值
                                "%Y-%m-%d %H:%M:%S"
                            ).strftime("%Y/%m/%d")

                            all_data.append({
                                "比赛ID": match['id'],
                                "日期": match_date,
                                "主客场": "主场" if is_home else "客场",
                                "比赛城市": city,
                                "球员": player.get('name', '未知球员'),
                                "位置": player.get('position', '未知位置'),
                                "跑动(km)": round(player.get('running_distance', 0) / 1000, 1),
                                "射门": player.get('shots', 0),
                                "射正": player.get('shots_on_target', 0),
                                "传球成功率": f"{player.get('pass_success_rate', 0)}%",
                                "抢断": player.get('tackles', 0),
                                "评分": player.get('rating', 6.0),
                                "海拔(m)": CITY_ALTITUDE.get(city, 100),  # 默认海拔
                                "血氧模拟值": max(80, 95 - (player.get('running_distance', 0) / 1000 * 2))
                            })
                        except Exception as e:
                            print(f"处理球员数据出错: {str(e)}")
                            continue
            except Exception as e:
                print(f"处理比赛数据出错: {str(e)}")
                continue

    # 补充模拟数据 (确保字段存在)
    print(f"\n[生成模拟数据] 补充{SIM_MATCHES}场比赛")
    base_date = datetime(2024, 3, 1)
    for i in range(SIM_MATCHES):
        match_date = (base_date + timedelta(days=3 * i)).strftime("%Y/%m/%d")
        is_home = i % 2 == 0
        city = "玉溪" if is_home else random.choice([c for c in CITY_ALTITUDE if c != "玉溪"])

        for player_num in range(1, PLAYERS_PER_MATCH +1):
            all_data.append({
                "比赛ID": f"SIM_{i + 1}",
                "日期": match_date,
                "主客场": "主场" if is_home else "客场",
                "比赛城市": city,
                "球员": f"模拟球员{player_num}",
                "位置": random.choice(["前锋", "中场", "后卫", "门将"]),
                "跑动(km)": round(random.uniform(8.5, 12.5), 1),
                "射门": random.randint(0, 5),
                "射正": random.randint(0, 3),
                "传球成功率": f"{random.randint(65, 90)}%",
                "抢断": random.randint(0, 6),
                "评分": round(random.uniform(6.0, 8.9), 1),
                "海拔(m)": CITY_ALTITUDE.get(city, 100),

            })

    # 转换为DataFrame并验证
    df = pd.DataFrame(all_data)

    # 确保日期列存在
    if '日期' not in df.columns:
        df['日期'] = pd.to_datetime('2024-01-01')  # 创建默认列
        print("警告: 自动创建默认日期列")

    # 统一日期格式
    try:
        df['日期'] = pd.to_datetime(df['日期'])
    except:
        df['日期'] = pd.to_datetime('2024-01-01')

    return df


# ================== 主程序 ==================
if __name__ == "__main__":
    # 获取实时数据
    real_matches = get_real_matches()

    # 处理数据
    start_time = time.time()
    df = process_data(real_matches)

    # 数据验证
    print("\n[数据验证]")
    print("有效列:", df.columns.tolist())
    print("样本数据:")
    print(df.head(2))

    # 保存数据
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False, encoding='utf_8_sig')

    # 统计信息
    try:
        print(f"\n生成数据统计:")
        print(f"- 总数据条数: {len(df):,}")
        print(f"- 时间范围: {df['日期'].min().date()} 至 {df['日期'].max().date()}")
        print(f"- 包含比赛: {df['比赛ID'].nunique()} 场")
        print(f"- 球员数量: {df['球员'].nunique()} 人")
    except Exception as e:
        print(f"统计信息获取失败: {str(e)}")

    print(f"\n文件已保存至: {OUTPUT_PATH}")
    print(f"总耗时: {time.time() - start_time:.2f}秒")