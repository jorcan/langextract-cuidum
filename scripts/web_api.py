"""Servicio web portable de Langextract — API + UI.

Endpoints:
  GET  /health                      → estado
  GET  /api/v1/schemas              → lista de schemas disponibles
  POST /api/v1/extract              → extracción (síncrona) con consenso dual opcional
  GET  /api/v1/stats                → KPIs de observabilidad (n8n_odoo)
  GET  /api/v1/review               → cola HITL pendientes
  POST /api/v1/review/{call_id}     → aprobar/rechazar/corregir campos
  GET  /                           → UI (probador + revisión)

Seguridad:
  - /api/* requiere header X-API-Key == API_TOKEN (hmac.compare_digest)
  - si API_TOKEN no está definido: el servicio avisa y solo es seguro en localhost
  - límite de body (MAX_BODY), validación Pydantic, sin logs de secretos
  - escucha en 0.0.0.0 pero se espera detrás de Traefik (VPS) o nginx/SSH (local)

Portable: mismo código/imagen en cualquier host — solo cambia el compose
(red traefik-public en el VPS; 127.0.0.1 o túnel en local).
"""
import hmac
import json
import logging
import os
import time
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT),):  # permite import core.* / adapters.*
    import sys
    if p not in sys.path:
        sys.path.insert(0, p)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("langextract-web")

API_TOKEN = os.environ.get("API_TOKEN", "").strip()
MAX_BODY = int(os.environ.get("MAX_BODY_BYTES", 10 * 1024 * 1024))  # 10 MB
UI_DIR = ROOT / "ui"

app = FastAPI(title="Langextract Service", version="1.0.0")


# ── Actividad en vivo (observabilidad del extract en curso) ─────────────
# Cola thread-safe de eventos: cada /extract emite pasos con timestamp y
# duración. La UI hace polling a /api/v1/activity y pinta el progreso real.
_ACTIVITY = deque(maxlen=300)
_ACTIVITY_LOCK = threading.Lock()


def _log_event(evt: dict):
    """Añade un evento de actividad con timestamp UTC ISO."""
    evt = dict(evt)
    evt.setdefault("ts", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    with _ACTIVITY_LOCK:
        _ACTIVITY.appendleft(evt)


def _timing(t0: float) -> float:
    return round(time.monotonic() - t0, 1)


# ── Seguridad ────────────────────────────────────────────────────────────
def _auth_ok(x_api_key: Optional[str]) -> bool:
    if not API_TOKEN:
        return False
    if x_api_key and hmac.compare_digest(x_api_key, API_TOKEN):
        return True
    return False


def _require_auth(x_api_key: Optional[str] = Header(None), request: Request = None):
    if not API_TOKEN:
        raise HTTPException(503, "API_TOKEN no configurado en el servidor")
    # Header X-API-Key  O  cookie httpOnly same-origin (seteada al servir /)
    key = x_api_key or (request.cookies.get("lxt_api_token") if request else None)
    if not _auth_ok(key):
        raise HTTPException(401, "API key inválida o ausente")


# ── Schemas de petición ─────────────────────────────────────────────────
class ExtractRequest(BaseModel):
    texto: str = Field("", min_length=0, max_length=200_000)
    schema: str = "partner-fill"
    use_dual: bool = True
    provider_a: str = "openrouter-deepseek"
    provider_b: Optional[str] = "openrouter-gemma4"
    examples: Optional[list[dict]] = None
    max_chars: Optional[int] = Field(
        None, description="Recorta el texto a los últimos N caracteres (para transcripciones largas). Default: sin recorte.")
    call_id: Optional[int] = Field(
        None, description="ID de crm_phonecall en Odoo Cuidum. Si se pasa, la transcripción se lee del campo description y se añade el contexto del partner (vocabulario selection real).")
    use_partner_context: bool = Field(
        True, description="Cargar campos selection reales del partner (res.partner) para restringir allowed y no re-extraer lo ya poblado.")


class ReviewDecision(BaseModel):
    campo: str
    accion: str  # approve | reject | fix
    valor: Optional[str] = None


class ReviewRequest(BaseModel):
    decisiones: list[ReviewDecision]


class ExampleIn(BaseModel):
    schema: str = "partner-fill"
    text: str = Field(..., min_length=1)
    extractions: dict = Field(..., description="Campos corregidos (nombre -> valor) que el LLM debe aprender")


# ── Helpers ──────────────────────────────────────────────────────────────
def _load_fields(schema_ref: str):
    from adapters.cuidum import partner_fill
    if schema_ref == "partner-fill":
        fields, _ = partner_fill.load_partner_fill_schema()
        return fields
    if schema_ref == "candidata-entrevista":
        fields, _ = partner_fill.load_schema_file(
            ROOT / "data/schemas/candidata_entrevista.json")
        return fields
    if schema_ref == "cuidum-102":
        from adapters.cuidum.schema_102 import FIELDS_102
        return FIELDS_102
    p = Path(schema_ref)
    if p.exists() and p.suffix == ".json":
        fields, _ = partner_fill.load_schema_file(p)
        return fields
    raise HTTPException(400, f"Schema desconocido: {schema_ref}")


# ── Endpoints ────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "langextract", "version": "1.0.0",
            "token_configured": bool(API_TOKEN)}


