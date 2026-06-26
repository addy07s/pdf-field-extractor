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

# System deps: Tesseract OCR; ffmpeg; OpenCV / image runtime libraries.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        ffmpeg \
        libsm6 \
        libxext6 \
        libgl1 \
        libglib2.0-0 \
        libxrender1 \
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

RUN mkdir -p outputs

EXPOSE 8501

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8501"]
