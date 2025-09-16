#!/bin/bash
# Quick Development Environment Setup for FXML4
# This script sets up a minimal working development environment

set -e

echo "🚀 Setting up FXML4 development environment..."

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Copy development environment file
echo "📄 Setting up development .env file..."
if [[ -f "$PROJECT_ROOT/.env" ]]; then
    echo "⚠️  Existing .env file found. Creating backup..."
    cp "$PROJECT_ROOT/.env" "$PROJECT_ROOT/.env.backup.$(date +%Y%m%d_%H%M%S)"
fi

cp "$PROJECT_ROOT/.env.dev" "$PROJECT_ROOT/.env"
echo "✅ Development .env file configured"

# Make wrapper script executable
echo "🔧 Making script wrapper executable..."
chmod +x "$PROJECT_ROOT/scripts/run_with_fxml4.sh"
echo "✅ Script wrapper ready"

echo ""
echo "🎉 Development environment setup complete!"
echo ""
echo "📋 Next steps:"
echo "  1. Activate your virtual environment: source venv/bin/activate"
echo "  2. Install dependencies: pip install -r requirements.txt"
echo "  3. Start API server: ./scripts/run_with_fxml4.sh scripts/start_fxml4_api.py"
echo "  4. Run tests: ./scripts/run_with_fxml4.sh scripts/testing/run_basic_tests.py fast"
echo ""
echo "💡 All scripts should now be run using the wrapper:"
echo "   ./scripts/run_with_fxml4.sh [script-path] [args...]"
echo ""
echo "🔧 Configuration file: .env (copied from .env.dev)"
echo "📚 Documentation: Check CLAUDE.md for detailed setup instructions"
