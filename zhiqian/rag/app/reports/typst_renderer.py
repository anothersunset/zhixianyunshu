"""v2-step-27: Typst PDF 渲染。

Typst 是映陆 LaTeX 的现代排版引擎, 编译极快 (<1s), 语法类 Markdown, 中文支持佳。
需本机装 typst CLI (`brew install typst` / `cargo install typst-cli`)。未装优雅返 503。
"""
from __future__ import annotations
import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


def typst_available() -> bool:
    return shutil.which("typst") is not None


def render_pdf(template: str, data: Dict[str, Any]) -> Optional[bytes]:
    """用 template (不含 .typ) + data 渲 PDF, 返 bytes。未装 typst 返 None。"""
    if not typst_available():
        logger.warning("typst CLI not found in PATH")
        return None

    tpl_path = TEMPLATES_DIR / f"{template}.typ"
    if not tpl_path.exists():
        raise FileNotFoundError(f"template not found: {tpl_path}")

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        # 复制模板 + 写 data.json
        work_tpl = td_path / f"{template}.typ"
        work_tpl.write_text(tpl_path.read_text(encoding="utf-8"), encoding="utf-8")
        (td_path / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        out_pdf = td_path / "output.pdf"

        # typst compile <input> <output>
        cmd = ["typst", "compile", str(work_tpl), str(out_pdf)]
        try:
            subprocess.run(cmd, check=True, cwd=td_path,
                           capture_output=True, timeout=30)
        except subprocess.CalledProcessError as e:
            logger.error("typst compile failed: %s", e.stderr.decode("utf-8", errors="ignore"))
            return None
        except subprocess.TimeoutExpired:
            logger.error("typst compile timeout")
            return None

        return out_pdf.read_bytes()
