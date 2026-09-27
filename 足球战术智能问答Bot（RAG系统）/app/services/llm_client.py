# File: app/services/llm_client.py
"""LLM 调用模块：通过 OpenAI 兼容接口调用 DeepSeek / 通义千问 / OpenAI / Kimi / Ollama 等。

支持 Mock 模式（LLM_MOCK_MODE=true）：不请求外部 LLM，基于检索上下文生成
带 [n] 引用标注的模拟回答，用于在未配置真实 API Key 时验证问答链路。
"""
import re

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)

from app.config import settings


class LLMError(Exception):
    """LLM 配置缺失或调用失败的自定义异常（携带用户可读的中文提示）。"""


def _mock_completion(user_prompt: str) -> str:
    """Mock 模式实现：解析上下文中的编号资料块，生成固定格式的验证用回答。"""
    blocks = re.findall(r"^\[(\d+)\]（来源：.+?）\n(.+)$", user_prompt, flags=re.MULTILINE)
    lines = ["**（Mock 模式回答：未调用真实 LLM，仅用于验证问答链路与引用展示）**", ""]
    if blocks:
        lines.append("根据知识库检索结果，各引用来源的首句内容归纳如下：")
        lines.append("")
        for num, text in blocks:
            snippet = re.sub(r"\s+", " ", text.strip())[:80]
            lines.append(f"- 资料 {num} 开头内容：{snippet}…… [{num}]")
        lines.append("")
        lines.append("以上回答中的 [n] 标记应在前端被高亮展示，并可与下方引用来源一一对应。")
    else:
        lines.append("当前为 Mock 模式，且知识库中未检索到相关资料，此回答用于验证无引用场景。")
    return "\n".join(lines)


def chat_completion(system_prompt: str, user_prompt: str) -> str:
    """调用 LLM 生成回答文本。

    :param system_prompt: 系统提示词（角色与规则约束）
    :param user_prompt: 用户提示词（参考资料 + 问题）
    :return: 模型生成的回答文本
    :raises LLMError: 未配置 API Key 或调用失败
    """
    if settings.LLM_MOCK_MODE:
        return _mock_completion(user_prompt)

    if not settings.OPENAI_API_KEY:
        raise LLMError(
            "未配置 OPENAI_API_KEY，请复制 .env.example 为 .env 并填入 API Key 后重启服务"
        )

    client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        timeout=settings.LLM_TIMEOUT,
    )
    try:
        resp = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=settings.LLM_TEMPERATURE,
        )
        return (resp.choices[0].message.content or "").strip()
    except AuthenticationError:
        raise LLMError("LLM 鉴权失败：API Key 无效或已过期，请检查 OPENAI_API_KEY 配置")
    except (APIConnectionError, APITimeoutError):
        raise LLMError(
            f"无法连接 LLM 服务（{settings.OPENAI_BASE_URL}），请检查网络或 OPENAI_BASE_URL 配置"
        )
    except RateLimitError:
        raise LLMError("LLM 调用触发限流，请稍后重试或检查账户配额")
    except APIStatusError as e:
        raise LLMError(f"LLM 服务返回错误（HTTP {e.status_code}）：{e.message}")
