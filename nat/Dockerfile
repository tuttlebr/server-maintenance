FROM python:3.12-slim AS cryptography-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cargo \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# NAT 1.9 requires cryptography 48.x. Build it from source so it links to
# Debian's patched OpenSSL instead of using the OpenSSL bundled in PyPI wheels.
RUN pip wheel --no-cache-dir --no-binary=cryptography \
    --wheel-dir /wheels \
    "cryptography==48.0.1"

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libssl3t64 \
    openssl \
    && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 10002 nat \
    && useradd --system --uid 10002 --gid nat --create-home --home-dir /home/nat nat

ENV HOME=/home/nat \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install NeMo Agent Toolkit, Milvus, and local embedding model
COPY --from=cryptography-builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/cryptography-48.0.1-*.whl && \
    pip install --no-cache-dir \
    "nvidia-nat[redis,mcp,langchain,phoenix,async_endpoints]==1.9.0" \
    "starlette>=1.3.1,<2" \
    pymilvus \
    langchain-nvidia-ai-endpoints && \
    pip check && \
    rm -rf /wheels

COPY config.yml .
COPY prepare_config.py .
COPY ingest.py .
COPY embedding_response.py .
COPY pyproject.toml .
COPY fleet_rag/ ./fleet_rag/
RUN pip install --no-cache-dir . && pip check
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh && chown -R nat:nat /app /home/nat

EXPOSE 8000

USER nat:nat

ENTRYPOINT ["./entrypoint.sh"]
