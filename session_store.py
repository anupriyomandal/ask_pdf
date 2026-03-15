"""
session_store.py
----------------
In-memory session store for document text and conversation history.

Session shape:
    {
        "document": "<full plain text>",
        "conversation_history": [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."},
        ]
    }
"""

import logging
from typing import Optional

from config import config

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Global in-memory store
# ─────────────────────────────────────────────
_sessions: dict[str, dict] = {}


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def create_session(user_id: str) -> None:
    """Initialise an empty session for *user_id* (idempotent)."""
    if user_id not in _sessions:
        _sessions[user_id] = {"document": "", "conversation_history": []}
        logger.debug("Session created for user_id=%s", user_id)


def store_document(user_id: str, document_text: str) -> None:
    """
    Store *document_text* for *user_id* and reset conversation history.

    Uploading a new document always clears the previous conversation.
    """
    create_session(user_id)
    _sessions[user_id]["document"] = document_text
    _sessions[user_id]["conversation_history"] = []
    logger.info("Document stored and history cleared for user_id=%s", user_id)


def get_document(user_id: str) -> Optional[str]:
    """Return the stored document text, or *None* if no session exists."""
    return _sessions.get(user_id, {}).get("document") or None


def get_history(user_id: str) -> list[dict]:
    """Return the conversation history list (may be empty)."""
    return _sessions.get(user_id, {}).get("conversation_history", [])


def append_message(user_id: str, role: str, content: str) -> None:
    """
    Append a message to the conversation history for *user_id*.

    Automatically trims history: if the total count exceeds
    MAX_HISTORY_MESSAGES, only the last KEEP_HISTORY_MESSAGES are retained.
    """
    create_session(user_id)
    history = _sessions[user_id]["conversation_history"]
    history.append({"role": role, "content": content})

    if len(history) > config.MAX_HISTORY_MESSAGES:
        _sessions[user_id]["conversation_history"] = history[-config.KEEP_HISTORY_MESSAGES:]
        logger.debug(
            "History trimmed to %d messages for user_id=%s",
            config.KEEP_HISTORY_MESSAGES,
            user_id,
        )


def clear_session(user_id: str) -> None:
    """Remove all session data for *user_id*."""
    _sessions.pop(user_id, None)
    logger.info("Session cleared for user_id=%s", user_id)


def session_exists(user_id: str) -> bool:
    """Return True if a session exists for *user_id*."""
    return user_id in _sessions
