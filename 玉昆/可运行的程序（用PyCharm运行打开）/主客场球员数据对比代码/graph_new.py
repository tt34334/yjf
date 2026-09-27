import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

# 项目根目录（本文件位于：项目根目录/可运行的程序（用PyCharm运行打开）/主客场球员数据对比代码/本文件）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# 图表输出目录
CHART_DIR = PROJECT_ROOT / "outputs" / "图表"
CHART_DIR.mkdir(parents=True, exist_ok=True)

# 用于正常显示中文
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'WenQuanYi Zen Hei']
# 用于正常显示符号
plt.rcParams['axes.unicode_minus'] = False

# 读取 CSV 文件（数据集自带的天气+球员总数据）
df = pd.read_csv(PROJECT_ROOT / "数据集" / "合并数据" / "天气球员总数据+血氧、气压.csv")

# 特征列的原始名称
original_feature = ['跑动(km)', '传球成功率', '抢断', '射门', '射正']

# 特征列的新名称
new_feature = ['跑动距离 (km)', '传球成功率 (%)', '抢断次数', '射门次数', '射正次数']

# 数据清洗：确保所有特征列都是数值类型
# 如果某些列包含百分比符号（%），需要先将其转换为数值
for col in original_feature:
    if not pd.api.types.is_numeric_dtype(df[col]):  # 非数值类型（字符串）需要清洗
        if df[col].astype(str).str.contains('%').any():  # 检查是否包含百分比符号
            df[col] = df[col].astype(str).str.replace('%', '', regex=False).astype(float) / 100  # 去掉百分比符号并转换为数值
        else:
            df[col] = df[col].astype(float)  # 直接转换为数值类型

# 重命名特征列
df.rename(columns=dict(zip(original_feature, new_feature)), inplace=True)

# 筛选特定球员的数据
player_name = '模拟球员9'# 指定球员名称
home_away = ['主场', '客场']  # 指定主场和客场

# 初始化存储均值的列表
player_means = []

# 分别计算主场和客场的均值
for ha in home_away:
    filtered_df = df[(df['球员'] == player_name) & (df['主客场'] == ha)]
    player_means.append(filtered_df[new_feature].mean().values)

# 设置每个数据点的显示位置，在雷达图上用角度表示
angles = np.linspace(0, 2 * np.pi, len(new_feature), endpoint=False)
angles_concatenated = np.append(angles, angles[0])  # 拼接后的角度，用于绘图

# 绘图
fig = plt.figure(figsize=(8, 8))  # 设置图形大小
ax = fig.add_subplot(111, polar=True)  # 创建极坐标子图

# 定义颜色
colors = ['b', 'r']  # 蓝色代表主场，红色代表客场

# 修改图例标签以更符合实际需求
labels = ['主场表现', '客场表现']

# 绘制主场和客场的雷达图
for values, color, label in zip(player_means, colors, labels):
    values_concatenated = np.append(values, values[0])  # 拼接后的数据，用于绘图
    ax.plot(angles_concatenated, values_concatenated, 'o-', linewidth=2, color=color, label=label)
    ax.fill(angles_concatenated, values_concatenated, alpha=0.25, color=color)

# 设置图标上的角度划分刻度，为每个数据点处添加标签
ax.set_thetagrids(angles * 180 / np.pi, new_feature)  # 使用新特征名称作为雷达图的轴标签

# 设置雷达图的范围
# 根据数据动态设置范围
min_value = df[new_feature].min().min()  # 所有特征列的最小值
max_value = df[new_feature].max().max()  # 所有特征列的最大值
ax.set_ylim(min_value - 1, max_value + 1)  # 留出一些空间

# 添加标题
plt.title(f'{player_name}在主场和客场多维适应能力')

# 添加网格线
ax.grid(True)

# 添加图例
ax.legend(loc='upper right', bbox_to_anchor=(1.2, 1.05))  # 调整图例位置

# 保存图形到 outputs/图表 目录
plt.savefig(CHART_DIR / f'{player_name}_主客场多维适应能力雷达图.png',
            bbox_inches='tight', dpi=300)
plt.show()