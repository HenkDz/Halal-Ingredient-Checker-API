# ============================================================
# Halal Check API - Multi-stage Dockerfile
# ============================================================

# Stage 1: Build - install dependencies
FROM python:3.12-alpine AS builder

WORKDIR /build

# Install build dependencies (compiled extensions only)
RUN apk add --no-cache gcc libffi-dev musl-dev

COPY requirements-prod.txt .
RUN pip install --no-cache-dir --no-compile --prefix=/install -r requirements-prod.txt && \
    find /install -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true

# Stage 2: Runtime - minimal production image
FROM python:3.12-alpine AS runtime

WORKDIR /app

# Install runtime dependencies (ca-certificates for HTTPS)
RUN apk add --no-cache libstdc++ && \
    addgroup -S appuser && adduser -S -G appuser -h /app -s /sbin/nologin appuser

# Copy installed packages from builder (strip unnecessary files)
COPY --from=builder /install /usr/local

# Aggressive cleanup to minimize image size
RUN find /usr/local -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true && \
    find /usr/local -type d -name tests -path "*/site-packages/*/tests" -exec rm -rf {} + 2>/dev/null; true && \
    rm -rf /usr/local/lib/python3.12/site-packages/*/tests 2>/dev/null; true && \
    rm -rf /usr/local/lib/python3.12/idlelib /usr/local/lib/python3.12/lib2to3 \
           /usr/local/lib/python3.12/tkinter /usr/local/lib/python3.12/turtledemo \
           /usr/local/lib/python3.12/pydoc_data /usr/local/lib/python3.12/ensurepip \
           /usr/local/lib/python3.12/venv /usr/local/lib/python3.12/curses \
           /usr/local/lib/python3.12/unittest /usr/local/lib/python3.12/xmlrpc \
           /usr/local/lib/python3.12/antigravity /usr/local/lib/python3.12/pdb.py 2>/dev/null; true && \
    find /usr/local -name '*.pyo' -delete 2>/dev/null; true && \
    find /usr/local -name '*.dist-info' -exec sh -c 'rm -f "$1/RECORD" "$1/top_level.txt" "$1/INSTALLER" "$1/WHEEL"' _ {} \; 2>/dev/null; true

# Copy application code
COPY app/ ./app/
COPY data/ ./data/
COPY monitoring/ ./monitoring/
COPY static/ ./static/
COPY gunicorn.conf.py .

# Create data directory and set ownership
RUN mkdir -p /app/data && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Environment defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    HOST=0.0.0.0 \
    PORT=8000 \
    WORKERS=4 \
    LOG_LEVEL=info

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"

# Expose port
EXPOSE 8000

# Run with gunicorn for production
CMD ["gunicorn", "app.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-c", "gunicorn.conf.py"]
