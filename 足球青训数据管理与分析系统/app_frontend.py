"""
⚽ 青训数据管理看板 —— 面向青训足球教练的全周期数据管理平台

运行方式：
    streamlit run app_frontend.py
默认监听 8501 端口，对接后端 http://localhost:8000

六大页面：数据总览 / 球员管理 / 比赛管理 / 赛程与对手 / 训练统计 / 导出报表
"""

import csv
import io
from datetime import date, datetime, timedelta
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ============================== 全局配置 ==============================
API_BASE = "http://localhost:8000"
ASSETS = Path(__file__).parent / "assets"

COLOR_PRIMARY = "#2E7D32"
COLOR_PRIMARY_LIGHT = "#43A047"
COLOR_ACCENT = "#FFB300"
COLOR_DARK = "#37474F"
COLOR_BG_SOFT = "#F1F8E9"
POSITIONS = ["全部", "前锋", "中场", "后卫"]
RESULT_COLORS = {"胜": "#2E7D32", "平": "#FFB300", "负": "#C62828"}


# ============================== API 封装 ==============================
def _show_error(msg: str):
    st.error(f"⚠️ {msg}")


def api_get(path: str, **params) -> dict | list | None:
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
        _show_error(f"接口返回 {r.status_code}：{r.text[:120]}")
        return None
    except requests.exceptions.ConnectionError:
        _show_error("无法连接后端服务，请确认 http://localhost:8000 已启动")
        return None
    except requests.exceptions.Timeout:
        _show_error("请求超时，请稍后重试")
        return None
    except Exception as e:  # noqa: BLE001
        _show_error(f"请求异常：{e}")
        return None


def api_call(method: str, path: str, json_body: dict | None = None) -> dict | None:
    try:
        r = requests.request(method, f"{API_BASE}{path}", json=json_body, timeout=10)
        if r.status_code in (200, 201):
            return r.json()
        if r.status_code == 204:
            return {"ok": True}
        _show_error(f"操作失败（{r.status_code}）：{r.text[:120]}")
        return None
    except requests.exceptions.ConnectionError:
        _show_error("无法连接后端服务，请确认 http://localhost:8000 已启动")
        return None
    except Exception as e:  # noqa: BLE001
        _show_error(f"请求异常：{e}")
        return None


def render_image(name: str, caption: str = "", width: int = 260):
    p = ASSETS / name
    if p.exists():
        st.image(str(p), caption=caption, width=width)


def md_table(rows: list, columns: list | None = None) -> str:
    """生成 markdown 表格，避开 pandas/pyarrow"""
    if not rows:
        return "（无数据）"
    if columns is None:
        columns = list(rows[0].keys())
    header = "| " + " | ".join(str(c) for c in columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    body = "\n".join(
        "| " + " | ".join(str(r.get(c, "")) for c in columns) + " |" for r in rows
    )
    return f"{header}\n{sep}\n{body}"


# ============================== 通用辅助函数 ==============================
def parse_upload_file(uploaded_file):
    """解析上传的 CSV 或 Excel 文件，返回 list[dict] 或 (None, error_msg)"""
    if not uploaded_file:
        return None, "未选择文件"
    name = uploaded_file.name.lower()
    try:
        if name.endswith(".csv"):
            content = uploaded_file.getvalue().decode("utf-8-sig", errors="replace")
            reader = csv.DictReader(io.StringIO(content))
            rows = [dict(row) for row in reader]
            return rows, None
        elif name.endswith(".xlsx"):
            try:
                import pandas as pd
                df = pd.read_excel(uploaded_file)
                df = df.where(pd.notnull(df), None)
                rows = df.to_dict("records")
                return rows, None
            except Exception:
                pass
            try:
                import openpyxl
                wb = openpyxl.load_workbook(uploaded_file)
                ws = wb.active
                rows_iter = ws.iter_rows(values_only=True)
                try:
                    header = next(rows_iter)
                except StopIteration:
                    return [], None
                header = [str(h).strip() if h is not None else f"col{i}" for i, h in enumerate(header)]
                rows = []
                for row in rows_iter:
                    if row is None or all(v is None or (isinstance(v, str) and not v.strip()) for v in row):
                        continue
                    d = {}
                    for i, col in enumerate(header):
                        val = row[i] if i < len(row) else None
                        if isinstance(val, datetime):
                            d[col] = val.isoformat()
                        elif isinstance(val, date):
                            d[col] = val.isoformat()
                        else:
                            d[col] = val
                    rows.append(d)
                return rows, None
            except ImportError:
                return None, "缺少 openpyxl 库，无法解析 Excel，请安装 openpyxl 或使用 CSV 格式"
        else:
            return None, "不支持的文件格式，请上传 .csv 或 .xlsx"
    except Exception as e:
        return None, f"文件解析失败：{e}"


def match_columns(raw_rows, field_aliases):
    """将原始数据列名按别名映射到目标字段，返回 (mapped_rows, matched_fields)"""
    if not raw_rows:
        return [], []
    raw_cols = list(raw_rows[0].keys())
    col_norm = {str(c).strip().lower(): c for c in raw_cols}
    target_map = {}
    matched = []
    for target, aliases in field_aliases.items():
        found = None
        for alias in aliases:
            norm = alias.strip().lower()
            if norm in col_norm:
                found = col_norm[norm]
                break
        if found:
            target_map[target] = found
            matched.append(target)
    mapped_rows = []
    for r in raw_rows:
        new_r = {}
        for target, src in target_map.items():
            val = r.get(src)
            if isinstance(val, str):
                val = val.strip()
            new_r[target] = val
        mapped_rows.append(new_r)
    return mapped_rows, matched


def batch_import(api_path, rows, create_required=None, skip_invalid=True):
    """逐行 POST 批量导入，返回统计结果"""
    success = 0
    failed = 0
    errors = []
    for idx, row in enumerate(rows, start=1):
        if create_required:
            missing = [f for f in create_required if not row.get(f)]
            if missing:
                if skip_invalid:
                    failed += 1
                    errors.append(f"第{idx}行：缺少必填字段 {','.join(missing)}")
                    continue
                else:
                    errors.append(f"第{idx}行：缺少必填字段 {','.join(missing)}")
        body = {}
        for k, v in row.items():
            if v is None or v == "":
                continue
            body[k] = v
        res = api_call("POST", api_path, json_body=body)
        if res:
            success += 1
        else:
            failed += 1
            errors.append(f"第{idx}行：接口创建失败")
    return {"success": success, "failed": failed, "errors": errors}


def _to_int(v, default=None):
    try:
        if v is None or v == "":
            return default
        return int(float(v))
    except Exception:
        return default


def _to_float(v, default=None):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default


def _to_date(v, default=None):
    try:
        if v is None or v == "":
            return default
        if isinstance(v, date):
            return v.isoformat()
        if isinstance(v, datetime):
            return v.date().isoformat()
        s = str(v).strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%m/%d/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(s, fmt).date().isoformat()
            except Exception:
                pass
        try:
            return date.fromisoformat(s).isoformat()
        except Exception:
            return default
    except Exception:
        return default


def _to_datetime(v, default=None):
    try:
        if v is None or v == "":
            return default
        if isinstance(v, datetime):
            return v.isoformat()
        if isinstance(v, date):
            return datetime(v.year, v.month, v.day).isoformat()
        s = str(v).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt).isoformat()
            except Exception:
                pass
        try:
            return datetime.fromisoformat(s).isoformat()
        except Exception:
            return default
    except Exception:
        return default


