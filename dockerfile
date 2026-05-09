FROM python:3.13-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


FROM python:3.13-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl sudo \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

ARG BITCOIN_VERSION=27.2
RUN ARCH=$(dpkg --print-architecture) \
    && case "$ARCH" in \
        amd64) BITCOIN_ARCH="x86_64-linux-gnu" ;; \
        arm64) BITCOIN_ARCH="aarch64-linux-gnu" ;; \
        *) echo "Architecture non supportée: $ARCH" && exit 1 ;; \
       esac \
    && curl -fsSL "https://bitcoincore.org/bin/bitcoin-core-${BITCOIN_VERSION}/bitcoin-${BITCOIN_VERSION}-${BITCOIN_ARCH}.tar.gz" \
       | tar -xz --strip-components=2 -C /usr/local/bin "bitcoin-${BITCOIN_VERSION}/bin/bitcoin-cli"

COPY . .

EXPOSE ${SERVER_PORT:-8086}

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${SERVER_PORT:-8086}/health || exit 1

CMD ["python", "main.py"]
