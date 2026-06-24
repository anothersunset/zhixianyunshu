"""一次性迁移脚本：从三处硬编码 KB 迁移到统一 YAML 格式。

Usage:
    cd zhixianyunshu && python -m kb.cli
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

# 确保项目根在 path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "eval"))

from kb.kb_loader import extract_terms

ACTIVE_DIR = PROJECT_ROOT / "kb" / "active"


def load_index_kb_docs() -> List[Dict[str, Any]]:
    """从 eval/index_kb.py 加载 KB_DOCS（最完整的 50+ 条）。"""
    from index_kb import KB_DOCS, DEMO_DOCS
    docs = list(KB_DOCS) + list(DEMO_DOCS)
    # 标准化 meta 字段: DEMO_DOCS 用 dialect 而非 source_dialect/target_dialect
    for d in docs:
        meta = d.setdefault("meta", {})
        if "source_dialect" not in meta and "dialect" in meta:
            # DEMO_DOCS 的 dialect 是目标方言名
            meta["source_dialect"] = "mysql"
            meta["target_dialect"] = meta.pop("dialect")
        # 确保有 terms 字段（给 Java mock 用）
        if "terms" not in d:
            d["terms"] = extract_terms(d["text"])
    return docs


def load_retriever_docs() -> List[Dict[str, Any]]:
    """从 retriever.py 加载 _DEMO_DOCS（28 条）。"""
    rag_app = PROJECT_ROOT / "zhiqian" / "rag" / "app"
    sys.path.insert(0, str(rag_app))
    from pipelines.retriever import _DEMO_DOCS
    docs = []
    for d in _DEMO_DOCS:
        meta = d.get("meta", {})
        new_doc = {
            "id": d["id"],
            "text": d["text"],
            "source": d.get("source", ""),
            "meta": {
                "category": meta.get("category", "MISC"),
                "source_dialect": meta.get("source_dialect",
                                           "mysql" if meta.get("dialect") in ("openGauss", "PostgreSQL") else meta.get("dialect", "mysql")),
                "target_dialect": meta.get("target_dialect",
                                           meta.get("dialect", "opengauss")),
            },
            "terms": extract_terms(d["text"]),
        }
        docs.append(new_doc)
    return docs


def merge_docs(all_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按 id 去重，index_kb 优先（它最完整）。"""
    seen: Dict[str, Dict[str, Any]] = {}
    for d in all_docs:
        did = d["id"]
        if did not in seen:
            seen[did] = d
        else:
            # 保留 text 更长的
            if len(d.get("text", "")) > len(seen[did].get("text", "")):
                seen[did] = d
    return list(seen.values())


def group_by_category(docs: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """按 meta.category 分组。"""
    category_map = {
        "SYNTAX": "kb-syntax",
        "FUNCTION": "kb-functions",
        "TYPE_MAPPING": "kb-types",
        "DDL": "kb-ddl",
        "DML": "kb-dml",
        "PLSQL": "kb-plsql",
        "QUERY": "kb-syntax",       # QUERY 归入 syntax
        "SQL_REWRITE": "kb-syntax",  # SQL_REWRITE 归入 syntax
        "CONFIG": "kb-ddl",          # CONFIG 归入 ddl
        "DEPENDENCY": "kb-ddl",      # DEPENDENCY 归入 ddl
    }
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for d in docs:
        cat = d.get("meta", {}).get("category", "MISC")
        yaml_file = category_map.get(cat, "kb-syntax")
        groups.setdefault(yaml_file, []).append(d)
    return groups


def write_yaml_files(groups: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    """写入 YAML 文件，返回文件路径列表。"""
    written = []
    for yaml_name, docs in sorted(groups.items()):
        # 从文件名推导类别名
        cat_name = yaml_name.replace("kb-", "").upper()
        yaml_docs = []
        for d in docs:
            doc_entry = {
                "id": d["id"],
                "source_dialect": d.get("meta", {}).get("source_dialect", ""),
                "target_dialect": d.get("meta", {}).get("target_dialect", ""),
                "text": d["text"],
                "source": d.get("source", ""),
                "terms": d.get("terms", extract_terms(d["text"])),
            }
            yaml_docs.append(doc_entry)

        file_path = ACTIVE_DIR / f"{yaml_name}.yaml"
        content = {
            "category": cat_name,
            "docs": yaml_docs,
        }
        # 使用 yaml.dump 生成可读的 YAML
        file_path.write_text(
            yaml.dump(content, allow_unicode=True, default_flow_style=False, sort_keys=False, width=120),
            encoding="utf-8",
        )
        written.append(str(file_path))
    return written


def main():
    print("Loading KB docs from eval/index_kb.py...")
    index_docs = load_index_kb_docs()
    print(f"  {len(index_docs)} docs from index_kb.py")

    print("Loading KB docs from retriever.py...")
    retriever_docs = []
    try:
        retriever_docs = load_retriever_docs()
        print(f"  {len(retriever_docs)} docs from retriever.py")
    except Exception as e:
        print(f"  skipped (import error: {e})")

    all_docs = index_docs + retriever_docs
    unique = merge_docs(all_docs)
    print(f"  Merged: {len(unique)} unique docs (removed {len(all_docs) - len(unique)} duplicates)")

    groups = group_by_category(unique)
    print(f"\nGrouped into {len(groups)} categories:")
    for name, docs in sorted(groups.items()):
        print(f"  {name}.yaml: {len(docs)} docs")

    written = write_yaml_files(groups)
    print(f"\nWritten {len(written)} YAML files:")
    for path in written:
        print(f"  {path}")

    # 检查 kb_loader 是否能正确加载
    print("\nVerifying with kb_loader...")
    from kb.kb_loader import load_all_docs
    loaded = load_all_docs()
    print(f"  Loaded: {len(loaded)} docs")
    assert len(loaded) == len(unique), f"Mismatch: {len(loaded)} != {len(unique)}"
    print("  [OK] Verification passed!")

    print("\nDone! KB migration complete.")


if __name__ == "__main__":
    main()
