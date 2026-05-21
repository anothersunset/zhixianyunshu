"""v2-step-15: 结构化输出客户端。

双后端优先级:
  1. **outlines** (可选): 仅在 RAG_OUTLINES_ENABLED=true 且 import 成功时使用。
     LogitsProcessor 在采样时就强制输出合 schema, 零重试。需 transformers 重依赖。
  2. **deepseek_json_mode** (默认): OpenAI-compatible response_format={'type':'json_object'} +
     system prompt 加 JSON Schema 描述 + pydantic 验证 + 失败重试 报错文本注入下一轮。
  3. **pydantic_only** (降级): 无 LLM key 时, 走 template 生成合理默认值, pydantic 验证后返。

设计原则:
- 对外统一 .generate_json(prompt, schema_cls, max_retries=3) -> StructuredResult
- StructuredResult 透明: backend / attempts / errors / data
- Langfuse trace 包全过程
- 任何一个后端不可用 都能降级到下一个, 不报 500
"""
from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Type, Optional, List, Dict

import httpx
from pydantic import BaseModel, ValidationError

from app.core.observability import get_langfuse
from app.core.schemas import export_schema


# ===== 可选加载 outlines =====
_OUTLINES_AVAILABLE = False
try:
    import outlines  # noqa: F401
    _OUTLINES_AVAILABLE = True
except Exception:
    _OUTLINES_AVAILABLE = False


def outlines_available() -> bool:
    return _OUTLINES_AVAILABLE


@dataclass
class StructuredResult:
    ok: bool
    backend: str                            # outlines / deepseek_json_mode / pydantic_only
    attempts: int                           # 1..max_retries
    data: Optional[Dict[str, Any]] = None   # pydantic model_dump()
    errors: List[str] = field(default_factory=list)
    elapsed_ms: int = 0


