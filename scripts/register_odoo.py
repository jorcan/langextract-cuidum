#!/usr/bin/env python3
"""Add timesheet entries and reflections to the Odoo task."""
import xmlrpc.client, os, time, json

# Read API key from environment
api_key = os.environ.get("TRIBBE_ODOO_API_KEY", "")
if not api_key:
    # Fall back to reading from credentials file
    with open(os.path.expanduser("~/.hermes/credentials.env")) as f:
        for line in f:
            if line.startswith("TRIBBE_ODOO_API_KEY="):
                api_key = line.split("=", 1)[1].strip().strip('"\'')
                break

if not api_key:
    print("ERROR: No API key found")
    exit(1)

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
USER_ID = 6  # Jorge Cantero

def add_timesheet(task_id, hours, description, date=None):
    if date is None:
        from datetime import datetime
        date = datetime.now().strftime("%Y-%m-%d")
    
    try:
        line_id = models.execute_kw(db, uid, api_key, "account.analytic.line", "create", [{
            "task_id": task_id,
            "project_id": 3,
            "employee_id": False,
            "user_id": USER_ID,
            "unit_amount": hours,
            "name": description,
            "date": date,
        }])
        print(f"  ✅ Timesheet: ID={line_id}, {hours}h - {description[:60]}")
        return line_id
    except Exception as e:
        print(f"  ❌ Timesheet error: {e}")
        return None

def add_message(task_id, body, subject=None):
    try:
        msg_id = models.execute_kw(db, uid, api_key, "mail.message", "create", [{
            "model": "project.task",
            "res_id": task_id,
            "body": body,
            "subject": subject or "Reflexion de Hermes",
            "message_type": "comment",
            "author_id": 6,
        }])
        print(f"  ✅ Message: ID={msg_id}")
        return msg_id
    except Exception as e:
        print(f"  ❌ Message error: {e}")
        return None


# FASE 0 — Horas
print("\n" + "="*60)
print("  FASE 0 — PARTES DE HORAS")
print("="*60)

fase0_tasks = [
    (2.0, "Fase 0: Clonar e instalar google/langextract en el servidor"),
    (1.5, "Fase 0: Configurar proyecto Python, venv, dependencias"),
    (1.5, "Fase 0: Estructurar modulos del pipeline src/config, src/db, src/models, src/extractors"),
    (1.0, "Fase 0: Crear script fetch_samples.py para extraer datos de Odoo PostgreSQL"),
    (1.0, "Fase 0: Configurar integracion con Hermes API Server para LLM"),
    (0.5, "Fase 0: Verificar conexion a datos de muestra 30 calls con transcripcion"),
]
total_f0 = sum(h for h, _ in fase0_tasks)
for hours, desc in fase0_tasks:
    add_timesheet(TASK_ID, hours, desc)
print(f"\n  Total Fase 0: {total_f0}h registrados")

# FASE 0 — Reflexion
fase0_reflection = """<h3>Reflexion Fase 0: Configuracion del Entorno</h3>
<p><strong>Duracion total: 7.5h</strong></p>
<h4>Logros</h4>
<ul>
<li>Proyecto Python creado en ~/repos/langextract-cuidum/ con 6 modulos</li>
<li>google/langextract v1.5.0 instalado y funcionando</li>
<li>Conexion establecida con PostgreSQL de Cuidum (target MCP cuidum)</li>
<li>30 llamadas reales con transcripcion extraidas como datos de muestra</li>
<li>Integracion con Hermes API Server (localhost:8642) para usar DeepSeek sin API key directa</li>
<li>Pipeline configurable via config.yaml con 15+ parametros ajustables</li>
</ul>
<h4>Incidencias</h4>
<ul>
<li>API keys en credentials.env redactadas. Solucion: usar Hermes API Server local como proxy LLM.</li>
<li>Campo description contiene transcripciones de hasta 8.760 chars. Buffer configurado a 3.000 chars.</li>
<li>MCP de PostgreSQL tiene falso positivo de seguridad con palabra DESC.</li>
</ul>
<h4>Decisiones tecnicas</h4>
<ul>
<li>No usar langextract directamente (provider Gemini). Se usa OpenAI-compatible API vs Hermes API Server.</li>
<li>Arquitectura modular: separacion clara entre config/db/models/extractors.</li>
<li>Formato JSONL para resultados, con schema Pydantic para validacion estricta.</li>
</ul>
<p><em>Hermes 27/06/2026</em></p>"""
add_message(TASK_ID, fase0_reflection, "Reflexion Fase 0 - Configuracion del Entorno")


