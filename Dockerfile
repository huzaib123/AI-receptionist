# ── Stage 1: Build Frontend ──────────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /build

# Disable SSL verification in case build environment is behind corporate proxy
RUN npm config set strict-ssl false

COPY frontend/package.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# ── Stage 2: Build Backend ───────────────────────────────────────────────────
FROM python:3.11-slim
WORKDIR /workspace

# Install system dependencies for psycopg2 and building libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application files
COPY app/ ./app
COPY alembic/ ./alembic
COPY alembic.ini .
COPY ml/ ./ml

# Copy built frontend assets into the FastAPI static files directory
COPY --from=frontend-builder /build/dist/ ./app/static/

# Run as an unprivileged user so a compromised app can't change the image.
RUN useradd --create-home --uid 10001 aura && chown -R aura /workspace
USER aura

EXPOSE 8000

# Run Alembic migrations and startup the Uvicorn application server
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
