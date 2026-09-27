import pandas as pd
from pathlib import Path

# 项目根目录（本文件位于：项目根目录/可运行的程序（用PyCharm运行打开）/数据预处理代码/本文件）
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 读取 concat3.py 生成的天气与球员比赛合并数据
file1 = PROJECT_ROOT / "outputs" / "预处理中间表" / "合并数据.csv"
df1 = pd.read_csv(file1)

# 移除温度中的 "℃" 并转换为数值
df1['最高气温'] = df1['最高气温'].str.replace('℃', '', regex=False).astype(float)
df1['最低气温'] = df1['最低气温'].str.replace('℃', '', regex=False).astype(float)

# 移除湿度中的 "%" 并转换为数值
df1['湿度'] = df1['湿度'].str.replace('%', '', regex=False).astype(float)

# 计算平均气温
df1['平均气温'] = (df1['最高气温'] + df1['最低气温']) / 2

# 计算海拔压力系数，并保留两位小数
df1['海拔系数'] = (df1['海拔(m)'] / 1000).round(4)

# 计算气候压力指数
df1['气候压力指数'] = ((df1['平均气温'] * df1['湿度']) / 1000 * df1['海拔系数'])

# 计算血氧值
df1['血氧值'] = (95 - (df1['海拔(m)'] / 1000) * 5 - df1['跑动(km)'] * 0.3).round(2)

# 删除不需要的列
df1 = df1.drop(columns=['海拔系数', '平均气温'])

# 将温度和湿度转换回原始格式
df1['最高气温'] = df1['最高气温'].astype(str) + '℃'
df1['最低气温'] = df1['最低气温'].astype(str) + '℃'
df1['湿度'] = df1['湿度'].astype(str) + '%'

# 保存最终的特征数据（与数据集中自带的“天气球员总数据+血氧、气压.csv”结构一致）
output_file = PROJECT_ROOT / "outputs" / "天气球员总数据+血氧、气压.csv"
output_file.parent.mkdir(parents=True, exist_ok=True)
df1.to_csv(output_file, index=False, encoding='utf-8-sig')
print(f"合并后的数据已保存到 {output_file}")
