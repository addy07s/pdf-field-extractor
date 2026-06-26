"""FastAPI entrypoint — API server and production React static host."""

from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes import router
from api.settings import OUTPUT_DIR, cors_origins

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"

# First path segment — never hand off to the SPA shell.
_RESERVED_SPA_SEGMENTS = frozenset({"api", "docs", "redoc", "openapi.json", "outputs"})

app = FastAPI(
    title="GST Invoice Field Extractor",
    description="Upload GST invoices for AI extraction and deterministic validation.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _configure_exports(static_app: FastAPI) -> None:
    """Serve generated Excel/CSV files for browser download."""
    output_dir = Path(OUTPUT_DIR)
    if output_dir.is_dir():
        static_app.mount(
            "/outputs",
            StaticFiles(directory=output_dir),
            name="export-outputs",
        )


_configure_exports(app)


def _configure_frontend(static_app: FastAPI) -> None:
    """Mount compiled React assets when frontend/dist exists (production / Docker)."""
    if not FRONTEND_INDEX.is_file():
        logging.info("frontend/dist not found — API-only mode (use Vite dev server for UI)")
        return

    if FRONTEND_ASSETS.is_dir():
        static_app.mount(
            "/assets",
            StaticFiles(directory=FRONTEND_ASSETS),
            name="frontend-assets",
        )

    @static_app.get("/{catchall:path}")
    def serve_spa(catchall: str = "") -> FileResponse:
        """Serve static files from dist or fall back to index.html for SPA routing."""
        first_segment = catchall.split("/", 1)[0] if catchall else ""
        if first_segment in _RESERVED_SPA_SEGMENTS:
            raise HTTPException(status_code=404, detail="Not Found")

        if catchall:
            candidate = FRONTEND_DIST / catchall
            if candidate.is_file():
                return FileResponse(candidate)

        return FileResponse(FRONTEND_INDEX)


_configure_frontend(app)
