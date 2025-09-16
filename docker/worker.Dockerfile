# FXML4 Worker Service Container
# Optimized for background workers and ML training

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for ML and data processing
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements for worker services
COPY requirements-worker.txt* requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

# Copy source code
COPY fxml4/ ./fxml4/
COPY scripts/ ./scripts/
COPY config/ ./config/
COPY db/ ./db/
COPY models/ ./models/
COPY pyproject.toml ./

# Install package
RUN pip install -e .

# Health check for worker processes
HEALTHCHECK --interval=60s --timeout=15s --start-period=10s --retries=2 \
    CMD python -c "import fxml4; print('Worker healthy')" || exit 1

# Default command - can be overridden
CMD ["python", "-m", "fxml4.workers.signal_processor"]
