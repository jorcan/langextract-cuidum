# langextract-cuidum — Extractor de entidades genérico + adapter Cuidum

Refactor del proyecto original en dos capas: un **core de extracción agnóstico**
(entra texto, schema dinámico y ejemplos; salen entidades con **evidencia de
cita literal**) y un **adapter Cuidum** (crm_phonecall → core → tabla de
revisión HITL). Independiente de Odoo: el core no importa ni menciona Odoo
(guard en `tests/core/test_isolation.py`).

```
texto + FieldSpec[] + ejemplos + existing_data
        │
        ▼
   core.extract_entities()   ── provider (OpenRouter: DeepSeek / Gemma4)
        │                        │
        ├── Compuerta 1: grounding (cita literal + offsets)
        ├── Compuerta 2: consenso dual A/B (opcional)
        └── Compuerta 3: validadores deterministas (dni/nie/phone/email/date)
        ▼
   ExtractionDoc → Evidence[]  (value, quote, start, end, status)
```

## Estructura

```
core/                    # GENÉRICO — sin Odoo
  schema.py              # FieldSpec + build_dynamic_model (pydantic runtime)
  prompt.py              # build_prompt(fields, examples, existing_data, text)
  coerce.py              # coerción declarativa por FieldSpec.type
  grounding.py           # compuerta 1: verificación de cita literal
  validators.py          # compuerta 3: DNI módulo 23, NIE, phone ES, email, date
  extractor.py           # extract_entities() → ExtractionDoc
  consensus.py           # compuerta 2: evaluate_consensus + run_dual
  providers.py           # factory: hermes-api | openrouter-deepseek | openrouter-gemma4 | dict
adapters/cuidum/         # TODO lo específico de Cuidum
  phonecalls.py          # fetch crm_phonecall (migrado de src/db)
  schema_102.py          # FIELDS_102 generado desde el legacy (paridad garantizada)
  partner_fill.py        # caso de uso: rellenar campos vacíos del partner
  review.py              # tabla HITL hermes_partner_fill (n8n_odoo)
data/
  schemas/partner_fill.json   # schema del caso cuidador + targets (columnas reales)
  samples/golden_30.json      # golden set etiquetado para evaluar
  examples/cuidum-102.json    # few-shot del schema 102 (3 ejemplos)
scripts/
  extract_cli.py         # CLI: --schema partner-fill|cuidum-102|<file.json>
  pilot_one_by_one.py    # PILOTO 1-en-1: extracción dual + revisión humana por campo
  golden_eval.py         # métricas por campo contra el golden set
  export_review.py       # CSV de la cola HITL para aprobar/aplicar
  inventory.py           # inventario de columnas res_partner (cuidador/contacto)
  generate_schema_102.py # regenera adapters/cuidum/schema_102.py desde src.models
src/                     # LEGACY (en proceso de decomisión; los scripts
                         #   run_pipeline/batch_extract/triage aún lo usan)
```

## Uso rápido

```bash
source .venv/bin/activate

# Ver el schema del caso cuidador
python scripts/extract_cli.py --schema partner-fill --mode schema

# Extracción de UN texto con el core (sin BD)
python -c "
from core import extract_entities, FieldSpec, make_provider
doc = extract_entities(
    'Cliente: Mi hija Marta, vive conmigo. Tel 34612345678',
    [FieldSpec(name='parentesco', type='literal', allowed=['hija','hijo']),
     FieldSpec(name='telefono', type='string', validator='phone_es')],
    provider=make_provider('openrouter-deepseek'))
print(doc.format())
"

# PILOTO 1-en-1 (candidato real de crm_phonecall con campos vacíos)
python scripts/pilot_one_by_one.py          # requiere terminal interactiva

# Golden eval (métricas por campo)
python scripts/golden_eval.py --provider openrouter-deepseek

# Export de la cola de revisión humana
python scripts/export_review.py --status pending
```

## Servicio web + API (portable, docker-compose)