@app.get("/api/v1/schemas", dependencies=[] )
async def get_schemas(request: Request, x_api_key: Optional[str] = Header(None)):
    _require_auth(x_api_key, request=request)
    out = []
    for sid in ("partner-fill", "candidata-entrevista", "cuidum-102"):
        try:
            fields = _load_fields(sid)
        except Exception:
            continue
        out.append({"id": sid, "campos": [
            {"name": f.name, "type": f.type, "validator": f.validator,
             "allowed": f.allowed} for f in fields]})
    return {"schemas": out}


@app.post("/api/v1/extract", dependencies=[])
async def extract(request: Request, req: ExtractRequest, x_api_key: Optional[str] = Header(None)):
    _require_auth(x_api_key, request=request)
    t0 = time.monotonic()
    texto = (req.texto or "").strip()
    recortado = False
    call_info = None
    partner_ctx = None
    existing_data = None

    # ── Fuente por call_id: transcripción en crm_phonecall.description ──
    if req.call_id:
        from adapters.cuidum.phonecalls import fetch_call_by_id, fetch_partner_selection_context
        call = fetch_call_by_id(req.call_id)
        if call is None:
            raise HTTPException(404, f"crm_phonecall {req.call_id} no existe")
        desc = call.get("description") or ""
        if req.use_partner_context and call.get("partner_id"):
            partner_ctx = fetch_partner_selection_context(call["partner_id"])
        call_info = {
            "call_id": call["id"],
            "name": call.get("name"),
            "partner_id": call.get("partner_id"),
            "clave": f"{call.get('nombre_clave')} ({call.get('codigo_clave')})" if call.get("nombre_clave") else call.get("clave"),
            "subclave": f"{call.get('nombre_subclave')} ({call.get('codigo_subclave')})" if call.get("nombre_subclave") else call.get("subclave"),
            "description_chars": len(desc),
        }
        if not texto:
            texto = desc
        elif desc:
            # texto explícito + transcripción: adjuntar la llamada como contexto
            texto = f"{texto}\n\n=== TRANSCRIPCIÓN DE LA LLAMADA #{call['id']} ===\n{desc}"
    if not texto:
        raise HTTPException(422, "texto vacío — pasa texto o call_id de crm_phonecall")

    if req.max_chars and len(texto) > req.max_chars:
        texto = texto[-req.max_chars:]  # tramo FINAL (datos personales al final)
        recortado = True

    fields = _load_fields(req.schema)

    # ── Restricción al vocabulario real de Odoo (campos selection) ────
    if partner_ctx:
        from adapters.cuidum.odoo_enrich import enrich_fields_with_odoo, existing_values_from_partner
        fields = enrich_fields_with_odoo(fields, partner_ctx)
        existing_data = existing_values_from_partner(fields, partner_ctx)

    # ── Ejemplos few-shot: los pasados explícitamente o los guardados ──
    if not req.examples:
        examples_path = ROOT / "data" / "examples" / f"{req.schema}.json"
        if examples_path.exists():
            try:
                req.examples = json.loads(examples_path.read_text(encoding="utf-8")) or None
            except Exception:
                req.examples = None

    _log_event({"tipo": "extract.inicio", "schema": req.schema,
                "chars": len(texto), "recortado": recortado,
                "call_id": req.call_id, "partner_ctx": bool(partner_ctx),
                "modelos": req.provider_a + ("," + req.provider_b if req.use_dual and req.provider_b else "")})

    # ── Estimación de coste (antes de llamar al LLM) ───────────────────
    from core.providers import get_openrouter_models, estimate_extract_cost
    models = get_openrouter_models()
    model_a_id = req.provider_a[len("openrouter-model:"):] if req.provider_a.startswith("openrouter-model:") else req.provider_a
    n_calls = 2 if (req.use_dual and req.provider_b) else 1
    cost_est = estimate_extract_cost(model_a_id, len(texto), 80 + 24 * len(fields),
                                     n_calls=n_calls, models=models)
    if cost_est.get("estimado"):
        _log_event({"tipo": "coste.estimado", "modelo": model_a_id,
                    "coste_usd": cost_est["coste_estimado_usd"],
                    "tokens_prompt": cost_est["prompt_tokens"],
                    "tokens_completion": cost_est["completion_tokens"]})

    if req.use_dual and req.provider_b:
        from core.consensus import run_dual
        from core.providers import make_provider
        prov_a = make_provider(req.provider_a)
        prov_b = make_provider(req.provider_b)
        critical = [f.name for f in fields if f.validator or f.type == "bool"]
        _log_event({"tipo": "llm.a.inicio", "modelo": req.provider_a})
        verdict, doc_a, _ = run_dual(
            texto, fields, provider_a=prov_a, provider_b=prov_b,
            critical_fields=critical, examples=req.examples,
            existing_data=existing_data)
        _log_event({"tipo": "llm.a.fin", "duracion_s": _timing(t0)})
        payload = doc_a.format()
        _log_event({"tipo": "extract.verdict", "verdict": verdict})
    else:
        from core.extractor import extract_entities
        from core.providers import make_provider
        prov = make_provider(req.provider_a)
        _log_event({"tipo": "llm.inicio", "modelo": req.provider_a})
        doc = extract_entities(texto, fields, provider=prov, examples=req.examples,
                               existing_data=existing_data)
        _log_event({"tipo": "llm.fin", "duracion_s": _timing(t0)})
        payload = doc.format()
        verdict = "single_model"
        _log_event({"tipo": "extract.verdict", "verdict": verdict})
    _log_event({"tipo": "extract.fin", "duracion_total_s": _timing(t0)})

    resp = {"verdict": verdict, "doc": payload, "coste_estimado": cost_est}
    if call_info:
        resp["call"] = call_info
    if partner_ctx:
        resp["partner"] = {
            "partner_id": (partner_ctx.get("partner") or {}).get("id"),
            "name": (partner_ctx.get("partner") or {}).get("name"),
            "selections_poblados": {
                k: v for k, v in (partner_ctx.get("selections") or {}).items()
                if v.get("valor_actual") is not None
            },
            "vocabulario_campos": sorted(partner_ctx.get("selections") or {}),
        }
    return resp


