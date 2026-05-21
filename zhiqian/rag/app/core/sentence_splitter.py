"""轻量中英文句子切分器。v2-step-06 新增。
- 不依赖 nltk / spaCy，快且趋近邶都合理。
- 保留句末标点，避免丢失语义。
"""
from __future__ import annotations
import re
from typing import List

# 中文句终：。 ！ ？ ；；英文：. ! ? ;；以及两个连续换行作为段落边界。
_SENT_BOUNDARY = re.compile(r"([\u3002\uff01\uff1f\uff1b]|[\.!?;](?=\s|$)|\n{2,})")
_WHITESPACE = re.compile(r"\s+")


def split_sentences(text: str, min_chars: int = 6) -> List[str]:
    """切句。返回去除纯空白与过短碎片后的句子列表。保留句末标点。"""
    if not text:
        return []
    parts = _SENT_BOUNDARY.split(text)
    sents: List[str] = []
    buf = ""
    for p in parts:
        if p is None:
            continue
        if _SENT_BOUNDARY.fullmatch(p):
            buf += p
            sents.append(buf.strip())
            buf = ""
        else:
            buf += p
    if buf.strip():
        sents.append(buf.strip())
    # 过滤过短片段，合并到前句
    result: List[str] = []
    for s in sents:
        s = _WHITESPACE.sub(" ", s).strip()
        if not s:
            continue
        if len(s) < min_chars and result:
            result[-1] = result[-1] + " " + s
        else:
            result.append(s)
    return result
