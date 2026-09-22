"""ablation 汇总守卫: 某组失败被 continue 跳过时, to_markdown 输出 skipped 占位行而非 KeyError 崩溃。"""
from __future__ import annotations

from eval.ablation import RETRIEVAL_CHOICES, to_markdown


def test_to_markdown_placeholder_for_missing_groups():
    """缺失组 (后端不可用被跳过) 输出 skipped 占位, 不抛 KeyError。"""
    table = {
        "bm25": {
            "summary": {"recall@5": 0.5, "sql_repair_rate": 0.4, "report_accuracy": 0.9, "n": 10},
            "rows": [],
        },
    }
    md = to_markdown(table)
    lines = md.splitlines()
    # 表头 + 分隔线 + 每组一行 (5 组全展示)
    assert len(lines) == 2 + len(RETRIEVAL_CHOICES)
    assert "skipped" in md
    # 已完成组的数字仍正常展示
    bm25_line = next(line for line in lines if line.startswith("| A"))
    assert "0.5000" in bm25_line
    assert "0.4" in bm25_line
    # 缺失组的行确实标记 skipped 且 n=0
    missing_line = next(line for line in lines if line.startswith("| E"))
    assert "skipped" in missing_line
    assert missing_line.rstrip().endswith("| 0 |")


def test_to_markdown_empty_table_does_not_crash():
    """整轮全失败 (table 为空) 也不崩溃, 5 组全部 skipped。"""
    md = to_markdown({})
    skipped_lines = [line for line in md.splitlines() if "| skipped |" in line]
    assert len(skipped_lines) == len(RETRIEVAL_CHOICES)


def test_to_markdown_malformed_entry_treated_as_missing():
    """entry 结构异常 (缺 summary/非 dict) 同样按缺失处理。"""
    table = {r: "garbage" for r in RETRIEVAL_CHOICES}
    table["bm25"] = {"rows": []}  # 有 entry 但没 summary
    md = to_markdown(table)
    lines = md.splitlines()
    assert len(lines) == 2 + len(RETRIEVAL_CHOICES)
    # 除了 bm25 外全是 skipped
    skipped_lines = [line for line in lines if "skipped" in line]
    assert len(skipped_lines) == len(RETRIEVAL_CHOICES)
