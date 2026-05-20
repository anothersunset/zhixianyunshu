from pathlib import Path
from typing import List
from jinja2 import Template
from . import ValidationHandler
from ..models import PatchItem, ValidationScript

TEMPLATE = Template((Path(__file__).parent.parent / "templates" / "unit_hint.java.j2").read_text("utf-8"))

class UnitHintHandler(ValidationHandler):
    kind = "unit_hint"

    def supports(self, item: PatchItem) -> bool:
        return item.category in ("api_rename", "sql_dialect")

    def build(self, item: PatchItem) -> List[ValidationScript]:
        class_name = self._guess_test_class(item.target_file)
        content = TEMPLATE.render(
            unit_id=item.unit_id,
            class_name=class_name,
            category=item.category,
            rationale=item.rationale or "",
        )
        return [ValidationScript(
            script_id=f"val-unit-{item.unit_id}",
            kind=self.kind,
            target_path=f"validation/unit-hint/{class_name}Hint.md",
            content=content,
            related_unit_ids=[item.unit_id],
        )]

    @staticmethod
    def _guess_test_class(path: str) -> str:
        name = Path(path).stem
        return name + "Migration"
