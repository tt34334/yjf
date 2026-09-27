import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score, confusion_matrix
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
import matplotlib.pyplot as plt
import seaborn as sns
import re
import warnings
import joblib
from pathlib import Path

# 项目根目录（本文件位于：项目根目录/可运行的程序（用PyCharm运行打开）/胜率预测模型代码/本文件）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# 图表与模型输出目录
CHART_DIR = PROJECT_ROOT / "outputs" / "图表"
MODEL_DIR = PROJECT_ROOT / "outputs" / "模型"
CHART_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# 设置 Matplotlib 支持中文
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'WenQuanYi Zen Hei']
plt.rcParams['axes.unicode_minus'] = False  # 正确显示负号


warnings.filterwarnings('ignore')

# --------------------------
# 数据准备
# --------------------------
# 加载数据（数据集自带的天气+球员总数据）
df = pd.read_csv(PROJECT_ROOT / "数据集" / "合并数据" / "天气球员总数据+血氧、气压.csv")


# --------------------------
# 数据预处理
# --------------------------
def preprocess_data(df):
    """将球员级数据转为比赛级数据"""

    # 数据清洗
    # 处理温度湿度字段（示例："25℃" -> 25）
    df['最高气温'] = df['最高气温'].apply(lambda x: float(re.findall(r'\d+', str(x))[0]))
    df['最低气温'] = df['最低气温'].apply(lambda x: float(re.findall(r'\d+', str(x))[0]))
    df['湿度'] = df['湿度'].apply(lambda x: float(re.findall(r'\d+', str(x))[0]))

    # 转换百分比字段（示例："85%" -> 0.85）
    df['传球成功率'] = df['传球成功率'].str.replace('%', '').astype(float) / 100

    # 按比赛聚合球员数据
    match_features = df.groupby('比赛ID').agg({
        '跑动(km)': ['mean', 'sum'],
        '射门': 'sum',
        '射正': 'sum',
        '传球成功率': 'mean',
        '抢断': 'sum',
        '评分': 'mean',
        '主客场': 'first',
        '比赛城市': 'first',
        '海拔(m)': 'first',
        '最高气温': 'first',
        '最低气温': 'first',
        '天气': 'first',
        '风向': 'first',
        '风级': 'first',
        '湿度': 'first'
    })

    # 扁平化多级索引
    match_features.columns = ['_'.join(col).strip() for col in match_features.columns.values]
    match_features.rename(columns={
        '主客场_first': '主客场',
        '比赛城市_first': '比赛城市',
        '海拔(m)_first': '海拔(m)',
        '最高气温_first': '最高气温',
        '最低气温_first': '最低气温',
        '天气_first': '天气',
        '风向_first': '风向',
        '风级_first': '风级',
        '湿度_first': '湿度'
    }, inplace=True)

    # 添加气候特征
    match_features['温差'] = match_features['最高气温'] - match_features['最低气温']

    # 生成目标变量（假设客场球队固定为负）
    # 注意：需要根据实际比赛结果修改此逻辑！！！
    match_features['胜负'] = np.where(
        (match_features['主客场'] == '主场') &
        (match_features['射正_sum'] > match_features['射正_sum'].median()),
        1, 0
    )

    return match_features


# 执行预处理
match_df = preprocess_data(df)

# --------------------------
# 特征工程
# --------------------------
# 定义特征列
numeric_features = [
    '跑动(km)_mean', '射门_sum', '射正_sum', '传球成功率_mean',
    '抢断_sum', '评分_mean', '海拔(m)', '最高气温',
    '最低气温', '湿度', '温差'
]

categorical_features = ['天气', '风向']

# 定义预处理管道
preprocessor = ColumnTransformer(
    transformers=[
        ('num', StandardScaler(), numeric_features),
        ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_features)
    ]
)

# 定义特征和目标
X = match_df[numeric_features + categorical_features]
y = match_df['胜负']

# 划分数据集（当某一类别样本过少无法分层时，退回为普通随机划分）
split_kwargs = dict(test_size=0.2, random_state=42)
if y.nunique() > 1 and y.value_counts().min() >= 2:
    split_kwargs['stratify'] = y
X_train, X_test, y_train, y_test = train_test_split(X, y, **split_kwargs)

