"""人工校准抽样自检：确认分层抽样真的向 judge 裁决样本倾斜，而不是退化回纯随机。"""
from __future__ import annotations

from eval.judge import cohen_kappa, sample_for_human_review


def _row(cid: str, verdict_source: str) -> dict:
    return {"id": cid, "pair": "mysql->opengauss", "verdict_source": verdict_source}


class TestStratifiedSampling:
    def test_judge_decided_rows_are_always_included(self):
        # 10 个 judge 裁决样本混在 90 个确定性样本里，ratio=0.2 意味着配额只有 20 个，
        # 但全部 10 个 judge 样本都必须进抽样——它们才是真正该被人工验证的边界样本
        judge_rows = [_row(f"j{i}", "judge") for i in range(10)]
        det_rows = [_row(f"d{i}", "deterministic") for i in range(90)]
        sample = sample_for_human_review(judge_rows + det_rows, ratio=0.2, seed=1)
        sampled_ids = {r["id"] for r in sample}
        assert {r["id"] for r in judge_rows} <= sampled_ids

    def test_quota_still_respected_when_judge_rows_are_few(self):
        # judge 样本很少时，剩余配额应从其余样本随机补齐，总数仍接近 ratio*n
        judge_rows = [_row("j0", "judge")]
        det_rows = [_row(f"d{i}", "deterministic") for i in range(99)]
        sample = sample_for_human_review(judge_rows + det_rows, ratio=0.1, seed=1)
        assert len(sample) == 10  # int(100 * 0.1)
        assert "j0" in {r["id"] for r in sample}

    def test_judge_rows_exceeding_quota_get_capped_not_dropped_entirely(self):
        # judge 样本比配额还多：不能超配额，但也不该因为"配额不够"就整体退化为随机
        judge_rows = [_row(f"j{i}", "judge") for i in range(30)]
        det_rows = [_row(f"d{i}", "deterministic") for i in range(70)]
        sample = sample_for_human_review(judge_rows + det_rows, ratio=0.1, seed=1)
        assert len(sample) == 10
        # 抽到的应该全部来自 judge 池（因为 judge 池本身已超配额）
        assert all(r["verdict_source"] == "judge" for r in sample)

    def test_backward_compatible_with_rows_missing_verdict_source(self):
        # 旧结果文件没有 verdict_source 字段：不应报错，应退化为纯随机抽样
        rows = [{"id": f"c{i}", "pair": "x"} for i in range(50)]
        sample = sample_for_human_review(rows, ratio=0.2, seed=1)
        assert len(sample) == 10


class TestCohenKappa:
    def test_perfect_agreement_is_kappa_one(self):
        labels = [1, 0, 1, 1, 0]
        assert cohen_kappa(labels, labels) == 1.0

    def test_systematic_disagreement_gives_low_kappa(self):
        judge = [1, 1, 1, 1, 1]
        human = [0, 0, 0, 0, 0]
        assert cohen_kappa(judge, human) <= 0.0
