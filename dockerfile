FROM python:3.13-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN --mount=type=secret,id=pipindex \
    PIP_EXTRA_INDEX_URL="$(cat /run/secrets/pipindex 2>/dev/null || true)" \
    pip install --no-cache-dir --trusted-host 172.16.0.1 -r requirements.txt
# Client Prisma généré dans site-packages, et CLI (node + moteurs) mis en cache dans ~/.cache,
# tous deux repris par l'image finale (le CLI sert à `prisma migrate deploy` au démarrage).
COPY prisma ./prisma
RUN DATABASE_URL=postgresql://build:build@localhost/build prisma generate && prisma --version


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

ENTRYPOINT ["/app/docker/entrypoint.sh"]
