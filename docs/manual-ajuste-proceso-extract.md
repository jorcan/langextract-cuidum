# Manual (dummie): ajustar y mejorar el proceso de extracción de Langextract

> Para desarrolladores y operadores del servicio. Qué se puede tocar, dónde, y qué
> efecto tiene — sin leer todo el código. Ruta del repo: `~/repos/langextract-cuidum`.

---

## 1. Qué es el proceso en 30 segundos

Entra una transcripción de llamada (o un texto manual) y salen campos estructurados
(nombre, DNI, parentesco, teléfono…) listos para revisar y, en el futuro, escribir en
Odoo. Un LLM hace la extracción guiado por un **esquema** (qué campos, con qué
vocabulario), opcionalmente con **consenso dual** (dos modelos y un veredicto), y el
resultado queda en una **cola de revisión humana** (HITL).

Diagrama completo del pipeline: `data/diagrams/langextract-pipeline.html`

```
transcripción (call_id → crm_phonecall.description)
      │
      ▼
adapter + contexto partner (vocabulario REAL de Odoo, campos ya poblados se saltan)
      │
      ▼
prompt + esquema + ejemplos few-shot (data/examples/<schema>.json)
      │
      ▼
LLM A ──► consenso ──► LLM B   (dual opcional)
      │
      ▼
grounding (citas) + coerce (normalización) + validadores (DNI, email, teléfono)
      │
      ▼
coste estimado + resultado → cola HITL → loop few-shot (guardar correcciones)
```

---

## 2. Mapa de mandos (qué quiero hacer → dónde)

| Quiero… | Lo hago en… |
|---|---|
| Cambiar qué campos se extraen | `data/schemas/*.json` (o código para partner-fill: `adapters/cuidum/partner_fill.py`) |
| Restringir el vocabulario de un campo | `allowed` en el esquema (si es columna selection de Odoo, se hace SOLO) |
| Mejorar el acierto de un caso concreto | Guardar la corrección desde la UI → `data/examples/<schema>.json` |
| Cambiar el modelo / ver precios | Selector de modelos en la UI (432 modelos, precios reales por 1M) |
| Quitar el doble modelo (más rápido, menos fiable) | Desmarcar "Consenso dual" en la UI, o `use_dual: false` en el POST |
| Trabajar con transcripciones largas | Checkbox "Recortar a 6000 chars" (recorta por el FINAL, donde suelen estar los datos) |
| Revisar lo extraído | Pestaña "🧾 Cola de revisión" de la UI |
| Procesar muchas llamadas de golpe | CLI: `python scripts/extract_cli.py --mode extract` |
| Verificar que no he roto nada | `pytest` desde la raíz del repo |
| Ver actividad en tiempo real | Pestaña "👁 Actividad en vivo" (polling 2s) |

---

## 3. Ajustar QUÉ se extrae (el esquema)

Los esquemas son ficheros JSON. Existen dos editables + uno generado:

| Schema | Dónde vive | Cuándo usarlo |
|---|---|---|
| `partner-fill` | `data/schemas/partner_fill.json` (la UI usa `adapters/cuidum/partner_fill.py`, que puede cargar más campos por código) | Rellenar el bloque cuidador/familia desde una llamada |
| `candidata-entrevista` | `data/schemas/candidata_entrevista.json` | Perfil de candidata desde entrevista de trabajo |
| `cuidum-102` | Generado: `adapters/cuidum/schema_102.py` (regenerar con `scripts/generate_schema_102.py`) | Paridad con el modelo legacy de 102 entidades |

Formato de cada campo (ejemplo real de `partner_fill.json`):

```json
{
  "name": "dni_cuidador",
  "type": "string",            // string | literal | bool | list
  "validator": "dni",          // opcional: dni | nie | email | phone_es | ...
  "allowed": ["hija", "hijo", "no_mencionado"],   // SOLO para type=literal
  "description": "8 dígitos + letra de control (mayúsculas)"
}
```

Reglas prácticas:

- **Un campo por dato**. Si el LLM tiene que mezclar dos datos en uno, falla.
- **`literal` = vocabulario cerrado**. Cuanto más corto y real sea `allowed`, mejor
  acierto. El valor `no_mencionado` (o `null`) es OBLIGATORIO en literales para que el
  modelo pueda decir "esto no se dice".
- **`description` escrita como la gente habla**, con ejemplos de dichos reales
  ("'mi hija' → hija"). Es lo que lee el LLM.
