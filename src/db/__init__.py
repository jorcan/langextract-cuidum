"""Database connection and query helpers for Odoo PostgreSQL."""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Local fallback: load sample data when no DB available
SAMPLE_DATA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data" / "samples" / "raw_calls.json"
)


def load_sample_calls(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load call records from a local JSON file (sample data or cached)."""
    path = Path(path or SAMPLE_DATA_PATH)
    if not path.exists():
        logger.warning("Sample data file not found: %s", path)
        return []
    with open(path) as f:
        return json.load(f)


def format_call_for_extraction(call: dict[str, Any], max_chars: int = 3000) -> str:
    """Format a phonecall record into a text block for LLM extraction."""
    name = call.get("name") or "(sin resumen)"
    description = call.get("description") or "(sin transcripción)"

    # Truncate description to save tokens
    if len(description) > max_chars:
        description = description[:max_chars] + "..."

    lines = [
        f"=== LLAMADA #{call.get('id')} ===",
        f"Resumen: {name.strip()}",
        f"Fecha: {call.get('create_date', 'desconocida')}",
        f"Clave/Subclave: {call.get('clave')}/{call.get('subclave')}",
        "",
        "Transcripción:",
        description.strip(),
    ]
    return "\n".join(lines)


def get_calls_needing_extraction(
    calls: list[dict[str, Any]],
    already_done: set[int] | None = None,
    skip_empty: bool = True,
) -> list[dict[str, Any]]:
    """Filter calls that need processing."""
    already_done = already_done or set()
    result = []
    for c in calls:
        cid = c.get("id")
        if cid in already_done:
            continue
        desc = c.get("description") or ""
        if skip_empty and not desc.strip():
            continue
        result.append(c)
    return result
