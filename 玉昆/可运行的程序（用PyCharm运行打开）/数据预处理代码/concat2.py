import pandas as pd
from pathlib import Path

# 项目根目录（本文件位于：项目根目录/可运行的程序（用PyCharm运行打开）/数据预处理代码/本文件）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# concat1.py 生成的分城市合并表所在目录
INTERIM_DIR = PROJECT_ROOT / "outputs" / "预处理中间表" / "分城市合并"
# 所有城市天气数据总表的输出路径
OUTPUT_FILE = PROJECT_ROOT / "outputs" / "预处理中间表" / "城市天气总表_data.csv"

# 读取目录下所有城市的合并表（文件名格式：城市名_data.csv）
city_files = sorted(INTERIM_DIR.glob("*_data.csv"))
if not city_files:
    raise FileNotFoundError(
        f"未在 {INTERIM_DIR} 下找到分城市合并表，请先运行 concat1.py"
    )

df_list = [pd.read_csv(f) for f in city_files]
print(f"共读取 {len(df_list)} 个城市的天气数据：{[f.stem for f in city_files]}")

# 使用 pandas.concat() 按行合并所有城市的 DataFrame
merged_df = pd.concat(df_list, ignore_index=True)

# 查看合并后的 DataFrame
print("合并后的数据：")
print(merged_df.head())

# 保存合并后的数据到新的 CSV 文件
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
merged_df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
print(f"合并后的数据已保存到 {OUTPUT_FILE}")
