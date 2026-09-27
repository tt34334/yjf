# File: app/services/document_parser.py
"""文档解析模块：支持 PDF / TXT / Markdown 三种格式的文本提取。"""
import io
from pathlib import Path

from pypdf import PdfReader


def parse_pdf(data: bytes) -> str:
    """解析 PDF 文件，按页提取并拼接文本。"""
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as e:
        raise ValueError(f"PDF 文件解析失败，文件可能已损坏：{e}")
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text.strip())
    text = "\n\n".join(pages)
    if not text.strip():
        raise ValueError(
            "无法从 PDF 中提取到文本，文件可能是扫描件或纯图片 PDF，请先进行 OCR 处理"
        )
    return text


def parse_text_like(data: bytes) -> str:
    """读取 TXT / Markdown 文本，依次尝试常见编码（兼容中文 GBK 系编码）。"""
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    raise ValueError("无法识别文件编码，请使用 UTF-8 编码的文本文件")


def parse_document(filename: str, data: bytes) -> str:
    """根据文件扩展名分发到对应解析器，返回提取的原始文本。

    :param filename: 原始文件名（用于判断格式）
    :param data: 文件二进制内容
    :return: 提取出的文本
    :raises ValueError: 格式不支持 / 内容为空 / 解析失败
    """
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(data)
    if suffix in (".txt", ".md", ".markdown"):
        return parse_text_like(data)
    raise ValueError(f"不支持的文件格式「{suffix or '(无后缀)'}」，仅支持 PDF / TXT / Markdown")
