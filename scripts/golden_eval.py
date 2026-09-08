#!/usr/bin/env python3
"""Evaluación del schema partner-fill contra un golden set.

Métricas por campo: precisión, recall, fallos de grounding, fallos de
validador. Uso:

  python scripts/golden_eval.py --golden data/samples/golden_30.json        # LLM real
  python scripts/golden_eval.py --golden ... --provider mock:ruta.json      # pruebas
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def resolve_provider(ref: str):
    """'hermes-api' | 'openrouter-gemma4' | 'mock:<file.json>' (respuestas fijas)."""
    from core.providers import make_provider
    if ref.startswith("mock:"):
        path = ref.split("mock:", 1)[1]
        responses = [json.loads(l) for l in open(path, encoding="utf-8")]

        class Mock:
            def __init__(self, raws):
                self.raws = raws
                self.i = 0

            def infer(self, prompts):
                raw = json.dumps(self.raws[self.i % len(self.raws)], ensure_ascii=False)
                self.i += 1
                return [[type("O", (), {"output": raw})()]]

        return Mock(responses)
    return make_provider(ref)


def run_eval(provider, golden, fields) -> dict:
    from core.extractor import extract_entities
    per_field = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "grounding_fail": 0,
                                     "validator_fail": 0})
    CONTROL_KEYS = ("expected_status",)
    for item in golden:
        text = item["text"]
        exp = {k: v for k, v in item.get("expected", {}).items() if k not in CONTROL_KEYS}
        exp_status = item.get("expected_status", {})
        doc = extract_entities(text, fields, provider=provider)
        ev = {e.field_name: e for e in doc.extractions}
        for f, expected_val in exp.items():
            e = ev.get(f)
            got = e.value if e else None
            if e is None or e.status in ("not_found",):
                per_field[f]["fn"] += 1
            elif e.status == "grounding_fail":
                per_field[f]["grounding_fail"] += 1
                if exp_status.get(f) != "grounding_fail":
                    per_field[f]["fn"] += 1
            elif e.status == "validator_fail":
                per_field[f]["validator_fail"] += 1
                if exp_status.get(f) != "validator_fail":
                    per_field[f]["fn"] += 1
            elif e.status == "ok":
                if str(got) == str(expected_val):
                    per_field[f]["tp"] += 1
                else:
                    per_field[f]["fp"] += 1
                    per_field[f]["fn"] += 1
        # Falsos positivos: campos extraídos que el golden da como ausentes
        for f, e in ev.items():
            if e and e.status == "ok" and f not in exp:
                per_field[f]["fp"] += 1
    return per_field


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", default=str(ROOT / "data/samples/golden_30.json"))
    ap.add_argument("--schema", default="partner-fill")
    ap.add_argument("--provider", default="hermes-api")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    from scripts.extract_cli import resolve_schema
    fields, _ = resolve_schema(args.schema)
    golden = json.load(open(args.golden, encoding="utf-8"))
    provider = resolve_provider(args.provider)

    per_field = run_eval(provider, golden, fields)

    lines = [f"# Golden eval — {args.schema} ({len(golden)} casos) — "
             f"{datetime.now():%Y-%m-%d %H:%M}",
             "", "| campo | TP | FP | FN | grounding_fail | validator_fail | precision | recall |",
             "|---|---|---|---|---|---|---|---|"]
    tot_tp = tot_fp = tot_fn = 0
    for f in sorted(per_field):
        s = per_field[f]
        prec = s["tp"] / (s["tp"] + s["fp"]) if (s["tp"] + s["fp"]) else 1.0
        rec = s["tp"] / (s["tp"] + s["fn"]) if (s["tp"] + s["fn"]) else 1.0
        tot_tp += s["tp"]; tot_fp += s["fp"]; tot_fn += s["fn"]
        lines.append(f"| {f} | {s['tp']} | {s['fp']} | {s['fn']} | "
                     f"{s['grounding_fail']} | {s['validator_fail']} | {prec:.2f} | {rec:.2f} |")
    g_prec = tot_tp / (tot_tp + tot_fp) if (tot_tp + tot_fp) else 1.0
    g_rec = tot_tp / (tot_tp + tot_fn) if (tot_tp + tot_fn) else 1.0
    lines += ["", f"**Global: precision {g_prec:.3f} / recall {g_rec:.3f} "
                  f"(TP {tot_tp} FP {tot_fp} FN {tot_fn})**",
              "", "_Umbrales objetivo: precision >= 0.95, recall >= 0.90._"]

    out = args.out or (ROOT / "data/output" / f"golden_eval_{datetime.now():%Y%m%d_%H%M%S}.md")
    Path(out).write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())