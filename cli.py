"""
cli.py
------
Interactive CLI chat interface for the document Q&A assistant.

Built with Typer + Rich for a modern terminal experience.

Usage
-----
    python cli.py

CLI Commands (typed at the prompt)
-----------------------------------
/upload <path>   — Parse and load a document.
/new             — Clear session and start fresh.
/help            — Show available commands.
/exit            — Quit the CLI.

Any other input is treated as a question about the loaded document.
"""

import sys
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.markdown import Markdown

from config import config
from document_parser import parse_document
from llm_service import answer_question
from session_store import (
    append_message,
    clear_session,
    get_document,
    get_history,
    store_document,
)

# ─────────────────────────────────────────────
# Logging (suppress noisy third-party loggers)
# ─────────────────────────────────────────────
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Rich console
# ─────────────────────────────────────────────
console = Console()

# Fixed user_id for local CLI sessions
CLI_USER_ID = "local_cli_user"

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _print_banner() -> None:
    """Print a welcome banner."""
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]Document Q&A Assistant[/bold cyan]\n"
            "[dim]Powered by GPT-4o-mini[/dim]",
            border_style="cyan",
            padding=(1, 4),
        )
    )
    console.print(
        "[dim]Type [bold]/help[/bold] to see available commands.[/dim]\n"
    )


def _print_help() -> None:
    """Display the help panel."""
    console.print(
        Panel(
            "[bold]/upload [green]<path>[/green][/bold]  — Load a PDF or DOCX document\n"
            "[bold]/new[/bold]               — Clear session and start fresh\n"
            "[bold]/help[/bold]              — Show this help message\n"
            "[bold]/exit[/bold]              — Exit the CLI\n\n"
            "[dim]Any other input is treated as a question about the loaded document.[/dim]",
            title="[bold]Commands[/bold]",
            border_style="dim",
        )
    )


def _agent_prefix() -> None:
    """Print the coloured Agent > prefix."""
    console.print("[bold green]Agent >[/bold green] ", end="")


def _upload_document(file_path: str) -> None:
    """Parse a document and store it in the session."""
    path = Path(file_path.strip())

    if not path.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {path}")
        return

    with console.status("[cyan]Parsing document…[/cyan]", spinner="dots"):
        try:
            text = parse_document(path)
        except ValueError as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            return
        except Exception as exc:
            console.print(f"[bold red]Unexpected error:[/bold red] {exc}")
            return

    if not text.strip():
        console.print("[bold red]Error:[/bold red] Document appears to be empty or unreadable.")
        return

    store_document(CLI_USER_ID, text)
    _agent_prefix()
    console.print(
        f"[green]Document uploaded successfully.[/green] "
        f"[dim]({len(text):,} characters extracted from '{path.name}')[/dim]"
    )


def _ask_question(question: str) -> None:
    """
    Send a question to the LLM, collect the streamed response, and render
    it as Markdown once complete.

    Using a spinner + collect approach avoids the Rich.Live redraw artefact
    where each refresh tick appended a new copy of the growing text.
    """
    document = get_document(CLI_USER_ID)

    if not document:
        _agent_prefix()
        console.print(
            "[yellow]No document loaded.[/yellow] "
            "Use [bold]/upload <path>[/bold] to load a document first."
        )
        return

    history = get_history(CLI_USER_ID)

    # Collect all streamed tokens while showing a spinner
    collected: list[str] = []
    try:
        with console.status("[green]Thinking…[/green]", spinner="dots"):
            for chunk in answer_question(document, history, question, stream=True):
                collected.append(chunk)
    except RuntimeError as exc:
        console.print(f"[bold red]LLM error:[/bold red] {exc}")
        return

    full_answer = "".join(collected)

    # Render the complete answer as Markdown
    _agent_prefix()
    console.print(Markdown(full_answer))

    # Persist to history
    append_message(CLI_USER_ID, "user", question)
    append_message(CLI_USER_ID, "assistant", full_answer)


def _new_session() -> None:
    """Clear the current session."""
    clear_session(CLI_USER_ID)
    _agent_prefix()
    console.print("[green]Session cleared.[/green] Upload a new document to begin.")


# ─────────────────────────────────────────────
# Main REPL
# ─────────────────────────────────────────────

def _run_repl() -> None:
    """Main read-eval-print loop."""
    _print_banner()

    while True:
        try:
            # Coloured user prompt
            user_input = console.input("[bold cyan]User >[/bold cyan] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue

        # ── Commands ──────────────────────────────────
        if user_input.lower() == "/exit":
            console.print("[dim]Goodbye![/dim]")
            break

        elif user_input.lower() == "/help":
            _print_help()

        elif user_input.lower() == "/new":
            _new_session()

        elif user_input.lower().startswith("/upload"):
            parts = user_input.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                console.print(
                    "[bold red]Usage:[/bold red] /upload [green]<absolute_file_path>[/green]"
                )
            else:
                # Strip surrounding quotes (single or double) so paths with
                # spaces work whether the user wraps them in quotes or not.
                raw_path = parts[1].strip()
                if len(raw_path) >= 2 and raw_path[0] == raw_path[-1] and raw_path[0] in ('"', "'"):
                    raw_path = raw_path[1:-1]
                _upload_document(raw_path)

        elif user_input.startswith("/"):
            console.print(
                f"[yellow]Unknown command:[/yellow] {user_input}. "
                "Type [bold]/help[/bold] for a list of commands."
            )

        # ── Question ──────────────────────────────────
        else:
            console.print(Rule(style="dim"))
            _ask_question(user_input)
            console.print(Rule(style="dim"))


# ─────────────────────────────────────────────
# Typer entry-point
# ─────────────────────────────────────────────
app = typer.Typer(
    name="ask-pdf",
    help="Interactive document Q&A assistant powered by GPT-4o-mini.",
    add_completion=False,
)


@app.command()
def chat() -> None:
    """
    Start an interactive chat session.

    Upload a PDF or DOCX document using [bold green]/upload <path>[/bold green]
    and then ask questions in natural language.
    """
    _run_repl()


if __name__ == "__main__":
    app()
