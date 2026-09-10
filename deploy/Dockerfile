# LangExtract web service — imagen portable (misma imagen en cualquier host)
FROM python:3.11-slim

WORKDIR /app

# Dependencias runtime (versiones verificadas en local 08/09/2026)
COPY deploy/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Código (core genérico + adapters + servicio web + UI + datos de config)
COPY core/ core/
COPY adapters/ adapters/
COPY scripts/ scripts/
COPY ui/ ui/
COPY data/schemas/ data/schemas/
COPY data/examples/ data/examples/

ENV PYTHONUNBUFFERED=1 \
    PORT=8654 \
    PYTHONPATH=/app

EXPOSE 8654

HEALTHCHECK --interval=60s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8654/health', timeout=4)"

CMD ["python", "scripts/web_api.py"]