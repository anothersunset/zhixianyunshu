"""指标自检——不测业务代码，测"指标本身是否在测量它自称测量的东西"。

背景：消融实验梯度失真的一个根因是指标饱和（集合型 Recall 测不出排序变化），这批测试
把当时手工验证过的判别力断言固化下来，防止未来改动 metrics.py 时无声地退化回同样的
坑。见 docs/devlog-2026-07-09-p0-p1-audit.md 与 eval/README.md 的"消融梯度失真"一节。
"""
from __future__ import annotations

import math

from eval.metrics import discrimination_stats, mrr_at_k, recall_at_k, sql_equivalent


class TestRecallSaturatesButMrrDiscriminates:
    """核心断言：命中集合相同、排序不同时，Recall 应该"看不出"差异而 MRR 应该看得出。

    这不是巧合，是 Recall@k（集合型）与 MRR@k（排序敏感型）的定义决定的。如果这个
    测试哪天失败了，说明某次"优化"改坏了 MRR 的排序敏感性，消融又会退回到只能靠
    Recall 判断、而 Recall 在小文档池场景下测不出 rerank/CRAG 贡献的老问题。
    """

    gold = ["d3"]
    hit_at_rank_1 = ["d3", "d1", "d2", "d4", "d5"]
    hit_at_rank_5 = ["d1", "d2", "d4", "d5", "d3"]

    def test_recall_is_identical_regardless_of_rank(self):
        # 两种排序的 top-5 命中集合完全相同 -> Recall@5 必须相同（这是"饱和"的数学原因）
        assert recall_at_k(self.hit_at_rank_1, self.gold, k=5) == \
            recall_at_k(self.hit_at_rank_5, self.gold, k=5) == 1.0

    def test_mrr_discriminates_the_same_two_orderings(self):
        # 而 MRR@10 必须能分辨出命中在第 1 位还是第 5 位
        mrr_early = mrr_at_k(self.hit_at_rank_1, self.gold, k=10)
        mrr_late = mrr_at_k(self.hit_at_rank_5, self.gold, k=10)
        assert mrr_early == 1.0
        assert mrr_late == 0.2
        assert mrr_early > mrr_late


class TestMrrAtKEdgeCases:
    def test_no_gold_ids_returns_nan(self):
        assert math.isnan(mrr_at_k(["a", "b"], [], k=10))

    def test_miss_returns_zero_not_none(self):
        assert mrr_at_k(["x", "y", "z"], ["gold-doc"], k=10) == 0.0

    def test_hit_outside_k_counts_as_miss(self):
        # 命中在第 11 位，k=10 应该看不到——排序敏感不等于无视截断
        retrieved = [f"noise-{i}" for i in range(10)] + ["gold-doc"]
        assert mrr_at_k(retrieved, ["gold-doc"], k=10) == 0.0


class TestRecallAtKEdgeCases:
    def test_no_gold_ids_returns_nan(self):
        assert math.isnan(recall_at_k(["a", "b"], [], k=5))

    def test_partial_hit_is_fractional(self):
        # gold 有 2 个，只命中 1 个 -> 0.5，不是布尔值
        assert recall_at_k(["g1", "x", "y"], ["g1", "g2"], k=5) == 0.5


class TestDiscriminationStats:
    """跨模式判别力检查：识别"两组指标看着不同，其实只是均值被少数 case 拉动"的假梯度。"""

    def test_all_identical_flags_full_saturation(self):
        rows_a = [{"id": "c1", "recall@5": 0.8}, {"id": "c2", "recall@5": 0.6}]
        rows_b = [{"id": "c1", "recall@5": 0.8}, {"id": "c2", "recall@5": 0.6}]
        stats = discrimination_stats(rows_a, rows_b, "recall@5")
        assert stats["n"] == 2
        assert stats["identical"] == 2
        assert stats["identical_pct"] == 1.0

    def test_all_different_flags_zero_saturation(self):
        rows_a = [{"id": "c1", "recall@5": 0.8}, {"id": "c2", "recall@5": 0.6}]
        rows_b = [{"id": "c1", "recall@5": 0.4}, {"id": "c2", "recall@5": 1.0}]
        stats = discrimination_stats(rows_a, rows_b, "recall@5")
        assert stats["identical"] == 0
        assert stats["identical_pct"] == 0.0

    def test_no_common_ids_returns_none_not_crash(self):
        rows_a = [{"id": "c1", "recall@5": 0.8}]
        rows_b = [{"id": "c2", "recall@5": 0.8}]
        stats = discrimination_stats(rows_a, rows_b, "recall@5")
        assert stats["n"] == 0
        assert stats["identical_pct"] is None

    def test_missing_metric_key_treated_as_none_and_compared(self):
        # 两边都没算过这个指标（都是 None）也应算作"相同"，而不是抛异常
        rows_a = [{"id": "c1"}]
        rows_b = [{"id": "c1"}]
        stats = discrimination_stats(rows_a, rows_b, "mrr@10")
        assert stats["identical"] == 1


class TestSqlEquivalentSanity:
    """sql_equivalent 是所有下游指标（sql_repair_rate 等）的地基。这里不追求全面，只放
    几个"如果这个都判断错了，说明整套等价逻辑已经坏掉"级别的冒烟断言。
    """

    def test_identical_sql_is_equivalent(self):
        sql = "SELECT id, name FROM users WHERE age > 18"
        assert sql_equivalent(sql, sql, "postgresql") is True

    def test_ifnull_and_coalesce_are_semantically_equivalent(self):
        # MySQL IFNULL -> PostgreSQL/openGauss COALESCE 是标准转换，必须判等价
        pred = "SELECT COALESCE(name, 'x') FROM users"
        gold = "SELECT COALESCE(name, 'x') FROM users"
        assert sql_equivalent(pred, gold, "opengauss") is True

    def test_clearly_different_sql_is_not_equivalent(self):
        pred = "SELECT id FROM users"
        gold = "DELETE FROM users WHERE id = 1"
        assert sql_equivalent(pred, gold, "postgresql") is False
