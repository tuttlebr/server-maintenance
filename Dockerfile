# Stage 1: Build frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Build Rust documentation ingester
FROM rust:1.75-slim AS docs-ingester-build
WORKDIR /build/tools/dgx-doc-ingester
COPY tools/dgx-doc-ingester/Cargo.toml tools/dgx-doc-ingester/Cargo.lock ./
COPY tools/dgx-doc-ingester/src ./src
RUN cargo build --release --locked

# Stage 3: Python runtime
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    sshpass \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 10001 fleet \
    && useradd --system --uid 10001 --gid fleet --create-home --home-dir /home/fleet fleet

ENV HOME=/home/fleet \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=America/Detroit
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Ansible collection dependencies in the system collection path so the
# non-root runtime user can load them.
COPY requirements.yml .
RUN ansible-galaxy collection install \
    --requirements-file requirements.yml \
    --collections-path /usr/share/ansible/collections

# Copy backend code
COPY --chown=fleet:fleet backend/ ./backend/

# Copy docs for fallback chat
COPY --chown=fleet:fleet docs/ ./docs/

# Copy Rust documentation ingester
COPY --from=docs-ingester-build /build/tools/dgx-doc-ingester/target/release/dgx-doc-ingester /usr/local/bin/dgx-doc-ingester

# Copy built frontend into static directory
COPY --from=frontend-build /app/frontend/dist ./backend/static/

# Create data directory
RUN mkdir -p /app/data /app/ansible /home/fleet/.ssh /home/fleet/.ansible \
    && chown -R fleet:fleet /app /home/fleet

EXPOSE 8000

USER fleet:fleet

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
