# -----------------------------------------------------------------------------
# Stage 1 — build the React production bundle
# -----------------------------------------------------------------------------
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# -----------------------------------------------------------------------------
# Stage 2 — FastAPI runtime with Tesseract OCR and compiled static UI
# -----------------------------------------------------------------------------
FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# System deps: Tesseract OCR + OpenCV/image runtime libraries.
# PDF rendering uses PyMuPDF (no Poppler required).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py models.py ./
COPY api/ api/
COPY config/ config/
COPY pipeline/ pipeline/
COPY validate/ validate/
COPY extract/ extract/
COPY provider/ provider/
COPY sources/ sources/
COPY output/ output/

COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

RUN mkdir -p outputs \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/health" || exit 1

# Honor PORT from the host platform (Caasify / ECS / etc.).
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
