# Document Q&A Assistant

A production-ready document question-answering assistant for policy documents. Upload a PDF or Word document and ask questions in natural language — the system maintains conversation context so follow-up questions work naturally.

Supports **two interfaces** powered by the **same FastAPI backend**:

| Interface | How to use |
|-----------|-----------|
| 🤖 Telegram Bot | Chat with the bot on Telegram |
| 💻 CLI Tool | Run `python cli.py` in your terminal |

---

## Features

- 📄 Upload **PDF** and **DOCX** documents
- 🧠 **Conversation memory** — follow-up questions work naturally
- 🔄 **New document** clears previous context automatically
- 🚀 **Streaming responses** in the CLI
- 🏗️ Shared backend logic (DRY architecture)
- ☁️ Railway-ready deployment

---

## Project Structure

```
ask_pdf/
│
├── app.py              # FastAPI server (REST API)
├── telegram_bot.py     # Telegram bot interface
├── cli.py              # CLI chat interface (Rich + Typer)
│
├── document_parser.py  # PDF + DOCX text extraction
├── llm_service.py      # OpenAI GPT-4o-mini integration
├── session_store.py    # In-memory session management
├── config.py           # Environment-based configuration
│
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variables template
└── README.md
```

### Module Responsibilities

| File | Purpose |
|------|---------|
| `config.py` | Loads all settings from `.env` via `python-dotenv`. Single source of truth for config. |
| `session_store.py` | In-memory store for document text and conversation history per user. History is capped at 10 messages (keeps last 6 when trimmed). |
| `document_parser.py` | `extract_pdf_text()` via PyMuPDF, `extract_docx_text()` via python-docx. `parse_document()` auto-detects format. |
| `llm_service.py` | `answer_question()` builds the prompt (system + document + history + question) and calls GPT-4o-mini. Supports both streaming and blocking modes. |
| `app.py` | FastAPI server with `/upload`, `/ask`, `/new_conversation`, and `/health` endpoints. |
| `telegram_bot.py` | Telegram bot using `python-telegram-bot`. Downloads uploaded files → POSTs to FastAPI. |
| `cli.py` | Typer + Rich REPL with streamed responses and coloured prompts. Calls `llm_service` directly (no HTTP hop). |

---

## Architecture

```
User (Telegram / CLI)
        │
        ▼
  Interface Layer
  ┌─────────────┐     ┌───────────┐
  │ telegram    │     │   cli.py  │
  │ _bot.py     │     │  (direct) │
  │ (HTTP POST) │     │           │
  └──────┬──────┘     └─────┬─────┘
         │                  │
         ▼                  │
  ┌─────────────┐           │
  │   app.py    │           │
  │  (FastAPI)  │           │
  └──────┬──────┘           │
         │                  │
         └──────┬───────────┘
                ▼
         llm_service.py
                │
                ▼
         OpenAI GPT-4o-mini
```

---

## Installation

### 1. Clone and set up

```bash
git clone <your-repo-url>
cd ask_pdf

python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```env
OPENAI_API_KEY=sk-...
TELEGRAM_BOT_TOKEN=your-bot-token
BACKEND_URL=http://localhost:8000
```

---

## Running Locally

### Start the FastAPI server

```bash
python app.py
# or
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

API docs available at: [http://localhost:8000/docs](http://localhost:8000/docs)

### Start the Telegram bot

```bash
python telegram_bot.py
```

> The Telegram bot requires the FastAPI server to be running and reachable at `BACKEND_URL`.

### Run the CLI tool

```bash
python cli.py
```

The CLI communicates **directly** with the shared backend modules (no HTTP required).

---

## CLI Usage

```
User > /upload /Users/anu/Documents/policy.pdf
Agent > Document uploaded successfully. (12,450 characters extracted from 'policy.pdf')

User > what is the warranty period?
Agent > The document states that the warranty period is three years from the date of purchase.

User > what if the tyre fails in year two?
Agent > According to the policy, failures within the warranty period qualify for prorated replacement at no charge.

User > /new
Agent > Session cleared. Upload a new document to begin.

User > /exit
Goodbye!
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `/upload <path>` | Load a PDF or DOCX document |
| `/new` | Clear session and start fresh |
| `/help` | Show available commands |
| `/exit` | Exit the CLI |

---

## Telegram Bot Setup

1. Open [@BotFather](https://t.me/botfather) on Telegram.
2. Create a new bot: `/newbot`
3. Copy the token into your `.env` file as `TELEGRAM_BOT_TOKEN`.
4. Start the FastAPI server, then run `python telegram_bot.py`.

### Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Show available commands |
| `/new_conversation` | Clear document and history |
| Send a file | Upload PDF or DOCX |
| Send text | Ask a question |

---

## API Reference

### `POST /upload`
Upload a document for a user.

**Form fields:**
- `file` — PDF or DOCX file
- `user_id` — string identifier for the user

**Response:**
```json
{
  "message": "Document uploaded successfully. You can now ask questions.",
  "user_id": "123456",
  "chars_extracted": 12450
}
```

### `POST /ask`
Ask a question about the uploaded document.

**Body (JSON):**
```json
{
  "user_id": "123456",
  "question": "What is the warranty period?"
}
```

**Response:**
```json
{
  "answer": "The warranty period is three years."
}
```

### `POST /new_conversation`
Clear the session for a user.

**Form field:** `user_id`

### `GET /health`
Health check endpoint.

---

## Railway Deployment

### 1. Push to GitHub

```bash
git init && git add . && git commit -m "initial commit"
git remote add origin https://github.com/your/repo.git
git push -u origin main
```

### 2. Create a new Railway project

- Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub Repo**
- Select your repository

### 3. Set environment variables in Railway

Add these in the Railway dashboard under **Variables**:

```
OPENAI_API_KEY=sk-...
TELEGRAM_BOT_TOKEN=your-bot-token
BACKEND_URL=https://your-app.up.railway.app
```

### 4. Set the start command

In Railway → **Settings** → **Deploy** → **Start Command**:

```bash
uvicorn app:app --host 0.0.0.0 --port $PORT
```

> Railway automatically provides the `$PORT` environment variable.

### 5. Deploy Telegram bot separately (optional)

You can deploy the Telegram bot as a **separate Railway service** in the same project, pointing `BACKEND_URL` at the FastAPI service URL.

---

## Session Management

Sessions are stored **in-memory** per user:

```python
sessions = {
    "telegram_user_id": {
        "document": "<full plain text>",
        "conversation_history": [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."}
        ]
    }
}
```

- **History cap:** When conversation history exceeds **10 messages**, it is trimmed to the last **6 messages**.
- **New document:** Uploading a new document clears the entire conversation history automatically.
- **CLI user ID:** `"local_cli_user"` (fixed constant).

> ⚠️ In-memory sessions are lost on server restart. For production persistence, replace `session_store.py` with a Redis or database-backed implementation.

---

## LLM System Prompt

The assistant is instructed to answer **only from the document**:

> *"You are a policy assistant. Answer ONLY using the provided document. If the document does not contain the answer, respond: 'The document does not mention this.' Provide concise answers."*

---

## Requirements

- Python 3.11+
- OpenAI API key
- Telegram Bot Token (optional, for Telegram interface)
