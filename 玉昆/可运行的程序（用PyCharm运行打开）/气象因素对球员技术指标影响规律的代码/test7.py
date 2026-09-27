import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.ticker as ticker
import numpy as np
from pathlib import Path

# 项目根目录（本文件位于：项目根目录/可运行的程序（用PyCharm运行打开）/气象因素对球员技术指标影响规律的代码/本文件）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# 图表输出目录
CHART_DIR = PROJECT_ROOT / "outputs" / "图表"
CHART_DIR.mkdir(parents=True, exist_ok=True)

# 设置图片清晰度
plt.rcParams['figure.dpi'] = 300
# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'WenQuanYi Zen Hei']
# 解决负号显示问题
plt.rcParams['axes.unicode_minus'] = False

# 加载数据（数据集自带的天气+球员总数据）
data = pd.read_csv(PROJECT_ROOT / "数据集" / "合并数据" / "天气球员总数据+血氧、气压.csv")

# 预处理数据
data['最高气温'] = data['最高气温'].str.extract(r'(\d+)').astype(int)
data['最低气温'] = data['最低气温'].str.extract(r'(\d+)').astype(int)
data['湿度'] = data['湿度'].str.rstrip('%').astype(float)
data['传球成功率'] = data['传球成功率'].str.rstrip('%').astype(float)

# 处理射门列中的0值，这里选择将0值替换为极小值
data['射门'] = np.where(data['射门'] == 0, 1e-10, data['射门'])

# 计算射正率
data['射正率'] = data['射正'] / data['射门']

# 计算平均温度
data['平均温度'] = (data['最高气温'] + data['最低气温']) / 2

# 对温度进行分箱
data['温度区间'] = pd.cut(data['平均温度'], bins=5)

# 计算每个温度区间内的平均传球成功率
grouped_temp = data.groupby('温度区间', observed=True)['传球成功率'].mean().reset_index()

# 提取每个温度区间的边界值作为横坐标标签，并确保区间显示完整
x_labels = []
for interval in grouped_temp['温度区间']:
    left = f"{interval.left:.1f}"
    right = f"{interval.right:.1f}"
    label = f"[{left}, {right}]"
    x_labels.append(label)

# 对湿度进行分箱
data['湿度区间'] = pd.cut(data['湿度'], bins=5)

# 计算每个湿度区间内的平均射正数
grouped_shots_on_target = data.groupby('湿度区间', observed=True)['射正'].mean().reset_index()

# 绘制温度与传球成功率的折线图
plt.figure(figsize=(20, 4))
plt.plot(grouped_temp['温度区间'].astype(str), grouped_temp['传球成功率'], marker='o')
plt.xlabel('温度区间')
plt.ylabel('平均传球成功率')
plt.title('温度与传球成功率关系图')

# 手动设置刻度位置和标签
ax = plt.gca()
ax.xaxis.set_major_locator(ticker.FixedLocator(range(len(grouped_temp))))
ax.xaxis.set_major_formatter(ticker.FixedFormatter(x_labels))

# 调整刻度标签旋转角度和对齐方式
plt.xticks(rotation=0, ha='center', rotation_mode='anchor')
# 进一步调整子图布局，让图形底部留出更多空间
plt.subplots_adjust(bottom=0.16)

# 添加数据标签
for x, y in zip(range(len(grouped_temp)), grouped_temp['传球成功率']):
    plt.annotate(f'{y:.2f}', (x, y), textcoords='offset points', xytext=(0, 7), ha='center')

# 保存图形到 outputs/图表 目录
plt.savefig(CHART_DIR / '温度与传球成功率关系图.png', bbox_inches='tight')
plt.show()

# 把湿度区间转换为字符串类型
grouped_shots_on_target['湿度区间'] = grouped_shots_on_target['湿度区间'].astype(str)

# 绘制不同湿度下平均射正数的散点图
plt.figure(figsize=(15, 10))
sns.scatterplot(x='湿度区间', y='射正', data=grouped_shots_on_target)
plt.xlabel('湿度区间')
plt.xticks(rotation=30, ha='right', fontsize=5)
plt.ylabel('平均射正数')
plt.title('湿度与平均射正数关系图')

# 添加数据标签，保留一位小数（可根据需求调整）
for i, row in grouped_shots_on_target.iterrows():
    value = round(row["射正"], 1)
    plt.annotate(f'{value}', (i, row['射正']), textcoords='offset points', xytext=(0, 8), ha='center')

# 调整图形布局
plt.subplots_adjust(bottom=0.25, left=0.1, right=0.95)

# 保存图形到 outputs/图表 目录
plt.savefig(CHART_DIR / '湿度与平均射正数关系图.png', bbox_inches='tight')
plt.show()