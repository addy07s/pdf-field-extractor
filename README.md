# GST Invoice Field Extractor (Production Grade v2)

Extract structured fields from Indian GST tax invoices—digital PDFs and scanned images—and export a styled **Excel** file and companion **CSV**, one row per document. A vision model reads each invoice; deterministic validators decide what to trust. Values that fail validation or look uncertain are **visually flagged** so reviewers focus only on what needs checking.

---

## Core architecture

This project uses a **decoupled client–server design**:

| Layer | Stack | Responsibility |
| ----- | ----- | -------------- |
| **Backend** | FastAPI (`main.py`) | File upload API, orchestration, Excel/CSV export |
| **Frontend** | React + TypeScript + Tailwind (`frontend/`) | High-interactivity review workspace |
| **Engine** | `pipeline/`, `validate/`, `extract/` | Extraction, validation, and trust scoring (frozen) |

- **`GET /api/config`** — field layout from `config/fields.yaml` plus runtime metadata (provider, OCR status, concurrency).
- **`POST /api/extract`** — multipart batch upload; returns `DocumentResult[]`, `excel_path`, and `csv_path`.

Batch processing runs inside **worker threads** via `asyncio.to_thread()`. This isolates the synchronous `run_batch()` pipeline (which uses `asyncio.run()` internally) from FastAPI/uvicorn's async event loop, preventing nested event-loop errors while keeping the pipeline code unchanged.

The legacy Streamlit UI (`app.py`) is **deprecated**. It now shows a migration notice only.

---

## The immutable accuracy rule

> **Do not modify core extraction or validation code for frontend or API changes.**

The following paths control extraction accuracy and trust scoring. Treat them as a **frozen boundary**:

| Path | Purpose |
| ---- | ------- |
| `pipeline/` | Batch orchestration and per-document processing |
| `validate/` | Deterministic validators (GSTIN, PAN, grounding, dates, arithmetic) |
| `extract/` | Prompt/schema assembly and text-layer corrections |
| `config/fields.yaml` | Field definitions, validators, and output columns |

Changes to the React UI, FastAPI routes, or styling must **not** alter this layer. Accuracy regressions belong here; UX improvements belong in `frontend/` or `api/`.

---

## Key principle: never silently guess

The AI **proposes** field values. It does **not** decide trust. Separate validation code assigns every field a status (`OK`, `LOW_CONFIDENCE`, `NOT_FOUND`, or `FAILED_VALIDATION`):

| Fill | Meaning |
| ---- | ------- |
| No highlight | Passed all checks |
| **Yellow** | Low confidence — verify before using |
| **Red** | Failed validation — do not use as-is |
| **Grey** | Not found / processing failed |

A blank flagged cell is preferable to a confident wrong number.

---

## Key features (React workspace)

- **Cell-level color highlighting** — matches Excel export rules exactly (`#FFEB9C` yellow, `#FFC7CE` red, `#D9D9D9` grey) based on per-field `FieldStatus`.
- **Instant row-by-row preview** — each row has a **View** action that opens the original PDF (iframe) or image in a modal overlay using in-browser blob URLs. No backend re-fetch or page reload.
- **Drag-and-drop batch upload** — up to 100 files per run (PDF, JPG, JPEG, PNG).
- **Summary metrics** — OK / Needs review / Failed counts after processing.
- **Server-side exports** — timestamped `.xlsx` and `.csv` written to `outputs/`.

---

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for the React frontend)
- **One** of the following vision backends:

### (a) Gemini API key (cloud — default)