- **Mapeo a Odoo**: el bloque `targets` dice a qué columna de `res.partner` va cada
  campo (`x_relacion_familiar`, `mobile`, `email`…). Los campos sin columna (ej.
  `nombre_cuidador`) se extraen como evidencia pero NO se pueden persistir aún.
- **Campos selection de Odoo**: si el campo target es una columna `x_*` de tipo
  selection, el servicio lee el vocabulario REAL de `ir_model_fields_selection` y
  sustituye `allowed` automáticamente (NO inventes los códigos; deja que los inyecte).
  Además, si el partner ya tiene ese campo poblado, se añade a `existing_data` y el
  LLM no lo vuelve a extraer (ahorra coste y evita sobrescribir).

---

## 4. Ajustar CÓMO se extrae (modelo, coste, dual)

### Modelo y coste
- La UI lista todos los modelos OpenRouter con su **precio real por 1M tokens**
  (prompt/completion separados) y muestra el **coste estimado tras cada extracción**
  (tokens ≈ chars/4 × precios del modelo).
- En el API: `provider_a: "openrouter-model:<id>"` (plugin al final para no romper el
  formato: los IDs van como `deepseek/deepseek-v4-flash-0731`).
- Estimación: `estimate_extract_cost()` en `core/providers.py` — útil para decidir
  si merece usar modelo caro sobre transcripciones largas.

### Consenso dual
- `use_dual: true` + `provider_b` → dos modelos, el veredicto sale de
  `core/consensus.py::run_dual`. Más fiable pero **lento (73–180s por llamada)**.
- La UI lo permite desmarcar para pruebas rápidas. Para campañas grandes, plantéate
  un modelo B barato o monomodelo + revisión humana.

### Recorte
- `max_chars: 6000` recorta por el tramo FINAL del texto (los datos personales suelen
  caer al final). El coste baja en proporción; el acierto varía si el dato está al
  principio — pruébalo.

---

## 5. Mejorar el acierto (en este orden)

Cuando un campo sale mal o no se encuentra, ataca por pasos, del más probable al más raro:

1. **¿Es el esquema correcto para este documento?** Un esquema de "familia/cuidador"
   sobre una transcripción de entrevista de trabajo devuelve casi todo
   `no_mencionado` — no es que el LLM esté roto, es que el esquema no corresponde al
   género del documento. Cambia de schema.
2. **¿El campo tiene vocabulario real?** En literales con códigos de Odoo (nivel
   formativo → 00/10/20/30; cómo nos conoció → tv/radio/google…), verifica que el
   vocabulario inyectado es el real y que el modelo respeta los códigos. Si el LLM
   devuelve el código como número (`20` en vez de `"20"`), ya no crashea (fix en
   `core/coerce.py`) — pero revisa que el valor llegó.
3. **¿La `description` del campo da ejemplos de la forma de hablar real?** Un campo
   con un ejemplo de "dicho" concreto acierta mucho más.
4. **Guarda un ejemplo few-shot** (el método más potente y barato): en la UI tras una
   extracción, corrige los campos y pulsa **"＋ Guardar correcciones como ejemplo"**.
   La corrección queda en `data/examples/<schema>.json` y se reinyecta automáticamente
   en cada `/extract` (endpoints `GET/POST /api/v1/examples`). Es un aprendizaje
   permanente — cuantos más y más variados, mejor acierto.
5. **Activa el consenso dual** solo si el caso lo merece (campos con validador o bool
   son "críticos" y van a consenso).
6. **Ajusta validadores**: DNI/NIE/email/teléfono se corrigen en `core/validators.py`
   con tests en `tests/core/test_validators.py`. NO copies ejemplos "válidos" de un
   LLM sin calcularlos — el algoritmo de la letra del DNI se ejecuta, no se inventa.

---

## 6. Revisión humana (HITL)

- Cada extracción termina con `verdict` (`ok` | `review` | `single_model`…). Los casos
  con campos `no_found` o `grounding_fail` van a la cola.
- Cola: `GET /api/v1/review` (lee `hermes_partner_fill` en la BD de n8n). Decisiones:
  `POST /api/v1/review/{call_id}` con `approve | reject | fix`.
- ⚠️ Estado actual (verificado 2026-09-11): la aprobación **NO escribe todavía en
  Odoo `res.partner`** — los datos quedan en la tabla n8n como evidencia. El cierre
  del bucle (escribir los campos aprobados en Odoo) es trabajo pendiente planificado.
- El botón "Guardar correcciones como ejemplo" es EL puente entre la revisión y la
  mejora: lo que corriges aquí alimenta el few-shot del punto 5.4.

