"""noise_floor.compare_runs 自检：用合成数据验证噪声地板计算逻辑本身正确。

真实用法需要真的跑两次评测（见 noise_floor.py 顶部文档），这里只验证比较函数本身
不出错——包括零假设最重要的性质：两份完全相同的结果，噪声地板必须是 0。
"""
from __future__ import annotations

from eval.noise_floor import compare_runs


def _row(cid: str, sql_ok: bool, recall: float, mrr: float) -> dict:
    return {"id": cid, "sql_ok": sql_ok, "recall@5": recall, "mrr@10": mrr}


class TestCompareRuns:
    def test_identical_runs_have_zero_noise_floor(self):
        rows = [_row("c1", True, 0.8, 0.5), _row("c2", False, 0.4, 0.2)]
        stats = compare_runs(rows, rows)
        assert stats["sql_ok"]["flip_rate"] == 0.0
        assert stats["sql_ok"]["rate_delta"] == 0.0
        assert stats["recall@5"]["mean_abs_diff"] == 0.0
        assert stats["mrr@10"]["mean_delta"] == 0.0

    def test_completely_different_runs_show_full_flip_rate(self):
        rows_a = [_row("c1", True, 1.0, 1.0), _row("c2", True, 1.0, 1.0)]
        rows_b = [_row("c1", False, 0.0, 0.0), _row("c2", False, 0.0, 0.0)]
        stats = compare_runs(rows_a, rows_b)
        assert stats["sql_ok"]["flip_rate"] == 1.0
        assert stats["sql_ok"]["rate_delta"] == 1.0
        assert stats["recall@5"]["mean_abs_diff"] == 1.0

    def test_partial_noise_is_captured(self):
        # 10 个 case，1 个翻转 -> flip_rate 应为 0.1
        rows_a = [_row(f"c{i}", True, 0.8, 0.5) for i in range(10)]
        rows_b = [_row(f"c{i}", True, 0.8, 0.5) for i in range(9)] + [_row("c9", False, 0.8, 0.5)]
        stats = compare_runs(rows_a, rows_b)
        assert stats["sql_ok"]["flip_rate"] == 0.1

    def test_no_common_ids_reports_error_not_crash(self):
        rows_a = [_row("a1", True, 1.0, 1.0)]
        rows_b = [_row("b1", True, 1.0, 1.0)]
        stats = compare_runs(rows_a, rows_b)
        assert stats["n"] == 0
        assert "error" in stats

    def test_none_metric_values_are_excluded_not_treated_as_zero(self):
        rows_a = [{"id": "c1", "sql_ok": True, "recall@5": None}]
        rows_b = [{"id": "c1", "sql_ok": True, "recall@5": 0.9}]
        stats = compare_runs(rows_a, rows_b)
        assert stats["recall@5"]["n"] == 0  # 一边为 None，不该被当成 0 参与计算
