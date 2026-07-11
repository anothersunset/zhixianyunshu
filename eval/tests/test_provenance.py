from eval.provenance import build_run_metadata, dataset_fingerprint
from eval.run_eval import summarize


def test_dataset_fingerprint_is_stable_across_mapping_order():
    assert dataset_fingerprint([{"id": "1", "value": 2}]) == dataset_fingerprint(
        [{"value": 2, "id": "1"}]
    )


def test_metadata_records_dataset_config_and_cost_contract():
    metadata = build_run_metadata(cases=[{"id": "case-1"}], config={"seed": 7})
    assert metadata["dataset"]["cases"] == 1
    assert len(metadata["dataset"]["sha256"]) == 64
    assert metadata["config"]["seed"] == 7
    assert metadata["cost_contract"]["source"] == "backend_reported_only"


def test_summary_separates_deterministic_and_judged_metrics():
    base = {"recall@5": None, "mrr@10": None, "risk_level": "low", "retrieval_real": True,
            "gold_quality": "ok", "models": [], "reported_cost_usd": None}
    rows = [
        {**base, "sql_ok": True, "deterministic_sql_ok": False, "verdict_source": "judge",
         "judge_enabled": True, "report_acc": 1.0, "deterministic_report_acc": 0.0,
         "latency_ms": 10, "token_in": 3, "token_out": 2, "models": ["judge-model"],
         "reported_cost_usd": 0.01},
        {**base, "sql_ok": True, "deterministic_sql_ok": True, "verdict_source": "deterministic",
         "judge_enabled": True, "report_acc": 0.5, "deterministic_report_acc": 0.5,
         "latency_ms": 20, "token_in": 4, "token_out": 1},
    ]
    summary = summarize(rows)
    assert summary["deterministic_metrics"]["sql_repair_rate"] == 0.5
    assert summary["judge_metrics"]["enabled"] is True
    assert summary["runtime"]["p95_latency_ms"] == 20
    assert summary["runtime"]["token_in"] == 7
    assert summary["runtime"]["reported_cost_usd"] == 0.01
