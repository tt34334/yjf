# ⚽ 足球青训数据管理与分析系统

> 面向青训足球教练的全周期数据管理平台：球员档案、训练负荷、比赛表现、赛程对手、统计报表，一站式管理。

一套 **FastAPI（后端） + Streamlit（前端）** 的全栈练手项目，覆盖真实业务中的增删改查、复杂聚合统计、异步任务、缓存设计、文件导入导出等核心场景。

---

## ✨ 功能总览

前端共六大页面，全部对接后端 REST API：

| 页面 | 功能 |
|------|------|
| 📊 数据总览 | 战绩走势、胜负分布、进球榜 TOP5、下一场比赛预告、本月训练概览 |
| 👥 球员管理 | 球员档案 CRUD、CSV/Excel 一键批量导入、比赛履历查询 |
| 🏟️ 比赛管理 | 比赛记录 CRUD、多条件筛选分页、单场球员表现批量录入 |
| 📅 赛程与对手 | 对手球队库（实力/风格/历史交锋）、未来赛程安排 |
| 📈 训练统计 | 各位置训练负荷聚合、每日趋势折线图、出勤率排行、训练记录管理 |
| 📤 导出报表 | 异步生成 Excel 统计报告（训练/比赛两种模板），任务状态查询 |

## 🛠 技术栈

- **后端**：Python 3.12 · FastAPI · SQLAlchemy 2.0（ORM） · Pydantic v2
- **前端**：Streamlit · Plotly（可视化图表）
- **数据库**：SQLite（本地零配置开箱即用） / MySQL 8.0（Docker 部署）
- **缓存**：Redis（接口缓存 + 异步任务状态，不可用时自动降级）
- **部署**：Docker Compose（MySQL + Redis + API 一键编排）

## 🏗 系统架构

```
┌─────────────────┐        HTTP         ┌──────────────────┐
│  Streamlit 前端  │ ──────────────────▶ │   FastAPI 后端    │
│  localhost:8501 │ ◀────────────────── │  localhost:8000  │
└─────────────────┘     JSON / File     └────────┬─────────┘
                                                 │
                              ┌──────────────────┼──────────────┐
                              ▼                  ▼              ▼
                        ┌──────────┐      ┌──────────┐   ┌───────────┐
                        │  SQLite  │      │  Redis   │   │ exports/  │
                        │  / MySQL │      │  缓存    │   │ Excel 报告│
                        └──────────┘      └──────────┘   └───────────┘
```

## 🚀 快速开始

### 方式一：Windows 一键启动（推荐）

双击 **`启动系统.bat`**，脚本会自动完成：

1. 检测 / 创建 Python 虚拟环境
2. 安装依赖（失败自动切换国内镜像源）
3. 生成默认配置（默认 SQLite，**无需安装 MySQL/Redis**）
4. 初始化数据库与种子数据（20 名球员、220+ 条训练记录、10 场比赛等）
5. 拉起后端（8000）与前端（8501），自动打开浏览器

> 前端页面：<http://localhost:8501> · API 文档：<http://localhost:8000/docs>

### 方式二：手动启动

```bash
# 1. 创建虚拟环境并安装依赖
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt

# 2. 生成配置（复制示例，本地默认用 SQLite 即可）
cp .env.example .env            # Windows 用 copy

# 3. 初始化种子数据
python -m app.seed

# 4. 启动后端（终端 1）
uvicorn app.main:app --host 127.0.0.1 --port 8000

# 5. 启动前端（终端 2）
streamlit run app_frontend.py
```

### 方式三：Docker Compose（MySQL + Redis 完整版）

```bash
docker compose up --build
```

自动完成：MySQL 8.0 + Redis 7 + API 服务编排、建库、种子数据注入。
API 服务监听 `8000` 端口，前端仍建议本地 `streamlit run app_frontend.py` 启动。

## 📡 API 一览

