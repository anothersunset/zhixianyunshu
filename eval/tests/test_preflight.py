"""preflight check_checkpoint 的自检（离线，不发任何 HTTP 请求）。

背景：check_checkpoint 旧实现把自检文件硬编码为 "/tmp/preflight_checkpoint_test.json"，
Windows 会解析为当前盘符根下的 \\tmp（通常是 C:\\tmp）——该目录多半不存在，
预检第 4 项会直接 FAIL。修复后应解析到 tempfile.gettempdir()。
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import eval.preflight as preflight
import eval.run_eval as run_eval


def test_checkpoint_test_path_resolves_to_platform_tempdir():
    """路径必须落在平台真实临时目录下，且该目录确实存在。"""
    p = Path(preflight._checkpoint_test_path())
    assert p.name == "preflight_checkpoint_test.json"
    assert p.parent == Path(tempfile.gettempdir())
    assert p.parent.is_dir()  # 旧实现硬编码 /tmp 时，Windows 下父目录不存在


def test_check_checkpoint_roundtrip_with_fakes(monkeypatch):
    """monkeypatch 掉 evaluate/load_dataset，端到端验证 check_checkpoint 判定逻辑。"""
    captured = {}

    def fake_load_dataset(path, pair):
        return [{"id": f"case-{i}", "pair": pair} for i in range(8)]

    def fake_evaluate(cases, retrieval, client, fast=False, checkpoint_path=None, **kwargs):
        captured["checkpoint_path"] = checkpoint_path
        rows = [{"id": c["id"], "sql_ok": True} for c in cases]  # 8 个 case，取前 5
        Path(checkpoint_path).write_text(
            json.dumps({"rows": rows}), encoding="utf-8"
        )
        return rows

    monkeypatch.setattr(run_eval, "load_dataset", fake_load_dataset)
    monkeypatch.setattr(run_eval, "evaluate", fake_evaluate)

    assert preflight.check_checkpoint() is True

    # 自检文件写到了平台临时目录（而非硬编码 /tmp），且检查完后被清理
    ckpt = Path(captured["checkpoint_path"])
    assert ckpt.parent == Path(tempfile.gettempdir())
    assert not ckpt.exists()
