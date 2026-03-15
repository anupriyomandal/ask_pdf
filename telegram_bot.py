"""
telegram_bot.py
---------------
Telegram bot interface for the document Q&A assistant.

All messages are sent with parse_mode='HTML' for maximum compatibility.
LLM output is converted from Markdown to HTML before sending.

Commands
--------
/start            — Welcome message.
/help             — List available commands.
/new_conversation — Clear current session.

Document upload
---------------
User sends a PDF or DOCX file → bot downloads it → POSTs to /upload.

Q&A flow
--------
User sends a text message → bot POSTs to /ask → replies with HTML answer.
"""

import logging
import os
import re
import tempfile

import requests
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import config

# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

BACKEND = config.BACKEND_URL


# ─────────────────────────────────────────────
# Markdown → HTML conversion
# ─────────────────────────────────────────────

def _md_to_html(text: str) -> str:
    """
    Convert a Markdown-flavoured LLM response to Telegram-safe HTML.

    Conversions applied (in order):
        1. Escape raw HTML special chars (&, <, >) to avoid injection.
        2. ``**bold**``  → ``<b>bold</b>``
        3. ``*italic*``  → ``<i>italic</i>``
        4. `` `code` ``  → ``<code>code</code>``
        5. Numbered list items  → plain numbered lines (Telegram HTML has no <ol>)
        6. Bullet list items (-, *) → • prefixed lines
        7. Remove any leftover orphan ``**`` that the LLM emitted by mistake.

    Parameters
    ----------
    text : str
        Raw LLM-generated text, possibly containing Markdown.

    Returns
    -------
    str
        HTML string safe to pass to Telegram with parse_mode='HTML'.
    """
    # 1. Escape HTML special characters first so our tags aren't double-escaped
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # 2. Bold: **text** → <b>text</b>  (non-greedy, no newlines inside)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)

    # 3. Italic: *text* → <i>text</i>  (only single *, not already consumed)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)

    # 4. Inline code: `code` → <code>code</code>
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    # 5. Numbered list: lines starting with "1. ", "2. ", etc.
    text = re.sub(r"^(\d+)\.\s+", r"\1. ", text, flags=re.MULTILINE)

    # 6. Bullet list: lines starting with "- " or "* " → "• "
    text = re.sub(r"^[-\*]\s+", "• ", text, flags=re.MULTILINE)

    # 7. Remove any stray / orphan ** left over (LLM artefacts)
    text = re.sub(r"\*\*", "", text)

    return text.strip()


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _user_id(update: Update) -> str:
    """Return a stable string user-id derived from the Telegram user id."""
    return str(update.effective_user.id)  # type: ignore[union-attr]


async def _reply(update: Update, text: str, *, html: bool = False) -> None:
    """
    Send a text reply using HTML parse mode, splitting long messages if needed.

    Parameters
    ----------
    update : Update
        Incoming Telegram update.
    text : str
        Message text. When *html=True* the text is treated as already-valid HTML.
        When *html=False* (default) it is sent as plain text (no parse mode).
    html : bool
        Pass True when the message contains HTML formatting.
    """
    max_len = 4096
    parse_mode = ParseMode.HTML if html else None
    for i in range(0, len(text), max_len):
        await update.message.reply_text(  # type: ignore[union-attr]
            text[i : i + max_len],
            parse_mode=parse_mode,
        )