启动后访问 `/docs` 查看 Swagger 交互式文档。核心接口：

| 模块 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 球员 | GET/POST/PUT/DELETE | `/api/players` | 球员档案 CRUD、分页 |
| 球员 | GET | `/api/players/{id}/match-history` | 球员比赛履历 |
| 训练 | GET/POST/PUT/DELETE | `/api/training/records` | 训练记录 CRUD |
| 训练 | GET | `/api/training/statistics` | 复杂聚合统计（JOIN + GROUP BY + HAVING） |
| 训练 | GET | `/api/training/daily_trend` | 每日训练趋势 |
| 训练 | GET | `/api/training/records/avg_sql` | 原生 SQL 聚合演示 |
| 导出 | POST | `/api/training/export` | 异步导出 Excel 报告（202 + 后台任务） |
| 导出 | GET | `/api/training/export/{task_id}` | 查询导出任务状态 |
| 比赛 | GET/POST/PUT/DELETE | `/api/matches` | 比赛 CRUD、多条件筛选 |
| 比赛 | POST | `/api/matches/{id}/performances` | 球员表现批量录入 |
| 对手 | GET/POST/PUT/DELETE | `/api/opponents` | 对手球队库、历史交锋 |
| 赛程 | GET/POST/PUT/DELETE | `/api/schedules` | 赛程安排 |
| 统计 | GET | `/api/statistics/team` | 球队胜率/进失球统计 |
| 统计 | GET | `/api/statistics/player-ranking` | 球员数据排行 |
| 统计 | GET | `/api/statistics/trend` | 战绩趋势 |
| 系统 | GET | `/health` | 健康检查 |

## 💡 技术亮点

- **复杂聚合查询**：多表 JOIN + GROUP BY + HAVING 统计各位置训练负荷、出勤率排行
- **异步导出任务**：`BackgroundTasks` 后台生成 Excel（openpyxl 定制样式），任务状态写入 Redis，前端轮询
- **优雅降级**：Redis 不可用时导出仍可执行，仅状态查询不可用；本地开发无需任何外部服务
- **缓存防雪崩**：接口缓存 TTL 叠加随机抖动（jitter）
- **批量导入**：CSV/Excel 双格式解析，含异常行定位与回滚
- **分页与筛选**：统一分页模型，比赛支持日期/对手/赛事/结果多条件组合查询
- **零配置启动**：默认 SQLite，`启动系统.bat` 一键跑通全流程

## 📁 项目结构

```
足球青训数据管理与分析系统/
├── app/                    # FastAPI 后端
│   ├── main.py             # 应用入口（路由注册 / 健康检查）
│   ├── config.py           # pydantic-settings 配置
│   ├── database.py         # SQLAlchemy 引擎与会话
│   ├── models.py           # ORM 模型（6 张表）
│   ├── schemas.py          # Pydantic 请求/响应模型
│   ├── cache.py            # Redis 封装（含降级逻辑）
│   ├── tasks.py            # 后台 Excel 导出任务
│   ├── seed.py             # 种子数据生成
│   └── routers/            # 路由：players/training/matches/opponents/schedules/statistics
├── app_frontend.py         # Streamlit 前端（六大页面）
├── launcher.py             # 一键启动器
├── 启动系统.bat / .ps1      # Windows 双击入口
├── docker-compose.yml      # MySQL + Redis + API 编排
├── Dockerfile
└── requirements.txt
```

## ❓ 常见问题

- **需要安装 MySQL / Redis 吗？** 不需要。本地默认 SQLite，Redis 相关功能自动降级；Docker 方式才会启用 MySQL + Redis。
- **数据从哪来？** 首次启动自动生成中文种子数据，也可在页面上用 CSV/Excel 批量导入真实数据。
- **端口冲突？** 后端固定 8000、前端固定 8501，启动前请确保端口空闲（残留进程可用任务管理器结束）。

## 📄 License

[MIT](LICENSE)