@app.get("/api/v1/stats", dependencies=[])
async def get_stats(request: Request, x_api_key: Optional[str] = Header(None)):
    _require_auth(x_api_key, request=request)
    try:
        from scripts.obs_dashboard import collect
        return collect()
    except Exception as e:
        logger.warning("stats error: %s", e)
        raise HTTPException(502, f"No se pudo leer estadísticas: {e}")


@app.get("/api/v1/review", dependencies=[])
async def list_review(request: Request, status: str = "pending", x_api_key: Optional[str] = Header(None)):
    _require_auth(x_api_key, request=request)
    import os
    import psycopg2
    from dotenv import load_dotenv
    load_dotenv()
    dsn = os.environ.get("N8N_DB_URL")
    if not dsn:
        raise HTTPException(503, "N8N_DB_URL no configurado")
    rows = []
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute("""
            SELECT call_id, partner_id, consensus_status, extracted_data::text,
                   evidence::text, review_status, created_at
            FROM hermes_partner_fill WHERE review_status = %s ORDER BY created_at ASC
        """, (status,))
        for r in cur.fetchall():
            rows.append({"call_id": r[0], "partner_id": r[1], "consensus_status": r[2],
                         "extracted_data": json.loads(r[3] or "{}"),
                         "evidence": json.loads(r[4] or "{}"),
                         "review_status": r[5], "created_at": str(r[6])})
        cur.close(); conn.close()
    except Exception as e:
        raise HTTPException(502, f"Error leyendo HITL: {e}")
    return {"items": rows}


