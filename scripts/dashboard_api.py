#!/usr/bin/env python3
"""
Dashboard API + HTML UI for LangExtract-Cuidum.
Serves extraction data from PostgreSQL at /api/data and a rich dashboard at /.

Usage:
    cd ~/repos/langextract-cuidum && source .venv/bin/activate
    python3 scripts/dashboard_api.py [--port 8650]
"""

import argparse
import json
import logging
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.db import _get_n8n_conn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dashboard")

PORT = int(os.environ.get("DASHBOARD_PORT", 8650))


def fetch_data():
    """Fetch all extraction records from PostgreSQL."""
    conn = _get_n8n_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, call_id, partner_id, extraction_data, 
               schema_version, confidence, extracted_at
        FROM hermes_langextract_cuidum
        ORDER BY id
    """)
    rows = []
    for r in cur.fetchall():
        rows.append({
            "id": r[0],
            "call_id": r[1],
            "partner_id": r[2],
            "extraction_data": r[3],
            "schema_version": r[4],
            "confidence": float(r[5]) if r[5] else None,
            "extracted_at": str(r[6]) if r[6] else None,
        })
    cur.close()
    conn.close()
    return rows


def compute_aggregations(data):
    """Compute aggregate statistics from extraction data."""
    records = [r["extraction_data"] for r in data]
    n = len(records)

    # Categorical fields with distributions
    cat_fields = {
        "urgencia": {},
        "quien_llama": {},
        "relacion_llamante_paciente": {},
        "patologia_principal": {},
        "tipo_servicio_actual": {},
        "convivencia_paciente": {},
        "movilidad_actual": {},
        "estado_cognitivo": {},
        "confianza_empresa": {},
        "lealtad_marca": {},
        "fase_ciclo_cliente_inferida": {},
        "intencion_permanencia": {},
        "claridad_comunicacion": {},
        "receptividad_gestion": {},
        "actitud": {},
        "nivel_urgencia_voz": {},
        "sentimiento_apertura": {},
        "sentimiento_cierre": {},
        "tendencia_emocional_en_llamada": {},
        "frecuencia_contacto_inferida": {},
        "tipo_contrato": {},
        "situacion_pagos": {},
        "confianza_economica": {},
        "soledad_aislamiento": {},
        "deseo_cambio_cuidadora": {},
    }

    numerics = {
        "churn_risk_score": [],
        "baja_probabilidad_inferida": [],
        "satisfaccion_general": [],
    }

    bools = {
        "menciona_baja": [0, 0],
        "menciona_queja": [0, 0],
        "upsell_opportunity": [0, 0],
        "downgrade_risk": [0, 0],
        "anomalia_comportamiento": [0, 0],
        "agradecimiento_cliente": [0, 0],
        "empatia_gestor": [0, 0],
        "negociacion_tarifa": [0, 0],
        "ampliacion_horas_interes": [0, 0],
        "reduccion_horas_riesgo": [0, 0],
        "amenaza_reclamacion_legal": [0, 0],
        "deseo_cambio_cuidadora_bool": [0, 0],
        "soledad_aislamiento_bool": [0, 0],
        "mejora_salud_implica_baja_bool": [0, 0],
    }

    campos_por_registro = []

    for rec in records:
        # Count non-null fields per record
        non_null = sum(1 for v in rec.values() if v is not None and v != "" and v not in ("no_mencionado", "no_mencionada", "no_aplica", "no_aplica_sin_cuidadora"))
        campos_por_registro.append(non_null)

        # Categorical
        for field in cat_fields:
            v = rec.get(field)
            if v is not None and v != "":
                v_str = str(v)[:60]
                cat_fields[field][v_str] = cat_fields[field].get(v_str, 0) + 1

        # Numeric
        for field in numerics:
            v = rec.get(field)
            if v is not None:
                try:
                    numerics[field].append(float(v))
                except (ValueError, TypeError):
                    pass

        # Boolean
        for field in bools:
            key = field.replace("_bool", "")
            v = rec.get(key)
            if v is True:
                bools[field][0] += 1
            elif v is False:
                bools[field][1] += 1

    # Aggregate categorical to top values
    cat_agg = {}
    for field, dist in cat_fields.items():
        total = sum(dist.values())
        top = sorted(dist.items(), key=lambda x: -x[1])[:10]
        cat_agg[field] = {
            "total": total,
            "top": [{"value": k, "count": v, "pct": round(v / total * 100, 1) if total else 0} for k, v in top],
        }

    # Aggregate numeric
    num_agg = {}
    for field, vals in numerics.items():
        if vals:
            num_agg[field] = {
                "avg": round(sum(vals) / len(vals), 2),
                "min": round(min(vals), 2),
                "max": round(max(vals), 2),
                "count": len(vals),
                "distribution": sorted(vals),
            }
        else:
            num_agg[field] = {"avg": None, "min": None, "max": None, "count": 0, "distribution": []}

    # Aggregate bool
    bool_agg = {}
    for field, (yes, no) in bools.items():
        total = yes + no
        bool_agg[field] = {
            "yes": yes,
            "no": no,
            "pct_yes": round(yes / total * 100, 1) if total else 0,
            "total": total,
        }

    # Average non-null fields per record
    avg_campos = round(sum(campos_por_registro) / len(campos_por_registro), 1) if campos_por_registro else 0

    return {
        "total_records": n,
        "avg_campos_por_registro": avg_campos,
        "categorical": cat_agg,
        "numeric": num_agg,
        "boolean": bool_agg,
    }


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/data":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                data = fetch_data()
                aggs = compute_aggregations(data)
                self.wfile.write(json.dumps({
                    "success": True,
                    "records": data,
                    "aggregations": aggs,
                }, ensure_ascii=False).encode())
            except Exception as e:
                logger.error("Error fetching data: %s", e)
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": str(e),
                }).encode())

        elif path == "/" or path == "":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html_path = Path(os.path.expanduser("~")) / "static-docs" / "dashboard-langextract.html"
            if html_path.exists():
                self.wfile.write(html_path.read_bytes())
            else:
                self.wfile.write(b"<html><body><h1>Dashboard HTML not found</h1></body></html>")

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")

    def log_message(self, format, *args):
        logger.info(format, *args)


def run_server(port):
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    logger.info("Dashboard en http://0.0.0.0:%d", port)
    logger.info("  API: http://localhost:%d/api/data", port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", "-p", type=int, default=PORT)
    args = parser.parse_args()
    run_server(args.port)