# ─────────────────────────────────────────────
# Command handlers
# ─────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start."""
    await _reply(
        update,
        (
            "👋 <b>Welcome to the Document Q&amp;A Assistant!</b>\n\n"
            "📄 Upload a PDF or Word (.docx) document and I'll answer questions about it.\n\n"
            "Use /help to see all available commands."
        ),
        html=True,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help."""
    await _reply(
        update,
        (
            "📋 <b>Available commands</b>\n\n"
            "/start — Welcome message\n"
            "/new_conversation — Clear current document and start fresh\n"
            "/help — Show this help message\n\n"
            "📤 <b>How to use</b>\n"
            "1. Upload a PDF or DOCX document.\n"
            "2. Ask questions in plain text.\n"
            "3. Use /new_conversation to switch to a different document."
        ),
        html=True,
    )


async def cmd_new_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /new_conversation — clear session."""
    uid = _user_id(update)
    try:
        resp = requests.post(
            f"{BACKEND}/new_conversation",
            data={"user_id": uid},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.error("Failed to clear session for user_id=%s: %s", uid, exc)
        await _reply(update, "⚠️ Could not clear the session. Please try again.")
        return

    await _reply(
        update,
        "🔄 Session cleared! Upload a new document to start a fresh conversation.",
    )


# ─────────────────────────────────────────────
# Document upload handler
# ─────────────────────────────────────────────

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming file uploads (PDF / DOCX)."""
    uid = _user_id(update)
    doc = update.message.document  # type: ignore[union-attr]

    if doc is None:
        await _reply(update, "⚠️ No document received.")
        return

    filename: str = doc.file_name or "upload"
    suffix = os.path.splitext(filename)[1].lower()

    if suffix not in {".pdf", ".docx", ".doc"}:
        await _reply(
            update,
            f"⚠️ Unsupported file type: <code>{suffix}</code>. Please upload a PDF or DOCX file.",
            html=True,
        )
        return

    await _reply(update, "⏳ Processing your document, please wait…")

    # Download from Telegram
    tmp_path: str = ""
    try:
        tg_file = await context.bot.get_file(doc.file_id)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            await tg_file.download_to_drive(tmp.name)
            tmp_path = tmp.name
    except Exception as exc:
        logger.error("Failed to download file for user_id=%s: %s", uid, exc)
        await _reply(update, "⚠️ Failed to download the file from Telegram. Please try again.")
        return

    # POST to FastAPI /upload
    try:
        with open(tmp_path, "rb") as fh:
            resp = requests.post(
                f"{BACKEND}/upload",
                files={"file": (filename, fh, "application/octet-stream")},
                data={"user_id": uid},
                timeout=60,
            )
        resp.raise_for_status()
        data = resp.json()
        await _reply(
            update,
            (
                "✅ <b>Document uploaded successfully!</b>\n"
                f"📊 Extracted {data.get('chars_extracted', '?')} characters.\n\n"
                "You can now ask questions about this document."
            ),
            html=True,
        )
    except requests.HTTPError as exc:
        detail = exc.response.json().get("detail", str(exc)) if exc.response else str(exc)
        logger.error("Upload HTTP error for user_id=%s: %s", uid, detail)
        await _reply(update, f"⚠️ Upload failed: {detail}")
    except Exception as exc:
        logger.error("Upload error for user_id=%s: %s", uid, exc)
        await _reply(update, "⚠️ An unexpected error occurred during upload.")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


# ─────────────────────────────────────────────
# Text message handler (Q&A)
# ─────────────────────────────────────────────

async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle plain-text messages as questions to the document.

    Converts the LLM's Markdown output to Telegram-safe HTML before sending.
    """
    uid = _user_id(update)
    question = (update.message.text or "").strip()  # type: ignore[union-attr]

    if not question:
        return

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,  # type: ignore[union-attr]
        action="typing",
    )

    try:
        resp = requests.post(
            f"{BACKEND}/ask",
            json={"user_id": uid, "question": question},
            timeout=60,
        )
        resp.raise_for_status()
        raw_answer = resp.json().get("answer", "")

        # Convert Markdown → HTML and strip stray **
        html_answer = _md_to_html(raw_answer)
        await _reply(update, html_answer, html=True)

    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            await _reply(
                update,
                "📄 Please upload a document first before asking questions.",
            )
        else:
            detail = exc.response.json().get("detail", str(exc)) if exc.response else str(exc)
            logger.error("Ask HTTP error for user_id=%s: %s", uid, detail)
            await _reply(update, f"⚠️ Error: {detail}")
    except Exception as exc:
        logger.error("Ask error for user_id=%s: %s", uid, exc)
        await _reply(update, "⚠️ An unexpected error occurred. Please try again.")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main() -> None:
    """Build and run the Telegram bot (long-polling)."""
    if not config.TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set. Check your .env file.")

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("new_conversation", cmd_new_conversation))

    # File uploads
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Text questions
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question)
    )

    logger.info("Telegram bot started — polling for updates…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
