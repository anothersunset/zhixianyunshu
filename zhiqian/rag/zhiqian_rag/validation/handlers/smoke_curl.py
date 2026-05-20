from pathlib import Path
from typing import List
from jinja2 import Template
from . import ValidationHandler
from ..models import PatchItem, ValidationScript

TEMPLATE = Template((Path(__file__).parent.parent / "templates" / "smoke_curl.sh.j2").read_text("utf-8"))

class SmokeCurlHandler(ValidationHandler):
    kind = "smoke_curl"

    def supports(self, item: PatchItem) -> bool:
        return item.category in ("config", "middleware")

    def build(self, item: PatchItem) -> List[ValidationScript]:
        content = TEMPLATE.render(unit_id=item.unit_id, category=item.category,
                                   rationale=item.rationale or "")
        return [ValidationScript(
            script_id=f"val-smoke-{item.unit_id}",
            kind=self.kind,
            target_path=f"validation/smoke/{item.unit_id}.sh",
            content=content,
            related_unit_ids=[item.unit_id],
        )]