# ============================== 主题样式 ==============================
def inject_theme():
    st.markdown(
        f"""
        <style>
        /* 卡片式 KPI */
        .kpi-card {{
            background: linear-gradient(135deg, {COLOR_BG_SOFT} 0%, #ffffff 100%);
            border-left: 5px solid {COLOR_PRIMARY};
            border-radius: 10px;
            padding: 16px 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }}
        .kpi-value {{ font-size: 30px; font-weight: 800; color: {COLOR_PRIMARY}; }}
        .kpi-label {{ font-size: 13px; color: {COLOR_DARK}; margin-top: 4px; }}
        /* 比赛结果徽章 */
        .badge {{ display:inline-block; padding:3px 12px; border-radius:12px; color:#fff; font-weight:700; font-size:13px; }}
        .badge-win {{ background:{COLOR_PRIMARY}; }}
        .badge-draw {{ background:{COLOR_ACCENT}; color:#333; }}
        .badge-loss {{ background:#C62828; }}
        /* 页面标题 */
        .page-title {{ font-size:24px; font-weight:800; color:{COLOR_PRIMARY}; border-bottom:3px solid {COLOR_PRIMARY}; padding-bottom:8px; margin-bottom:16px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 侧边栏品牌化样式（独立字符串，避免 f-string 的 {} 转义）
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] { background: #f8f9fa !important; }
        section[data-testid="stSidebar"][aria-expanded="true"] { width: 280px !important; }
        section[data-testid="stSidebar"][aria-expanded="true"] > div,
        section[data-testid="stSidebar"][aria-expanded="true"] [data-testid="stSidebarContent"] { width: 280px !important; }
        .brand-title { font-size: 22px; font-weight: 800; color: #1B5E20; line-height: 1.3; }
        .brand-sub { font-size: 12px; color: #9e9e9e; font-weight: 500; margin-top: 2px; letter-spacing: 0.6px; }
        section[data-testid="stSidebar"] button[kind="secondary"] {
            background: #ffffff !important; border: 1px solid #e3e3e3 !important;
            border-left: 4px solid transparent !important; border-radius: 10px !important;
            padding: 12px 16px !important; font-weight: 700 !important; font-size: 16px !important;
            color: #455a64 !important; margin-bottom: 8px !important; text-align: left !important; transition: all 0.2s ease;
        }
        section[data-testid="stSidebar"] button[kind="secondary"]:hover { background: #f0f0f0 !important; }
        section[data-testid="stSidebar"] button[kind="primary"] {
            background: #2E7D32 !important; border: 1px solid #2E7D32 !important;
            border-left: 4px solid #FFB300 !important; border-radius: 10px !important;
            padding: 12px 16px !important; font-weight: 700 !important; font-size: 16px !important;
            color: #fff !important; margin-bottom: 8px !important; text-align: left !important;
            box-shadow: 0 3px 10px rgba(46,125,50,0.3);
        }
        .side-copyright { font-size: 12px; color: #9e9e9e; text-align: center; margin-top: 24px; padding-top: 12px; border-top: 1px solid #eceff1; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_title(text: str):
    st.markdown(f'<div class="page-title">{text}</div>', unsafe_allow_html=True)


def kpi_card(value: str, label: str):
    st.markdown(
        f'<div class="kpi-card"><div class="kpi-value">{value}</div><div class="kpi-label">{label}</div></div>',
        unsafe_allow_html=True,
    )


def result_badge(result: str | None) -> str:
    if result == "胜":
        return '<span class="badge badge-win">胜</span>'
    if result == "平":
        return '<span class="badge badge-draw">平</span>'
    if result == "负":
        return '<span class="badge badge-loss">负</span>'
    return '<span class="badge" style="background:#9e9e9e">待赛</span>'


# ============================== 页面一：数据总览 ==============================
def page_dashboard():
    page_title("📊 数据总览")
    today = date.today()
    month_start = today.replace(day=1)

    with st.spinner("加载球队数据..."):
        team = api_get("/api/statistics/team")
        players_data = api_get("/api/players", page=1, size=1)
        trend = api_get("/api/statistics/trend", limit=10)
        ranking = api_get("/api/statistics/player-ranking", sort_by="goals", limit=5)
        upcoming = api_get("/api/matches/upcoming")
        training = api_get("/api/training/statistics", start=month_start.isoformat(), end=today.isoformat())

    if not team:
        return

    # ---- 4 个 KPI 卡片 ----
    c1, c2, c3, c4 = st.columns(4)
    total_players = players_data.get("total", 0) if players_data else 0
    with c1:
        kpi_card(str(total_players), "总球员数")
    with c2:
        kpi_card(str(team["total_matches"]), "总比赛数")
    with c3:
        kpi_card(f"{team['win_rate']}%", "胜率")
    with c4:
        kpi_card(str(team["avg_goals"]), "场均进球")

    st.markdown("---")

    # ---- 近期战绩走势图（折线，颜色区分胜平负）----
    st.subheader("📈 近期战绩走势")
    if trend:
        dates = [t["match_date"] for t in trend]
        result_map = {"胜": 3, "平": 1, "负": 0}
        scores = [result_map.get(t["result"], -1) for t in trend]
        colors = [RESULT_COLORS.get(t["result"], "#9e9e9e") for t in trend]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates, y=scores, mode="lines+markers+text",
            text=[t["result"] or "" for t in trend], textposition="top center",
            line=dict(color=COLOR_PRIMARY, width=3),
            marker=dict(size=14, color=colors, line=dict(width=2, color="white")),
        ))
        fig.update_yaxes(tickvals=[0, 1, 3], ticktext=["负", "平", "胜"], range=[-0.5, 3.5])
        fig.update_layout(height=320, margin=dict(t=10, b=10), xaxis_title="比赛日期", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        # ---- 比赛结果分布饼图 ----
        st.subheader("🥧 比赛结果分布")
        if team["total_matches"] > 0:
            fig_pie = go.Figure(data=[go.Pie(
                labels=["胜", "平", "负"],
                values=[team["wins"], team["draws"], team["losses"]],
                hole=0.4,
                marker=dict(colors=[COLOR_PRIMARY, COLOR_ACCENT, "#C62828"]),
            )])
            fig_pie.update_layout(height=300, margin=dict(t=10, b=10), showlegend=True)
            st.plotly_chart(fig_pie, use_container_width=True)

    with col_b:
        # ---- 球员进球榜 TOP5（横向条形）----
        st.subheader("⚽ 球员进球榜 TOP5")
        if ranking:
            names = [r["name"] for r in reversed(ranking)]
            goals = [r["goals"] for r in reversed(ranking)]
            fig_bar = go.Figure(go.Bar(
                x=goals, y=names, orientation="h",
                marker_color=COLOR_PRIMARY, text=goals, textposition="auto",
            ))
            fig_bar.update_layout(height=300, margin=dict(t=10, b=10), xaxis_title="进球数", showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)

    # ---- 进球/失球趋势双折线 ----
    st.subheader("🥅 进球与失球趋势")
    if trend:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=dates, y=[t["score_our"] for t in trend],
            name="我方进球", line=dict(color=COLOR_PRIMARY, width=2.5), mode="lines+markers",
        ))
        fig2.add_trace(go.Scatter(
            x=dates, y=[t["score_opponent"] for t in trend],
            name="失球", line=dict(color="#C62828", width=2.5), mode="lines+markers",
        ))
        fig2.update_layout(height=300, margin=dict(t=10, b=10), xaxis_title="比赛日期", yaxis_title="进球数")
        st.plotly_chart(fig2, use_container_width=True)

    # ---- 下一场比赛预告 + 训练概览 ----
    st.markdown("---")
    c_left, c_right = st.columns(2)
    with c_left:
        st.subheader("🏟️ 下一场比赛预告")
        up = upcoming.get("upcoming") if upcoming else None
        if up:
            st.markdown(f"""
            <div class="kpi-card">
                <div style="font-size:18px;font-weight:700;color:{COLOR_PRIMARY}">vs {up.get('opponent','')}</div>
                <div style="margin-top:8px">📅 {up.get('match_date','')}</div>
                <div>📍 {up.get('venue','')}</div>
                <div>🏆 {up.get('competition','')}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("暂无已安排的未来比赛")
    with c_right:
        st.subheader("🏃 本月训练概览")
        if training:
            m1, m2 = st.columns(2)
            m1.metric("本月训练次数", training.get("total_sessions", 0))
            if training.get("top3_attendance"):
                top = training["top3_attendance"][0]
                m2.metric("出勤最高", f"{top['name']}({top['attendance']}次)")
        else:
            st.info("本月暂无训练数据")


# ============================== 页面二：球员管理 ==============================
def page_players():
    page_title("👥 球员管理")

    tab_list, tab_import = st.tabs(["📋 球员列表", "📥 一键导入球员"])

    # ========================= Tab A：球员列表（原有功能）=========================
    with tab_list:
        # 筛选器
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
        pos = col1.selectbox("位置", POSITIONS)
        min_h = col2.number_input("最低身高(0=不过滤)", 0, 250, 0, step=5)
        page = col3.number_input("页码", 1, 100, 1, step=1)
        col4.markdown("&nbsp;")
        if col4.button("🔍 查询", use_container_width=True, type="primary"):
            st.rerun()

        if 0 < min_h < 100:
            st.error("最低身高筛选值需为 0（不过滤）或 ≥ 100cm")
        else:
            params = {"page": int(page), "size": 15}
            if pos != "全部":
                params["position"] = pos
            if min_h >= 100:
                params["min_height"] = int(min_h)

            data = api_get("/api/players", **params)
            if data:
                st.markdown(f"**共 {data['total']} 名球员 · 第 {data['page']} 页**")
                rows = [
                    {
                        "ID": p["id"], "球衣": p.get("jersey_number") or "-",
                        "姓名": p["name"], "位置": p["position"],
                        "身高": p["height"], "惯用脚": p.get("preferred_foot") or "-",
                        "入队日期": p["join_date"],
                    }
                    for p in data["items"]
                ]
                st.markdown(md_table(rows), unsafe_allow_html=True)

        st.markdown("---")
        c_new, c_view = st.columns(2)
        c_new.subheader("➕ 新增球员")
        with c_new.form("add_player"):
            name = st.text_input("姓名")
            position = st.selectbox("位置", ["前锋", "中场", "后卫"])
            height = st.number_input("身高(cm)", 150, 220, 170)
            join_date = st.date_input("入队日期", date.today())
            jersey = st.number_input("球衣号码", 1, 99, 1)
            foot = st.selectbox("惯用脚", ["左", "右", "双脚"])
            nationality = st.text_input("国籍", "中国")
            if st.form_submit_button("提交新增", type="primary"):
                if not name:
                    st.error("姓名不能为空")
                else:
                    res = api_call("POST", "/api/players", json_body={
                        "name": name, "position": position, "height": int(height),
                        "join_date": str(join_date), "jersey_number": int(jersey),
                        "preferred_foot": foot, "nationality": nationality,
                    })
                    if res:
                        st.success(f"新增成功：{res['name']}（ID={res['id']}）")
                        st.rerun()

        # 查看球员详情与历史比赛
        c_view.subheader("📋 球员详情与历史比赛")
        all_players = api_get("/api/players", page=1, size=100)
        if all_players:
            sel = c_view.selectbox("选择球员查看 / 编辑", [f"{p['id']} - {p['name']}" for p in all_players["items"]])
            if sel:
                pid = int(sel.split(" - ")[0])
                detail = api_get(f"/api/players/{pid}")
                history = api_get(f"/api/players/{pid}/match-history")
                if detail:
                    with c_view.expander(f"✏️ 编辑 {detail['name']}", expanded=False):
                        with st.form(f"edit_{pid}"):
                            ename = st.text_input("姓名", detail["name"])
                            epos = st.selectbox("位置", ["前锋", "中场", "后卫"], index=["前锋","中场","后卫"].index(detail["position"]))
                            eheight = st.number_input("身高", 100, 250, max(100, int(detail["height"] or 100)))
                            efoot = st.selectbox("惯用脚", ["左", "右", "双脚"], index=0 if detail.get("preferred_foot")=="左" else (1 if detail.get("preferred_foot")=="右" else 2))
                            if st.form_submit_button("保存修改", type="primary"):
                                res = api_call("PUT", f"/api/players/{pid}", json_body={
                                    "name": ename, "position": epos, "height": int(eheight), "preferred_foot": efoot,
                                })
                                if res:
                                    st.success("修改成功")
                                    st.rerun()
                    if history:
                        st.markdown(f"**历史比赛汇总**：{history['matches_played']} 场 · 进球 {history['total_goals']} · 助攻 {history['total_assists']} · 场均评分 {history['avg_rating']}")
                        if history.get("recent_ratings"):
                            st.subheader("📊 近期评分趋势")
                            fig = go.Figure(go.Bar(
                                x=list(range(1, len(history["recent_ratings"])+1)),
                                y=history["recent_ratings"],
                                marker_color=COLOR_PRIMARY_LIGHT, text=history["recent_ratings"], textposition="auto",
                            ))
                            fig.update_layout(height=280, margin=dict(t=10,b=10), xaxis_title="场次(近→远)", yaxis_title="评分", yaxis_range=[0,10])
                            st.plotly_chart(fig, use_container_width=True)

    # ========================= Tab B：一键导入球员 =========================
    with tab_import:
        st.subheader("📥 批量导入球员")
        p_file = st.file_uploader("上传球员 CSV/Excel", type=["csv", "xlsx"], key="player_upload")
        if p_file:
            rows, err = parse_upload_file(p_file)
            if err:
                st.error(err)
            elif rows:
                st.markdown(f"**读取到 {len(rows)} 行数据**")
                field_aliases = {
                    "name": ["姓名", "名字", "name"],
                    "position": ["位置", "司职", "角色"],
                    "height": ["身高", "身高cm"],
                    "join_date": ["入队日期", "加入日期", "进队日期", "报到日期"],
                    "jersey_number": ["球衣号", "球衣", "号码", "jersey"],
                    "preferred_foot": ["惯用脚", "脚法", "脚"],
                    "nationality": ["国籍", "国家", "nation"],
                }
                mapped, matched = match_columns(rows, field_aliases)
                st.markdown(f"**匹配字段**：{', '.join(matched)}")
                if not matched:
                    st.warning("未匹配到任何字段，请检查列名")
                else:
                    processed = []
                    for row in mapped:
                        body = {}
                        if row.get("name"):
                            body["name"] = row["name"]
                        if row.get("position"):
                            body["position"] = row["position"]
                        h = _to_int(row.get("height"))
                        if h:
                            body["height"] = h
                        else:
                            body["height"] = 170
                        jd = _to_date(row.get("join_date"))
                        if jd:
                            body["join_date"] = jd
                        else:
                            body["join_date"] = date.today().isoformat()
                        jn = _to_int(row.get("jersey_number"))
                        if jn:
                            body["jersey_number"] = jn
                        if row.get("preferred_foot"):
                            body["preferred_foot"] = row["preferred_foot"]
                        if row.get("nationality"):
                            body["nationality"] = row["nationality"]
                        processed.append(body)

                    st.markdown("**预览前 3 行（处理后）**")
                    st.markdown(md_table(processed[:3]), unsafe_allow_html=True)
                    if st.checkbox("确认无误，提交导入球员", key="pl_import_confirm"):
                        with st.spinner("导入中..."):
                            result = batch_import("/api/players", processed, create_required=["name", "position", "height", "join_date"])
                        st.success(f"✅ 导入完成：成功 {result['success']} 条，失败 {result['failed']} 条")
                        if result["errors"]:
                            with st.expander(f"查看 {len(result['errors'])} 条错误"):
                                for e in result["errors"]:
                                    st.warning(e)
                        st.rerun()


# ============================== 页面三：比赛管理 ====================
def page_matches():
    page_title("🏟️ 比赛管理")

    tab_main, tab_import = st.tabs(["📋 比赛列表 + 表现录入", "📥 一键导入比赛"])

    # ========================= Tab A：比赛列表与详情（原有）=========================
    with tab_main:
        col1, col2, col3, col4 = st.columns(4)
        f_comp = col1.text_input("赛事", "")
        f_result = col2.selectbox("结果", ["全部", "胜", "平", "负"])
        f_start = col3.date_input("开始", date.today() - timedelta(days=180))
        f_end = col4.date_input("结束", date.today() + timedelta(days=90))
        if col1.button("🔍 查询比赛", type="primary"):
            st.rerun()

        params = {"page": 1, "size": 50}
        if f_comp:
            params["competition"] = f_comp
        if f_result != "全部":
            params["result"] = f_result
        params["start"] = str(f_start)
        params["end"] = str(f_end)

        data = api_get("/api/matches", **params)
        if data:
            items = data["items"]
            st.markdown(f"**共 {data['total']} 场比赛**")
            rows = []
            for m in items:
                rows.append({
                    "ID": m["id"], "日期": m["match_date"], "对手": m["opponent"],
                    "比分": f"{m['score_our']} : {m['score_opponent']}",
                    "结果": m["result"] or "待赛", "赛事": m.get("competition") or "-",
                    "场地": m.get("venue") or "-",
                })
            st.markdown(md_table(rows), unsafe_allow_html=True)

            # 删除比赛（selectbox + 按钮）
            st.subheader("🗑️ 删除比赛")
            del_opts = [f"{m['id']} - {m['opponent']} ({m['match_date']})" for m in items]
            if del_opts:
                dcol1, dcol2 = st.columns([3, 1])
                sel_del = dcol1.selectbox("选择比赛ID删除", del_opts, key="del_match_sel")
                if dcol2.button("🗑️ 确认删除", type="primary", use_container_width=True):
                    if sel_del:
                        mid_del = int(sel_del.split(" - ")[0])
                        res = api_call("DELETE", f"/api/matches/{mid_del}")
                        if res:
                            st.success(f"比赛 #{mid_del} 已删除")
                            st.rerun()
        else:
            items = []

        st.markdown("---")
        left, right = st.columns([1, 1])
        # 新增比赛
        left.subheader("➕ 新增比赛")
        with left.form("add_match"):
            m_opp = st.text_input("对手球队")
            m_date = st.date_input("比赛日期", date.today())
            m_venue = st.selectbox("场地", ["主场", "客场"])
            m_comp = st.selectbox("赛事", ["友谊赛", "联赛", "杯赛"])
            m_so = st.number_input("我方进球", 0, 20, 0)
            m_sp = st.number_input("对方进球", 0, 20, 0)
            if m_so > m_sp:
                m_res, suggestion = "胜", "胜"
            elif m_so == m_sp:
                m_res, suggestion = "平", "平"
            else:
                m_res, suggestion = "负", "负"
            st.info(f"根据比分自动判定结果：{suggestion}")
            if st.form_submit_button("创建比赛", type="primary"):
                if not m_opp:
                    st.error("对手名称不能为空")
                else:
                    res = api_call("POST", "/api/matches", json_body={
                        "opponent": m_opp, "match_date": str(m_date), "venue": m_venue,
                        "competition": m_comp, "score_our": int(m_so), "score_opponent": int(m_sp), "result": m_res,
                    })
                    if res:
                        st.success(f"比赛创建成功（ID={res['id']}）")
                        st.rerun()

        # 比赛详情 + 球员表现录入
        right.subheader("📋 比赛详情与表现录入")
        if items:
            sel_match = right.selectbox("选择比赛查看详情", [f"{m['id']} - {m['opponent']} ({m['match_date']})" for m in items])
            if sel_match:
                mid = int(sel_match.split(" - ")[0])
                detail = api_get(f"/api/matches/{mid}")
                if detail:
                    right.markdown(f"**对手**：{detail['opponent']} ｜ **比分**：{detail['score_our']}:{detail['score_opponent']} ｜ **结果**：{detail['result'] or '待赛'}")
                    right.markdown(f"**日期**：{detail['match_date']} ｜ **赛事**：{detail.get('competition') or '-'} ｜ **场地**：{detail.get('venue') or '-'}")
                    perfs = detail.get("performances") or []
                    if perfs:
                        right.markdown("**已录入球员表现**")
                        prow = [{
                            "球员": p.get("player_name") or f"#{p['player_id']}", "位置": p.get("position_played") or "-",
                            "进球": p["goals"], "助攻": p["assists"], "分钟": p["minutes_played"], "评分": p.get("rating") or "-",
                        } for p in perfs]
                        right.markdown(md_table(prow), unsafe_allow_html=True)
                    else:
                        right.info("该场比赛暂无球员表现数据")

                    # 批量录入表现
                    right.subheader("✏️ 批量录入球员表现")
                    all_players = api_get("/api/players", page=1, size=50)
                    if all_players and perfs is not None:
                        with right.form(f"perf_{mid}"):
                            edits = []
                            for p in all_players["items"][:11]:
                                existing = next((x for x in perfs if x["player_id"] == p["id"]), None)
                                cc1, cc2, cc3, cc4, cc5 = st.columns([2, 1, 1, 1, 1])
                                goals = cc1.number_input(f"{p['name']} 进球", 0, 10, existing["goals"] if existing else 0, key=f"g_{mid}_{p['id']}")
                                assists = cc2.number_input("助攻", 0, 10, existing["assists"] if existing else 0, key=f"a_{mid}_{p['id']}")
                                mins = cc3.number_input("分钟", 0, 120, existing["minutes_played"] if existing else 0, key=f"m_{mid}_{p['id']}")
                                rating = cc4.number_input("评分", 0.0, 10.0, float(existing["rating"]) if existing and existing.get("rating") else 7.0, step=0.1, key=f"r_{mid}_{p['id']}")
                                pos_played = cc5.text_input("位置", existing.get("position_played") if existing else p["position"], key=f"p_{mid}_{p['id']}")
                                if goals or assists or mins:
                                    edits.append({"player_id": p["id"], "goals": int(goals), "assists": int(assists), "minutes_played": int(mins), "rating": float(rating), "position_played": pos_played})
                            if st.form_submit_button("保存球员表现", type="primary"):
                                res = api_call("POST", f"/api/matches/{mid}/performances", json_body={"performances": edits})
                                if res is not None:
                                    st.success(f"已保存 {res.get('saved', 0)} 条球员表现")
                                    st.rerun()

    # ========================= Tab B：一键导入比赛 =========================
    with tab_import:
        st.subheader("📥 批量导入比赛")
        m_file = st.file_uploader("上传比赛 CSV/Excel", type=["csv", "xlsx"], key="match_upload")
        if m_file:
            rows, err = parse_upload_file(m_file)
            if err:
                st.error(err)
            elif rows:
                st.markdown(f"**读取到 {len(rows)} 行数据**")
                field_aliases = {
                    "opponent": ["对手", "对手球队", "对方"],
                    "match_date": ["日期", "比赛日期", "比赛时间"],
                    "venue": ["场地", "主场客场"],
                    "score_our": ["我方进球", "进球", "我方比分", "进"],
                    "score_opponent": ["对方进球", "失球", "对方比分", "丢球"],
                    "competition": ["赛事", "比赛类型", "赛事名称", "联赛杯赛"],
                }
                mapped, matched = match_columns(rows, field_aliases)
                st.markdown(f"**匹配字段**：{', '.join(matched)}")
                if not matched:
                    st.warning("未匹配到任何字段")
                else:
                    processed = []
                    warn_msgs = []
                    for idx, row in enumerate(mapped, start=1):
                        body = {}
                        opp = row.get("opponent")
                        if not opp:
                            warn_msgs.append(f"第{idx}行：缺少对手名称")
                            continue
                        body["opponent"] = opp
                        d = _to_date(row.get("match_date"))
                        if not d:
                            warn_msgs.append(f"第{idx}行：日期无效")
                            continue
                        body["match_date"] = d
                        so = _to_int(row.get("score_our"), 0)
                        sp = _to_int(row.get("score_opponent"), 0)
                        body["score_our"] = so
                        body["score_opponent"] = sp
                        if so > sp:
                            body["result"] = "胜"
                        elif so == sp:
                            body["result"] = "平"
                        else:
                            body["result"] = "负"
                        if row.get("venue"):
                            body["venue"] = row["venue"]
                        if row.get("competition"):
                            body["competition"] = row["competition"]
                        processed.append(body)

                    if warn_msgs:
                        with st.expander(f"⚠️ 警告/跳过（{len(warn_msgs)} 条）"):
                            for w in warn_msgs:
                                st.warning(w)

                    if processed:
                        st.markdown(f"**将导入 {len(processed)} 条比赛，预览前 3 条：**")
                        st.markdown(md_table(processed[:3]), unsafe_allow_html=True)
                        if st.checkbox("确认无误，提交导入比赛", key="m_import_confirm"):
                            with st.spinner("导入中..."):
                                result = batch_import("/api/matches", processed, create_required=["opponent", "match_date"])
                            st.success(f"✅ 导入完成：成功 {result['success']} 条，失败 {result['failed']} 条")
                            if result["errors"]:
                                with st.expander(f"查看 {len(result['errors'])} 条错误"):
                                    for e in result["errors"]:
                                        st.warning(e)
                            st.rerun()


# ============================== 页面四：赛程与对手 ==============================
def page_schedule():
    page_title("📅 赛程与对手")

    # 下一场比赛准备区（保留原有）
    st.subheader("🏟️ 下一场比赛准备区")
    upcoming = api_get("/api/matches/upcoming")
    up = upcoming.get("upcoming") if upcoming else None
    if up:
        days_left = (date.fromisoformat(up["match_date"]) - date.today()).days
        col_a, col_b = st.columns([2, 1])
        col_a.markdown(f"""
        <div class="kpi-card">
            <div style="font-size:20px;font-weight:700;color:{COLOR_PRIMARY}">vs {up.get('opponent','')}</div>
            <div style="margin-top:6px">📅 {up.get('match_date','')} ｜ 📍 {up.get('venue','')} ｜ 🏆 {up.get('competition','')}</div>
        </div>
        """, unsafe_allow_html=True)
        col_b.metric("距比赛还有", f"{days_left} 天")
    else:
        st.info("暂无未来比赛安排")

    st.markdown("---")

    tab_sched, tab_opp, tab_import = st.tabs(["📋 赛程安排", "🏴 对手库", "📥 一键导入（对手+赛程）"])

    # ========================= Tab 1：赛程安排 =========================
    with tab_sched:
        opps_all = api_get("/api/opponents")
        opps_items = (opps_all or {}).get("items") or []

        st.subheader("🔍 赛程筛选")
        fc1, fc2, fc3, fc4 = st.columns(4)
        f_status = fc1.selectbox("状态", ["全部", "待赛", "已赛", "已取消"])
        f_start = fc2.date_input("日期从", date.today() - timedelta(days=90))
        f_end = fc3.date_input("日期到", date.today() + timedelta(days=180))
        do_search = fc4.button("🔍 查询", type="primary", use_container_width=True)

        sched = api_get("/api/schedules")
        sched_items = (sched or {}).get("items") or []
        filtered = []
        for s in sched_items:
            mdate_str = s["match_date"][:10] if isinstance(s["match_date"], str) else str(s["match_date"])[:10]
            try:
                md = date.fromisoformat(mdate_str)
            except Exception:
                continue
            if f_status != "全部" and s.get("status", "") != f_status:
                continue
            if md < f_start or md > f_end:
                continue
            filtered.append(s)

        st.markdown(f"**共 {len(filtered)} 条赛程**")
        if filtered:
            srows = []
            for s in filtered:
                mdate_str = s["match_date"][:10] if isinstance(s["match_date"], str) else str(s["match_date"])[:10]
                try:
                    days = (date.fromisoformat(mdate_str) - date.today()).days
                except Exception:
                    days = 0
                srows.append({
                    "ID": s["id"],
                    "日期": mdate_str,
                    "对手": s.get("opponent_name") or (f"#{s.get('opponent_id','-')}" if s.get("opponent_id") else "-"),
                    "场地": s.get("venue") or "-",
                    "状态": s.get("status", "-"),
                    "距今天数": f"{days:+d}天",
                })
            st.markdown(md_table(srows), unsafe_allow_html=True)

            st.subheader("📝 编辑/删除赛程")
            sched_opts = [f"{s['id']} - {s.get('opponent_name') or '#'+str(s.get('opponent_id'))} ({mdate_str})" for s, mdate_str in zip(filtered, [r["日期"] for r in srows])]
            if sched_opts:
                sel_s = st.selectbox("选择赛程ID编辑/删除", sched_opts)
                if sel_s:
                    sid = int(sel_s.split(" - ")[0])
                    single = next((s for s in sched_items if s["id"] == sid), None)
                    if single:
                        with st.expander(f"✏️ 编辑赛程 #{sid}", expanded=True):
                            with st.form(f"edit_sched_{sid}"):
                                es_opts = [f"{o['id']} - {o['name']}" for o in opps_items]
                                es_oid_cur = single.get("opponent_id")
                                es_oid_idx = 0
                                if es_oid_cur and es_opts:
                                    for i, opt in enumerate(es_opts):
                                        if int(opt.split(" - ")[0]) == es_oid_cur:
                                            es_oid_idx = i
                                            break
                                es_opp = st.selectbox("对手", es_opts or ["- 无对手 -"], index=es_oid_idx if es_opts else 0)
                                cur_dt = single.get("match_date")
                                try:
                                    if isinstance(cur_dt, str):
                                        if "T" in cur_dt:
                                            dt_def = datetime.fromisoformat(cur_dt.replace("Z", ""))
                                        else:
                                            dt_def = datetime.fromisoformat(cur_dt)
                                    else:
                                        dt_def = cur_dt
                                except Exception:
                                    dt_def = datetime.now()
                                es_dt = st.datetime_input("比赛时间", dt_def)
                                es_venue = st.text_input("场地", single.get("venue") or "")
                                es_status = st.selectbox("状态", ["待赛", "已赛", "已取消"], index=0 if single.get("status")=="待赛" else (1 if single.get("status")=="已赛" else 2))
                                col_sv, col_del = st.columns(2)
                                if col_sv.form_submit_button("💾 保存修改", type="primary"):
                                    oid_sel = int(es_opp.split(" - ")[0]) if (es_opts and es_opp != "- 无对手 -") else None
                                    res = api_call("PUT", f"/api/schedules/{sid}", json_body={
                                        "opponent_id": oid_sel,
                                        "match_date": es_dt.isoformat(),
                                        "venue": es_venue,
                                        "status": es_status,
                                    })
                                    if res:
                                        st.success("赛程已更新")
                                        st.rerun()
                                if col_del.form_submit_button("🗑️ 删除赛程"):
                                    res = api_call("DELETE", f"/api/schedules/{sid}")
                                    if res:
                                        st.success("赛程已删除")
                                        st.rerun()
        else:
            st.info("暂无符合条件的赛程")

        st.markdown("---")
        st.subheader("➕ 新增赛程")
        with st.form("add_schedule_form"):
            asc1, asc2 = st.columns(2)
            opp_opts = [f"{o['id']} - {o['name']}" for o in opps_items]
            if opp_opts:
                as_opp = asc1.selectbox("对手", opp_opts)
                as_oid = int(as_opp.split(" - ")[0])
            else:
                as_oid = None
                asc1.info("暂无对手，请先在对手库创建")
            as_dt = asc1.datetime_input("比赛日期时间", datetime.now() + timedelta(days=7))
            as_venue = asc2.selectbox("场地", ["主场", "客场", "中立"])
            as_status = asc2.selectbox("状态", ["待赛", "已赛", "已取消"])
            if st.form_submit_button("创建赛程", type="primary"):
                if as_oid is None:
                    st.error("请先在对手库创建对手")
                else:
                    res = api_call("POST", "/api/schedules", json_body={
                        "opponent_id": as_oid,
                        "match_date": as_dt.isoformat(),
                        "venue": as_venue,
                        "status": as_status,
                    })
                    if res:
                        st.success(f"赛程创建成功（ID={res['id']}）")
                        st.rerun()

    # ========================= Tab 2：对手库 =========================
    with tab_opp:
        opps = api_get("/api/opponents")
        opps_items = (opps or {}).get("items") or []

        col_list, col_op = st.columns([3, 2])
        with col_list:
            st.subheader("🏴 对手库列表")
            if opps_items:
                orows = [{
                    "ID": o["id"], "名称": o["name"],
                    "实力": o.get("strength_level") or "-",
                    "风格": o.get("play_style") or "-",
                    "胜": o.get("head_to_head_wins", 0),
                    "平": o.get("head_to_head_draws", 0),
                    "负": o.get("head_to_head_losses", 0),
                } for o in opps_items]
                st.markdown(md_table(orows), unsafe_allow_html=True)
            else:
                st.info("暂无对手数据")

        with col_op:
            st.subheader("➕ 新增对手")
            with st.form("add_opp_form"):
                ao_name = st.text_input("名称")
                ao_strength = st.selectbox("实力等级", ["强", "中", "弱"])
                ao_style_suggestions = ["传控", "防反", "长传冲吊", "高位逼抢", "边路突破", "中路渗透"]
                ao_style = st.text_input("战术风格（可自由输入，参考：" + "、".join(ao_style_suggestions) + "）")
                ao_notes = st.text_area("备注")
                if st.form_submit_button("创建对手", type="primary"):
                    if not ao_name:
                        st.error("对手名称不能为空")
                    else:
                        res = api_call("POST", "/api/opponents", json_body={
                            "name": ao_name,
                            "strength_level": ao_strength,
                            "play_style": ao_style,
                            "notes": ao_notes,
                        })
                        if res:
                            st.success(f"对手创建成功（ID={res['id']}）")
                            st.rerun()

            st.subheader("✏️ 编辑/删除对手")
            if opps_items:
                sel_opp_edit = st.selectbox("选择对手ID", [f"{o['id']} - {o['name']}" for o in opps_items])
                if sel_opp_edit:
                    oid = int(sel_opp_edit.split(" - ")[0])
                    opp_detail = api_get(f"/api/opponents/{oid}")
                    if opp_detail:
                        with st.form(f"edit_opp_{oid}"):
                            eo_name = st.text_input("名称", opp_detail.get("name", ""))
                            cur_st = opp_detail.get("strength_level") or "中"
                            eo_strength = st.selectbox("实力等级", ["强", "中", "弱"], index=0 if cur_st=="强" else (1 if cur_st=="中" else 2))
                            eo_style = st.text_input("战术风格", opp_detail.get("play_style") or "")
                            eo_notes = st.text_area("备注", opp_detail.get("notes") or "")
                            col_es, col_ed = st.columns(2)
                            if col_es.form_submit_button("💾 保存", type="primary"):
                                if not eo_name:
                                    st.error("名称不能为空")
                                else:
                                    res = api_call("PUT", f"/api/opponents/{oid}", json_body={
                                        "name": eo_name,
                                        "strength_level": eo_strength,
                                        "play_style": eo_style,
                                        "notes": eo_notes,
                                    })
                                    if res:
                                        st.success("对手已更新")
                                        st.rerun()
                            if col_ed.form_submit_button("🗑️ 删除"):
                                res = api_call("DELETE", f"/api/opponents/{oid}")
                                if res:
                                    st.success("对手已删除")
                                    st.rerun()

        st.markdown("---")
        st.subheader("📊 对手交锋统计")
        if opps_items:
            sel_opp = st.selectbox("选择对手查看交锋详情", [f"{o['id']} - {o['name']}" for o in opps_items], key="opp_h2h_sel")
            if sel_opp:
                oid = int(sel_opp.split(" - ")[0])
                h2h = api_get(f"/api/opponents/{oid}/head-to-head")
                if h2h:
                    st.markdown(f"**{h2h['opponent_name']}**：{h2h['wins']}胜 {h2h['draws']}平 {h2h['losses']}负（共{h2h['total']}场）")
                    if h2h["total"] > 0:
                        fig = go.Figure(go.Pie(
                            labels=["胜", "平", "负"], values=[h2h["wins"], h2h["draws"], h2h["losses"]],
                            hole=0.4, marker=dict(colors=[COLOR_PRIMARY, COLOR_ACCENT, "#C62828"]),
                        ))
                        fig.update_layout(height=280, margin=dict(t=10, b=10))
                        st.plotly_chart(fig, use_container_width=True)
                    if h2h.get("recent_results"):
                        st.markdown("**近期交锋**：" + " ｜ ".join(h2h["recent_results"]))

    # ========================= Tab 3：一键导入 =========================
    with tab_import:
        # ---------- 对手导入 ----------
        st.subheader("🏴 批量导入对手")
        opp_file = st.file_uploader("上传对手 CSV/Excel", type=["csv", "xlsx"], key="opp_upload")
        if opp_file:
            rows, err = parse_upload_file(opp_file)
            if err:
                st.error(err)
            elif rows:
                st.markdown(f"**读取到 {len(rows)} 行数据**")
                field_aliases = {
                    "name": ["名称", "名字", "name", "球队", "对手", "球队名称"],
                    "strength_level": ["实力", "实力等级", "强弱"],
                    "play_style": ["风格", "打法", "战术风格"],
                    "notes": ["备注", "说明", "note"],
                }
                mapped, matched = match_columns(rows, field_aliases)
                st.markdown(f"**匹配字段**：{', '.join(matched)}")
                if not matched:
                    st.warning("未匹配到任何字段，请检查列名是否正确")
                else:
                    st.markdown("**预览前 3 行（映射后）**")
                    preview_rows = mapped[:3]
                    preview_cols = list(field_aliases.keys())
                    st.markdown(md_table(preview_rows, preview_cols), unsafe_allow_html=True)
                    if st.checkbox("确认无误，提交导入对手", key="opp_import_confirm"):
                        with st.spinner("导入中..."):
                            result = batch_import("/api/opponents", mapped, create_required=["name"])
                        st.success(f"✅ 导入完成：成功 {result['success']} 条，失败 {result['failed']} 条")
                        if result["errors"]:
                            with st.expander(f"查看 {len(result['errors'])} 条错误"):
                                for e in result["errors"]:
                                    st.warning(e)
                        st.rerun()

        st.markdown("---")
        # ---------- 赛程导入 ----------
        st.subheader("📅 批量导入赛程")
        sched_file = st.file_uploader("上传赛程 CSV/Excel", type=["csv", "xlsx"], key="sched_upload")
        if sched_file:
            rows, err = parse_upload_file(sched_file)
            if err:
                st.error(err)
            elif rows:
                st.markdown(f"**读取到 {len(rows)} 行数据**")
                opps_latest = api_get("/api/opponents")
                opps_list = (opps_latest or {}).get("items") or []
                opp_name_map = {}
                for o in opps_list:
                    opp_name_map[str(o["name"]).strip().lower()] = o["id"]

                field_aliases = {
                    "opponent_id": ["对手ID", "对手id"],
                    "opponent_name": ["对手", "对手名称", "球队"],
                    "match_date": ["比赛日期", "日期", "比赛时间", "时间"],
                    "venue": ["场地", "主客场", "主场客场"],
                    "status": ["状态"],
                }
                mapped, matched = match_columns(rows, field_aliases)
                st.markdown(f"**匹配字段**：{', '.join(matched)}")
                if not matched:
                    st.warning("未匹配到任何字段")
                else:
                    processed = []
                    warn_msgs = []
                    for idx, row in enumerate(mapped, start=1):
                        oid = row.get("opponent_id")
                        oname = row.get("opponent_name")
                        final_oid = None
                        if oid:
                            try:
                                final_oid = int(oid)
                            except Exception:
                                pass
                        if final_oid is None and oname:
                            key = str(oname).strip().lower()
                            if key in opp_name_map:
                                final_oid = opp_name_map[key]
                            else:
                                warn_msgs.append(f"第{idx}行：找不到对手 '{oname}'，请先创建对手")
                                continue
                        if final_oid is None:
                            warn_msgs.append(f"第{idx}行：缺少对手信息（需 opponent_id 或 opponent_name）")
                            continue
                        dt_val = _to_datetime(row.get("match_date"))
                        body = {"opponent_id": final_oid}
                        if dt_val:
                            body["match_date"] = dt_val
                        else:
                            warn_msgs.append(f"第{idx}行：比赛日期格式无效")
                            continue
                        if row.get("venue"):
                            body["venue"] = row["venue"]
                        if row.get("status"):
                            body["status"] = row["status"]
                        else:
                            body["status"] = "待赛"
                        processed.append(body)

                    if warn_msgs:
                        with st.expander(f"⚠️ 警告/跳过（{len(warn_msgs)} 条）"):
                            for w in warn_msgs:
                                st.warning(w)

                    if processed:
                        st.markdown(f"**将导入 {len(processed)} 条赛程，预览前 3 条：**")
                        st.markdown(md_table(processed[:3]), unsafe_allow_html=True)
                        if st.checkbox("确认无误，提交导入赛程", key="sched_import_confirm"):
                            with st.spinner("导入中..."):
                                result = batch_import("/api/schedules", processed, create_required=["opponent_id", "match_date"])
                            st.success(f"✅ 导入完成：成功 {result['success']} 条，失败 {result['failed']} 条")
                            if result["errors"]:
                                with st.expander(f"查看 {len(result['errors'])} 条错误"):
                                    for e in result["errors"]:
                                        st.warning(e)
                            st.rerun()


# ============================== 页面五：训练统计 ==============================
def page_statistics():
    page_title("📈 训练统计")

    tab_chart, tab_record, tab_import = st.tabs(["📊 训练统计图表", "📋 训练记录管理", "📥 一键导入训练记录"])

    # ========================= Tab A：训练统计图表（原有）=========================
    with tab_chart:
        today = date.today()
        month_start = today.replace(day=1)
        col1, col2 = st.columns(2)
        start = col1.date_input("开始日期", month_start, key="stat_start")
        end = col2.date_input("结束日期", today, key="stat_end")

        with st.spinner("加载训练统计..."):
            data = api_get("/api/training/statistics", start=str(start), end=str(end))
        if data:
            # KPI 卡片
            c1, c2, c3 = st.columns(3)
            c1.metric("本月训练次数", data["total_sessions"])
            avg_dist = data["position_stats"][0]["avg_distance"] if data["position_stats"] else 0
            c2.metric("平均跑动距离", f"{round(avg_dist)} 米")
            if data["top3_attendance"]:
                c3.metric("出勤最高", f"{data['top3_attendance'][0]['name']}")

            st.markdown("---")
            # 各位置平均跑动距离（柱状）
            st.subheader("🏃 各位置平均跑动距离")
            if data["position_stats"]:
                fig = go.Figure(go.Bar(
                    x=[s["position"] for s in data["position_stats"]],
                    y=[s["avg_distance"] for s in data["position_stats"]],
                    marker_color=COLOR_PRIMARY, text=[round(s["avg_distance"]) for s in data["position_stats"]], textposition="auto",
                ))
                fig.update_layout(height=320, margin=dict(t=10, b=10), yaxis_title="平均跑动距离(米)")
                st.plotly_chart(fig, use_container_width=True)

            # 出勤率前5（横向条形）
            st.subheader("🏆 出勤率前 5 球员")
            if data["top3_attendance"]:
                tops = data["top3_attendance"][:5]
                fig2 = go.Figure(go.Bar(
                    x=[t["attendance"] for t in reversed(tops)],
                    y=[t["name"] for t in reversed(tops)],
                    orientation="h", marker_color=COLOR_PRIMARY_LIGHT,
                    text=[t["attendance"] for t in reversed(tops)], textposition="auto",
                ))
                fig2.update_layout(height=300, margin=dict(t=10, b=10), xaxis_title="出勤次数")
                st.plotly_chart(fig2, use_container_width=True)

            # 原始数据表格
            with st.expander("查看位置统计原始数据"):
                st.markdown(md_table([{
                    "位置": s["position"], "平均跑动": round(s["avg_distance"]), "平均时长": round(s["avg_duration"]), "球员数": s["player_count"],
                } for s in data["position_stats"]]), unsafe_allow_html=True)

    # ========================= Tab B：训练记录管理 =========================
    with tab_record:
        st.subheader("🔍 训练记录筛选")
        rec_all_players = api_get("/api/players", page=1, size=200)
        rec_pitems = (rec_all_players or {}).get("items") or []

        rfc1, rfc2, rfc3, rfc4 = st.columns(4)
        player_opts = ["全部"] + [f"{p['id']} - {p['name']}" for p in rec_pitems]
        rf_pid = rfc1.selectbox("球员", player_opts)
        rf_start = rfc2.date_input("日期从", date.today() - timedelta(days=60), key="rec_start")
        rf_end = rfc3.date_input("日期到", date.today(), key="rec_end")
        rf_do = rfc4.button("🔍 查询", type="primary", use_container_width=True)

        rec_params = {"page": 1, "size": 200}
        if rf_pid != "全部":
            rec_params["player_id"] = int(rf_pid.split(" - ")[0])
        rec_params["start"] = str(rf_start)
        rec_params["end"] = str(rf_end)
        records_data = api_get("/api/training/records", **rec_params)
        rec_items = (records_data or {}).get("items") or (records_data if isinstance(records_data, list) else [])

        st.markdown(f"**共 {len(rec_items)} 条训练记录**")
        if rec_items:
            rec_rows = []
            for rec in rec_items:
                pname = "-"
                if rec.get("player_id"):
                    matched = next((p for p in rec_pitems if p["id"] == rec["player_id"]), None)
                    if matched:
                        pname = matched["name"]
                    else:
                        pname = f"#{rec['player_id']}"
                rec_rows.append({
                    "ID": rec["id"],
                    "球员": pname,
                    "日期": rec.get("training_date") or "-",
                    "跑动距离(米)": rec.get("distance", 0),
                    "时长(分钟)": rec.get("duration", 0),
                })
            st.markdown(md_table(rec_rows), unsafe_allow_html=True)
        else:
            st.info("暂无训练记录")

        st.markdown("---")
        col_new, col_edit = st.columns(2)

        # 新增训练记录
        col_new.subheader("➕ 新增训练记录")
        with col_new.form("add_training_rec"):
            if rec_pitems:
                atr_opts = [f"{p['id']} - {p['name']}" for p in rec_pitems]
                atr_p = st.selectbox("球员", atr_opts)
                atr_pid = int(atr_p.split(" - ")[0])
            else:
                atr_pid = None
                st.info("暂无球员，请先创建")
            atr_date = st.date_input("训练日期", date.today())
            atr_dist = st.number_input("跑动距离(米)", 0, 20000, 5000, step=100)
            atr_dur = st.number_input("训练时长(分钟)", 0, 300, 90, step=5)
            if st.form_submit_button("创建记录", type="primary"):
                if atr_pid is None:
                    st.error("请先创建球员")
                else:
                    res = api_call("POST", "/api/training/records", json_body={
                        "player_id": atr_pid,
                        "training_date": str(atr_date),
                        "distance": float(atr_dist),
                        "duration": int(atr_dur),
                    })
                    if res:
                        st.success(f"训练记录创建成功（ID={res['id']}）")
                        st.rerun()

        # 编辑/删除训练记录
        col_edit.subheader("✏️ 编辑/删除记录")
        if rec_items:
            rec_opts = [f"{r['id']} - #{r.get('player_id','-')} ({r.get('training_date','-')})" for r in rec_items]
            sel_rec = col_edit.selectbox("选择记录ID", rec_opts)
            if sel_rec:
                rid = int(sel_rec.split(" - ")[0])
                single_rec = next((r for r in rec_items if r["id"] == rid), None)
                if not single_rec:
                    single_rec = api_get(f"/api/training/records/{rid}")
                if single_rec:
                    with col_edit.form(f"edit_rec_{rid}"):
                        cur_pid = single_rec.get("player_id")
                        etr_opts = [f"{p['id']} - {p['name']}" for p in rec_pitems]
                        etr_idx = 0
                        if cur_pid and etr_opts:
                            for i, opt in enumerate(etr_opts):
                                if int(opt.split(" - ")[0]) == cur_pid:
                                    etr_idx = i
                                    break
                        etr_p = st.selectbox("球员", etr_opts or ["- 无 -"], index=etr_idx if etr_opts else 0)
                        cur_td = single_rec.get("training_date")
                        try:
                            etr_date = st.date_input("训练日期", date.fromisoformat(str(cur_td)[:10]))
                        except Exception:
                            etr_date = st.date_input("训练日期", date.today())
                        etr_dist = st.number_input("跑动距离(米)", 0, 20000, int(float(single_rec.get("distance") or 0)), step=100)
                        etr_dur = st.number_input("时长(分钟)", 0, 300, int(single_rec.get("duration") or 0), step=5)
                        col_sv, col_del = st.columns(2)
                        if col_sv.form_submit_button("💾 保存", type="primary"):
                            if etr_opts and etr_p != "- 无 -":
                                etr_pid = int(etr_p.split(" - ")[0])
                                res = api_call("PUT", f"/api/training/records/{rid}", json_body={
                                    "player_id": etr_pid,
                                    "training_date": str(etr_date),
                                    "distance": float(etr_dist),
                                    "duration": int(etr_dur),
                                })
                                if res:
                                    st.success("记录已更新")
                                    st.rerun()
                        if col_del.form_submit_button("🗑️ 删除"):
                            res = api_call("DELETE", f"/api/training/records/{rid}")
                            if res:
                                st.success("记录已删除")
                                st.rerun()

    # ========================= Tab C：一键导入训练记录 =========================
    with tab_import:
        st.subheader("📥 批量导入训练记录")
        t_file = st.file_uploader("上传训练记录 CSV/Excel", type=["csv", "xlsx"], key="train_upload")
        if t_file:
            rows, err = parse_upload_file(t_file)
            if err:
                st.error(err)
            elif rows:
                st.markdown(f"**读取到 {len(rows)} 行数据**")
                train_all_p = api_get("/api/players", page=1, size=300)
                train_pitems = (train_all_p or {}).get("items") or []
                pname_map = {}
                for p in train_pitems:
                    pname_map[str(p["name"]).strip().lower()] = p["id"]

                field_aliases = {
                    "player_id": ["球员ID", "球员id"],
                    "player_name": ["球员姓名", "球员", "姓名"],
                    "training_date": ["训练日期", "日期", "训练时间"],
                    "distance": ["跑动距离", "距离", "distance", "米数"],
                    "duration": ["训练时长", "时长", "时间", "分钟"],
                }
                mapped, matched = match_columns(rows, field_aliases)
                st.markdown(f"**匹配字段**：{', '.join(matched)}")
                if not matched:
                    st.warning("未匹配到任何字段")
                else:
                    processed = []
                    warn_msgs = []
                    for idx, row in enumerate(mapped, start=1):
                        pid = row.get("player_id")
                        pname = row.get("player_name")
                        final_pid = None
                        if pid:
                            try:
                                final_pid = int(pid)
                            except Exception:
                                pass
                        if final_pid is None and pname:
                            key = str(pname).strip().lower()
                            if key in pname_map:
                                final_pid = pname_map[key]
                            else:
                                warn_msgs.append(f"第{idx}行：找不到球员 '{pname}'")
                                continue
                        if final_pid is None:
                            warn_msgs.append(f"第{idx}行：缺少球员信息")
                            continue
                        td = _to_date(row.get("training_date"))
                        if not td:
                            warn_msgs.append(f"第{idx}行：日期无效")
                            continue
                        dist = _to_float(row.get("distance"))
                        dur = _to_int(row.get("duration"))
                        if dist is None:
                            warn_msgs.append(f"第{idx}行：跑动距离无效")
                            continue
                        if dur is None:
                            warn_msgs.append(f"第{idx}行：时长无效")
                            continue
                        processed.append({
                            "player_id": final_pid,
                            "training_date": td,
                            "distance": float(dist),
                            "duration": int(dur),
                        })

                    if warn_msgs:
                        with st.expander(f"⚠️ 警告/跳过（{len(warn_msgs)} 条）"):
                            for w in warn_msgs:
                                st.warning(w)

                    if processed:
                        st.markdown(f"**将导入 {len(processed)} 条记录，预览前 3 条：**")
                        preview = []
                        for r in processed[:3]:
                            pn = "-"
                            for p in train_pitems:
                                if p["id"] == r["player_id"]:
                                    pn = p["name"]
                                    break
                            preview.append({
                                "球员": pn,
                                "日期": r["training_date"],
                                "距离(米)": r["distance"],
                                "时长(分)": r["duration"],
                            })
                        st.markdown(md_table(preview), unsafe_allow_html=True)
                        if st.checkbox("确认无误，提交导入训练记录", key="t_import_confirm"):
                            with st.spinner("导入中..."):
                                result = batch_import("/api/training/records", processed, create_required=["player_id", "training_date", "distance", "duration"])
                            st.success(f"✅ 导入完成：成功 {result['success']} 条，失败 {result['failed']} 条")
                            if result["errors"]:
                                with st.expander(f"查看 {len(result['errors'])} 条错误"):
                                    for e in result["errors"]:
                                        st.warning(e)
                            st.rerun()


# ============================== 页面六：导出报表 ==============================
def page_export():
    page_title("📤 导出报表")
    today = date.today()
    month_start = today.replace(day=1)
    col1, col2 = st.columns(2)
    start = col1.date_input("开始日期", month_start, key="exp_start")
    end = col2.date_input("结束日期", today, key="exp_end")

    st.subheader("选择报表类型")
    report_type = st.radio("报表类型", ["🧾 训练数据报表", "🏟️ 比赛数据报表"], label_visibility="collapsed")

    if st.button("🚀 生成报表", type="primary"):
        rtype = "training" if "训练" in report_type else "match"
        res = api_call("POST", "/api/training/export", json_body={
            "start": str(start), "end": str(end), "report_type": rtype,
        })
        if res:
            task_id = res["task_id"]
            st.success(f"任务已提交：{task_id}")
            progress = st.progress(0, text="正在生成报表...")
            for i in range(10):
                import time
                time.sleep(0.5)
                r = api_get(f"/api/training/export/{task_id}")
                if r and r.get("status") == "done":
                    progress.progress(100, text="✅ 生成完成")
                    st.success("报表已生成！")
                    fp = r.get("file_path", "")
                    if fp:
                        st.code(fp)
                        try:
                            with open(fp, "rb") as f:
                                fname = Path(fp).name
                                st.download_button("📥 下载报表", f, file_name=fname)
                        except Exception:
                            st.info(f"文件路径：{fp}")
                    return
                progress.progress((i + 1) * 10, text=f"生成中... ({(i+1)*10}%)")
            st.warning("后台生成中，请稍后刷新查看")


# ============================== 主入口 ==============================
def main():
    st.set_page_config(page_title="青训数据管理", page_icon="⚽", layout="wide")
    inject_theme()

    if "nav" not in st.session_state:
        st.session_state.nav = "dashboard"

    with st.sidebar:
        st.markdown('<div class="brand-title">⚽ 青训数据管理</div><div class="brand-sub">Youth Training Manager</div>', unsafe_allow_html=True)
        st.markdown("<hr style='border:none;border-top:1px solid #e3e3e3;margin:14px 0'/>", unsafe_allow_html=True)
        menus = [
            ("dashboard", "📊", "数据总览"),
            ("players", "👥", "球员管理"),
            ("matches", "🏟️", "比赛管理"),
            ("schedule", "📅", "赛程与对手"),
            ("statistics", "📈", "训练统计"),
            ("export", "📤", "导出报表"),
        ]
        for key, icon, label in menus:
            active = st.session_state.nav == key
            arrow = "▸ " if active else "　"
            if st.button(f"{arrow}{icon}  {label}", key=f"nav_{key}", type="primary" if active else "secondary", use_container_width=True):
                st.session_state.nav = key
                st.rerun()
        st.markdown('<div class="side-copyright">© 2026 青训管理系统 v2.0</div>', unsafe_allow_html=True)

    if Path(ASSETS / "banner.jpg").exists():
        st.image(str(ASSETS / "banner.jpg"), use_container_width=True)

    pages = {
        "dashboard": page_dashboard,
        "players": page_players,
        "matches": page_matches,
        "schedule": page_schedule,
        "statistics": page_statistics,
        "export": page_export,
    }
    pages.get(st.session_state.nav, page_dashboard)()


if __name__ == "__main__":
    main()
