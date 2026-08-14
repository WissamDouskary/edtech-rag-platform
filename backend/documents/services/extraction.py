import logging
from io import BytesIO

import pdfplumber
import pypdf
import pypdfium2 as pdfium
import pytesseract

from ..constants import MAX_PAGE_COUNT

logger = logging.getLogger(__name__)


class PdfExtractionError(Exception):
    """Raised for any condition that should mark the document as FAILED."""


def _extract_with_pdfplumber(pdf_bytes):
    pages = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            pages.append([i, text])
    return pages


def _extract_with_pypdf(pdf_bytes):
    reader = pypdf.PdfReader(BytesIO(pdf_bytes))
    if reader.is_encrypted:
        try:
            result = reader.decrypt("")
        except Exception as exc:
            raise PdfExtractionError("PDF protégé par mot de passe.") from exc
        if not result:
            raise PdfExtractionError("PDF protégé par mot de passe.")

    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        pages.append([i, text])
    return pages


def _ocr_empty_pages(pdf_bytes, pages):
    empty_indexes = [i for i, (_, text) in enumerate(pages) if not text]
    if not empty_indexes:
        return

    try:
        pdf_doc = pdfium.PdfDocument(pdf_bytes)
    except Exception:
        logger.warning("Could not open PDF with pypdfium2 for OCR rendering")
        return

    for idx in empty_indexes:
        try:
            page = pdf_doc[idx]
            bitmap = page.render(scale=2.0)
            pil_image = bitmap.to_pil()
            ocr_text = pytesseract.image_to_string(pil_image).strip()
            pages[idx][1] = ocr_text
        except pytesseract.TesseractNotFoundError:
            logger.warning("Tesseract binary not found — skipping OCR fallback")
            break
        except Exception:
            logger.warning("OCR failed for page %s", idx + 1, exc_info=True)
            continue


def extract_pages_text(pdf_bytes):
    """Returns a list of [page_number, text] (1-indexed). Raises PdfExtractionError
    for corrupted, password-protected, or otherwise unreadable PDFs."""
    try:
        pages = _extract_with_pdfplumber(pdf_bytes)
    except Exception:
        try:
            pages = _extract_with_pypdf(pdf_bytes)
        except PdfExtractionError:
            raise
        except Exception as exc:
            raise PdfExtractionError("Fichier PDF corrompu ou illisible.") from exc

    if not pages:
        raise PdfExtractionError("Le document ne contient aucune page.")

    if len(pages) > MAX_PAGE_COUNT:
        raise PdfExtractionError(f"Le document dépasse la limite de {MAX_PAGE_COUNT} pages.")

    _ocr_empty_pages(pdf_bytes, pages)

    if not any(text.strip() for _, text in pages):
        raise PdfExtractionError("Texte illisible même après OCR.")

    return [(i, text) for i, text in pages]
