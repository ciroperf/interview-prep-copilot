# Build multi-stage: le dipendenze si compilano in uno stage separato, così
# nell'immagine finale non finiscono né i compilatori né le cache di pip.
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install -r requirements.txt

# ---------------------------------------------------------------------------

FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000

# Utente non privilegiato: se qualcuno esce dal processo, non è root.
RUN useradd --create-home --uid 10001 appuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=appuser:appuser app ./app

USER appuser
EXPOSE 8000

# Container Apps usa la readiness probe definita nel Terraform, ma questo rende
# l'immagine diagnosticabile anche con un semplice `docker run`.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health').read()"

# Una sola worker: l'app tiene in memoria l'indice della knowledge base e con
# più processi ogni worker avrebbe la propria copia. Si scala per repliche.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1"]