Servicio FastAPI que expone el core como API y una UI de pruebas, empaquetado
en un contenedor **portable** (migrar = copiar `deploy/` + `.env` y `up -d`):

```bash
# Local (este host, solo 127.0.0.1:8654)
docker compose -f deploy/docker-compose.yml --env-file deploy/.env.local up -d

# Prod-A (VPS/Traefik) + override
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.traefik.yml \
  --env-file deploy/.env up -d
```

Endpoints (requieren `X-API-Key` = `API_TOKEN`):

| Endpoint | Qué hace |
|---|---|
| `GET /health` | estado del servicio |
| `GET /api/v1/schemas` | schemas disponibles (partner-fill, cuidum-102) |
| `POST /api/v1/extract` | extracción síncrona (single o consenso dual) desde texto |
| `GET /api/v1/stats` | KPIs de observabilidad (n8n_odoo) |
| `GET /api/v1/review` | cola HITL pendientes |
| `POST /api/v1/review/{call_id}` | aprobar/rechazar/corregir campos |
| `GET /` | UI web de pruebas (probador + cola + KPIs) |

Guía de migración y portabilidad: `deploy/README-MIGRACION.md`.
Verificado E2E (08/09): health, 401 sin token, schemas, extract real con citas,
stats y POST review con persistencia.

## Providers

| Nombre | Modelo | Vía |
|---|---|---|
| `openrouter-deepseek` | `deepseek/deepseek-v4-flash-0731` | OpenRouter (API key en `OPENROUTER_API_KEY`) |
| `openrouter-gemma4` | `google/gemma-4-31b-it` | OpenRouter (consenso B) |
| `hermes-api` | gateway local :8642 | requiere Hermes API Server VIVO (si da 401, usar OpenRouter) |
| dict `{model_id, base_url, api_key}` | cualquiera | OpenAI-compatible |

**Nota (2026-09-08):** el Hermes API Server local (`127.0.0.1:8642`) devolvía
401 (key stale o servidor caído); OpenRouter responde 200 con la key de
`~/.hermes/credentials.env`. El pipeline usa OpenRouter directamente.

## Esquema partner-fill y mapeo a columnas reales

Inventario real de `res_partner` (2026-09-08): `x_relacion_familiar` 99% vacío,
`mobile` 16.6%, `email` <5%. Mapeo actual en `data/schemas/partner_fill.json`:

| Campo lógico | Columna destino | Estado |
|---|---|---|
| `parentesco_cuidador` | `x_relacion_familiar` | ✅ existe (99% vacía) |
| `telefono_contacto` | `mobile` | ✅ existe |
| `email_contacto` | `email` | ✅ existe |
| `nombre_cuidador` | — | ⚠️ **no existe columna** → crear `x_*` en Odoo (decidir) |
| `telefono_cuidador` | — | ⚠️ idem |
| `dni_cuidador` | — | ⚠️ idem |
| `vive_con_paciente` | — | ⚠️ idem |

Los campos sin columna destino se extraen igualmente como **evidencia para
revisión**; la persistencia requiere crear los campos `x_*` en Odoo (decisión
de Jorge).

## Contribuir / regenerar

- `python scripts/generate_schema_102.py` — regenera `schema_102.py` y los ejemplos desde `src.models.CallEntities`.
- Añadir un adapter nuevo = crear `adapters/<dominio>/` con su fetch + schema JSON; el core no cambia.
- Los tests del core NO tocan red (providers mockeados); tests de paridad validan el contrato 102.

## Contexto de negocio

La tarea original #230 (LangExtract, análisis de señales churn/sentimiento) se
cerró como no viable: Aura y SIRC ya extraen señales en tiempo real. Este
proyecto NO reabre eso: entrega (1) una herramienta de extracción reutilizable
independiente del dominio y (2) relleno de **datos maestros vacíos del partner**
con cita literal como evidencia, en modo piloto 1-en-1 con revisión humana.