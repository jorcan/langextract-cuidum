"""Consensus between two independent extractions — Gate 2.

Two LLMs (A=extractor, B=auditor) run independently; a value is only
auto-approved when normalized(A) == normalized(B). Discrepancies go to
human review. In single-model mode, critical fields always go to review.
"""
import logging
import unicodedata
from typing import Any, Optional

from core.extractor import ExtractionDoc, Evidence, extract_entities

logger = logging.getLogger(__name__)

_VERDICT_AUTO_OK = "auto_ok"
_VERDICT_REVIEW = "review"
_VERDICT_NOT_FOUND = "not_found"
_VERDICT_SINGLE_MODEL = "single_model"


def normalize(value: Any) -> Optional[str]:
    """Normalize for comparison: lowercase, strip accents, collapse spaces."""
    if value is None:
        return None
    s = unicodedata.normalize("NFKD", str(value))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.strip().lower().split())


def _value_map(doc: Optional[ExtractionDoc]) -> dict[str, tuple[Any, str, Optional[str]]]:
    """{field: (value, status, quote)} from a doc's evidence."""
    if doc is None:
        return {}
    out = {}
    for e in doc.extractions:
        out[e.field_name] = (e.value, e.status, e.verbatim_quote)
    return out


def evaluate_consensus(
    doc_a: Optional[ExtractionDoc],
    doc_b: Optional[ExtractionDoc],
    critical_fields: list[str],
) -> tuple[str, dict[str, Any], list[str]]:
    """Compare extractions. Returns (verdict, payload, mismatched_fields).

    - "auto_ok":     all values agree (or single-model non-critical)
    - "review":      discrepancy / A has value & B didn't confirm / critical in
                     single-model mode
    - "not_found":   both models found nothing
    """
    map_a = _value_map(doc_a)
    map_b = _value_map(doc_b)
    all_keys = sorted(set(map_a) | set(map_b))

    single = doc_b is None
    payload: dict[str, Any] = {}
    mismatched: list[str] = []

    for key in all_keys:
        va, status_a, quote_a = map_a.get(key, (None, "not_found", None))
        vb, status_b, quote_b = map_b.get(key, (None, "not_found", None))

        if single:
            # Un solo modelo: los críticos NO se autoaprueban
            if key in critical_fields and va is not None:
                mismatched.append(key)
                payload[key] = {"a": va, "b": None, "single_model": True}
            elif va is None:
                payload[key] = None
            else:
                payload[key] = va
            continue

        if va is None and vb is None:
            payload[key] = None
            continue

        if va is None or vb is None:
            mismatched.append(key)
            payload[key] = {"a": va, "b": vb}
            continue

        if status_a != "ok" or status_b != "ok":
            mismatched.append(key)
            payload[key] = {"a": va, "b": vb, "status_a": status_a, "status_b": status_b}
            continue

        if normalize(va) == normalize(vb):
            payload[key] = va
        else:
            mismatched.append(key)
            payload[key] = {"a": va, "b": vb}

    if mismatched:
        return _VERDICT_REVIEW, payload, mismatched
    if all(v is None for v in payload.values()):
        return _VERDICT_NOT_FOUND, payload, []
    if single:
        return _VERDICT_SINGLE_MODEL, payload, []
    return _VERDICT_AUTO_OK, payload, []


def run_dual(
    text: str,
    fields: list,
    provider_a: Any,
    provider_b: Optional[Any] = None,
    critical_fields: Optional[list[str]] = None,
    examples: Optional[list[dict]] = None,
    existing_data: Optional[dict] = None,
    temperature_a: float = 0.05,
    temperature_b: float = 0.0,
) -> tuple[str, ExtractionDoc, Optional[ExtractionDoc]]:
    """Run A and B in parallel (ThreadPoolExecutor) and return the verdict.

    Returns (verdict, doc_a, doc_b).
    """
    import concurrent.futures

    critical_fields = critical_fields or []

    def run(p, temp):
        return extract_entities(text, fields, examples=examples,
                                existing_data=existing_data, provider=p,
                                temperature=temp)

    if provider_b is None:
        doc_a = run(provider_a, temperature_a)
        verdict = evaluate_consensus(doc_a, None, critical_fields)[0]
        return verdict, doc_a, None

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        fut_a = pool.submit(run, provider_a, temperature_a)
        fut_b = pool.submit(run, provider_b, temperature_b)
        doc_a = fut_a.result()
        doc_b = fut_b.result()

    verdict, _, _ = evaluate_consensus(doc_a, doc_b, critical_fields)
    return verdict, doc_a, doc_b