# --------------------------
# 模型训练
# --------------------------
# 创建完整流水线
# 类别不平衡权重：负样本数 / 正样本数（训练集中没有正样本时取 1）
_pos_count = max(len(y_train[y_train == 1]), 1)
pipeline = Pipeline([
    ('preprocessor', preprocessor),
    ('classifier', xgb.XGBClassifier(
        objective='binary:logistic',
        eval_metric='auc',
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.5,
        reg_lambda=1,
        scale_pos_weight=len(y_train[y_train == 0]) / _pos_count
    ))
])

# 训练模型
pipeline.fit(X_train, y_train)

# --------------------------
# 模型评估
# --------------------------
# 预测结果
y_pred = pipeline.predict(X_test)
y_proba = pipeline.predict_proba(X_test)[:, 1]

# 评估指标
print("\n模型评估报告:")
print(f"准确率: {accuracy_score(y_test, y_pred):.2%}")
if y_test.nunique() > 1:
    print(f"AUC-ROC: {roc_auc_score(y_test, y_proba):.3f}")
else:
    print("AUC-ROC: 测试集仅含一个类别，跳过该指标")

# 混淆矩阵
cm = confusion_matrix(y_test, y_pred)
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=['负', '胜'], yticklabels=['负', '胜'])
plt.xlabel('预测值')
plt.ylabel('真实值')
plt.title('混淆矩阵')
plt.savefig(CHART_DIR / '胜率预测_混淆矩阵.png', bbox_inches='tight', dpi=300)
plt.show()

# --------------------------
# 特征重要性
# --------------------------
# 提取特征名称
cat_encoder = pipeline.named_steps['preprocessor'].named_transformers_['cat']
cat_features = cat_encoder.get_feature_names_out(categorical_features)
all_features = numeric_features + list(cat_features)

# 获取重要性
importance = pipeline.named_steps['classifier'].feature_importances_
importance_df = pd.DataFrame({'特征': all_features, '重要性': importance})
importance_df = importance_df.sort_values('重要性', ascending=False)

# 可视化
plt.figure(figsize=(10, 6))
sns.barplot(x='重要性', y='特征', data=importance_df.head(15), palette='viridis', hue='特征', legend=False)
plt.title('Top 15 特征重要性')
plt.tight_layout()
plt.savefig(CHART_DIR / '胜率预测_Top15特征重要性.png', bbox_inches='tight', dpi=300)
plt.show()

# --------------------------
# 高原特征分析
# --------------------------
# 生成模拟数据观察海拔影响
def generate_sim_data(base_data, n_samples=100):
    """生成高原影响分析专用模拟数据"""
    # 固定其他特征为中位数/众数
    sim_df = pd.DataFrame({
        '跑动(km)_mean': [base_data['跑动(km)_mean'].median()] * n_samples,
        '射门_sum': [base_data['射门_sum'].median()] * n_samples,
        '射正_sum': [base_data['射正_sum'].median()] * n_samples,
        '传球成功率_mean': [base_data['传球成功率_mean'].median()] * n_samples,
        '抢断_sum': [base_data['抢断_sum'].median()] * n_samples,
        '评分_mean': [base_data['评分_mean'].median()] * n_samples,
        '最低气温': [base_data['最低气温'].median()] * n_samples,
        '天气': [base_data['天气'].mode()[0]] * n_samples,
        '风向': [base_data['风向'].mode()[0]] * n_samples,
        '海拔(m)': np.linspace(0, 2000, n_samples),
        '最高气温': [base_data['最高气温'].median()] * n_samples,
        '湿度': [base_data['湿度'].median()] * n_samples,
        '温差': [base_data['温差'].median()] * n_samples
    })
    return sim_df

# 生成模拟数据
sim_data = generate_sim_data(X_train, n_samples=100)

# 预处理模拟数据（使用完整流水线）
sim_processed = pipeline.named_steps['preprocessor'].transform(sim_data)

# 预测胜率变化
sim_proba = pipeline.named_steps['classifier'].predict_proba(sim_processed)[:, 1]
plt.figure(figsize=(10, 6))
plt.plot(sim_data['海拔(m)'], sim_proba, color='darkred')
plt.xlabel('海拔(m)')
plt.ylabel('预测胜率')
plt.title('海拔高度对胜率的影响预测')
plt.grid(True)
plt.savefig(CHART_DIR / '胜率预测_海拔高度对胜率的影响.png', bbox_inches='tight', dpi=300)
plt.show()

# --------------------------
# 模型保存
# --------------------------
model_path = MODEL_DIR / 'xgboost_pipeline.pkl'
joblib.dump(pipeline, model_path)
print(f"模型已保存为 {model_path}")