# File: frontend/app.py
"""Streamlit 前端：足球战术智能问答 RAG 系统。

启动方式（项目根目录执行）：
    streamlit run frontend/app.py --server.port 8501
"""
import os
import re

import requests
import streamlit as st

st.set_page_config(page_title="足球战术智能问答", page_icon="⚽", layout="wide")

# 后端 API 地址（docker-compose 中通过环境变量覆盖为 http://api:8000）
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
UPLOAD_EXTS = ["pdf", "txt", "md"]


# ---------- 会话状态初始化 ----------
if "messages" not in st.session_state:
    # 每条消息: {"role": "user"|"assistant", "content": str, "sources": list|None}
    st.session_state.messages = []


# ---------- 工具函数 ----------
def highlight_citations(text: str) -> str:
    """把回答中的 [n] 引用标记替换为高亮徽标（内联 HTML）。"""
    return re.sub(
        r"\[(\d+)\]",
        r'<span style="background:#dbeafe;color:#1d4ed8;padding:1px 7px;'
        r'border-radius:10px;font-size:0.85em;font-weight:600;">[\1]</span>',
        text,
    )


def render_sources(sources: list) -> None:
    """渲染引用来源列表：文档名 + 段落序号 + 原文片段 + 相似度（高亮展示）。"""
    for s in sources:
        with st.expander(
            f"[{s['index']}] 📄 {s['doc_name']} · 第 {s['chunk_index'] + 1} 段"
            f" · 相似度 {s['score']:.0%}"
        ):
            st.markdown(f"> {s['snippet']}")


def extract_detail(resp) -> str:
    """从 API 错误响应中提取中文错误信息。"""
    if resp is None:
        return "后端服务不可用，请检查 API 是否已启动"
    try:
        return resp.json().get("detail", f"HTTP {resp.status_code}")
    except Exception:
        return f"HTTP {resp.status_code}"


def api_get(path: str, timeout: int = 30):
    """发起 GET 请求，失败时返回 None。"""
    try:
        return requests.get(f"{API_BASE}{path}", timeout=timeout)
    except requests.RequestException:
        return None


def api_post(path: str, timeout: int = 60, **kwargs):
    """发起 POST 请求，失败时返回 None。"""
    try:
        return requests.post(f"{API_BASE}{path}", timeout=timeout, **kwargs)
    except requests.RequestException:
        return None


def api_delete(path: str, timeout: int = 60):
    """发起 DELETE 请求，失败时返回 None。"""
    try:
        return requests.delete(f"{API_BASE}{path}", timeout=timeout)
    except requests.RequestException:
        return None


# ---------- 页面标题 ----------
st.title("⚽ 足球战术智能问答")
st.caption("基于 RAG（检索增强生成）的足球战术知识库系统 · 引用来源可溯源")

# ---------- 侧边栏：系统状态 ----------
with st.sidebar:
    st.header("⚙️ 系统状态")
    st.caption(f"API 地址：`{API_BASE}`")
    h = api_get("/api/health", timeout=5)
    if h is not None and h.status_code == 200:
        info = h.json()
        st.success("后端服务运行中")
        if info.get("llm_mock"):
            llm_line = "🧪 **Mock 模式**（不调用真实 LLM，仅模拟回答）"
        elif info["llm_configured"]:
            llm_line = f"已配置 `{info['llm_model']}`"
        else:
            llm_line = "⚠️ **未配置 API Key**（请在 .env 中填写 OPENAI_API_KEY）"
        st.markdown(
            f"- 文档数量：**{info['document_count']}**\n"
            f"- 向量块数：**{info['vector_count']}**\n"
            f"- LLM：{llm_line}\n"
            f"- Embedding：`{info['embedding_model']}`"
        )
    else:
        st.error("无法连接后端服务，请先启动 API：\n`uvicorn app.main:app --port 8000`")

tab_chat, tab_kb = st.tabs(["💬 智能问答", "📚 知识库管理"])

