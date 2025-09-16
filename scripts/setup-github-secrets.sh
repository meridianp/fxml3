#!/bin/bash
set -e

# FXML4 GitHub Secrets Setup Script
# This script helps you set up all necessary secrets in your GitHub repository

echo "🔐 FXML4 GitHub Secrets Setup"
echo "============================"
echo "This script will help you add all necessary secrets to your GitHub repository."
echo "All values will be prompted interactively and securely stored in GitHub."
echo ""

# Configuration
REPO="meridianp/fxml4"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_section() {
    echo -e "\n${YELLOW}$1${NC}"
    echo "----------------------------------------"
}

# Function to set a secret
set_secret() {
    local secret_name=$1
    local prompt_text=$2
    local default_value=$3

    echo -n "$prompt_text"
    if [ -n "$default_value" ]; then
        echo -n " [$default_value]: "
    else
        echo -n ": "
    fi

    read -s secret_value
    echo "" # New line after hidden input

    # Use default if no value provided
    if [ -z "$secret_value" ] && [ -n "$default_value" ]; then
        secret_value=$default_value
    fi

    if [ -n "$secret_value" ]; then
        echo "$secret_value" | gh secret set "$secret_name" --repo "$REPO"
        print_status "Set $secret_name"
    else
        echo "Skipping $secret_name (no value provided)"
    fi
}

# Check prerequisites
print_section "Checking Prerequisites"

# Check gh CLI
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) not found. Please install it first."
    exit 1
fi
print_status "GitHub CLI found"

# Check authentication
if ! gh auth status &> /dev/null; then
    echo "❌ Not authenticated with GitHub. Please run: gh auth login"
    exit 1
fi
print_status "Authenticated with GitHub"

# External Database Configuration
print_section "External PostgreSQL Database Configuration"
print_info "Configure connection to your external PostgreSQL/TimescaleDB instance."

set_secret "DB_HOST" "Enter database host" "postgres01.tailb381ec.ts.net"
set_secret "DB_PORT" "Enter database port" "5432"
set_secret "DB_USER" "Enter database user" "postgres"
set_secret "DB_PASSWORD" "Enter database password"
set_secret "DB_NAME" "Enter database name" "fxml4"

# Infrastructure Secrets
print_section "Infrastructure Service Passwords"
print_info "These passwords will be used for your infrastructure services."
print_info "Use strong, unique passwords for each service."
set_secret "REDIS_PASSWORD" "Enter Redis password"
set_secret "RABBITMQ_PASSWORD" "Enter RabbitMQ password"
set_secret "GRAFANA_PASSWORD" "Enter Grafana admin password"

# API Keys
print_section "External API Keys"
print_info "Enter your API keys for external services."
print_info "Leave blank to skip if you don't have the key yet."

set_secret "OPENAI_API_KEY" "Enter OpenAI API key"
set_secret "ANTHROPIC_API_KEY" "Enter Anthropic API key"
set_secret "POLYGON_API_KEY" "Enter Polygon.io API key"
set_secret "ALPHA_VANTAGE_API_KEY" "Enter Alpha Vantage API key"
set_secret "FRED_API_KEY" "Enter FRED API key"

# Interactive Brokers
print_section "Interactive Brokers Configuration"
print_info "Configure your IB Gateway connection settings."

set_secret "IB_GATEWAY_HOST" "Enter IB Gateway host (e.g., localhost or IP)"
set_secret "IB_GATEWAY_PORT" "Enter IB Gateway port" "7497"
set_secret "IB_CLIENT_ID" "Enter IB client ID" "1"

# Pinecone
print_section "Pinecone Vector Database"
print_info "Configure your Pinecone vector database settings."

set_secret "PINECONE_API_KEY" "Enter Pinecone API key"
set_secret "PINECONE_ENVIRONMENT" "Enter Pinecone environment (e.g., us-east-1-aws)"

# Summary
print_section "Setup Complete!"
echo "All secrets have been added to your GitHub repository."
echo ""
echo "To view all secrets:"
echo "  gh secret list --repo $REPO"
echo ""
echo "To update a specific secret:"
echo "  gh secret set SECRET_NAME --repo $REPO"
echo ""
echo "Next steps:"
echo "1. Commit and push your changes to trigger the CI/CD pipeline"
echo "2. The GitHub Actions workflow will use these secrets automatically"
echo "3. For Kubernetes deployment, run: ./scripts/deploy/deploy.sh"
echo ""
print_info "Remember to keep your API keys secure and rotate them regularly!"