class StructuredOutputClient:
    """结构化输出主入口。 由 main 启动时单例创建。"""

    def __init__(self) -> None:
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
        self.chat_model = os.getenv("DEEPSEEK_CHAT_MODEL", "deepseek-chat")
        self.outlines_enabled = os.getenv("RAG_OUTLINES_ENABLED", "false").lower() in ("1", "true", "yes")
        self.timeout = float(os.getenv("DEEPSEEK_TIMEOUT", "60"))

    def current_backend(self) -> str:
        if self.outlines_enabled and _OUTLINES_AVAILABLE:
            return "outlines"
        if self.api_key:
            return "deepseek_json_mode"
        return "pydantic_only"

    def generate_json(
        self,
        prompt: str,
        schema_cls: Type[BaseModel],
        max_retries: int = 3,
        template_fallback: Optional[Dict[str, Any]] = None,
    ) -> StructuredResult:
        """主入口。返 StructuredResult。任何后端失败会自动降级。"""
        lf = get_langfuse()
        t0 = time.time()
        backend = self.current_backend()
        with lf.trace(
            "structured.generate",
            input={"backend": backend, "schema": schema_cls.__name__, "prompt_chars": len(prompt)},
            tags=["structured"],
        ) as tr:
            try:
                if backend == "outlines":
                    return self._with_timing(self._gen_outlines(prompt, schema_cls, max_retries, tr), t0, backend)
                if backend == "deepseek_json_mode":
                    return self._with_timing(self._gen_deepseek(prompt, schema_cls, max_retries, tr), t0, backend)
                return self._with_timing(self._gen_template(schema_cls, template_fallback, tr), t0, backend)
            except Exception as e:
                # 最后一道防线: 任何后端炸均退到 template
                tr.update(output={"fallback_to_template": True, "error": str(e)})
                return self._with_timing(self._gen_template(schema_cls, template_fallback, tr), t0, "pydantic_only")

    @staticmethod
    def _with_timing(result: StructuredResult, t0: float, backend: str) -> StructuredResult:
        result.elapsed_ms = int((time.time() - t0) * 1000)
        if not result.backend:
            result.backend = backend
        return result

    # -------- outlines 后端 --------
    def _gen_outlines(self, prompt: str, schema_cls, max_retries: int, tr) -> StructuredResult:
        """outlines 路径: 在 RAG_OUTLINES_ENABLED 且 outlines installed 时走。
        需要 RAG_OUTLINES_MODEL=microsoft/Phi-3.5-mini 或类似本地 transformers 模型。
        这里仅提供骨架, 未装 transformers 时降级到 deepseek。"""
        try:
            import outlines
            from outlines import models, generate
            model_name = os.getenv("RAG_OUTLINES_MODEL", "microsoft/Phi-3.5-mini-instruct")
            with tr.span("outlines.load_model", input={"model": model_name}) as sp:
                model = models.transformers(model_name)
                sp.output({"ok": True})
            with tr.span("outlines.generate", input={"schema": schema_cls.__name__}) as sp:
                gen = generate.json(model, schema_cls)
                obj = gen(prompt)
                sp.output({"ok": True})
            data = obj.model_dump() if isinstance(obj, BaseModel) else dict(obj)
            return StructuredResult(ok=True, backend="outlines", attempts=1, data=data)
        except Exception as e:
            tr.update(output={"outlines_failed": str(e), "fallback": "deepseek_json_mode"})
            if self.api_key:
                return self._gen_deepseek(prompt, schema_cls, max_retries, tr)
            return self._gen_template(schema_cls, None, tr)

    # -------- DeepSeek JSON mode 后端 --------
    def _gen_deepseek(self, prompt: str, schema_cls, max_retries: int, tr) -> StructuredResult:
        schema = export_schema(schema_cls)
        system_msg = (
            "你是严格输出 JSON 的助手。只输出合以下 JSON Schema 的对象, 不要 markdown, 不要解释。\n\n"
            f"JSON Schema:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
            "输出必须是合法 JSON 且能被 pydantic 验证通过。"
        )
        last_err = None
        errors: List[str] = []
        user_msg = prompt
        for attempt in range(1, max_retries + 1):
            with tr.span(f"deepseek.attempt_{attempt}", input={"prompt_chars": len(user_msg)}) as sp:
                try:
                    raw = self._call_deepseek(system_msg, user_msg)
                    sp.output({"raw_chars": len(raw)})
                except Exception as e:
                    last_err = f"http: {e}"
                    errors.append(last_err)
                    sp.output({"err": last_err})
                    continue
            with tr.span(f"parse.attempt_{attempt}") as sp:
                try:
                    parsed = json.loads(raw)
                except Exception as e:
                    last_err = f"json_parse: {e}"
                    errors.append(last_err)
                    sp.output({"err": last_err})
                    user_msg = (
                        f"{prompt}\n\n上一轮你返的内容不是合法 JSON, 报错: {e}\n请只输出纯 JSON, 不要 markdown。"
                    )
                    continue
                try:
                    obj = schema_cls.model_validate(parsed)
                    sp.output({"ok": True})
                    return StructuredResult(ok=True, backend="deepseek_json_mode", attempts=attempt,
                                            data=obj.model_dump(), errors=errors)
                except ValidationError as e:
                    last_err = f"pydantic: {e}"
                    errors.append(last_err)
                    sp.output({"err": last_err})
                    user_msg = (
                        f"{prompt}\n\n上一轮 JSON 不符合 schema, pydantic 报错:\n{e}\n请修正后重新输出纯 JSON。"
                    )
                    continue
        return StructuredResult(ok=False, backend="deepseek_json_mode", attempts=max_retries,
                                data=None, errors=errors)

    def _call_deepseek(self, system_msg: str, user_msg: str) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.chat_model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 1500,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        return data["choices"][0]["message"]["content"]

    # -------- pydantic_only 降级后端 --------
    def _gen_template(self, schema_cls, template_fallback, tr) -> StructuredResult:
        """无 LLM 时: template_fallback 提供默认值 → pydantic 验证 → 返。避免 500。"""
        base = template_fallback or self._default_fallback(schema_cls)
        try:
            obj = schema_cls.model_validate(base)
            with tr.span("template.validate") as sp:
                sp.output({"ok": True})
            return StructuredResult(ok=True, backend="pydantic_only", attempts=1, data=obj.model_dump())
        except ValidationError as e:
            return StructuredResult(ok=False, backend="pydantic_only", attempts=1, data=None,
                                    errors=[f"template_validate: {e}"])

    @staticmethod
    def _default_fallback(schema_cls) -> Dict[str, Any]:
        """为三个业务 schema 提供保守默认值。其他 schema 走空 dict (pydantic 会报缺字段)。"""
        name = schema_cls.__name__
        if name == "TranspileExplanation":
            return {"function_mappings": [], "pagination_change": None, "type_change": None,
                    "risk_level": "low", "confidence": 0.5, "notes": ["LLM 未配置, 由模板生成"]}
        if name == "SchemaAnalysisResult":
            return {"tables_total": 0, "tables_top": [], "relations_total": 0,
                    "suggested_migration_order": [], "notes": ["LLM 未配置"]}
        if name == "MigrationRiskReport":
            return {"task_id": 0, "overall_risk": "low", "confidence": 0.5,
                    "risks": [], "recommendations": [], "summary": "LLM 未配置, 仅默认报告"}
        return {}
