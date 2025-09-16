# Multi-stage Dockerfile for FXML4 Worker Services
# Optimized for background processing and trading operations

# ============================================================================
# Stage 1: Build Dependencies
# ============================================================================
FROM python:3.11-slim as builder

# Build arguments
ARG BUILD_DATE
ARG VCS_REF
ARG SERVICE=worker

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install wheel
RUN pip install --upgrade pip wheel setuptools

# Copy requirements
COPY requirements-base.txt requirements-worker.txt ./
RUN pip install --no-cache-dir -r requirements-base.txt
RUN pip install --no-cache-dir -r requirements-worker.txt

# Copy source code and install
COPY . /app
WORKDIR /app
RUN pip install --no-cache-dir -e .

# ============================================================================
# Stage 2: Runtime Image
# ============================================================================
FROM python:3.11-slim as runtime

# Build arguments for labels
ARG BUILD_DATE
ARG VCS_REF
ARG SERVICE=worker

# Add labels
LABEL maintainer="FXML4 Trading System" \
      org.opencontainers.image.title="FXML4 Worker Services" \
      org.opencontainers.image.description="Background worker services for trading operations" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      service.name="fxml4-worker" \
      service.component="worker" \
      service.part-of="fxml4-trading-system"

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd -r fxml4 && useradd -r -g fxml4 fxml4

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --from=builder /app /app
WORKDIR /app

# Create directories and set permissions
RUN mkdir -p /app/logs /app/data /app/config && \
    chown -R fxml4:fxml4 /app

# Switch to non-root user
USER fxml4

# Environment variables
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FXML4_SERVICE=worker \
    CELERY_APP=core.worker.celery_app \
    CELERY_WORKER_CONCURRENCY=4

# Health check (for worker services)
HEALTHCHECK --interval=60s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "from core.worker.health import check_worker_health; check_worker_health()" || exit 1

# Start command (Celery worker)
CMD ["celery", "-A", "core.worker.celery_app", "worker", "--loglevel=info", "--concurrency=4"]
