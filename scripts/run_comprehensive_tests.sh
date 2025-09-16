#!/bin/bash

# FXML4 Comprehensive Test Suite Runner
# Executes full test suite with coverage analysis and reporting

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
VENV_NAME="venv-test"
COVERAGE_TARGET=80
REPORT_DIR="test_reports"

echo -e "${BLUE}🧪 FXML4 Comprehensive Test Suite${NC}"
echo "==========================================="

# Check if virtual environment exists
if [[ ! -d "$VENV_NAME" ]]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Running setup...${NC}"
    ./scripts/setup_test_environment.sh
fi

# Activate virtual environment
source "$VENV_NAME/bin/activate"
echo -e "${GREEN}✅ Virtual environment activated${NC}"

# Set up test environment variables
export FXML4_DATABASE_PASSWORD=test
export FXML4_DATABASE_URL=sqlite:///:memory:
export FXML4_JWT_SECRET_KEY=test_jwt_secret_key_for_testing_only
export FTML4_DATABASE_PASSWORD=test
export FTML4_DATABASE_URL=sqlite:///:memory:

# Create reports directory
mkdir -p "$REPORT_DIR"

# Function to run test suite with specific markers
run_test_category() {
    local category="$1"
    local description="$2"
    local extra_args="${3:-}"

    echo -e "\n${BLUE}🔍 Running $description tests${NC}"
    echo "----------------------------------------"

    pytest tests/ -m "$category" $extra_args \
        --cov=fxml4 \
        --cov-report=term-missing \
        --cov-report=html:"$REPORT_DIR/htmlcov_$category" \
        --cov-report=xml:"$REPORT_DIR/coverage_$category.xml" \
        --json-report --json-report-file="$REPORT_DIR/report_$category.json" \
        --tb=short \
        --disable-warnings \
        -v || {
        echo -e "${YELLOW}⚠️  Some $description tests failed${NC}"
        return 1
    }

    return 0
}

# Run different test categories
echo -e "${BLUE}📊 Test Execution Plan${NC}"
echo "1. Unit tests (fast, isolated)"
echo "2. Integration tests (requires services)"
echo "3. API tests (endpoint validation)"
echo "4. Security tests (auth, compliance)"
echo "5. Full coverage analysis"

# 1. Unit Tests (should be fast and stable)
echo -e "\n${BLUE}=== PHASE 1: UNIT TESTS ===${NC}"
run_test_category "unit and not slow" "Unit (Fast)" "--maxfail=10" || echo "Phase 1 completed with issues"

# 2. Integration Tests (may require external services)
echo -e "\n${BLUE}=== PHASE 2: INTEGRATION TESTS ===${NC}"
run_test_category "integration and not requires_ib" "Integration (No IB)" "--maxfail=5" || echo "Phase 2 completed with issues"

# 3. API Tests
echo -e "\n${BLUE}=== PHASE 3: API TESTS ===${NC}"
run_test_category "api" "API Endpoints" "--maxfail=5" || echo "Phase 3 completed with issues"

# 4. Security Tests
echo -e "\n${BLUE}=== PHASE 4: SECURITY TESTS ===${NC}"
run_test_category "security or auth" "Security & Auth" "--maxfail=3" || echo "Phase 4 completed with issues"

# 5. Full Test Suite with comprehensive coverage
echo -e "\n${BLUE}=== PHASE 5: FULL COVERAGE ANALYSIS ===${NC}"
pytest tests/ \
    --cov=fxml4 \
    --cov-report=term-missing \
    --cov-report=html:"$REPORT_DIR/htmlcov_full" \
    --cov-report=xml:"$REPORT_DIR/coverage_full.xml" \
    --cov-fail-under=10 \
    --json-report --json-report-file="$REPORT_DIR/report_full.json" \
    --tb=short \
    --disable-warnings \
    --maxfail=20 \
    -v || {
    echo -e "${YELLOW}⚠️  Full test suite completed with failures${NC}"
}

# Generate coverage summary
echo -e "\n${BLUE}📈 Coverage Analysis${NC}"
echo "==========================================="

# Extract coverage percentage from the full report
if [[ -f "$REPORT_DIR/coverage_full.xml" ]]; then
    coverage_percent=$(python3 -c "
import xml.etree.ElementTree as ET
try:
    tree = ET.parse('$REPORT_DIR/coverage_full.xml')
    root = tree.getroot()
    coverage = root.get('line-rate')
    print(f'{float(coverage)*100:.2f}%' if coverage else 'Unknown')
except:
    print('Unknown')
")
    echo -e "Current Coverage: ${GREEN}$coverage_percent${NC}"
else
    echo -e "Coverage: ${RED}Report not generated${NC}"
fi

# Identify modules with low/no coverage
echo -e "\n${BLUE}🎯 Priority Modules for Testing${NC}"
python3 -c "
import os
import glob

# Find all Python modules in fxml4/
modules = []
for root, dirs, files in os.walk('fxml4'):
    # Skip __pycache__ and .pyc files
    dirs[:] = [d for d in dirs if d != '__pycache__']

    for file in files:
        if file.endswith('.py') and not file.startswith('__'):
            module_path = os.path.join(root, file)
            # Convert to module name
            module_name = module_path.replace('/', '.').replace('.py', '')
            modules.append(module_name)

# Priority modules (business critical)
priority_modules = [
    'fxml4.risk_management',
    'ftml4.brokers.adapters',
    'ftml4.ml.models',
    'ftml4.api.routers',
    'fxml4.data_engineering',
    'fxml4.backtesting'
]

print('High Priority Modules (need tests):')
for module in priority_modules:
    print(f'  • {module}')

print(f'\nTotal modules found: {len(modules)}')
print('Detailed coverage by module available in HTML report.')
"

# Display test summary
echo -e "\n${BLUE}📋 Test Execution Summary${NC}"
echo "==========================================="
echo "Reports Location: $REPORT_DIR/"
echo "HTML Coverage: $REPORT_DIR/htmlcov_full/index.html"
echo "XML Coverage: $REPORT_DIR/coverage_full.xml"
echo "JSON Report: $REPORT_DIR/report_full.json"

# Check if coverage meets target
echo -e "\n${BLUE}🎯 Coverage Target Analysis${NC}"
if [[ -f "$REPORT_DIR/coverage_full.xml" ]]; then
    current_coverage=$(python3 -c "
import xml.etree.ElementTree as ET
try:
    tree = ET.parse('$REPORT_DIR/coverage_full.xml')
    root = tree.getroot()
    coverage = root.get('line-rate')
    print(int(float(coverage)*100) if coverage else 0)
except:
    print(0)
")

    if [[ $current_coverage -ge $COVERAGE_TARGET ]]; then
        echo -e "${GREEN}🎉 Coverage target achieved: $current_coverage% >= $COVERAGE_TARGET%${NC}"
    else
        needed=$((COVERAGE_TARGET - current_coverage))
        echo -e "${YELLOW}⚠️  Coverage below target: $current_coverage% < $COVERAGE_TARGET% (need +$needed%)${NC}"
    fi
fi

echo -e "\n${GREEN}🏁 Comprehensive test suite completed!${NC}"
