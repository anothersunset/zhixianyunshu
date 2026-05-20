from __future__ import annotations
import logging
from pathlib import Path
from .models import PatchSet, ValidationBundle, ValidationScript
from .handlers.sql_val import SqlValHandler
from .handlers.unit_hint import UnitHintHandler
from .handlers.smoke_curl import SmokeCurlHandler
from .handlers.compile_gate import CompileGateHandler

log = logging.getLogger(__name__)

class ValidationScriptGenerator:
    def __init__(self):
        self.handlers = [
            SqlValHandler(),
            UnitHintHandler(),
            SmokeCurlHandler(),
            CompileGateHandler(),
        ]

    def generate(self, patch_set: PatchSet) -> ValidationBundle:
        scripts: list[ValidationScript] = []
        for item in patch_set.results:
            for h in self.handlers:
                if h.supports(item):
                    scripts.extend(h.build(item))
        scripts.extend(CompileGateHandler().build_global(patch_set))
        log.info("[Val] task=%s scripts=%d", patch_set.task_id, len(scripts))
        return ValidationBundle(task_id=patch_set.task_id, scripts=scripts)

    def dump(self, bundle: ValidationBundle, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        for s in bundle.scripts:
            p = out_dir / s.target_path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(s.content, encoding="utf-8")
