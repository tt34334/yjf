import pandas as pd
from pathlib import Path

# 项目根目录（本文件位于：项目根目录/可运行的程序（用PyCharm运行打开）/数据预处理代码/本文件）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "数据集"

# 读取两个 CSV 文件为 DataFrame
# 1）所有城市天气数据总表（数据集自带完整版；concat2.py 重新生成的版本位于 outputs 目录）
file1 = DATA_DIR / "气候数据" / "城市天气总表_data.csv"
# 2）玉昆队球员模拟数据与比赛海拔数据
file2 = DATA_DIR / "玉昆队球员模拟数据与比赛海拔数据" / "玉昆队_大数据.csv"

df1 = pd.read_csv(file1)
df2 = pd.read_csv(file2)

# 对“比赛城市”进行排序
merged_df = df2.sort_values(by='比赛城市')

# 根据“比赛城市”和“日期”进行右连接（保留全部球员比赛记录，匹配对应城市当日天气）
merged_df = pd.merge(df1, df2, on=['比赛城市', '日期'], how='right')

merged_df = merged_df.sort_values(by=['比赛城市', '日期'])

# 查看合并后的 DataFrame
print("合并后的数据：")
print(merged_df.head())

# 保存合并后的数据到新的 CSV 文件
output_file = PROJECT_ROOT / "outputs" / "预处理中间表" / "合并数据.csv"
output_file.parent.mkdir(parents=True, exist_ok=True)
merged_df.to_csv(output_file, index=False, encoding='utf-8-sig')
print(f"合并后的数据已保存到 {output_file}")
