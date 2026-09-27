import pandas as pd
import os
from pathlib import Path

# 项目根目录（本文件位于：项目根目录/可运行的程序（用PyCharm运行打开）/数据预处理代码/本文件）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# 天气爬虫抓取的原始城市天气数据目录
RAW_WEATHER_DIR = PROJECT_ROOT / "数据集" / "气候数据" / "城市数据"
# 分城市合并结果的输出目录（中间表）
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "预处理中间表" / "分城市合并"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# 定义一个函数来读取并合并指定的文件，并添加“比赛城市”列
def merge_csv_files(file_paths, city_name, output_path):
    # 读取每个 CSV 文件为一个 DataFrame，并添加“比赛城市”列
    dataframes = []
    for file_path in file_paths:
        df = pd.read_csv(file_path)
        df['比赛城市'] = city_name  # 添加“比赛城市”列
        dataframes.append(df)

    # 使用 pandas.concat() 按行合并 DataFrame
    merged_df = pd.concat(dataframes, ignore_index=True)

    # 保存合并后的数据到新的 CSV 文件
    os.makedirs(os.path.dirname(output_path), exist_ok=True)  # 确保目标文件夹存在
    merged_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"{city_name}：合并 {len(file_paths)} 个文件，共 {len(merged_df)} 条数据，已保存到 {output_path}")


# 自动发现原始天气文件，文件名格式为“城市名_YYYYMM天气数据.csv”，按城市分组
raw_files = sorted(RAW_WEATHER_DIR.glob("*天气数据.csv"))
if not raw_files:
    raise FileNotFoundError(
        f"未在 {RAW_WEATHER_DIR} 下找到任何天气数据文件，请先运行 天气挖掘代码/finddata.py"
    )

cities_data = {}
for file_path in raw_files:
    city_name = file_path.name.split('_')[0]  # 文件名中“_”前的部分为城市名
    cities_data.setdefault(city_name, []).append(file_path)

# 合并每个城市的天气数据（同一城市的多个月份），并添加“比赛城市”列
for city, files in sorted(cities_data.items()):
    output_file = OUTPUT_DIR / f'{city}_data.csv'
    merge_csv_files([str(f) for f in sorted(files)], city, str(output_file))
