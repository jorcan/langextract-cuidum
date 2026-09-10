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
    texto: str = Field(..., min_length=1, max_length=200_000)
    schema: str = "partner-fill"
    use_dual: bool = True
    provider_a: str = "openrouter-deepseek"
    provider_b: Optional[str] = "openrouter-gemma4"
    examples: Optional[list[dict]] = None
    max_chars: Optional[int] = Field(
        None, description="Recorta el texto a los últimos N caracteres (para transcripciones largas). Default: sin recorte.")


class ReviewDecision(BaseModel):
    campo: str
    accion: str  # approve | reject | fix
    valor: Optional[str] = None


class ReviewRequest(BaseModel):
    decisiones: list[ReviewDecision]


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
    texto = req.texto
    recortado = False
    if req.max_chars and len(texto) > req.max_chars:
        texto = texto[-req.max_chars:]  # tramo FINAL: en entrevistas van los datos personales al final
        recortado = True
    fields = _load_fields(req.schema)
    _log_event({"tipo": "extract.inicio", "schema": req.schema,
                "chars": len(texto), "recortado": recortado,
                "modelos": req.provider_a + ("," + req.provider_b if req.use_dual and req.provider_b else "")})
    if req.use_dual and req.provider_b:
        from core.consensus import run_dual
        from core.providers import make_provider
        prov_a = make_provider(req.provider_a)
        prov_b = make_provider(req.provider_b)
        critical = [f.name for f in fields if f.validator or f.type == "bool"]
        _log_event({"tipo": "llm.a.inicio", "modelo": req.provider_a})
        verdict, doc_a, _ = run_dual(
            texto, fields, provider_a=prov_a, provider_b=prov_b,
            critical_fields=critical, examples=req.examples)
        _log_event({"tipo": "llm.a.fin", "duracion_s": _timing(t0)})
        payload = doc_a.format()
        _log_event({"tipo": "extract.verdict", "verdict": verdict})
    else:
        from core.extractor import extract_entities
        from core.providers import make_provider
        prov = make_provider(req.provider_a)
        _log_event({"tipo": "llm.inicio", "modelo": req.provider_a})
        doc = extract_entities(texto, fields, provider=prov, examples=req.examples)
        _log_event({"tipo": "llm.fin", "duracion_s": _timing(t0)})
        payload = doc.format()
        verdict = "single_model"
        _log_event({"tipo": "extract.verdict", "verdict": verdict})
    _log_event({"tipo": "extract.fin", "duracion_total_s": _timing(t0)})
    return {"verdict": verdict, "doc": payload}


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
        import urllib.request
        from core.providers import get_openrouter_key, OPENROUTER_URL
        key = get_openrouter_key()
        # cachear 10 min para no martillear la API de OpenRouter
        import time as _t
        now = _t.time()
        models = getattr(get_models, "_cache", None)
        if not (models and now - getattr(get_models, "_ts", 0) < 600):
            req = urllib.request.Request(f"{OPENROUTER_URL}/models",
                                        headers={"Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode()).get("data", [])
            out = []
            for m in data:
                pr = m.get("pricing", {})
                prompt = float(pr.get("prompt") or 0)      # USD por token
                comp = float(pr.get("completion") or 0)    # USD por token
                coste_1m = round((prompt + comp) * 1_000_000, 6)  # USD por 1M tokens
                if coste_1m < 0:
                    continue  # modelos sin precio publicado (openrouter/auto, etc.)
                out.append({
                    "id": m["id"],
                    "name": m.get("name", m["id"]),
                    "coste_1m_usd": coste_1m,
                })
            out.sort(key=lambda x: (x["coste_1m_usd"], x["id"]))  # menor a mayor
            models = out
            get_models._cache = models
            get_models._ts = now
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