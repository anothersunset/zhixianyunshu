from __future__ import annotations

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from typing import List, Dict, Any

_TPL_DIR = Path(__file__).resolve().parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TPL_DIR)),
    autoescape=select_autoescape([]),
    keep_trailing_newline=True,
    trim_blocks=False,
    lstrip_blocks=False,
)

_TEMPLATE_MAP: Dict[str, str] = {
    "SQL_REWRITE":  "validation_sql_diff.sql.j2",
    "DIALECT":      "validation_sql_diff.sql.j2",
    "TYPE_MAPPING": "validation_type_mapping.sql.j2",
    "CONFIG":       "validation_config_check.sh.j2",
    "DEPENDENCY":   "validation_dependency_check.sh.j2",
}


def validate_request_payload(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(payload.get("task_id"), int):
        errors.append("task_id 必须为整数")
    suggestions = payload.get("suggestions")
    if not isinstance(suggestions, list) or not suggestions:
        errors.append("suggestions 必须为非空列表")
    else:
        for i, s in enumerate(suggestions):
            if not isinstance(s, dict):
                errors.append(f"suggestions[{i}] 必须为对象")
                continue
            if "category" not in s or "target" not in s:
                errors.append(f"suggestions[{i}] 缺少 category / target")
    return errors


def generate_validation_script(
    task_id: int,
    suggestions: List[Dict[str, Any]],
    target_db: str = "openGauss",
) -> List[Dict[str, Any]]:
    scripts: List[Dict[str, Any]] = []
    for idx, s in enumerate(suggestions, start=1):
        category = s.get("category", "SQL_REWRITE")
        tpl_name = _TEMPLATE_MAP.get(category, "validation_sql_diff.sql.j2")
        try:
            tpl = _env.get_template(tpl_name)
            content = tpl.render(
                task_id=task_id,
                target_db=target_db,
                suggestion=s,
                index=idx,
            )
        except Exception as e:
            content = f"-- 模板渲染失败: {e!r}\n-- payload={s!r}\n"
        scripts.append({
            "index": idx,
            "category": category,
            "target": s.get("target"),
            "template": tpl_name,
            "file_path": f"validation/task-{task_id}/{idx:02d}-{category.lower()}.sql",
            "content": content,
        })
    return scripts
