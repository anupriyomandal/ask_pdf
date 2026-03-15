# ─────────────────────────────────────────────────────────────
# Build stage: install dependencies
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# System deps for PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmupdf-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─────────────────────────────────────────────────────────────
# Runtime stage
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Make startup script executable
RUN chmod +x start.sh

# Railway sets $PORT automatically; expose it for documentation
EXPOSE 8000

# Default command — Railway overrides this via Procfile / Start Command
CMD ["./start.sh"]
