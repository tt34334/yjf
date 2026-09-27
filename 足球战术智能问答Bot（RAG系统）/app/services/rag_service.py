# File: app/services/rag_service.py
"""RAG 问答核心模块：Top-K 检索 -> 组装上下文 -> 调用 LLM 生成带引用标注的回答。"""
import logging

from app.config import settings
from app.core import vector_store
from app.services.llm_client import chat_completion

logger = logging.getLogger(__name__)

# 有检索结果时的系统提示词：要求回答中用 [编号] 标注引用
SYSTEM_PROMPT_WITH_CONTEXT = """你是一位专业的足球战术分析师。请严格根据下面提供的参考资料回答用户问题，并遵循以下规则：
1. 使用中文回答，条理清晰，可以使用 Markdown 排版；
2. 引用参考资料时，请在对应结论的句末使用 [编号] 标注来源（编号即资料前的序号），例如 [1]；
3. 只依据参考资料作答，不要编造资料中不存在的内容；
4. 如果资料不足以完整回答问题，请如实说明，并可基于可靠的足球战术知识做适当补充，补充部分无需标注引用；
5. 不要在回答末尾重复罗列参考资料。"""

# 无检索结果时的系统提示词：明确告知用户回答基于模型自身知识
SYSTEM_PROMPT_NO_CONTEXT = """你是一位专业的足球战术分析师。当前知识库中没有检索到与用户问题相关的资料，请基于你掌握的足球战术知识用中文回答，并在回答开头注明"（提示：知识库中未检索到相关内容，以下回答基于模型自身知识）"。"""


def build_context(hits: list[dict]) -> tuple[str, list[dict]]:
    """将检索结果组装为带编号的上下文文本，并生成对应的来源列表。

    :param hits: 检索到的文档块列表
    :return: (上下文文本, 来源信息列表)
    """
    blocks: list[str] = []
    sources: list[dict] = []
    for i, hit in enumerate(hits, start=1):
        blocks.append(
            f"[{i}]（来源：{hit['filename']} · 第 {hit['chunk_index'] + 1} 段）\n{hit['text']}"
        )
        sources.append(
            {
                "index": i,
                "doc_id": hit["doc_id"],
                "doc_name": hit["filename"],
                "chunk_index": hit["chunk_index"],
                "snippet": hit["text"][:120] + ("..." if len(hit["text"]) > 120 else ""),
                "score": hit["score"],
            }
        )
    return "\n\n".join(blocks), sources


def answer_question(question: str) -> dict:
    """RAG 主流程：检索 Top-K 相关文档块，作为上下文调用 LLM 生成回答。

    :param question: 用户问题
    :return: {"question": 问题, "answer": 回答, "sources": 引用来源列表}
    :raises LLMError: LLM 未配置或调用失败
    """
    question = question.strip()
    if not question:
        raise ValueError("问题不能为空")

    # 1. 向量检索 Top-K
    hits = vector_store.search(question, top_k=settings.TOP_K)
    logger.info("问题「%s」检索到 %d 个相关文档块", question, len(hits))

    # 2. 组装上下文并调用 LLM
    if hits:
        context, sources = build_context(hits)
        user_prompt = f"参考资料：\n\n{context}\n\n---\n用户问题：{question}"
        answer = chat_completion(SYSTEM_PROMPT_WITH_CONTEXT, user_prompt)
    else:
        sources = []
        answer = chat_completion(SYSTEM_PROMPT_NO_CONTEXT, f"用户问题：{question}")

    return {"question": question, "answer": answer, "sources": sources}
