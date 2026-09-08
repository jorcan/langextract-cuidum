#!/usr/bin/env python3
"""Generador del panel de observabilidad de Langextract-Cuidum.

Patrón cron-generated static HTML (skill standalone-dashboard):
consulta n8n_odoo (hermes_langextract_cuidum + hermes_partner_fill),
escribe un HTML self-contained en ~/static-docs/obs-langextract.html,
que nginx sirve tras el login por contraseña de agente.tribbe.es.

Uso:
  python3 scripts/obs_dashboard.py [--out /home/ubuntu/static-docs/obs-langextract.html]
Cron (cada 5 min, no_agent): refresca el panel en solitario.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

OUT_DEFAULT = Path.home() / "static-docs" / "obs-langextract.html"
TZ = timezone(timedelta(hours=2))  # Madrid


def get_dsn() -> str:
    from dotenv import load_dotenv
    load_dotenv()
    dsn = os.environ.get("N8N_DB_URL", "")
    if not dsn:
        for line in (root / ".env").read_text().splitlines():
            if line.startswith("N8N_DB_URL="):
                return line.split("=", 1)[1].strip()
    return dsn


def _q(cur, sql, params=None):
    cur.execute(sql, params or ())
    return cur.fetchall()


def collect() -> dict:
    import psycopg2
    conn = psycopg2.connect(get_dsn())
    cur = conn.cursor()

    payload = {"generated_at": datetime.now(TZ).strftime("%Y-%m-%d %H:%M")}

    # 1. Pipeline de extracción
    payload["total"] = _q(cur, "SELECT count(*) FROM hermes_langextract_cuidum")[0][0]
    payload["schema_counts"] = _q(
        cur, "SELECT schema_version, count(*) FROM hermes_langextract_cuidum GROUP BY 1 ORDER BY 2 DESC")
    payload["last_extraction"] = _q(
        cur, "SELECT max(extracted_at) FROM hermes_langextract_cuidum")[0][0]
    # Media de campos no nulos por extracción (contar claves en extraction_data::text)
    payload["avg_fields"] = _q(cur, """
        SELECT round(avg(n), 1) FROM (
            SELECT (jsonb_typeof(extraction_data) = 'object' AND
                    jsonb_array_length(extraction_data->'extracted_fields') > 0)::int AS n
            FROM hermes_langextract_cuidum
        ) t""")[0][0]

    # Campos ok/review/etc en la última tanda: usamos partner_fill para HITL y
    # hermes_langextract para el estado de extracción.
    payload["timeline"] = _q(cur, """
        SELECT date(extracted_at) d, count(*)
        FROM hermes_langextract_cuidum
        WHERE extracted_at >= NOW() - INTERVAL '30 days'
        GROUP BY 1 ORDER BY 1""")

    # Errores: filas con extraction_data vacío o confidence NULL
    payload["errors"] = _q(cur, """
        SELECT count(*) FROM hermes_langextract_cuidum
        WHERE extraction_data IS NULL OR extraction_data = '{}'::jsonb OR confidence IS NULL""")[0][0]

    # Últimas 10 extracciones
    payload["recent"] = _q(cur, """
        SELECT id, call_id, partner_id, schema_version, confidence, extracted_at
        FROM hermes_langextract_cuidum
        ORDER BY extracted_at DESC NULLS LAST LIMIT 10""")

    # 2. Cola HITL
    payload["hitl_total"] = _q(cur, "SELECT count(*) FROM hermes_partner_fill")[0][0]
    payload["hitl_by_status"] = _q(
        cur, "SELECT review_status, count(*) FROM hermes_partner_fill GROUP BY 1 ORDER BY 2 DESC")
    payload["hitl_by_consensus"] = _q(
        cur, "SELECT consensus_status, count(*) FROM hermes_partner_fill GROUP BY 1 ORDER BY 2 DESC")
    payload["hitl_pending_age_days"] = _q(cur, """
        SELECT coalesce(max(EXTRACT(DAY FROM (NOW() - created_at)))::int, 0)
        FROM hermes_partner_fill WHERE review_status = 'pending'""")[0][0]
    payload["hitl_pending_list"] = _q(cur, """
        SELECT call_id, partner_id, consensus_status,
               (SELECT count(*) FROM jsonb_object_keys(extracted_data)) AS n_fields,
               created_at
        FROM hermes_partner_fill WHERE review_status = 'pending'
        ORDER BY created_at ASC LIMIT 20""")

    cur.close(); conn.close()
    return payload


def render(payload: dict) -> str:
    data_json = json.dumps(payload, ensure_ascii=False, default=str)
    return TEMPLATE.replace("__DATA__", data_json)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    args = ap.parse_args(argv)

    payload = collect()
    html = render(payload)
    out = Path(args.out)
    out.write_text(html, encoding="utf-8")
    out.chmod(0o644)
    print(f"obs-langextract: {payload['total']} extracciones, "
          f"{payload['hitl_total']} HITL -> {out}")
    return 0


TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="300">
<title>Obs LangExtract — Panel de procesos</title>
<style>
  :root{--bg:#0d1117;--card:#161b22;--border:#30363d;--text:#e6edf3;--muted:#8b949e;
        --accent:#58a6ff;--green:#3fb950;--orange:#d29922;--red:#f85149;}
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:ui-monospace,'SF Mono',Menlo,monospace,sans-serif;background:var(--bg);color:var(--text);padding:24px}
  h1{font-size:1.4rem;color:var(--accent)} h1 small{color:var(--muted)}
  .sub{color:var(--muted);font-size:.85rem;margin:8px 0 20px}
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px}
  .kpi{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px}
  .kpi .v{font-size:1.7rem;font-weight:700}
  .kpi .v.green{color:var(--green)} .kpi .v.orange{color:var(--orange)} .kpi .v.red{color:var(--red)}
  .kpi .l{color:var(--muted);font-size:.8rem;margin-top:4px}
  section{margin-top:22px} h2{font-size:1.05rem;color:var(--text);margin-bottom:10px}
  table{width:100%;border-collapse:collapse;font-size:.85rem}
  th,td{border:1px solid var(--border);padding:7px 10px;text-align:left}
  th{background:#1c2129;color:var(--muted)}
  tr:nth-child(even){background:#161b22}
  .badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:.75rem}
  .badge.pending{background:#3d2c00;color:var(--orange)}
  .badge.ok{background:#0f2e1a;color:var(--green)}
  .badge.review{background:#3d2c00;color:var(--orange)}
  .badge.not_found{background:#2a1e0f;color:#c9a227}
  .bar{background:var(--card);display:flex;align-items:flex-end;gap:2px;height:120px;padding:10px}
  .bar div{background:var(--accent);width:12px;border-radius:2px}
  .footer{color:var(--muted);font-size:.75rem;margin-top:24px}
  a{color:var(--accent);text-decoration:none}
</style>
</head>
<body>
<h1>◉ Obs LangExtract <small>— observabilidad del pipeline de extracción (Cuidum)</small></h1>
<div class="sub">Generado: <span id="gen"></span> · Refresco automático cada 5 min · Datos de n8n_odoo</div>

<div class="kpis">
  <div class="kpi"><div class="v" id="kpi-total">—</div><div class="l">Llamadas procesadas</div></div>
  <div class="kpi"><div class="v" id="kpi-avg">—</div><div class="l">Campos medios / registro</div></div>
  <div class="kpi"><div class="v" id="kpi-last">—</div><div class="l">Última extracción</div></div>
  <div class="kpi"><div class="v orange" id="kpi-hitl">—</div><div class="l">HITL pendientes (antigüedad máx)</div></div>
  <div class="kpi"><div class="v red" id="kpi-err">—</div><div class="l">Registros con error</div></div>
</div>

<section><h2>📊 Extracciones por día (últimos 30 días)</h2><div class="bar" id="bar-chart"></div></section>

<section><h2>🧪 Cola HITL (revisión humana — partner_fill)</h2>
  <table>
    <thead><tr><th>Estado</th><th>N</th></tr></thead>
    <tbody id="t-hitl-status"></tbody>
  </table>
  <br>
  <table>
    <thead><tr><th>Consenso</th><th>N</th></tr></thead>
    <tbody id="t-hitl-consensus"></tbody>
  </table>
  <br>
  <table>
    <thead><tr><th>call_id</th><th>partner_id</th><th>consenso</th><th># campos</th><th>creado</th><th>Odoo</th></tr></thead>
    <tbody id="t-hitl-pending"></tbody>
  </table>
</section>

<section><h2>📋 Últimas extracciones</h2>
  <table>
    <thead><tr><th>id</th><th>call_id</th><th>partner_id</th><th>schema</th><th>confianza</th><th>fecha</th></tr></thead>
    <tbody id="t-recent"></tbody>
  </table>
</section>

<div class="footer" id="footer"></div>

<script>
const D = __DATA__;
document.getElementById('gen').textContent = D.generated_at;
document.getElementById('kpi-total').textContent = D.total;
document.getElementById('kpi-avg').textContent = (D.avg_fields ?? '—') + '/102';
document.getElementById('kpi-last').textContent = (D.last_extraction ?? '—').toString().slice(0, 16);
document.getElementById('kpi-hitl').textContent = D.hitl_pending_age_days + ' d';
document.getElementById('kpi-err').textContent = D.errors;

// Serie temporal (barras)
const bar = document.getElementById('bar-chart');
if (D.timeline && D.timeline.length) {
  const vals = D.timeline.map(r => parseInt(r[1]));
  const max = Math.max.apply(null, vals);
  D.timeline.forEach(r => {
    const h = Math.max(2, Math.round(parseInt(r[1]) / max * 100));
    const d = document.createElement('div');
    d.style.height = h + 'px';
    d.title = r[0] + ': ' + r[1];
    bar.appendChild(d);
  });
} else { bar.textContent = '(sin datos en 30 días)'; }

// HITL por estado
const ts = document.getElementById('t-hitl-status');
(D.hitl_by_status || []).forEach(r => {
  const tr = document.createElement('tr');
  tr.innerHTML = '<td>' + r[0] + '</td><td>' + r[1] + '</td>';
  ts.appendChild(tr);
});
// HITL por consenso
const tc = document.getElementById('t-hitl-consensus');
(D.hitl_by_consensus || []).forEach(r => {
  const tr = document.createElement('tr');
  tr.innerHTML = '<td>' + r[0] + '</td><td>' + r[1] + '</td>';
  tc.appendChild(tr);
});
// HITL pendientes
const tp = document.getElementById('t-hitl-pending');
(D.hitl_pending_list || []).forEach(r => {
  const tr = document.createElement('tr');
  const badge = r[2] === 'auto_ok' ? 'ok' : (r[2] === 'not_found' ? 'not_found' : 'review');
  tr.innerHTML = '<td>' + r[0] + '</td><td>' + r[1] + '</td>' +
    '<td><span class="badge ' + badge + '">' + r[2] + '</span></td>' +
    '<td>' + (r[3] ?? 0) + '</td>' +
    '<td>' + String(r[4]).slice(0, 16) + '</td>' +
    '<td><a href="https://tribbe.es/odoo/action-384/3/tasks/??" target="_blank">ver</a></td>';
  tp.appendChild(tr);
});
// Últimas extracciones
const tr = document.getElementById('t-recent');
(D.recent || []).forEach(r => {
  const t = document.createElement('tr');
  t.innerHTML = '<td>' + r[0] + '</td><td>' + r[1] + '</td><td>' + r[2] + '</td>' +
    '<td>' + (r[3] ?? '—') + '</td><td>' + (r[4] ?? '—') + '</td><td>' + String(r[5]).slice(0, 16) + '</td>';
  tr.appendChild(t);
});

document.getElementById('footer').textContent =
  'Langextract-Cuidum · Panel interno · solo agregados (IDs numéricos, sin datos personales) · ' + D.generated_at;
</script>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())