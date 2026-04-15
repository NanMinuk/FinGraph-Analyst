# ── FastAPI (FinGraph Analyst API) ──────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /workspace


RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*


COPY app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

RUN mkdir -p data/chroma_langchain data/embedding_cache

EXPOSE 8000

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
