# Migración / portabilidad del servicio LangExtract (contenedor)

## Qué es portable
El servicio es un contenedor docker (`langextract-web`) que incluye:
- core/ (extractor genérico) + adapters/cuidum/ + scripts/ + UI
- Deps fijadas (deploy/requirements.txt)

**No incluye las BD** — se conectan por variables de entorno:
- `N8N_DB_URL`  → resultados + cola HITL (accesible desde este host Y desde PROD-A)
- `CUIDUM_DB_URL` → candidatos (transcripciones) — **SOLO accesible desde 141.94.92.173**
- `OPENROUTER_API_KEY` → LLM

## Migrar a otro servidor (p.ej. PROD-A 57.129.137.207)
```bash
# 1. En el origen, empaqueta la imagen y el repo (o usa git):
docker save langextract-web:1.0.0 | gzip > langextract-web.img.gz
tar czf langextract-deploy.tgz deploy/ .env.example   # o clona y fitx deploy/ desde git

# 2. En el destino (VPS):
mkdir -p /srv/infra/langextract && cd /srv/infra/langextract
gunzip -c langextract-web.img.gz | docker load
# Copiar deploy/ + crear .env con los valores del destino (ver .env.example)
cp .env.example .env && vim .env     # API_TOKEN nuevo, N8N_DB_URL, OPENROUTER_API_KEY, HOST_TRAEFIK
docker compose -f deploy/docker-compose.yml \
               -f deploy/docker-compose.traefik.yml \
               --env-file .env up -d
```

## Reglas de portabilidad
- **Nada de IPs hardcodeadas**: todo va por env (`HOST_TRAEFIK`, `*_DB_URL`, claves).
- **No exponer 0.0.0.0**: en local solo `127.0.0.1:8654`; en PROD-A lo publica Traefik (red `traefik-public`).
- **El IP de Cuidum es el bloqueante**: si el servicio se mueve a un host cuyo IP no autorice Cuidum, las transcripciones no serán alcanzables. Opciones: pedir a Cuidum abrir el IP del VPS en el firewall/PG, o mantener un "gateway de datos" en este host. El resto del servicio (API, HITL, stats sobre n8n, OpenRouter) sí es 100% portable.
- **Volumen `langextract-out`** (`/app/data/output`) persiste exports/HTML en el contenedor; en una migración, `docker cp langextract-web:/app/data/output ./backup-output`.
- Docker Compose: este host usa Compose v5 (mergea); PROD-A usa v2.40 (NO mergea `include` pero SÍ los overrides `-f` clásicos — por eso usamos `-f docker-compose.yml -f docker-compose.traefik.yml`, no `include:`).

## Verificación tras migrar
```bash
curl -s http://127.0.0.1:8654/health
curl -s -H "X-API-Key: $API_TOKEN" http://127.0.0.1:8654/api/v1/schemas
curl -s -H "X-API-Key: $API_TOKEN" http://127.0.0.1:8654/api/v1/stats
# UI: abrir http://127.0.0.1:8654/ (o el host traefik)
```