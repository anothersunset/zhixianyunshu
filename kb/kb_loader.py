"""统一 KB 加载器 — 所有 Python 消费者读取 KB 的唯一入口。

从 kb/active/*.yaml 加载知识库文档，返回与现有代码兼容的字典列表。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

KB_DIR = Path(__file__).resolve().parent / "active"


def load_all_docs() -> List[Dict[str, Any]]:
    """加载所有 KB 文档，返回扁平列表。"""
    docs: List[Dict[str, Any]] = []
    for yf in sorted(KB_DIR.glob("kb-*.yaml")):
        data = _read_yaml(yf)
        if not data:
            continue
        category = data.get("category", "MISC")
        for doc in data.get("docs", []):
            if "category" not in doc:
                doc["category"] = category
            docs.append(doc)
    return docs


def load_docs_for_dialect(source_dialect: str) -> List[Dict[str, Any]]:
    """加载特定源方言的 KB 文档。"""
    return [
        d for d in load_all_docs()
        if d.get("source_dialect") in (source_dialect, "any", None)
    ]


def load_recipes() -> List[Dict[str, Any]]:
    """加载翻译配方（从 recipes.yaml）。"""
    recipes_file = KB_DIR / "recipes.yaml"
    data = _read_yaml(recipes_file)
    return data.get("recipes", []) if data else []


def load_dialect_config(dialect: str) -> Optional[Dict[str, Any]]:
    """加载方言配置（从 dialects/<name>.yaml）。"""
    config_file = KB_DIR / "dialects" / f"{dialect}.yaml"
    return _read_yaml(config_file)


def extract_terms(text: str, max_terms: int = 8) -> str:
    """从 KB 文档文本中提取关键词（用于 Java mock fallback 的关键词匹配）。"""
    # 提取技术 token: SQL 关键字、函数名、中文词组
    sql_tokens = re.findall(r'[A-Z_][A-Z0-9_]{2,}', text)
    chinese_tokens = re.findall(r'[\u4e00-\u9fff]{2,}', text)
    # 去重、取前 N 个
    seen = set()
    terms = []
    for t in sql_tokens + chinese_tokens:
        lower = t.lower()
        if lower not in seen:
            seen.add(lower)
            terms.append(lower)
            if len(terms) >= max_terms:
                break
    return " ".join(terms)


def _read_yaml(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None
