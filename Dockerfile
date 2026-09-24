FROM node:20 AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app/backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    QDRANT_PATH=/app/data/qdrant_local \
    LEGAL_KNOWLEDGE_PATH=/app/backend/data/legal_knowledge \
    OLLAMA_URL=http://host.docker.internal:11434

COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && \
    pip install -r /tmp/requirements.txt

COPY backend ./
COPY data /app/data
COPY --from=frontend-builder /app/frontend/dist /app/backend/static

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
