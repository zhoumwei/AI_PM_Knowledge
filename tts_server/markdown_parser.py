"""Markdown 解析模块 - 将 markdown 转换为适合语音朗读的文本段"""

import re
from typing import List


def markdown_to_text(md: str) -> str:
    """将 markdown 转换为纯文本，移除所有格式标记"""
    text = md

    # 移除代码块
    text = re.sub(r'```[\s\S]*?```', '', text)
    # 移除行内代码
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # 移除图片
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', '', text)
    # 移除链接，保留文本
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # 移除 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)
    # 移除标题标记
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # 移除加粗/斜体
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'~~([^~]+)~~', r'\1', text)
    # 移除引用标记
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    # 移除列表标记
    text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)
    # 移除水平分割线
    text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)
    # 移除 markdown 注释
    text = re.sub(r'<!--[\s\S]*?-->', '', text)

    # 处理表格：保留内容，去掉管道符
    lines = text.split('\n')
    filtered = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and stripped.endswith('|'):
            cells = [c.strip() for c in stripped.strip('|').split('|')]
            cells = [c for c in cells if c and not re.match(r'^[-:]+$', c)]
            if cells:
                filtered.append('，'.join(cells))
            continue
        filtered.append(line)
    text = '\n'.join(filtered)

    # 清理多余空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    # 行首尾去空格
    text = '\n'.join(line.strip() for line in text.split('\n'))
    return text.strip()


def split_into_segments(text: str, max_length: int = 200) -> List[dict]:
    """将文本分割为朗读段，返回 [{index, text, length}] 列表

    策略：先按段落分割，超长段落再按句子拆分
    """
    paragraphs = text.split('\n\n')
    segments = []
    idx = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(para) <= max_length:
            segments.append({"index": idx, "text": para, "length": len(para)})
            idx += 1
        else:
            # 长段落按句子拆分
            sentences = re.split(r'(?<=[。！？\n.!?])', para)
            current = ""
            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue
                if len(current) + len(sent) <= max_length:
                    current += sent
                else:
                    if current:
                        segments.append({"index": idx, "text": current, "length": len(current)})
                        idx += 1
                    current = sent
            if current:
                segments.append({"index": idx, "text": current, "length": len(current)})
                idx += 1

    return segments
