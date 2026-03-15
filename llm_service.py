"""
llm_service.py
--------------
OpenAI GPT-4o-mini integration with streaming support.

The key function :func:`answer_question` is the single entry-point used
by *both* the FastAPI server and the CLI tool so all LLM logic stays
in one place.
"""

import logging
from collections.abc import Generator
from typing import Optional

from openai import OpenAI

from config import config

logger = logging.getLogger(__name__)

# Initialise the OpenAI client once at module load
_client = OpenAI(api_key=config.OPENAI_API_KEY)

SYSTEM_PROMPT = (
    "You are a policy assistant. "
    "Answer ONLY using the provided document. "
    "If the document does not contain the answer, respond: "
    "'The document does not mention this.' "
    "Provide concise, clear answers."
)


def _build_messages(
    document: str,
    history: list[dict],
    question: str,
) -> list[dict]:
    """
    Construct the full messages list for the Chat Completions API.

    Order:
        1. System prompt
        2. Document context (injected as a system-role message)
        3. Conversation history (user / assistant turns)
        4. Current user question

    Parameters
    ----------
    document : str
        Full plain text of the uploaded document.
    history : list[dict]
        Previous conversation turns in ``{"role": ..., "content": ...}`` form.
    question : str
        The current user question.

    Returns
    -------
    list[dict]
        Ready-to-send messages list.
    """
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "system",
            "content": f"DOCUMENT CONTENT:\n\n{document}",
        },
    ]
    messages.extend(history)
    messages.append({"role": "user", "content": question})
    return messages


def answer_question(
    document: str,
    history: list[dict],
    question: str,
    stream: bool = True,
) -> Generator[str, None, None] | str:
    """
    Query GPT-4o-mini and return the answer.

    Parameters
    ----------
    document : str
        Full plain text of the document to reason over.
    history : list[dict]
        Conversation history (list of role/content dicts).
    question : str
        The user's current question.
    stream : bool
        When *True* (default) yields text chunks one by one.
        When *False* returns the full response as a single string.

    Returns
    -------
    Generator[str, None, None] | str
        A generator of text chunks when *stream=True*, or a plain string.

    Raises
    ------
    RuntimeError
        If the OpenAI API call fails.
    """
    messages = _build_messages(document, history, question)

    logger.info(
        "Sending request to OpenAI — model=%s, history_len=%d, stream=%s",
        config.OPENAI_MODEL,
        len(history),
        stream,
    )

    try:
        if stream:
            return _stream_response(messages)
        else:
            return _blocking_response(messages)
    except Exception as exc:
        logger.error("OpenAI API error: %s", exc)
        raise RuntimeError(f"OpenAI API error: {exc}") from exc


def _stream_response(messages: list[dict]) -> Generator[str, None, None]:
    """Yield text chunks from a streaming OpenAI response."""
    response = _client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=messages,
        stream=True,
        temperature=0.2,
    )
    for chunk in response:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content


def _blocking_response(messages: list[dict]) -> str:
    """Return the full response text in a single call (used by FastAPI /ask)."""
    response = _client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=messages,
        stream=False,
        temperature=0.2,
    )
    return response.choices[0].message.content or ""
