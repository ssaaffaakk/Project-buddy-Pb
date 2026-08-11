# ProjectBuddy — production image
# Build:  docker build -t projectbuddy .
# Run:    docker compose up   (see docker-compose.yml for the full stack)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5001

WORKDIR /app

# Install dependencies first so Docker layer-caches them across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user — container escape hardening.
RUN useradd --create-home appuser \
    && mkdir -p instance logs static/uploads \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5001

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')" || exit 1

# Same command as the Procfile (Render/Heroku) so dev == prod.
CMD ["sh", "-c", "gunicorn --worker-class eventlet -w 1 --timeout 120 --bind 0.0.0.0:${PORT} wsgi:app"]
