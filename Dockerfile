FROM python:3.12-slim

# Prevent .pyc files and enable unbuffered stdout for logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Non-root user for security
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 --create-home appuser

# Install deps first (layer caching — only rebuilds when pyproject.toml changes)
COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[gateway,garmin]"

# Copy application code
COPY engine/ engine/
COPY mcp_server/ mcp_server/

# Create data/admin dir (volume mount point, but ensure structure exists)
RUN mkdir -p data/admin && chown -R appuser:appuser /app

USER appuser

EXPOSE 18800

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:18800/health')"]

CMD ["uvicorn", "engine.gateway.server:create_app", "--factory", "--host", "0.0.0.0", "--port", "18800"]
