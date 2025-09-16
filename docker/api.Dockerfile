# FXML4 API Service Container
# Optimized for API service with minimal dependencies

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for financial computing
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements for API service
COPY requirements-api.txt* requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

# Copy source code
COPY fxml4/ ./fxml4/
COPY scripts/ ./scripts/
COPY config/ ./config/
COPY db/ ./db/
COPY pyproject.toml ./

# Install package in development mode
RUN pip install -e .

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run API server
CMD ["python", "scripts/start_fxml4_api.py"]