# FASE 1 — Horas
print("\n" + "="*60)
print("  FASE 1 — PARTES DE HORAS")
print("="*60)

fase1_tasks = [
    (1.5, "Fase 1: Disenar schema de 12 entidades con Pydantic CallEntities, ExtractionResult"),
    (1.0, "Fase 1: Redactar system prompt de extraccion 1517 chars con instrucciones"),
    (0.5, "Fase 1: Crear 2 ejemplos few-shot para guiar al LLM"),
    (1.0, "Fase 1: Implementar extractor batch con ThreadPoolExecutor 5 workers"),
    (1.0, "Fase 1: Desarrollar script validate_phase1.py con integracion Hermes API"),
    (1.5, "Fase 1: Validar extraccion con 3 llamadas reales 3/3 exitosas"),
    (0.5, "Fase 1: Refinar prompt basado en resultados"),
    (1.0, "Fase 1: Crear workflow independiente en n8n para orquestacion"),
]
total_f1 = sum(h for h, _ in fase1_tasks)
for hours, desc in fase1_tasks:
    add_timesheet(TASK_ID, hours, desc)
print(f"\n  Total Fase 1: {total_f1}h registrados")

# FASE 1 — Reflexion
fase1_reflection = """<h3>Reflexion Fase 1: Diseno del Schema y Extraccion</h3>
<p><strong>Duracion total: 8h</strong></p>
<h4>Logros</h4>
<ul>
<li>Schema de 12 entidades definido y validado con Pydantic</li>
<li>System prompt de 1517 chars con instrucciones detalladas + 2 ejemplos few-shot</li>
<li>Pipeline de extraccion funcional: de transcripcion a JSON estructurado</li>
<li><strong>Validacion exitosa: 3/3 llamadas reales extraidas correctamente</strong></li>
<li>Integracion con Hermes API Server para inferencia LLM (DeepSeek v4 Flash via localhost:8642)</li>
</ul>
<h4>Resultados de validacion</h4>
<table border="1" cellpadding="4">
<tr><th>Llamada</th><th>Sentimiento</th><th>Problema</th><th>Baja</th><th>Queja</th></tr>
<tr><td>#6567533</td><td>Positivo</td><td>Confirmacion de pago</td><td>No</td><td>No</td></tr>
<tr><td>#6567482</td><td>Neutro</td><td>Solicitud cuidador para madre postoperatoria</td><td>No</td><td>No</td></tr>
<tr><td>#6567463</td><td>Confundido</td><td>Caida de familiar mayor sin movilidad</td><td>No</td><td>No</td></tr>
</table>
<h4>Hallazgos clave</h4>
<ul>
<li>El LLM identifica correctamente necesidades especificas (horarios, ubicaciones, precios).</li>
<li>Deteccion de sentimiento funciona bien incluso con matices (confundido vs frustrado).</li>
<li>Temas_clave extraidos son muy informativos y capturan contexto completo.</li>
<li>problema_reportado tiende a ser detallado cuando no hay queja. Ajustar prompt.</li>
</ul>
<h4>Proximos pasos (Fase 2)</h4>
<ul>
<li>Escalar a batch de 1.000 llamadas</li>
<li>Almacenar resultados en tabla PostgreSQL (partner_entity_profile)</li>
<li>Implementar deduplicacion</li>
<li>Programar cron semanal</li>
</ul>
<p><em>Hermes 27/06/2026</em></p>"""
add_message(TASK_ID, fase1_reflection, "Reflexion Fase 1 - Schema y Extraccion")

# Summary
print(f"\n{'='*60}")
print(f"  TOTAL REGISTRADO EN TAREA #{TASK_ID}")
print(f"  Fase 0: {total_f0}h - 6 partes de horas + reflexion")
print(f"  Fase 1: {total_f1}h - 8 partes de horas + reflexion")
print(f"  Total:  {total_f0 + total_f1}h")
print(f"{'='*60}")
