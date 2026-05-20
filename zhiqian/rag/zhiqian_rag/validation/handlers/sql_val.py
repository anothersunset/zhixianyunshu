import re
from pathlib import Path
from typing import List
from jinja2 import Template
from . import ValidationHandler
from ..models import PatchItem, ValidationScript

TEMPLATE = Template((Path(__file__).parent.parent / "templates" / "sql_val.sql.j2").read_text("utf-8"))

_SQL_HUNK = re.compile(r"^\+(.*)$", re.MULTILINE)

class SqlValHandler(ValidationHandler):
    kind = "sql_val"

    def supports(self, item: PatchItem) -> bool:
        return item.category == "sql_dialect"

    def build(self, item: PatchItem) -> List[ValidationScript]:
        new_sqls = [m.group(1).strip() for m in _SQL_HUNK.finditer(item.unified_diff) if m.group(1).strip()]
        if not new_sqls:
            return []
        content = TEMPLATE.render(unit_id=item.unit_id, target_file=item.target_file,
                                   evidence=item.evidence_ids, sqls=new_sqls)
        return [ValidationScript(
            script_id=f"val-sql-{item.unit_id}",
            kind=self.kind,
            target_path=f"validation/sql/{item.unit_id}.sql",
            content=content,
            related_unit_ids=[item.unit_id]
        )]