---

## 7. Probar los cambios

### Rápido, en la UI
`https://langextract.tribbe.es` (basic auth). Pestaña "Probar extracción": pega texto
o `call_id`, elige schema/modelo, Extraer. Pestaña "Actividad en vivo": todo lo que
hace el servidor, en tiempo real.

### Con curl (mismo que la UI)
```bash
# Con la cookie (se setea al visitar /) o con header:
curl -s -u langextract:TU_CLAVE_BASIC -H "X-API-Key: $API_TOKEN" \
  https://langextract.tribbe.es/api/v1/extract \
  -H "Content-Type: application/json" -d '{
    "call_id": 6717526,
    "schema": "partner-fill",
    "use_dual": false,
    "use_partner_context": true
  }'
```
(`$API_TOKEN` es el token del servicio; el servidor te lo da en la cookie `lxt_api_token`.)

### Tests de regresión
```bash
cd ~/repos/langextract-cuidum
source .venv/bin/activate
pytest              # 302 tests: la referencia de calidad es que sigan en verde
```

### Batch por CLI (campañas)
```bash
source .venv/bin/activate
python scripts/extract_cli.py --schema partner-fill --mode dry-run --limit 5   # qué se procesaría
python scripts/extract_cli.py --schema partner-fill --mode extract --limit 1 \
    --provider-a hermes-api --provider-b openrouter-gemma4 \
    --examples data/examples/cuidum-102.json
```
Salidas en `data/output/` (que SÍ es volumen del contenedor).

---

## 8. Errores típicos y soluciones (todos reales, verificados)

| Síntoma | Causa | Solución |
|---|---|---|
| La UI se queda en el modelo "fallback" sin error visible | Referencia JS rota dentro de un `try/catch` silencioso (el modelo no puebla) | Arregla el nombre de la función JS; `node --check` NO detecta esto — mirada E2E en navegador |
| `Error: 'int' object has no attribute 'strip'` | El LLM devolvió el literal como número (`20`) y `coerce_value` asumía str | Fix aplicado: castear a str (bool → "1"/"0"). No volver a asumir str |
| Un campo literal sale "inventado" que no está en el schema | El LLM no tiene `allowed` correcto (o la descripción no da ejemplo) | Verifica `allowed` + añade ejemplo en `description` |
| "sirve para nada, se queda inmóvil" | El esquema no corresponde al género del documento (todo `no_mencionado`) | Pregunta primero "¿es el esquema correcto?", no "¿está roto el LLM?" |
| Lista devuelta como `"['a','b']"` (string) | Los LLM serializan listas como strings | Post-procesa en `core/coerce.py` |
| Slow / timeout en transcripciones largas | Coste súperlineal en longitud × nº de campos + citas obligatorias | Recorte a tramo final (6000 chars), menos campos, o monomodelo |
| Al probar con URL `usuario:clave@host` la página no funciona | Las credenciales en la URL rompen todos los `fetch` relativos (artefacto de TEST, no de producción) | Prueba en URL limpia (el navegador cachea el auth básico) |
| Los ejemplos few-shot "desaparecen" al desplegar | `data/examples/` no es volumen del contenedor (solo `data/output`) | Commitea los ejemplos (o monta volumen) antes de reconstruir — pendiente de resolver |

---

## 9. Checklist rápido: "no extrae bien → probar esto"

1. ¿Schema correcto para el tipo de documento? (5.1)
2. ¿El campo tiene vocabulario `allowed` real y descripción con ejemplos? (3, 5.3)
3. ¿Hay un ejemplo few-shot de un caso parecido? Si no → crear (5.4)
4. ¿Vale la pena dual para este campo crítico? (4)
5. ¿El texto llega recortado por el tramo correcto? (4)
6. ¿El validador es correcto y tiene test? (5.6)
7. ¿El resultado se ve en la cola de revisión? (6)

---

## 10. Avisos importantes (estado verificado 2026-09-11)

- **Persistencia few-shot**: los ejemplos guardados desde la UI viven dentro del
  contenedor; se pierden al reconstruir si no se commitean (trabajo pendiente: montar
  volumen o commit automático).
- **HITL → Odoo**: la revisión no escribe en Odoo todavía (solo en la tabla n8n
  `hermes_partner_fill`). El cierre del bucle está planificado (decisión de contrato:
  write-back por xmlrpc vs workflow n8n).
- **Coste**: el selector de modelos con precios reales existe precisamente para que el
  coste sea una decisión consciente, no un misterio.