1. Create a free key at [Google AI Studio](https://aistudio.google.com/apikey).
2. The **free tier** is enough for testing and low volume (strict per-minute and daily limits apply).
3. For **production volume** or if you need higher limits, enable billing on your Google Cloud / AI Studio project and use a paid quota.
4. Invoice images are sent to Google's servers for processing.

### (b) Ollama (local — private)

1. Install [Ollama](https://ollama.com/) on your machine.
2. Pull a vision-capable model (e.g. `ollama pull llava`).
3. No API key; data never leaves your machine.
4. Requires reasonable CPU/GPU; accuracy may be lower than cloud models.

### OCR setup (for image/scanned invoices)

Image invoices (`.jpg`, `.png`) and scanned PDFs use **[Tesseract OCR](https://github.com/tesseract-ocr/tesseract)** to build a text layer for grounding and GSTIN/PAN auto-correction. The vision model remains the primary reader; OCR supports verification.

**Tesseract must be installed and on your system `PATH`.** Installing the binary alone is not enough on Windows — if `tesseract` is not found from a new terminal, OCR is silently skipped.

| OS | Install | Add to PATH |
| -- | ------- | ----------- |
| **Windows** | `winget install UB-Mannheim.TesseractOCR` | Add `C:\Program Files\Tesseract-OCR` to the system **Path** (see below) |
| **macOS** | `brew install tesseract` | Homebrew adds it to PATH automatically |
| **Linux** | `sudo apt install tesseract-ocr` | Package manager adds it to PATH automatically |

**Verify** (open a **new** terminal after installing):

```bash
tesseract --version
```

You should see something like `tesseract 5.4.0`. The API reports OCR status via `GET /api/config`.

#### Windows: add Tesseract to PATH

1. Press **Win + R**, type `sysdm.cpl`, press Enter.
2. Open the **Advanced** tab → **Environment Variables**.
3. Under **System variables**, select **Path** → **Edit** → **New**.
4. Add: `C:\Program Files\Tesseract-OCR`
5. Click **OK** on all dialogs, then **close and reopen** your terminal (and IDE).

**Without Tesseract:** the app still runs but **skips OCR**. Image and scanned invoices are processed vision-only and most fields are flagged for human review. **Digital PDFs are unaffected.** Tesseract is recommended, not required.

---

## Setup

### 1. Clone and create a virtual environment

**Windows (PowerShell)**

```powershell
git clone <your-repo-url>
cd pdf-field-extractor
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

**macOS / Linux**

```bash
git clone <your-repo-url>
cd pdf-field-extractor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 3. Configure environment variables

Edit `.env` in the project root:

```env
VISION_PROVIDER=cloud
GEMINI_API_KEY=paste-your-key-here
GEMINI_MODEL=gemini-2.5-flash
BATCH_CONCURRENCY=1
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173
```

Replace `paste-your-key-here` with your Gemini API key. Do **not** commit `.env` (it is gitignored).

---

## Local development workflow

Run the backend and frontend in **two separate terminals** from the project root.

**Terminal 1 — Backend (FastAPI)**

```bash
uvicorn main:app --reload --port 8000
```

- API: [http://localhost:8000](http://localhost:8000)
- Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

**Terminal 2 — Frontend (React + Vite)**

```bash
cd frontend
npm run dev
```

- UI: [http://localhost:5173](http://localhost:5173)

Vite proxies `/api` requests to port 8000 automatically. Upload invoices in the UI and click **Start processing**.

---

## Cloud vs local provider

Set `VISION_PROVIDER` in `.env`:

| Value | Backend | When to use |
| ----- | ------- | ----------- |
| `cloud` (default) | Gemini via `GEMINI_API_KEY` | Easiest setup; generally best accuracy; data sent to Google |
| `ollama` | Local Ollama server | No cloud dependency; fully private; needs local hardware |

**Cloud (`.env`)**

```env
VISION_PROVIDER=cloud
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-2.5-flash
```

**Local Ollama (`.env`)**

```env
VISION_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llava
```

Ensure Ollama is running before processing.

| | Cloud (Gemini) | Local (Ollama) |
| - | -------------- | -------------- |
| Cost | Free tier limited; paid for volume | Free |
| Privacy | Data leaves your machine | Stays on your machine |
| Setup | API key only | Install Ollama + model |
| Accuracy | Higher (vision models) | Depends on model/hardware |

---

## Tuning concurrency

`BATCH_CONCURRENCY` controls how many invoices are processed in parallel.

```env
BATCH_CONCURRENCY=3
```

| Tier | Recommended value |
| ---- | ----------------- |
| Gemini **free** tier | `1` or `2` — avoids 429 rate-limit errors |
| Gemini **paid** / Flash | `3`–`5` — balances speed vs 503 overload errors |
| High quota / batch jobs | `5`–`10+` depending on quota |

Lower concurrency reduces HTTP 503 (model overloaded) failures on Gemini Flash. The provider retries 429/500/503 automatically with exponential backoff.

---

## Configuring fields

Field definitions live in [`config/fields.yaml`](config/fields.yaml). This file drives:

- Which fields the model extracts
- Prompt hints for each field
- Which validators run
- Excel/CSV column headers

**Default fields:** company name, invoice number, invoice date, GSTIN, PAN, description, taxable amount, GST amount, total amount.

To add, remove, or edit a field, change the YAML only—no Python changes required:

```yaml
  - key: hsn_code
    display_label: HSN Code
    description: the HSN/SAC code for the line item
    data_type: string
    validators:
      - grounding
```

Restart the API after editing `fields.yaml`.

---

## Is the output trustworthy?

Trust is **earned by code**, not by model confidence.

After extraction, each field passes deterministic validators configured in `fields.yaml`:

| Check | What it does |
| ----- | ------------ |
| **Grounding** | Value must appear in the document text layer (exact for digital PDFs; fuzzy for OCR). Missing → yellow. |
| **GSTIN checksum** | Validates 15-character structure and official checksum digit. Fail → red. |
| **PAN structure** | Validates `[A-Z]{5}[0-9]{4}[A-Z]`. Fail → red. |
| **GSTIN ↔ PAN cross-check** | Characters 3–12 of GSTIN must match PAN when both are present. Fail → red on both. |
| **Date** | Parses common Indian formats; stores normalized ISO date. Fail → red. |
| **Arithmetic** | When taxable + GST ≈ total (within ₹1), amounts stay OK; mismatch → yellow on all three. |

Digital PDFs also use **text-layer correction** for GSTIN/PAN: if exactly one valid value exists in the document text, it replaces a misread AI value.

**How to read the output**

- **Green path (no fill):** Passed every check applied to that field. Still spot-check critical fields if the stakes are high.
- **Yellow:** Uncertain or ungrounded — **human, please verify this one.**
- **Red:** Failed a hard rule — **do not use without correction.**
- **Grey / blank:** Not extracted or document failed entirely — fill in manually or re-process.

The CSV **Flags** column lists every non-OK field and reason for spreadsheet-only workflows.

---

## Known limitations

- **Scanned / image invoices** — OCR text is lower trust than a native PDF text layer. Grounding uses fuzzy matching on OCR text. Unreadable scans still flag for review.
- **Multi-page PDFs** — only **page 1** is sent to the vision model today. Multi-page support is planned; check long invoices manually.
- **Free-tier API keys** — strict daily and per-minute limits. Large batches will see `FAILED` rows with rate-limit errors. Use a paid key or Ollama for production volume.
- **Vision model errors** — occasional misreads are mitigated by text-layer correction on digital PDFs and by validation; always review flagged cells.

---

## Project layout

```
main.py                 FastAPI entrypoint
api/                    HTTP routes, schemas, settings
frontend/               React + TypeScript + Tailwind UI
app.py                  Deprecated Streamlit notice (do not use)
config/fields.yaml      Field definitions (edit this)
pipeline/               Batch orchestration          [FROZEN]
sources/                PDF + image loading, OCR
provider/               Gemini (cloud) or Ollama (local)
extract/                Prompt/schema + corrections  [FROZEN]
validate/               Deterministic trust checks   [FROZEN]
output/                 Excel + CSV writers
models.py               Shared result types
outputs/                Generated export files
```

---

## Tests

```bash
pytest
```

Frontend production build:

```bash
cd frontend
npm run build
```

---

## Docker deployment

> **Note:** The current `Dockerfile` still targets the legacy Streamlit entrypoint. A production v2 image (FastAPI + static React build) will be added in a follow-up deployment step.

For local Docker testing of the legacy container:

```bash
docker build -t pdf-field-extractor .
docker run --rm -p 8501:8501 \
  -e GEMINI_API_KEY=your-gemini-api-key-here \
  -e GEMINI_MODEL=gemini-2.5-flash \
  -e VISION_PROVIDER=cloud \
  -e BATCH_CONCURRENCY=1 \
  pdf-field-extractor
```

Never bake secrets into the image — pass `GEMINI_API_KEY` at runtime.
