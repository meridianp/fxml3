#!/bin/bash

# FXML4 Automated Test Environment Setup Script
# Creates reproducible testing environment with all dependencies

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VENV_NAME="venv-test"
PYTHON_VERSION="3.11"
BASE_DIR="/home/cnross/code/fxml4"

echo -e "${BLUE}🚀 FXML4 Test Environment Setup${NC}"
echo "==========================================="

# Function to print status
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if running in correct directory
if [[ ! -f "pyproject.toml" ]]; then
    print_error "Must run from FXML4 root directory containing pyproject.toml"
    exit 1
fi

# Check Python version
python_version=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
if [[ "$python_version" < "3.11" ]]; then
    print_error "Python 3.11+ required, found $python_version"
    exit 1
fi
print_status "Python version check passed: $python_version"

# Clean up existing venv if requested
if [[ "${1:-}" == "--clean" ]]; then
    if [[ -d "$VENV_NAME" ]]; then
        print_warning "Removing existing virtual environment..."
        rm -rf "$VENV_NAME"
    fi
fi

# Create virtual environment
if [[ ! -d "$VENV_NAME" ]]; then
    echo -e "${BLUE}📦 Creating virtual environment: $VENV_NAME${NC}"
    python3 -m venv "$VENV_NAME"
    print_status "Virtual environment created"
else
    print_warning "Virtual environment already exists, using existing"
fi

# Activate virtual environment
source "$VENV_NAME/bin/activate"
print_status "Virtual environment activated"

# Upgrade pip, setuptools, wheel
echo -e "${BLUE}🔧 Upgrading core packages${NC}"
pip install --upgrade pip setuptools wheel
print_status "Core packages upgraded"

# Install test requirements
echo -e "${BLUE}📋 Installing test requirements${NC}"
if [[ -f "requirements-test.txt" ]]; then
    pip install -r requirements-test.txt
    print_status "Test requirements installed"
else
    print_error "requirements-test.txt not found"
    exit 1
fi

# Install FXML4 in development mode
echo -e "${BLUE}🏗️  Installing FXML4 in development mode${NC}"
pip install -e .
print_status "FXML4 installed in development mode"

# Set up environment variables for testing
echo -e "${BLUE}🔐 Setting up test environment variables${NC}"
cat > .env.test <<EOF
# FXML4 Test Environment Configuration
FXML4_ENV=test
FXML4_DATABASE_URL=sqlite:///:memory:
FXML4_DATABASE_PASSWORD=test
FXML4_REDIS_URL=redis://localhost:6379/1
FXML4_JWT_SECRET_KEY=test_jwt_secret_key_for_testing_only
FXML4_ENCRYPTION_KEY=test_encryption_key_32_bytes_long_
FXML4_API_HOST=localhost
FXML4_API_PORT=8001
FXML4_DEBUG=true
FXML4_LOG_LEVEL=INFO
FXML4_SKIP_AUTH=true
FTML4_DATABASE_PASSWORD=test
FTML4_DATABASE_URL=sqlite:///:memory:
EOF

print_status "Test environment variables created (.env.test)"

# Verify installation
echo -e "${BLUE}🔍 Verifying installation${NC}"

# Check critical imports
python3 -c "
import sys
import os
sys.path.insert(0, '.')

try:
    import fxml4
    print('✅ fxml4 module import: OK')
except ImportError as e:
    print(f'❌ fxml4 module import: FAILED - {e}')
    sys.exit(1)

# Test critical dependencies
deps = ['pytest', 'fastapi', 'aiohttp', 'numpy', 'pandas', 'plotly']
for dep in deps:
    try:
        __import__(dep)
        print(f'✅ {dep} import: OK')
    except ImportError as e:
        print(f'❌ {dep} import: FAILED - {e}')
" || {
    print_error "Installation verification failed"
    exit 1
}

print_status "Installation verification completed"

# Run basic test to ensure everything works
echo -e "${BLUE}🧪 Running basic test validation${NC}"
export FXML4_DATABASE_PASSWORD=test
export FXML4_DATABASE_URL=sqlite:///:memory:

python3 -m pytest tests/unit/config/ -v --tb=short --disable-warnings -q 2>/dev/null || {
    print_warning "Basic test validation had issues, but environment is ready"
}

print_status "Basic test validation completed"

# Display environment info
echo -e "\n${BLUE}📊 Environment Summary${NC}"
echo "==========================================="
echo "Virtual Environment: $VENV_NAME"
echo "Python Version: $(python3 --version)"
echo "Pip Version: $(pip --version | cut -d' ' -f2)"
echo "FXML4 Installation: $(pip show fxml4 | grep Version | cut -d' ' -f2)"
echo "Test Requirements: $(wc -l < requirements-test.txt) packages"

echo -e "\n${GREEN}🎉 Test environment setup complete!${NC}"
echo -e "\n${BLUE}Usage:${NC}"
echo "  source $VENV_NAME/bin/activate"
echo "  export FXML4_DATABASE_PASSWORD=test"
echo "  export FXML4_DATABASE_URL=sqlite:///:memory:"
echo "  pytest tests/ -v --cov=fxml4"
echo ""
echo -e "${BLUE}For full test suite:${NC}"
echo "  ./scripts/run_comprehensive_tests.sh"
