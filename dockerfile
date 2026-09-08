FROM python:3.13-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN --mount=type=secret,id=pipindex \
    PIP_EXTRA_INDEX_URL="$(cat /run/secrets/pipindex 2>/dev/null || true)" \
    pip install --no-cache-dir --trusted-host 10.10.0.3 -r requirements.txt


FROM python:3.13-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

EXPOSE ${SERVER_PORT:-8086}

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${SERVER_PORT:-8086}/health || exit 1

CMD ["python", "main.py"]
