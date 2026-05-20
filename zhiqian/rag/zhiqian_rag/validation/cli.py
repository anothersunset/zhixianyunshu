import json
from pathlib import Path
import typer
from .generator import ValidationScriptGenerator
from .models import PatchSet

app = typer.Typer(add_completion=False)

@app.command()
def build(patch_set: Path, out_dir: Path = Path("./report-staging/validation")):
    """Generate validation scripts from patch_set.json."""
    data = json.loads(patch_set.read_text("utf-8"))
    ps = PatchSet(**data)
    gen = ValidationScriptGenerator()
    bundle = gen.generate(ps)
    gen.dump(bundle, out_dir)
    typer.echo(f"wrote {len(bundle.scripts)} scripts -> {out_dir}")

if __name__ == "__main__":
    app()
