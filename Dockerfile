# ── FastAPI (FinGraph Analyst API) ──────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /workspace

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer cache)
COPY app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Data directories will be mounted as volumes; create them so the app can
# run even without a bind-mount.
RUN mkdir -p data/chroma_langchain data/embedding_cache

EXPOSE 8000

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
