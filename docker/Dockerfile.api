# Multi-stage Dockerfile for FXML4 Core API
# Optimized for trading system performance and security

# ============================================================================
# Stage 1: Build Dependencies
# ============================================================================
FROM python:3.11-slim as builder

# Build arguments
ARG BUILD_DATE
ARG VCS_REF
ARG SERVICE=api

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

# Copy requirements first for better caching
COPY requirements-base.txt requirements-production.txt ./
RUN pip install --no-cache-dir -r requirements-base.txt
RUN pip install --no-cache-dir -r requirements-production.txt

# Copy source code and install application
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
ARG SERVICE=api

# Add labels for container metadata
LABEL maintainer="FXML4 Trading System" \
      org.opencontainers.image.title="FXML4 Core API" \
      org.opencontainers.image.description="High-performance trading system API" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="https://github.com/meridianp/fxml4" \
      org.opencontainers.image.documentation="https://github.com/meridianp/fxml4/docs" \
      service.name="fxml4-api" \
      service.component="core" \
      service.part-of="fxml4-trading-system"

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r fxml4 && useradd -r -g fxml4 fxml4

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --from=builder /app /app
WORKDIR /app

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/config && \
    chown -R fxml4:fxml4 /app

# Switch to non-root user
USER fxml4

# Environment variables
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FXML4_SERVICE=api \
    FXML4_LOG_LEVEL=INFO

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Start command
CMD ["python", "-m", "uvicorn", "core.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
