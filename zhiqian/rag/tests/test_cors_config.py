"""RAG_CORS_ORIGINS 可配置性: 默认 "*" 不变 (不破坏本地搭配), 逗号分隔可收紧。"""
from __future__ import annotations

from app.config import Settings
from app.main import _cors_origins


def test_settings_default_is_wildcard(monkeypatch):
    monkeypatch.delenv("RAG_CORS_ORIGINS", raising=False)
    assert Settings(_env_file=None).cors_origins == "*"


def test_parse_default_and_blank_stay_wildcard():
    assert _cors_origins("*") == ["*"]
    assert _cors_origins("") == ["*"]
    assert _cors_origins("   ") == ["*"]
    assert _cors_origins(" , , ") == ["*"]


def test_parse_comma_separated_origins():
    assert _cors_origins("http://localhost:5173,https://zhiqian.example.com") == [
        "http://localhost:5173",
        "https://zhiqian.example.com",
    ]
    # 单一来源 + 周围空白
    assert _cors_origins("  http://a.example.com  ") == ["http://a.example.com"]


def test_installed_cors_middleware_defaults_to_wildcard():
    """应用实际装配的 CORSMiddleware 默认仍为 ["*"]。"""
    from app.main import app

    cors = next(m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware")
    assert cors.kwargs["allow_origins"] == ["*"]
