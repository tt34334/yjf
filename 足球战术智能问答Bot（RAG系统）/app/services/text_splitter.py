# File: app/services/text_splitter.py
"""文本分块模块：按 段落 -> 句子 -> 字符 的层级切分，相邻分块携带 overlap 重叠。

默认参数：chunk_size=500（字符）、overlap=50（字符），可在 .env 中调整。
"""
import re

from app.config import settings


def _hard_split(text: str, max_len: int) -> list[str]:
    """按固定字符数硬切文本（兜底策略，处理无标点的超长内容）。"""
    return [text[i : i + max_len] for i in range(0, len(text), max_len)]


def _split_long_unit(unit: str, max_len: int) -> list[str]:
    """将超过 max_len 的文本单元按句子边界二次切分，句子仍过长则按字符硬切。"""
    if len(unit) <= max_len:
        return [unit]
    parts: list[str] = []
    buf = ""
    # 在中英文句末标点/换行后切句（保留标点）
    sentences = [s for s in re.split(r"(?<=[。！？!?；;\n])\s*", unit) if s]
    for sentence in sentences:
        if len(sentence) > max_len:
            # 单个句子超长：先落盘缓冲，再硬切该句
            if buf:
                parts.append(buf)
                buf = ""
            parts.extend(_hard_split(sentence, max_len))
        elif len(buf) + len(sentence) <= max_len:
            buf += sentence
        else:
            parts.append(buf)
            buf = sentence
    if buf:
        parts.append(buf)
    return parts


def split_text(text: str) -> list[str]:
    """将原始文本切分为大小合适、首尾重叠的分块列表。

    切分策略：
    1. 以空行/换行为界切出段落，超长段落按句子二次切分；
    2. 贪心合并段落单元，生成不超过 chunk_size 的分块；
    3. 每个新分块开头保留上一分块末尾 overlap 个字符，保证跨块上下文连续。
    """
    chunk_size = settings.CHUNK_SIZE
    overlap = max(0, settings.CHUNK_OVERLAP)
    text = re.sub(r"\r\n?", "\n", text).strip()
    if not text:
        return []

    # 1. 段落级切分（以空行分段，段内按行合并）
    units: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        lines = [ln.strip() for ln in para.split("\n") if ln.strip()]
        units.extend(_split_long_unit("\n".join(lines), chunk_size))
    if not units:
        return []

    # 2. 贪心合并单元生成分块，块间携带 overlap
    chunks: list[str] = []
    current = ""
    for unit in units:
        if not current:
            current = unit
        elif len(current) + 1 + len(unit) <= chunk_size:
            current += "\n" + unit
        else:
            chunks.append(current)
            # 新块开头拼接上一块尾部 overlap 字符（携带上文语境）
            tail = current[-overlap:] if overlap > 0 and len(current) >= overlap else ""
            current = f"{tail}\n{unit}" if tail else unit
    if current:
        chunks.append(current)
    return chunks
