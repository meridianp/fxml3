FROM python:3.7-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    build-essential \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Note: ForexConnect API needs to be manually downloaded and placed
# Download from: https://fxcodebase.com/wiki/index.php/Download
# Set FOREXCONNECT_ROOT environment variable
ENV FOREXCONNECT_ROOT=/app/ForexConnectAPI

# Copy bridge service code
COPY bridge_service.py .
COPY fix_translator.py .
COPY config.py .

# Create directory for ForexConnect API (to be mounted or copied)
RUN mkdir -p $FOREXCONNECT_ROOT

# Expose port for bridge service
EXPOSE 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9090/health')"

# Run the bridge service
CMD ["python", "-u", "bridge_service.py"]