@app.post("/api/v1/review/{call_id}", dependencies=[])
async def decide(request: Request, call_id: int, req: ReviewRequest, x_api_key: Optional[str] = Header(None)):
    _require_auth(x_api_key, request=request)
    import os
    import psycopg2
    from dotenv import load_dotenv
    load_dotenv()
    dsn = os.environ.get("N8N_DB_URL")
    if not dsn:
        raise HTTPException(503, "N8N_DB_URL no configurado")
    # Aplicar decisiones: approve/reject en evidence + estado global
    updates = {}
    for d in req.decisiones:
        updates[d.campo] = {"accion": d.accion, "valor": d.valor}
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute("SELECT evidence::text FROM hermes_partner_fill WHERE call_id = %s", (call_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, f"call_id {call_id} no está en la cola")
        ev = json.loads(row[0] or "{}")
        for campo, dec in updates.items():
            ev[campo] = {**ev.get(campo, {}), "review": dec["accion"]}
            if dec["valor"]:
                ev[campo]["fix"] = dec["valor"]
        all_ok = all(d.accion == "approve" for d in req.decisiones)
        cur.execute(
            "UPDATE hermes_partner_fill SET evidence = %s::jsonb, review_status = %s, "
            "reviewed_by = %s, reviewed_at = NOW() WHERE call_id = %s",
            (json.dumps(ev, ensure_ascii=False),
             "approved" if all_ok else "rejected", "web-api", call_id))
        conn.commit()
        cur.close(); conn.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Error guardando decisión: {e}")
    return {"ok": True, "call_id": call_id, "review_status": "approved" if all_ok else "rejected"}


@app.post("/api/v1/examples", dependencies=[])
async def add_example(request: Request, req: ExampleIn, x_api_key: Optional[str] = Header(None)):
    """Guardar una extracción corregida como ejemplo few-shot (loop de mejora de acierto).

    Escribe en data/examples/<schema>.json; ese fichero se envía como
    `examples` en /extract para que el LLM aprenda de la corrección humana.
    """
    _require_auth(x_api_key, request=request)
    EXAMPLES_DIR = ROOT / "data" / "examples"
    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    path = EXAMPLES_DIR / f"{req.schema}.json"
    existing = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        except Exception:
            existing = []
    # Dedup por texto (normalizado): si ya existe, se sustituye
    norm_text = " ".join(req.text.strip().lower().split())
    existing = [e for e in existing
                if " ".join((e.get("text") or "").strip().lower().split()) != norm_text]
    existing.insert(0, {"text": req.text, "extractions": req.extractions})
    existing = existing[:30]  # top-N más recientes
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    _log_event({"tipo": "examples.guardado", "schema": req.schema,
                "total": len(existing), "campos": sorted(req.extractions)})
    return {"ok": True, "schema": req.schema, "total": len(existing), "path": str(path)}


@app.get("/api/v1/examples", dependencies=[])
async def list_examples(request: Request, schema: str = "partner-fill", x_api_key: Optional[str] = Header(None)):
    _require_auth(x_api_key, request=request)
    path = ROOT / "data" / "examples" / f"{schema}.json"
    if not path.exists():
        return {"schema": schema, "examples": [], "total": 0}
    try:
        examples = json.loads(path.read_text(encoding="utf-8")) or []
    except Exception:
        examples = []
    return {"schema": schema, "examples": examples, "total": len(examples)}


@app.get("/api/v1/activity", dependencies=[])
async def get_activity(request: Request, x_api_key: Optional[str] = Header(None)):
    _require_auth(x_api_key, request=request)
    with _ACTIVITY_LOCK:
        events = list(_ACTIVITY)
    return {"events": events}


@app.get("/api/v1/models", dependencies=[])
async def get_models(request: Request, x_api_key: Optional[str] = Header(None)):
    _require_auth(x_api_key, request=request)
    """Lista modelos de OpenRouter con su coste (USD por 1M tokens), ordenados de menor a mayor coste."""
    try:
        from core.providers import get_openrouter_models
        models = get_openrouter_models()
        return {"models": models, "total": len(models),
                "unidad": "USD por 1M tokens (prompt+completion)"}
    except Exception as e:
        logger.warning("models fetch error: %s", e)
        raise HTTPException(502, f"No se pudieron obtener modelos de OpenRouter: {e}")


# ── UI ───────────────────────────────────────────────────────────────────
@app.get("/")
async def ui_index():
    _ui = UI_DIR / "index.html"
    if not _ui.exists():
        return JSONResponse({"detail": "UI no encontrada (assets no copiados)"}, status_code=404)
    # El token de API se entrega como cookie httpOnly MISM-ORIGIN (no visible en JS/HTML).
    # El JS hace fetch('/api/...') y el navegador envía la cookie automáticamente.
    # CORS: solo mismo origen — la cookie httpOnly + SameSite=Strict impide usarla desde
    # otros orígenes. La API acepta la cookie como alternativa al header X-API-Key.
    resp = FileResponse(_ui, media_type="text/html")
    resp.set_cookie("lxt_api_token", API_TOKEN, httponly=True, samesite="strict", secure=True, max_age=3600)
    return resp


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8650))
    workers = int(os.environ.get("WEB_WORKERS", "1"))
    # Con más de 1 worker, /health responde aunque un /extract esté ocupando
    # el otro worker (la app es stateless: token y DB por env).
    uvicorn.run(app, host="0.0.0.0", port=port, workers=workers)