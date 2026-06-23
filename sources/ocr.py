"""OCR and image preprocessing for scanned invoices."""

from __future__ import annotations

import io
import logging
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

_MIN_UPSCALE_WIDTH = 1200
_TESSERACT_WARNED = False


@lru_cache(maxsize=1)
def get_tesseract_version() -> str | None:
    """Return the installed Tesseract version string, or None if not on PATH."""
    try:
        import pytesseract

        return str(pytesseract.get_tesseract_version())
    except Exception:
        return None


@lru_cache(maxsize=1)
def is_tesseract_available() -> bool:
    """Return True when the Tesseract binary is installed and reachable."""
    return get_tesseract_version() is not None


def ocr_startup_status_message() -> str:
    """One-line OCR mode summary for startup logging and UI."""
    version = get_tesseract_version()
    if version:
        return f"OCR enabled (Tesseract {version} found)"
    return (
        "OCR disabled: Tesseract not found on PATH — "
        "image invoices will be flagged, not auto-verified."
    )


def log_ocr_startup_status() -> str:
    """Log OCR availability once at app/batch startup. Returns the message."""
    message = ocr_startup_status_message()
    if is_tesseract_available():
        logger.info(message)
    else:
        logger.warning(message)
    return message


def _warn_tesseract_missing() -> None:
    global _TESSERACT_WARNED
    if _TESSERACT_WARNED:
        return
    _TESSERACT_WARNED = True
    logger.warning(
        "Tesseract OCR is not available. Image/scanned PDF text layers will be empty "
        "and grounding/correction will fall back to vision-only behavior. "
        "Install Tesseract (see README) to enable OCR."
    )


def _decode_image_bytes(image_bytes: bytes) -> np.ndarray:
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode image bytes")
    return image


def _encode_png(image: np.ndarray) -> bytes:
    success, encoded = cv2.imencode(".png", image)
    if not success:
        raise ValueError("Could not encode image to PNG")
    return encoded.tobytes()


def _deskew(gray: np.ndarray) -> np.ndarray:
    inverted = cv2.bitwise_not(gray)
    coords = np.column_stack(np.where(inverted > 0))
    if len(coords) < 20:
        return gray

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.5:
        return gray

    height, width = gray.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    return cv2.warpAffine(
        gray,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def _upscale_if_needed(gray: np.ndarray) -> np.ndarray:
    height, width = gray.shape[:2]
    if width >= _MIN_UPSCALE_WIDTH:
        return gray
    scale = _MIN_UPSCALE_WIDTH / width
    new_size = (int(width * scale), int(height * scale))
    return cv2.resize(gray, new_size, interpolation=cv2.INTER_CUBIC)


def preprocess_image(image_bytes: bytes) -> bytes:
    """Deskew, denoise, and enhance a scan for OCR and vision-model input."""
    try:
        image = _decode_image_bytes(image_bytes)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = _deskew(gray)
        gray = _upscale_if_needed(gray)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        gray = cv2.fastNlMeansDenoising(gray, h=10)
        gray = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            11,
        )
        return _encode_png(gray)
    except Exception as exc:
        logger.warning("Image preprocessing failed, using original bytes: %s", exc)
        return image_bytes


def ocr_text(image_bytes: bytes) -> str:
    """Extract text from an invoice image. Returns \"\" on any failure."""
    if not is_tesseract_available():
        _warn_tesseract_missing()
        return ""

    try:
        preprocessed = preprocess_image(image_bytes)
        image = Image.open(io.BytesIO(preprocessed))
        import pytesseract

        text = pytesseract.image_to_string(image, config="--psm 6")
        return text.strip()
    except Exception as exc:
        logger.warning("OCR failed: %s", exc)
        return ""


def enrich_scanned_content(
    image_bytes: bytes,
    native_text_layer: str = "",
) -> tuple[bytes, str, bool]:
    """Preprocess image and optionally populate an OCR text layer.

    Returns:
        (preprocessed_image_bytes, text_layer, text_layer_is_ocr)
    """
    preprocessed = preprocess_image(image_bytes)
    ocr_layer = ocr_text(preprocessed)
    if ocr_layer:
        return preprocessed, ocr_layer, True
    return preprocessed, native_text_layer, False
