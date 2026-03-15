"""
app.py
------
FastAPI server exposing the document upload and question-answering endpoints.

Endpoints
---------
POST /upload   — upload a document file; stores text, clears history.
POST /ask      — ask a question about the current document.
GET  /health   — health-check for Railway / load-balancers.
"""

import logging
import os
import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import config
from document_parser import parse_document
from llm_service import answer_question
from session_store import (
    append_message,
    get_document,
    get_history,
    store_document,
    clear_session,
)

# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# App
# ─────────────────────────────────────────────
app = FastAPI(
    title="Document Q&A Assistant",
    description="Upload policy documents and ask questions using GPT-4o-mini.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────
class AskRequest(BaseModel):
    user_id: str
    question: str


class AskResponse(BaseModel):
    answer: str


class UploadResponse(BaseModel):
    message: str
    user_id: str
    chars_extracted: int


class HealthResponse(BaseModel):
    status: str


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    """Return service health status."""
    return HealthResponse(status="ok")


@app.post("/upload", response_model=UploadResponse, tags=["Document"])
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Form(...),
) -> UploadResponse:
    """
    Upload a PDF or DOCX document for a given user.

    - Accepts multipart/form-data with ``file`` and ``user_id`` fields.
    - Parses the document, stores the text, and clears conversation history.
    - Supported formats: ``.pdf``, ``.docx``.
    """
    filename = file.filename or "upload"
    suffix = Path(filename).suffix.lower()

    if suffix not in {".pdf", ".docx", ".doc"}:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Supported: .pdf, .docx",
        )

    # Save to a temp file so document_parser can operate on a real path
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        document_text = parse_document(tmp_path)

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error during document parsing")
        raise HTTPException(status_code=500, detail=f"Parsing failed: {exc}") from exc
    finally:
        # Clean up temp file
        if "tmp_path" in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)

    if not document_text.strip():
        raise HTTPException(status_code=422, detail="Document appears to be empty or unreadable.")

    store_document(user_id, document_text)
    logger.info("Document uploaded — user_id=%s, chars=%d", user_id, len(document_text))

    return UploadResponse(
        message="Document uploaded successfully. You can now ask questions.",
        user_id=user_id,
        chars_extracted=len(document_text),
    )


@app.post("/ask", response_model=AskResponse, tags=["Question"])
async def ask_question(body: AskRequest) -> AskResponse:
    """
    Answer a question about the user's uploaded document.

    - Retrieves session document and conversation history.
    - Calls the LLM service (blocking mode for HTTP responses).
    - Appends both the question and answer to history.
    """
    document = get_document(body.user_id)
    if not document:
        raise HTTPException(
            status_code=404,
            detail="No document found for this user. Please upload a document first.",
        )

    history = get_history(body.user_id)

    try:
        answer = answer_question(
            document=document,
            history=history,
            question=body.question,
            stream=False,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Persist conversation turns
    append_message(body.user_id, "user", body.question)
    append_message(body.user_id, "assistant", answer)

    logger.info("Question answered — user_id=%s", body.user_id)
    return AskResponse(answer=answer)


@app.post("/new_conversation", tags=["Session"])
async def new_conversation(user_id: str = Form(...)) -> dict:
    """Clear the session for a user (document + history)."""
    clear_session(user_id)
    return {"message": "Session cleared. Upload a new document to begin."}


# ─────────────────────────────────────────────
# Entry-point (Railway / local dev)
# ─────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
    )
