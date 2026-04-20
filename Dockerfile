# ─── Build stage ──────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install deps into a prefix so we can copy them cleanly
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ─── Runtime stage ────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from build stage
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Persistent volume for SQLite DB and logs
RUN mkdir -p data logs

# Non-root user for safety
RUN useradd -m botuser && chown -R botuser:botuser /app
USER botuser

# Health check — verifies the process is still alive
HEALTHCHECK --interval=60s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import os; exit(0 if os.path.exists('data/finance_bot.db') else 1)"

CMD ["python", "-u", "main.py"]