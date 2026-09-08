"""Guard de aislamiento: core/ NO puede depender de Odoo/n8n/adapters/src."""
import ast
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parent.parent.parent / "core"
FORBIDDEN = {"src", "adapters", "odoo", "n8n", "psycopg2", "crm_phonecall", "res_partner"}

import ast
import re


def _imported_names(node: ast.AST):
    for n in ast.walk(node):
        if isinstance(n, ast.Import):
            for a in n.names:
                yield a.name.split(".")[0]
        elif isinstance(n, ast.ImportFrom):
            yield (n.module or "").split(".")[0]


def test_core_has_no_odoo_dependencies():
    offenders = {}
    for py in sorted(CORE_DIR.rglob("*.py")):
        if py.name == "__pycache__":
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        hits = sorted({name for name in _imported_names(tree) if name in FORBIDDEN})
        if hits:
            offenders[str(py.relative_to(CORE_DIR))] = hits
    assert not offenders, f"core/ importa dependencias prohibidas: {offenders}"


def test_core_source_never_mentions_odoo_tables():
    """El texto del prompt/instrucciones del core no debe mencionar Odoo/CRM."""
    for py in sorted(CORE_DIR.rglob("*.py")):
        src = py.read_text(encoding="utf-8")
        for w in ("crm_phonecall", "res_partner", "odoo", "n8n", "Odoo"):
            assert w not in src, f"{py.name} menciona '{w}'"