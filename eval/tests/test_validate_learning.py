"""validate_learning 部署/回退机制自检（完全离线，不发任何 HTTP 请求）。

隔离方式：deploy/rollback/_backup_active 等函数都通过模块级路径常量
（KB_ACTIVE / KB_PENDING / BACKUP_DIR / DEPLOY_LOG）解析目标位置，且函数体在
调用时才查这些全局名。因此用 monkeypatch.setattr 把常量重定向到 pytest 的
tmp_path 即可注入，不需要参数化改造源码，也保证绝不触碰真实 kb/ 目录
（不涉及 reingest_rag / retest_failed_cases——它们走真实网络与真实 kb 路径）。
"""
from __future__ import annotations

import json

import pytest
import yaml

import eval.validate_learning as vl


@pytest.fixture
def kb(tmp_path, monkeypatch):
    """构造隔离的假 kb 布局（active/ + pending/），并把模块路径常量重定向过去。"""
    root = tmp_path / "kb"
    active = root / "active"
    pending = root / "pending"
    active.mkdir(parents=True)
    pending.mkdir(parents=True)

    monkeypatch.setattr(vl, "KB_ACTIVE", active)
    monkeypatch.setattr(vl, "KB_PENDING", pending)
    monkeypatch.setattr(vl, "KB_PENDING_RECIPES", pending / "recipes")
    monkeypatch.setattr(vl, "BACKUP_DIR", root / "backups")
    monkeypatch.setattr(vl, "DEPLOY_LOG", root / "deploy_log.json")

    return {"root": root, "active": active, "pending": pending}


# ── preview ──

def test_preview_lists_pending_files_and_readiness(kb):
    (kb["pending"] / "kb-001.yaml").write_text("x", encoding="utf-8")
    recipes = kb["pending"] / "recipes"
    recipes.mkdir()
    (recipes / "recipe-001.yaml").write_text("dialect: hk\n", encoding="utf-8")

    status = vl.preview()

    assert status["pending_kb_docs"] == ["kb-001.yaml"]
    assert status["pending_recipes"] == ["recipe-001.yaml"]
    assert status["ready_to_deploy"] is True


def test_preview_on_empty_pending_reports_not_ready(kb):
    status = vl.preview()
    assert status["ready_to_deploy"] is False


# ── deploy ──

def test_deploy_overwrites_active_and_records_deploy_log(kb):
    (kb["active"] / "kb-001.yaml").write_text("old-content", encoding="utf-8")
    (kb["pending"] / "kb-001.yaml").write_text("new-content", encoding="utf-8")

    result = vl.deploy()

    # active 中同名文件被 pending 版本覆盖
    assert (kb["active"] / "kb-001.yaml").read_text(encoding="utf-8") == "new-content"
    assert result["deployed_kb"] == 1
    assert result["deployed_recipes"] == 0

    # deploy_log.json 记录了本次部署
    log_path = kb["root"] / "deploy_log.json"
    assert log_path.exists()
    history = json.loads(log_path.read_text(encoding="utf-8"))
    assert isinstance(history, list) and len(history) == 1
    assert history[0]["deployed_kb_docs"] == ["kb-001.yaml"]
    assert history[0]["deployed_recipes"] == []


def test_deploy_backs_up_previous_active_state_including_subdirs(kb):
    (kb["active"] / "kb-old.yaml").write_text("old-content", encoding="utf-8")
    dialects = kb["active"] / "dialects"
    dialects.mkdir()
    (dialects / "hk.yaml").write_text("dialect: hk\n", encoding="utf-8")
    (kb["pending"] / "kb-001.yaml").write_text("new", encoding="utf-8")

    vl.deploy()

    # 备份目录结构：backups/<timestamp>/ 镜像部署前的 active/
    backups_root = kb["root"] / "backups"
    backup_dirs = list(backups_root.iterdir())
    assert len(backup_dirs) == 1
    backup = backup_dirs[0]
    assert (backup / "kb-old.yaml").read_text(encoding="utf-8") == "old-content"
    assert (backup / "dialects" / "hk.yaml").read_text(encoding="utf-8") == "dialect: hk\n"

    # deploy_log 指向的 backup_path 与实际备份目录一致
    history = json.loads((kb["root"] / "deploy_log.json").read_text(encoding="utf-8"))
    assert history[-1]["backup_path"] == str(backup)


def test_deploy_appends_to_existing_deploy_log_history(kb):
    (kb["pending"] / "kb-001.yaml").write_text("v1", encoding="utf-8")
    vl.deploy()
    (kb["pending"] / "kb-001.yaml").write_text("v2", encoding="utf-8")
    vl.deploy()

    history = json.loads((kb["root"] / "deploy_log.json").read_text(encoding="utf-8"))
    assert len(history) == 2


