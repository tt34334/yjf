import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.ticker import MaxNLocator
from pathlib import Path

# 项目根目录（本文件位于：项目根目录/可运行的程序（用PyCharm运行打开）/不同海拔梯度下的球员技术指标代码/本文件）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# 图表输出目录
CHART_DIR = PROJECT_ROOT / "outputs" / "图表"
CHART_DIR.mkdir(parents=True, exist_ok=True)

# 设置中文字体（Windows系统使用SimHei，macOS可使用Arial Unicode MS，Linux系统可使用WenQuanYi Zen Hei等）
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'WenQuanYi Zen Hei']
# 解决负号显示问题
plt.rcParams['axes.unicode_minus'] = False

# 替换为前面计算不同海拔各指标平均值时的数据
data = {
    "海拔(m)": [4.0, 5.0, 11.0, 20.0, 23.3, 45.0, 76.0, 76.6, 100.0, 236.0, 500.0, 1071.0, 1650.0],
    "跑动(km)": [10.306522, 10.847826, 9.895652, 10.800000, 10.521739, 10.491304, 10.726087, 10.413043, 10.408696,
                 10.113043, 10.704348, 10.436957, 10.313043],
    "射门": [2.326087, 1.826087, 2.695652, 2.869565, 3.347826, 2.652174, 2.695652, 2.521739, 2.431884, 2.565217,
             2.565217, 2.543478, 2.608696],
    "射正": [1.500000, 1.260870, 1.173913, 1.739130, 1.782609, 2.000000, 1.521739, 1.478261, 1.539130, 1.434783,
             1.608696, 1.347826, 0.913043],
    "传球成功率": [0.767391, 0.775652, 0.762174, 0.795652, 0.738261, 0.759130, 0.772609, 0.780652, 0.772522, 0.761304,
                   0.796087, 0.765217, 0.789565],
    "抢断": [2.782609, 2.608696, 2.608696, 3.304348, 3.000000, 3.086957, 2.391304, 3.282609, 3.098551, 2.913043,
             3.304348, 3.456522, 2.434783],
    "评分": [7.332609, 7.517391, 7.495652, 7.339130, 7.186957, 7.521739, 7.556522, 7.032609, 7.400290, 7.721739,
             7.056522, 7.473913, 7.686957]
}
df = pd.DataFrame(data)

# 定义要绘制的指标列表，确保与df中的列名一致
metrics = ["跑动(km)", "射门", "射正", "传球成功率", "抢断", "评分"]

# 设置图片清晰度
plt.rcParams['figure.dpi'] = 300

for metric in metrics:
    plt.figure(figsize=(6, 3))
    ax = sns.lineplot(x="海拔(m)", y=metric, data=df)
    plt.title(f'{metric} 与 海拔(m)的关系', fontsize=10)
    plt.xlabel('海拔(m)', fontsize=12, weight='bold')

    # 使用MaxNLocator自动选择合适数量的刻度
    ax.xaxis.set_major_locator(MaxNLocator(nbins=len(df['海拔(m)']), integer=True))

    # 重新设置刻度标签旋转角度和字体大小，将字体大小设为10
    plt.xticks(rotation=45, fontsize=5)

    if metric == "跑动(km)":
        y_label = "平均跑动距离(km)"
    else:
        y_label = f"平均{metric}"
    plt.ylabel(y_label, fontsize=10)
    plt.yticks(fontsize=8)
    ax.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    # 保存图形到 outputs/图表 目录
    plt.savefig(CHART_DIR / f'{metric}_vs_altitude.png', bbox_inches='tight')
    plt.show()
    plt.close()