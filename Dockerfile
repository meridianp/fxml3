FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Install additional dependencies for the API server
RUN pip install --no-cache-dir fastapi uvicorn[standard] pyjwt python-multipart

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "fxml3.api.main:app", "--host", "0.0.0.0", "--port", "8000"]