"""
document_parser.py
------------------
Utility functions to extract plain text from PDF and DOCX files.

Supported formats:
    • PDF  — via PyMuPDF (fitz)
    • DOCX — via python-docx
"""

import logging
from pathlib import Path

import fitz  # PyMuPDF
from docx import Document

logger = logging.getLogger(__name__)


def extract_pdf_text(file_path: str | Path) -> str:
    """
    Extract and return plain text from a PDF file.

    Parameters
    ----------
    file_path : str | Path
        Absolute or relative path to the PDF file.

    Returns
    -------
    str
        Extracted plain text with pages separated by newlines.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the file is not a valid PDF or is unreadable.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    try:
        doc = fitz.open(str(path))
        pages_text: list[str] = []

        for page_num, page in enumerate(doc, start=1):
            text = page.get_text("text")
            pages_text.append(text.strip())
            logger.debug("Extracted page %d of %s", page_num, path.name)

        doc.close()
        full_text = "\n\n".join(pages_text)
        logger.info("PDF extracted: %d pages, %d chars — %s", len(pages_text), len(full_text), path.name)
        return full_text

    except Exception as exc:
        logger.error("Failed to extract PDF '%s': %s", path, exc)
        raise ValueError(f"Could not read PDF file: {exc}") from exc


def extract_docx_text(file_path: str | Path) -> str:
    """
    Extract and return plain text from a DOCX file.

    Parameters
    ----------
    file_path : str | Path
        Absolute or relative path to the DOCX file.

    Returns
    -------
    str
        Extracted plain text with paragraphs separated by newlines.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the file is not a valid DOCX or is unreadable.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    try:
        doc = Document(str(path))
        paragraphs = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
        full_text = "\n\n".join(paragraphs)
        logger.info("DOCX extracted: %d paragraphs, %d chars — %s", len(paragraphs), len(full_text), path.name)
        return full_text

    except Exception as exc:
        logger.error("Failed to extract DOCX '%s': %s", path, exc)
        raise ValueError(f"Could not read DOCX file: {exc}") from exc


def parse_document(file_path: str | Path) -> str:
    """
    Auto-detect file type and extract plain text.

    Delegates to :func:`extract_pdf_text` or :func:`extract_docx_text`
    based on the file extension.

    Parameters
    ----------
    file_path : str | Path
        Path to a PDF or DOCX file.

    Returns
    -------
    str
        Extracted plain text.

    Raises
    ------
    ValueError
        If the file extension is unsupported.
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return extract_pdf_text(path)
    elif suffix in {".docx", ".doc"}:
        return extract_docx_text(path)
    else:
        raise ValueError(f"Unsupported file type '{suffix}'. Supported: .pdf, .docx")
