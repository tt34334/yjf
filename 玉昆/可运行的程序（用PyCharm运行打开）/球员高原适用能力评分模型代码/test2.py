import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# 项目根目录（本文件位于：项目根目录/可运行的程序（用PyCharm运行打开）/球员高原适用能力评分模型代码/本文件）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# 图表输出目录
CHART_DIR = PROJECT_ROOT / "outputs" / "图表"
CHART_DIR.mkdir(parents=True, exist_ok=True)

# 设置 Matplotlib 支持中文
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'WenQuanYi Zen Hei']
plt.rcParams['axes.unicode_minus'] = False  # 正确显示负号



# 读取数据（数据集自带的天气+球员总数据）
# 数据包含列：'球员', '主客场', '评分' 等
data = pd.read_csv(PROJECT_ROOT / "数据集" / "合并数据" / "天气球员总数据+血氧、气压.csv")

# 检查数据
print("原始数据：")
print(data.head())

# 计算高原适应系数
# 首先，将数据按球员和主客场分组，计算每个球员的主场和客场评分
grouped = data.groupby(['球员', '主客场'])['评分'].mean().unstack()

# 显式按列名取出主、客场平均评分（避免依赖列的排列顺序）
result = pd.DataFrame({
    '球员': grouped.index,
    '主场评分': grouped['主场'].values,
    '客场评分': grouped['客场'].values
})

# 计算高原适应系数：主场相对客场评分的提升比例
result['高原适应系数'] = (result['主场评分'] - result['客场评分']) / result['客场评分']

# 选择需要展示的列
result = result[['球员', '高原适应系数']]

# 打印结果
print("\n计算结果：")
print(result)

# 可视化
plt.figure(figsize=(10, 6))
plt.bar(result['球员'], result['高原适应系数'], color='skyblue')
plt.xlabel('球员')
plt.ylabel('高原适应系数')
plt.title('球员高原适应系数')
plt.xticks(rotation=45, ha='right')  # 旋转x轴标签以便更清晰显示
plt.tight_layout()  # 自动调整子图参数，以确保子图之间有足够空间
# 保存图形到 outputs/图表 目录
plt.savefig(CHART_DIR / '球员高原适应系数.png', bbox_inches='tight', dpi=300)
plt.show()