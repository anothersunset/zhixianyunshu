from __future__ import annotations

import logging
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from typing import List, Dict, Any

from app.core.sql_transpiler import explain_transpile

log = logging.getLogger(__name__)

_TPL_DIR = Path(__file__).resolve().parent.parent / "templates"

# 使用自定义分隔符,避开上游系统对 ... 的压缩 URL 替换。
# 变量:<< var >>
# 控制块:<% for x in xs %> ... <% endfor %>
# 注释:<# this is a comment #>
_env = Environment(
    loader=FileSystemLoader(str(_TPL_DIR)),
    autoescape=select_autoescape([]),
    keep_trailing_newline=True,
    trim_blocks=False,
    lstrip_blocks=False,
    variable_start_string="<<",
    variable_end_string=">>",
    block_start_string="<%",
    block_end_string="%>",
    comment_start_string="<#",
    comment_end_string="#>",
)

_TEMPLATE_MAP: Dict[str, str] = {
    "SQL_REWRITE":  "validation_sql_diff.sql.j2",
    "DIALECT":      "validation_sql_diff.sql.j2",
    "TYPE_MAPPING": "validation_type_mapping.sql.j2",
    "CONFIG":       "validation_config_check.sh.j2",
    "DEPENDENCY":   "validation_dependency_check.sh.j2",
}

# v2-step-09: 走 sqlglot AST 转译的类别
_TRANSPILE_CATEGORIES = {"SQL_REWRITE", "DIALECT"}


def validate_request_payload(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(payload.get("task_id"), int):
        errors.append("task_id must be int")
    suggestions = payload.get("suggestions")
    if not isinstance(suggestions, list) or not suggestions:
        errors.append("suggestions must be a non-empty list")
    else:
        for i, s in enumerate(suggestions):
            if not isinstance(s, dict):
                errors.append(f"suggestions[{i}] must be an object")
                continue
            if "category" not in s or "target" not in s:
                errors.append(f"suggestions[{i}] missing category / target")
    return errors


def _derive_table_name(target: str) -> str:
    """
    从 suggestion.target 中推断表名:
    例 'com.demo.UserMapper.xml#listActive' -> 'user'
    例 'com.demo.entity.Order.amount' -> 'order'
    """
    if not target:
        return "unknown_table"
    head = target.split("#")[0]
    parts = head.split(".")
    name = parts[-1] if parts else head
    name = name.replace("Mapper", "").replace("xml", "").strip("._")
    return name.lower() or "unknown_table"


def _derive_column_name(target: str) -> str:
    if not target:
        return "value"
    parts = target.split(".")
    return parts[-1] if parts else "value"


def _maybe_transpile(s: Dict[str, Any], target_db: str) -> Dict[str, Any] | None:
    """v2-step-09: 为 SQL_REWRITE/DIALECT 类的 suggestion 自动走 sqlglot AST 转译。

    识别多个可能的字段名：before_sql / source_sql / sql / from_sql。
    转译失败不坏外层, 返回 None 让模板走 fallback。
    """
    category = s.get("category")
    if category not in _TRANSPILE_CATEGORIES:
        return None
    before_sql = (
        s.get("before_sql")
        or s.get("source_sql")
        or s.get("from_sql")
        or s.get("sql")
    )
    if not before_sql or not isinstance(before_sql, str):
        return None
    try:
        return explain_transpile(
            before_sql,
            source=s.get("source_dialect") or s.get("from_dialect") or "mysql",
            target=s.get("target_dialect") or s.get("to_dialect") or target_db,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("[validation] sqlglot 转译异常(忽略,走模板 fallback): %s", e)
        return {"ok": False, "error": str(e), "source": before_sql}


def generate_validation_script(
    task_id: int,
    suggestions: List[Dict[str, Any]],
    target_db: str = "openGauss",
) -> List[Dict[str, Any]]:
    scripts: List[Dict[str, Any]] = []
    for idx, s in enumerate(suggestions, start=1):
        category = s.get("category", "SQL_REWRITE")
        tpl_name = _TEMPLATE_MAP.get(category, "validation_sql_diff.sql.j2")

        # v2-step-09: 可选 “真 AST 转译”
        transpile_info = _maybe_transpile(s, target_db)
        transpile_target = (
            transpile_info.get("target")
            if transpile_info and transpile_info.get("ok")
            else None
        )
        transpile_notes = (
            transpile_info.get("notes", [])
            if transpile_info and transpile_info.get("ok")
            else []
        )

        try:
            tpl = _env.get_template(tpl_name)
            content = tpl.render(
                task_id=task_id,
                target_db=target_db,
                suggestion=s,
                index=idx,
                table_name=_derive_table_name(s.get("target", "")),
                column_name=_derive_column_name(s.get("target", "")),
                config_file=s.get("file") or "application-prod.yml",
                pom_file=s.get("file") or "pom.xml",
                # v2-step-09 注入 (模板不用也不报错)
                transpile_info=transpile_info,
                transpile_target=transpile_target,
                transpile_notes=transpile_notes,
            )
        except Exception as e:
            content = f"-- template render failed: {e!r}\n-- payload={s!r}\n"
        ext = "sh" if category in ("CONFIG", "DEPENDENCY") else "sql"
        scripts.append({
            "index": idx,
            "category": category,
            "target": s.get("target"),
            "template": tpl_name,
            "file_path": f"validation/task-{task_id}/{idx:02d}-{category.lower()}.{ext}",
            "content": content,
            # v2-step-09: 装在 script 输出里, 供 backend/web 直接用
            "transpile": transpile_info,
        })
    return scripts