# ==================== Tab 1：智能问答 ====================
with tab_chat:
    # 渲染历史消息
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                st.markdown(highlight_citations(msg["content"]), unsafe_allow_html=True)
                if msg.get("sources"):
                    st.markdown("**📎 引用来源**")
                    render_sources(msg["sources"])
            else:
                st.markdown(msg["content"])

    question = st.chat_input("请输入你的足球战术问题，例如：什么是高位逼抢？它的优缺点是什么？")
    if question:
        # 显示用户消息
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        # 调用后端 RAG 接口并展示回答
        with st.chat_message("assistant"):
            with st.spinner("🔍 正在检索知识库并生成回答…"):
                resp = api_post("/api/chat", json={"question": question}, timeout=180)
            if resp is not None and resp.status_code == 200:
                data = resp.json()
                content, sources = data["answer"], data["sources"]
                st.markdown(highlight_citations(content), unsafe_allow_html=True)
                if sources:
                    st.markdown("**📎 引用来源**")
                    render_sources(sources)
            else:
                content, sources = f"⚠️ 请求失败：{extract_detail(resp)}", []
                st.error(content)
        st.session_state.messages.append(
            {"role": "assistant", "content": content, "sources": sources}
        )

# ==================== Tab 2：知识库管理 ====================
with tab_kb:
    st.subheader("📤 上传文档")
    st.caption("支持 PDF / TXT / Markdown，文件在本地完成解析与向量化，数据不会上传到第三方。")
    files = st.file_uploader(
        "选择要上传的足球战术文档（支持多选）", type=UPLOAD_EXTS, accept_multiple_files=True
    )
    if st.button("🚀 开始上传", type="primary", disabled=not files):
        success_msgs, fail_msgs = [], []
        progress = st.progress(0.0, text="正在上传…")
        for i, f in enumerate(files, start=1):
            resp = api_post(
                "/api/documents/upload",
                files={"file": (f.name, f.getvalue())},
                timeout=600,
            )
            if resp is not None and resp.status_code == 200:
                d = resp.json()
                success_msgs.append(f"{d['filename']}（{d['chunk_count']} 个分块）")
            else:
                fail_msgs.append(f"{f.name}：{extract_detail(resp)}")
            progress.progress(i / len(files), text=f"已处理 {i}/{len(files)}")
        if success_msgs:
            st.success("上传成功：" + "；".join(success_msgs))
        if fail_msgs:
            st.error("上传失败：" + "；".join(fail_msgs))

    st.divider()
    st.subheader("📋 文档列表")
    list_resp = api_get("/api/documents", timeout=15)
    if list_resp is None:
        st.warning("无法获取文档列表：后端服务不可用")
    elif list_resp.status_code != 200:
        st.error(f"获取文档列表失败：{extract_detail(list_resp)}")
    else:
        docs = list_resp.json()["documents"]
        if not docs:
            st.info("知识库暂无文档，请先上传，或重启 API 自动导入 sample_docs 示例文档。")
        for d in docs:
            c1, c2, c3, c4, c5 = st.columns([3, 1.2, 1, 2, 1])
            c1.markdown(f"**📄 {d['filename']}**")
            c2.markdown(f"{d['size_bytes'] / 1024:.1f} KB")
            c3.markdown(f"{d['chunk_count']} 块")
            c4.markdown(f"`{d['uploaded_at']}`")
            if c5.button("🗑️ 删除", key=f"del_{d['doc_id']}"):
                del_resp = api_delete(f"/api/documents/{d['doc_id']}")
                if del_resp is not None and del_resp.status_code == 200:
                    result = del_resp.json()
                    st.success(
                        f"已删除「{result['filename']}」，连带清理 {result['deleted_chunks']} 个向量块"
                    )
                    st.rerun()
                else:
                    st.error(f"删除失败：{extract_detail(del_resp)}")
