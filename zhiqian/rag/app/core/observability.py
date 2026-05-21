"""Langfuse 全链路埋点 — RAG 端。

设计原则:
- 完全可选: 未安装 langfuse 包 或 未配 PUBLIC/SECRET 时静默 no-op,启动只多一条 INFO 日志。
- 调用代码恒等: 不管 enabled/disabled,业务侧都是 `with lf.trace(...) as tr: with tr.span(...) as sp:`。
- 性能开销 ≈ 0: disabled 路径走 _NoopTrace/_NoopSpan,无网络、无序列化。

环境变量 (直接 os.getenv,不入 pydantic Settings,避免 secret 进 repr 日志):
- LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY — 缺一即 disabled
- LANGFUSE_HOST — 默认 https://cloud.langfuse.com,自托管可填 http://langfuse:3000
"""
from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

log = logging.getLogger(__name__)


# ───── No-op 实现 (disabled 时使用) ─────

class _NoopSpan:
    def output(self, _data: Any) -> None: ...
    def update(self, **_kw: Any) -> None: ...


class _NoopTrace:
    @contextmanager
    def span(self, _name: str, **_kw: Any) -> Iterator[_NoopSpan]:
        yield _NoopSpan()

    def output(self, _data: Any) -> None: ...
    def update(self, **_kw: Any) -> None: ...


@contextmanager
def _noop_trace_cm() -> Iterator[_NoopTrace]:
    yield _NoopTrace()


# ───── 真实实现 (enabled 时使用) ─────

class _ActiveSpan:
    def __init__(self, sp_obj: Any) -> None:
        self._sp = sp_obj
        self._output: Any = None

    def output(self, data: Any) -> None:
        self._output = data

    def update(self, **kw: Any) -> None:
        try:
            self._sp.update(**kw)
        except Exception:  # noqa: BLE001
            pass


class _ActiveTrace:
    def __init__(self, tr_obj: Any) -> None:
        self._tr = tr_obj
        self._output: Any = None

    @contextmanager
    def span(
        self,
        name: str,
        input: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Iterator[Any]:
        t0 = time.perf_counter()
        try:
            sp = self._tr.span(name=name, input=input, metadata=metadata or {})
        except Exception as exc:  # noqa: BLE001
            log.debug("[langfuse] span(%s) 调用失败 %s,本次走 no-op", name, exc)
            yield _NoopSpan()
            return
        wrapped = _ActiveSpan(sp)
        try:
            yield wrapped
        finally:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            try:
                sp.end(
                    output=wrapped._output,
                    metadata={**(metadata or {}), "elapsed_ms": elapsed_ms},
                )
            except Exception:  # noqa: BLE001
                pass

    def output(self, data: Any) -> None:
        self._output = data

    def update(self, **kw: Any) -> None:
        try:
            self._tr.update(**kw)
        except Exception:  # noqa: BLE001
            pass


class LangfuseClient:
    """Lazy / fault-tolerant Langfuse 包装。第一次访问 .available 时才尝试 import + 连接。"""

    def __init__(self) -> None:
        self._tried = False
        self._client: Any = None
        self._enabled = False
        self._host = ""

    def _try_init(self) -> None:
        if self._tried:
            return
        self._tried = True
        pub = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
        sec = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com").strip()
        if not pub or not sec:
            log.info(
                "[langfuse] keys 未设置,观测能力 disabled "
                "(设 LANGFUSE_PUBLIC_KEY/SECRET_KEY 启用)"
            )
            return
        try:
            from langfuse import Langfuse  # type: ignore
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "[langfuse] 包未装 (%s),disabled。pip install langfuse 启用。",
                exc,
            )
            return
        try:
            self._client = Langfuse(public_key=pub, secret_key=sec, host=host)
            self._enabled = True
            self._host = host
            log.info("[langfuse] enabled host=%s", host)
        except Exception as exc:  # noqa: BLE001
            log.warning("[langfuse] 初始化失败 %s,disabled", exc)

    @property
    def available(self) -> bool:
        self._try_init()
        return self._enabled

    @property
    def host(self) -> str:
        self._try_init()
        return self._host

    def flush(self) -> None:
        if self.available and self._client is not None:
            try:
                self._client.flush()
            except Exception:  # noqa: BLE001
                pass

    @contextmanager
    def trace(
        self,
        name: str,
        input: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Iterator[Any]:
        if not self.available:
            with _noop_trace_cm() as t:
                yield t
            return
        client = self._client
        try:
            tr = client.trace(
                name=name,
                input=input,
                metadata=metadata or {},
                user_id=user_id,
                tags=tags or [],
            )
        except Exception as exc:  # noqa: BLE001
            log.debug("[langfuse] trace(%s) 创建失败 %s,本次走 no-op", name, exc)
            with _noop_trace_cm() as t:
                yield t
            return
        wrapped = _ActiveTrace(tr)
        t0 = time.perf_counter()
        try:
            yield wrapped
        finally:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            try:
                tr.update(
                    output=wrapped._output,
                    metadata={**(metadata or {}), "elapsed_ms": elapsed_ms},
                )
            except Exception:  # noqa: BLE001
                pass
            try:
                client.flush()
            except Exception:  # noqa: BLE001
                pass


_singleton: Optional[LangfuseClient] = None


def get_langfuse() -> LangfuseClient:
    """全局单例。所有调用方都通过这个拿 LangfuseClient,保证只 init 一次。"""
    global _singleton
    if _singleton is None:
        _singleton = LangfuseClient()
    return _singleton
