#!/bin/bash
set -e

# Quick setup script for external database configuration
# This script sets up the GitHub secrets for the external PostgreSQL database

echo "🚀 FXML4 External Database Quick Setup"
echo "====================================="
echo ""
echo "This will configure GitHub secrets for the external database:"
echo "Host: postgres01.tailb381ec.ts.net"
echo "Port: 5432"
echo "User: postgres"
echo "Database: fxml4"
echo ""

# Check if gh CLI is available
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) not found. Please install it first."
    exit 1
fi

# Check authentication
if ! gh auth status &> /dev/null; then
    echo "❌ Not authenticated with GitHub. Please run: gh auth login"
    exit 1
fi

echo "Setting GitHub secrets for meridianp/fxml4..."

# Set database configuration
gh secret set DB_HOST --repo meridianp/fxml4 --body "postgres01.tailb381ec.ts.net"
echo "✓ Set DB_HOST"

gh secret set DB_PORT --repo meridianp/fxml4 --body "5432"
echo "✓ Set DB_PORT"

gh secret set DB_USER --repo meridianp/fxml4 --body "postgres"
echo "✓ Set DB_USER"

# Database password (the actual password)
echo "0ctavian!" | gh secret set DB_PASSWORD --repo meridianp/fxml4
echo "✓ Set DB_PASSWORD"

gh secret set DB_NAME --repo meridianp/fxml4 --body "fxml4"
echo "✓ Set DB_NAME"

echo ""
echo "✅ External database secrets configured!"
echo ""
echo "Next steps:"
echo "1. Run: ./scripts/init-external-db.sh"
echo "   to initialize the database schema"
echo ""
echo "2. Run: ./scripts/setup-github-secrets.sh"
echo "   to set up the remaining application secrets"
echo ""
echo "3. Deploy the application:"
echo "   git push (to trigger CI/CD)"
echo "   or"
echo "   ./scripts/deploy/deploy.sh (manual deployment)"