def test_deploy_merges_recipe_into_dialect_yaml(kb):
    dialect_file = kb["active"] / "dialects" / "hk.yaml"
    dialect_file.parent.mkdir(parents=True)
    dialect_file.write_text(
        yaml.dump({"dialect": "hk", "features": [{"keyword": "existing"}]}),
        encoding="utf-8",
    )
    recipes = kb["pending"] / "recipes"
    recipes.mkdir()
    (recipes / "recipe-001.yaml").write_text(
        yaml.dump({"dialect": "hk", "keyword": "IFNULL", "pattern": "p", "fix": "f"}),
        encoding="utf-8",
    )

    result = vl.deploy()

    assert result["deployed_recipes"] == 1
    data = yaml.safe_load(dialect_file.read_text(encoding="utf-8"))
    assert [f["keyword"] for f in data["features"]] == ["existing", "IFNULL"]
    # dialect 字段是路由信息，不属于 feature 本体，不应被合并进去
    assert all("dialect" not in f for f in data["features"])


def test_deploy_skips_merge_for_duplicate_recipe_keyword(kb):
    """已存在相同 keyword（大小写不敏感）时，dialect 文件保持不变。"""
    dialect_file = kb["active"] / "dialects" / "hk.yaml"
    dialect_file.parent.mkdir(parents=True)
    original = yaml.dump({"dialect": "hk", "features": [{"keyword": "ifnull"}]})
    dialect_file.write_text(original, encoding="utf-8")
    recipes = kb["pending"] / "recipes"
    recipes.mkdir()
    (recipes / "recipe-001.yaml").write_text(
        yaml.dump({"dialect": "hk", "keyword": "IFNULL", "pattern": "p"}),
        encoding="utf-8",
    )

    vl.deploy()

    assert dialect_file.read_text(encoding="utf-8") == original


# ── rollback ──

def test_rollback_restores_backup_content_and_pops_log(kb):
    (kb["active"] / "kb-001.yaml").write_text("old-content", encoding="utf-8")
    dialects = kb["active"] / "dialects"
    dialects.mkdir()
    (dialects / "hk.yaml").write_text("old-dialect", encoding="utf-8")
    (kb["pending"] / "kb-001.yaml").write_text("new-content", encoding="utf-8")

    vl.deploy()
    assert (kb["active"] / "kb-001.yaml").read_text(encoding="utf-8") == "new-content"

    result = vl.rollback()

    assert result["rolled_back"] is True
    assert result["restored_kb"] == 1
    # active 恢复到备份内容（文件 + 子目录）
    assert (kb["active"] / "kb-001.yaml").read_text(encoding="utf-8") == "old-content"
    assert (dialects / "hk.yaml").read_text(encoding="utf-8") == "old-dialect"
    # 部署日志弹出该次记录
    history = json.loads((kb["root"] / "deploy_log.json").read_text(encoding="utf-8"))
    assert history == []


def test_rollback_removes_files_introduced_by_deploy(kb):
    """部署新引入、备份里没有的文件，回退后必须被清掉。"""
    (kb["active"] / "kb-old.yaml").write_text("old", encoding="utf-8")
    (kb["pending"] / "kb-new.yaml").write_text("new", encoding="utf-8")

    vl.deploy()
    assert (kb["active"] / "kb-new.yaml").exists()

    vl.rollback()

    assert not (kb["active"] / "kb-new.yaml").exists()
    assert (kb["active"] / "kb-old.yaml").read_text(encoding="utf-8") == "old"


def test_rollback_without_deploy_log_is_safe_noop(kb):
    result = vl.rollback()
    assert result["rolled_back"] is False
    assert result["reason"] == "no deployment log"
    assert not (kb["root"] / "deploy_log.json").exists()


def test_rollback_with_missing_backup_reports_reason(kb):
    entry = {
        "timestamp": "20260101-000000",
        "deployed_kb_docs": [],
        "deployed_recipes": [],
        "backup_path": str(kb["root"] / "backups" / "does-not-exist"),
    }
    (kb["root"] / "deploy_log.json").write_text(json.dumps([entry]), encoding="utf-8")

    result = vl.rollback()

    assert result["rolled_back"] is False
    assert "not found" in result["reason"]
    # 日志未被弹出（回退未执行）
    history = json.loads((kb["root"] / "deploy_log.json").read_text(encoding="utf-8"))
    assert len(history) == 1
