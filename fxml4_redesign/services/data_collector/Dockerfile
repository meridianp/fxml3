FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements-base.txt /app/
COPY services/data_collector/requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements-base.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules
COPY shared/ /app/shared/

# Copy service code
COPY services/data_collector/ /app/

# Create logs directory
RUN mkdir -p /app/logs

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import asyncio; from main import DataCollectorService; from shared.utils.base_service import ServiceConfig; s=DataCollectorService(ServiceConfig.from_env()); print('healthy' if asyncio.run(s.health_check())['status']=='healthy' else exit(1))"

# Run the service
CMD ["python", "main.py"]
