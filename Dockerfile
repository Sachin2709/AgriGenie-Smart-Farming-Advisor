# ── Stage: Production image ───────────────────────────────
FROM python:3.11-slim

# Keeps Python from buffering stdout/stderr (logs appear immediately in Render)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install OS-level build deps needed by faiss-cpu, Pillow, and sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer-cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code (excludes everything in .dockerignore)
COPY . .

# Create runtime directories that are gitignored but needed at startup
RUN mkdir -p instance reports uploads

# Render injects PORT at runtime; default to 5000 for local docker run
ENV PORT=5000

# Use 1 worker — sentence-transformers model is large; timeout 120s for RAG init
CMD exec gunicorn "app:create_app()" \
    --bind 0.0.0.0:${PORT:-10000} \
    --workers 1 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -