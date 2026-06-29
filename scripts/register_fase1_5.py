#!/usr/bin/env python3
"""Register Fase 1.5 progress in Odoo task."""
import xmlrpc.client, os

api_key = os.environ.get("TRIBBE_ODOO_API_KEY", "")
if not api_key:
    with open(os.path.expanduser("~/.hermes/credentials.env")) as f:
        for line in f:
            if line.startswith("TRIBBE_ODOO_API_KEY="):
                api_key = line.split("=", 1)[1].strip().strip('"\'')
                break

url = "https://tribbe.es"
db = "prod"
user = "jorge@tribbe.es"
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, user, api_key, {})
print(f"UID: {uid}")
if not uid:
    exit(1)

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
TASK_ID = 230
USER_ID = 6

def add_timesheet(task_id, hours, desc, date="2026-06-27"):
    try:
        line_id = models.execute_kw(db, uid, api_key, "account.analytic.line", "create", [{
            "task_id": task_id, "project_id": 3, "employee_id": False,
            "user_id": USER_ID, "unit_amount": hours, "name": desc, "date": date,
        }])
        print(f"  ✅ Timesheet: ID={line_id}, {hours}h - {desc[:60]}")
        return line_id
    except Exception as e:
        print(f"  ❌ Timesheet error: {e}")
        return None

def add_message(task_id, body, subject=None):
    try:
        msg_id = models.execute_kw(db, uid, api_key, "mail.message", "create", [{
            "model": "project.task", "res_id": task_id,
            "body": body, "subject": subject or "Reflexion de Hermes",
            "message_type": "comment", "author_id": USER_ID,
        }])
        print(f"  ✅ Message: ID={msg_id}")
        return msg_id
    except Exception as e:
        print(f"  ❌ Message error: {e}")
        return None

print("\n" + "="*60)
print("  FASE 1.5 — EXPANSION DEL SCHEMA (12 → 102 ENTIDADES)")
print("="*60)

fase15_tasks = [
    (1.0, "Fase 1.5: Inspeccionar res_partner (332 cols) y crm_lead (382 cols) en Odoo vía MCP PostgreSQL"),
    (2.5, "Fase 1.5: Identificar gaps estructurales y disenar schema ampliado de 102 entidades en 10 categorias"),
    (3.0, "Fase 1.5: Implementar modelo Pydantic, system prompt 6221 chars y 3 ejemplos few-shot"),
    (2.0, "Fase 1.5: Resolver problemas de chunking y parsing con google/langextract, extraer callback plano"),
    (1.0, "Fase 1.5: Validar extraccion real 61/102 campos en llamada #6567482"),
]
total_f15 = sum(h for h, _ in fase15_tasks)
for hours, desc in fase15_tasks:
    add_timesheet(TASK_ID, hours, desc)
print(f"\n  Total Fase 1.5: {total_f15}h registrados")

# Reflexion
reflection = """<h3>Reflexion Fase 1.5: Expansion del Schema a 102 Entidades</h3>
<p><strong>Duración total: 9.5h</strong></p>

<h4>Inspección de Odoo (res_partner + crm_lead)</h4>
<p>Se inspeccionaron ambas tablas vía MCP PostgreSQL. Resultados:</p>
<ul>
<li><strong>res_partner</strong> (332 campos): YA capturan patologías (20+ booleanos), perfil cuidadora, documentación, tracking (churn, agreement_count), matches, geo, relaciones familiares.</li>
<li><strong>crm_lead</strong> (382 campos): YA tienen inferencia ML (inference_risk_level, inference_probability), patologías detalladas, servicio, vivienda, motivos de pérdida, competidores, tiempos por etapa.</li>
<li><strong>Conclusión:</strong> Lo estructurado está cubierto. El GAP real es lo NO capturado: sentimiento, emociones, intenciones futuras, relación cuidadora-familia, señales tempranas, contexto vital, negociación real.</li>
</ul>

<h4>Schema ampliado: 12 → 102 entidades en 10 categorías</h4>
<table border="1" cellpadding="4">
<tr><th>Categoría</th><th>Entidades</th><th>Ejemplo de gap cubierto</th></tr>
<tr><td>A. Contexto Partner</td><td>10</td><td>quién_llama, relación, rotación inferida</td></tr>
<tr><td>B. Salud y Dependencia</td><td>20</td><td>evolución, movilidad, dolor crónico, necesidades no cubiertas</td></tr>
<tr><td>C. Económico-Contractual</td><td>12</td><td>confianza_económica, negociación tarifa, upselling</td></tr>
<tr><td>D. Relacionales y Emocionales</td><td>18</td><td>vínculo cuidadora-familia, estrés cuidador, lealtad, competidores</td></tr>
<tr><td>E. Operativas y Logística</td><td>12</td><td>rotación explícita, barreras logísticas, incidencias repetitivas</td></tr>
<tr><td>F. Comunicación y Estilo</td><td>8</td><td>claridad, coherencia, nivel urgencia voz</td></tr>
<tr><td>G. Señales Predictivas ML</td><td>15</td><td>churn_risk_score, ventana abandono, anomalía comportamiento</td></tr>
<tr><td>H. Features Temporales (derivadas)</td><td>8</td><td>avg_sentiment_30d, churn_score_compuesto, satisfacción_tendencia</td></tr>
</table>

<h4>Logros técnicos</h4>
<ul>
<li>System prompt expandido de 1.517 → 6.221 chars con 10 categorías detalladas</li>
<li>3 ejemplos few-shot que cubren: churn alto/competidores, upsell/confianza, escalada médica/urgencia</li>
<li>Pipeline refactorizado para usar OpenAILanguageModel (provider) de google/langextract + parseo JSON plano</li>
<li>Coerción de tipos: strings númericos → float/int, listas de texto → listas Python, bools desde texto</li>
</ul>

<h4>Validación real</h4>
<p><strong>Llamada #6567482</strong> (solicitud cuidador postoperatorio madre):</p>
<ul>
<li><strong>✅ 61/102 campos extraídos</strong></li>
<li>Sentimiento: cordial → mejora tras gestión</li>
<li>Patología: Parkinson moderada</li>
<li>Churn risk: 0.05 | Fase: onboarding</li>
<li>Confianza: alta | Upsell: True</li>
</ul>
<p>Los 41 campos restantes no aplicaban (no hay competidores, no hay quejas de precio, etc.). Schema correcto.</p>

<h4>Arquitectura final</h4>
<pre>
Odoo PostgreSQL → fetch_samples.py → lx OpenAILanguageModel.infer()
→ JSON plano → coerción tipos → Pydantic → JSONL
                    │
          Hermes API Server :8642
                    │
            DeepSeek v4 Flash
</pre>

<h4>Próximos pasos (Fase 2)</h4>
<ul>
<li>Batch extraction: procesar 1.000+ llamadas</li>
<li>Crear tabla PostgreSQL <code>partner_entity_profile</code> con historial por partner</li>
<li>Deduplicación y agregación temporal</li>
<li>Entrenar modelo XGBoost de churn con features extraídas</li>
</ul>

<p><em>Hermesio, secretario personal de Jorge Cantero — 27/06/2026</em></p>"""

add_message(TASK_ID, reflection, "Fase 1.5 - Expansion Schema 102 Entidades")

print(f"\n{'='*60}")
print(f"  TOTAL REGISTRADO EN TAREA #{TASK_ID}")
print(f"  Fase 1.5: {total_f15}h - {len(fase15_tasks)} partes + reflexion")
print(f"  Total acumulado: 25h (F0:7.5 + F1:8 + F1.5:{total_f15})")
print(f"{'='*60}")
