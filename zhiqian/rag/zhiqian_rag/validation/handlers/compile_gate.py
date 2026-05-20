from pathlib import Path
from typing import List
from jinja2 import Template
from . import ValidationHandler
from ..models import PatchItem, PatchSet, ValidationScript

TEMPLATE = Template((Path(__file__).parent.parent / "templates" / "compile_gate.sh.j2").read_text("utf-8"))

class CompileGateHandler(ValidationHandler):
    kind = "compile_gate"

    def supports(self, item: PatchItem) -> bool:
        return False

    def build(self, item: PatchItem) -> List[ValidationScript]:
        return []

    def build_global(self, patch_set: PatchSet) -> List[ValidationScript]:
        content = TEMPLATE.render(
            task_id=patch_set.task_id,
            total=patch_set.total,
            avg_conf=round(patch_set.avg_confidence, 3),
        )
        return [ValidationScript(
            script_id=f"val-compile-{patch_set.task_id}",
            kind=self.kind,
            target_path="validation/compile_gate.sh",
            content=content,
            related_unit_ids=[p.unit_id for p in patch_set.results],
        )]
