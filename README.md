# GST Invoice Field Extractor

Extract structured fields from Indian GST tax invoices—digital PDFs and scanned images—and export a styled **Excel** file and companion **CSV**, one row per document. A vision model reads each invoice; deterministic validators decide what to trust. Values that fail validation or look uncertain are **visually flagged** so reviewers focus only on what needs checking.

---

## Key principle: never silently guess

The AI **proposes** field values. It does **not** decide trust. Separate validation code assigns every field a status (`OK`, `LOW_CONFIDENCE`, `NOT_FOUND`, or `FAILED_VALIDATION`). In Excel:


| Fill         | Meaning                              |
| ------------ | ------------------------------------ |
| No highlight | Passed all checks                    |
| **Yellow**   | Low confidence — verify before using |
| **Red**      | Failed validation — do not use as-is |
| **Grey**     | Not found / processing failed        |


A blank flagged cell is preferable to a confident wrong number.

---

## Prerequisites

- Python 3.11+
- **One** of the following vision backends:

### (a) Gemini API key (cloud — default)

1. Create a free key at [Google AI Studio](https://aistudio.google.com/apikey).
2. The **free tier** is enough for testing and low volume (strict per-minute and daily limits apply).
3. For **production volume** or if you need higher limits, enable billing on your Google Cloud / AI Studio project and use a paid quota.
4. Invoice images are sent to Google’s servers for processing.

### (b) Ollama (local — private)

1. Install [Ollama](https://ollama.com/) on your machine.
2. Pull a vision-capable model (e.g. `ollama pull llava`).
3. No API key; data never leaves your machine.
4. Requires reasonable CPU/GPU; accuracy may be lower than cloud models.

### OCR Setup (for image/scanned invoices)

Image invoices (`.jpg`, `.png`) and scanned PDFs use **[Tesseract OCR](https://github.com/tesseract-ocr/tesseract)** to build a text layer for grounding and GSTIN/PAN auto-correction. The vision model remains the primary reader; OCR supports verification.

**Tesseract must be installed and on your system `PATH`.** Installing the binary alone is not enough on Windows — if `tesseract` is not found from a new terminal, OCR is silently skipped.


| OS          | Install                                   | Add to PATH                                                             |
| ----------- | ----------------------------------------- | ----------------------------------------------------------------------- |
| **Windows** | `winget install UB-Mannheim.TesseractOCR` | Add `C:\Program Files\Tesseract-OCR` to the system **Path** (see below) |
| **macOS**   | `brew install tesseract`                  | Homebrew adds it to PATH automatically                                  |
| **Linux**   | `sudo apt install tesseract-ocr`          | Package manager adds it to PATH automatically                           |


**Verify** (open a **new** terminal after installing):

```bash
tesseract --version
```

You should see something like `tesseract 5.4.0`. The app also prints OCR status on startup (see below).

#### Windows: add Tesseract to PATH

1. Press **Win + R**, type `sysdm.cpl`, press Enter.
2. Open the **Advanced** tab → **Environment Variables**.
3. Under **System variables**, select **Path** → **Edit** → **New**.
4. Add: `C:\Program Files\Tesseract-OCR`
5. Click **OK** on all dialogs, then **close and reopen** your terminal (and IDE).

**Without Tesseract:** the app still runs fine but **skips OCR**. Image and scanned invoices are processed vision-only and most fields are flagged for human review. **Digital PDFs are unaffected.** Tesseract is recommended, not required.

On launch, the Streamlit app and `run_real_batch.py` log one of:

- `OCR enabled (Tesseract X.X.X found)`
- `OCR disabled: Tesseract not found on PATH — image invoices will be flagged, not auto-verified.`

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

### 2. Configure environment variables

Edit `.env` in the project root:

```env
VISION_PROVIDER=cloud
GEMINI_API_KEY=paste-your-key-here
GEMINI_MODEL=gemini-2.5-flash
BATCH_CONCURRENCY=1
```

Replace `paste-your-key-here` with your Gemini API key. Do **not** commit `.env` (it is gitignored).

---

## How to run

From the project root with your virtual environment activated:

**Windows**

```powershell
.venv\Scripts\streamlit run app.py
```

**macOS / Linux**

```bash
streamlit run app.py
```

Streamlit opens a browser tab (usually `http://localhost:8501`).

1. **Drag and drop** invoice files (PDF, JPG, JPEG, or PNG)—up to 100 per run.
2. Click **Process**.
3. Review the summary table (status per document).
4. Download **Excel** (styled, flagged cells) and **CSV** (with a Flags column).

Processed files are also saved under `outputs/` with a timestamp.

---

## Docker deployment

Build and run the Streamlit app in a container with Tesseract pre-installed. **Never bake secrets into the image** — pass `GEMINI_API_KEY` (and other config) at runtime.

**Build**

```bash
docker build -t pdf-field-extractor .
```

**Run** (map port 8501, supply API key via environment)

```bash
docker run --rm -p 8501:8501 \
  -e GEMINI_API_KEY=your-gemini-api-key-here \
  -e GEMINI_MODEL=gemini-2.5-flash \
  -e VISION_PROVIDER=cloud \
  -e BATCH_CONCURRENCY=1 \
  pdf-field-extractor
```

Open `http://localhost:8501` in your browser.

On cloud platforms (Railway, Render, Fly.io, ECS, etc.), set the same environment variables in the service dashboard and expose container port **8501**. The `GEMINI_API_KEY` must be configured there — it is not read from a `.env` file inside the image.

---

## Configuring fields

Field definitions live in `[config/fields.yaml](config/fields.yaml)`. This file drives:

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

Restart the app after editing `fields.yaml`.

---

## Cloud vs local provider

Set `VISION_PROVIDER` in `.env`:


| Value             | Backend                     | When to use                                                 |
| ----------------- | --------------------------- | ----------------------------------------------------------- |
| `cloud` (default) | Gemini via `GEMINI_API_KEY` | Easiest setup; generally best accuracy; data sent to Google |
| `ollama`          | Local Ollama server         | No cloud dependency; fully private; needs local hardware    |


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


|          | Cloud (Gemini)                     | Local (Ollama)            |
| -------- | ---------------------------------- | ------------------------- |
| Cost     | Free tier limited; paid for volume | Free                      |
| Privacy  | Data leaves your machine           | Stays on your machine     |
| Setup    | API key only                       | Install Ollama + model    |
| Accuracy | Higher (vision models)             | Depends on model/hardware |


---

## Tuning concurrency

`BATCH_CONCURRENCY` controls how many invoices are processed in parallel.

```env
BATCH_CONCURRENCY=3
```

| Tier | Recommended value |
|------|-------------------|
| Gemini **free** tier | `1` or `2` — avoids 429 rate-limit errors |
| Gemini **paid** / Flash | `3`–`5` — balances speed vs 503 overload errors |
| High quota / batch jobs | `5`–`10+` depending on quota |

The Streamlit sidebar shows the active value. **Lower concurrency reduces HTTP 503 (model overloaded) failures** on Gemini Flash — firing many simultaneous requests during a Google-side spike tends to trigger more `UNAVAILABLE` responses. The provider retries 429/500/503 automatically with exponential backoff (up to 6 attempts), but keeping concurrency modest still helps.

---

## Known limitations

Be aware of these constraints when planning production use:

- **Scanned / image invoices** — OCR text is lower trust than a native PDF text layer (`is_scanned` stays `True`). Grounding uses fuzzy matching on OCR text. Unreadable scans still flag for review.
- **Multi-page PDFs** — only **page 1** is sent to the vision model today. Multi-page support is planned; check long invoices manually.
- **Free-tier API keys** — strict daily and per-minute limits. Large batches will see `FAILED` rows with rate-limit errors. Use a paid key or Ollama for production volume.
- **Vision model errors** — occasional misreads (e.g. extra character in GSTIN) are mitigated by text-layer correction on digital PDFs and by validation; always review flagged cells.

---

## Is the output trustworthy?

Trust is **earned by code**, not by model confidence.

After extraction, each field passes deterministic validators configured in `fields.yaml`:


| Check                       | What it does                                                                                            |
| --------------------------- | ------------------------------------------------------------------------------------------------------- |
| **Grounding**               | Value must appear in the document text layer (exact for digital PDFs; fuzzy for OCR). Missing → yellow. |
| **GSTIN checksum**          | Validates 15-character structure and official checksum digit. Fail → red.                               |
| **PAN structure**           | Validates `[A-Z]{5}[0-9]{4}[A-Z]`. Fail → red.                                                          |
| **GSTIN ↔ PAN cross-check** | Characters 3–12 of GSTIN must match PAN when both are present. Fail → red on both.                      |
| **Date**                    | Parses common Indian formats; stores normalized ISO date. Fail → red.                                   |
| **Arithmetic**              | When taxable + GST ≈ total (within ₹1), amounts stay OK; mismatch → yellow on all three.                |


Digital PDFs also use **text-layer correction** for GSTIN/PAN: if exactly one valid value exists in the document text, it replaces a misread AI value.

**How to read the output**

- **Green path (no fill):** Passed every check applied to that field. Still spot-check critical fields if the stakes are high.
- **Yellow:** Uncertain or ungrounded — **human, please verify this one.**
- **Red:** Failed a hard rule — **do not use without correction.**
- **Grey / blank:** Not extracted or document failed entirely — fill in manually or re-process.

The CSV **Flags** column lists every non-OK field and reason for spreadsheet-only workflows.

---

## Project layout

```
app.py              Streamlit UI
config/fields.yaml  Field definitions (edit this)
pipeline/           Batch orchestration
sources/            PDF + image loading, OCR preprocessing
provider/           Gemini (cloud) or Ollama (local)
extract/            Prompt/schema + text-layer corrections
validate/           Deterministic trust checks
output/             Excel + CSV writers
models.py           Shared result types
```

---

## Tests

```bash
pytest
```

---



