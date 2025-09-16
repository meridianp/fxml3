#!/bin/bash

# Set up minimal test environment variables
export FXML4_JWT_SECRET_KEY="test-secret-key"
export FXML4_JWT_TOKEN_EXPIRE_MINUTES="60"
export FXML4_DB_HOST="localhost"
export FXML4_DB_PORT="5433"
export FXML4_DB_NAME="fxml4"
export FXML4_DB_USER="postgres"
export FXML4_DB_PASSWORD="postgres"
export ALPHA_VANTAGE_API_KEY="test-key"
export POLYGON_API_KEY="test-key"
export OPENAI_API_KEY="test-key"
export ANTHROPIC_API_KEY="test-key"

echo "Test environment variables set"
