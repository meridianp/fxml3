#!/bin/bash

# FXML4 TDD Implementation Quick Start Script
# This script sets up the environment and runs initial TDD commands

set -e  # Exit on error

echo "🚀 FXML4 TDD Implementation Quick Start"
echo "========================================"
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check Python version
echo -e "${BLUE}Checking Python version...${NC}"
python_version=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
required_version="3.11"
if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo -e "${RED}Error: Python $required_version or higher is required (found $python_version)${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python $python_version${NC}"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for required tools
echo -e "${BLUE}Checking required tools...${NC}"
for tool in git pip npm docker; do
    if command_exists $tool; then
        echo -e "${GREEN}✓ $tool installed${NC}"
    else
        echo -e "${RED}✗ $tool not found - please install${NC}"
        exit 1
    fi
done

# Check for Claude TDD Framework
echo -e "\n${BLUE}Checking Claude TDD Framework...${NC}"
if [ -d ".claude-tdd" ]; then
    echo -e "${GREEN}✓ Framework directory found${NC}"
else
    echo -e "${RED}✗ Framework directory not found${NC}"
    exit 1
fi

# Install dependencies
echo -e "\n${BLUE}Installing TDD Framework dependencies...${NC}"
pip install -q -r .claude-tdd/requirements_phase5.txt 2>/dev/null || {
    echo -e "${YELLOW}Note: Some optional dependencies may not be available${NC}"
}
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Check for API keys
echo -e "\n${BLUE}Checking API keys for AI features...${NC}"
if [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${YELLOW}⚠ No AI API keys found. AI test generation will be unavailable.${NC}"
    echo "  To enable AI features, set one of:"
    echo "    export ANTHROPIC_API_KEY='your-key'"
    echo "    export OPENAI_API_KEY='your-key'"
else
    echo -e "${GREEN}✓ API keys configured${NC}"
fi

# Create necessary directories
echo -e "\n${BLUE}Setting up project structure...${NC}"
mkdir -p .claude-tdd/reports
mkdir -p .claude-tdd/ml/models
mkdir -p .claude-tdd/ml/data
mkdir -p logs/tdd
echo -e "${GREEN}✓ Directories created${NC}"

# Run initial framework check
echo -e "\n${BLUE}Running framework status check...${NC}"
python3 .claude-tdd/claude_tdd_main.py status --output json > .claude-tdd/reports/initial_status.json 2>/dev/null || {
    echo -e "${YELLOW}⚠ Status check failed - framework may need initialization${NC}"
}

# Generate baseline metrics
echo -e "\n${BLUE}Generating baseline metrics...${NC}"
echo "Analyzing current test coverage..."

# Discover existing tests
python3 .claude-tdd/claude_tdd_main.py discover 2>/dev/null | tee .claude-tdd/reports/baseline_tests.txt || {
    echo -e "${YELLOW}⚠ Test discovery incomplete${NC}"
}

# Display current status
echo -e "\n${BLUE}===============================================${NC}"
echo -e "${BLUE}📊 CURRENT TDD STATUS${NC}"
echo -e "${BLUE}===============================================${NC}"

# Try to get current coverage (may fail if tests haven't been run)
if command_exists coverage; then
    echo "Calculating coverage..."
    coverage run -m pytest tests/ -q 2>/dev/null || true
    coverage report --skip-empty 2>/dev/null | tail -5 || echo "Coverage data not available yet"
else
    echo "Coverage tool not installed"
fi

echo ""
echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}🎯 QUICK START COMMANDS${NC}"
echo -e "${BLUE}===============================================${NC}"
echo ""
echo "1. Run your first TDD cycle:"
echo -e "   ${GREEN}python .claude-tdd/claude_tdd_main.py cycle core --category unit${NC}"
echo ""
echo "2. Generate AI-powered tests:"
echo -e "   ${GREEN}python .claude-tdd/claude_tdd_main.py generate-tests core --llm-provider anthropic${NC}"
echo ""
echo "3. Run mutation testing:"
echo -e "   ${GREEN}python .claude-tdd/claude_tdd_main.py mutate core${NC}"
echo ""
echo "4. Check performance:"
echo -e "   ${GREEN}python .claude-tdd/claude_tdd_main.py performance core --performance-config peak_load${NC}"
echo ""
echo "5. Run complete ML-enhanced cycle:"
echo -e "   ${GREEN}python .claude-tdd/claude_tdd_main.py ml-cycle core${NC}"
echo ""
echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}📚 NEXT STEPS${NC}"
echo -e "${BLUE}===============================================${NC}"
echo ""
echo "1. Review the implementation guide:"
echo "   cat docs/TDD_IMPLEMENTATION_GUIDE.md"
echo ""
echo "2. Check Phase 1 checklist:"
echo "   cat docs/TDD_PHASE_CHECKLISTS.md | head -100"
echo ""
echo "3. Start team training:"
echo "   cat docs/TDD_TEAM_TRAINING.md"
echo ""
echo "4. Track progress:"
echo "   cat docs/TDD_IMPLEMENTATION_TRACKER.md"
echo ""
echo -e "${BLUE}===============================================${NC}"
echo -e "${GREEN}✅ TDD Quick Start Complete!${NC}"
echo -e "${BLUE}===============================================${NC}"
echo ""
echo "For help: python .claude-tdd/claude_tdd_main.py --help"
echo "Framework version: v5.0"
echo ""

# Create aliases for convenience
echo -e "${BLUE}Creating convenience aliases...${NC}"
cat > .tdd_aliases.sh << 'EOF'
# FXML4 TDD Convenience Aliases

# Basic commands
alias tdd='python .claude-tdd/claude_tdd_main.py'
alias tdd-cycle='python .claude-tdd/claude_tdd_main.py cycle'
alias tdd-status='python .claude-tdd/claude_tdd_main.py status'
alias tdd-discover='python .claude-tdd/claude_tdd_main.py discover'

# Test generation
alias tdd-gen='python .claude-tdd/claude_tdd_main.py generate-tests'
alias tdd-gen-ai='python .claude-tdd/claude_tdd_main.py generate-tests --llm-provider anthropic'

# Quality testing
alias tdd-mutate='python .claude-tdd/claude_tdd_main.py mutate'
alias tdd-property='python .claude-tdd/claude_tdd_main.py property'
alias tdd-perf='python .claude-tdd/claude_tdd_main.py performance'

# ML features
alias tdd-ml='python .claude-tdd/claude_tdd_main.py ml-cycle'
alias tdd-predict='python .claude-tdd/claude_tdd_main.py predict-quality'
alias tdd-optimize='python .claude-tdd/claude_tdd_main.py optimize-tests'
alias tdd-prioritize='python .claude-tdd/claude_tdd_main.py prioritize-tests'

# Deployment
alias tdd-deploy-staging='python .claude-tdd/claude_tdd_main.py deploy --environment staging'
alias tdd-deploy-prod='python .claude-tdd/claude_tdd_main.py deploy --environment production'

# Reports
alias tdd-report='python .claude-tdd/claude_tdd_main.py status --output markdown > tdd_report_$(date +%Y%m%d).md'

echo "TDD aliases loaded! Type 'alias | grep tdd' to see all available commands."
EOF

echo -e "${GREEN}✓ Aliases created in .tdd_aliases.sh${NC}"
echo ""
echo "To use aliases in your current session, run:"
echo -e "  ${GREEN}source .tdd_aliases.sh${NC}"
echo ""
echo "To make permanent, add to your shell config:"
echo -e "  ${GREEN}echo 'source $(pwd)/.tdd_aliases.sh' >> ~/.bashrc${NC}"
echo ""

# Final summary
echo -e "${BLUE}===============================================${NC}"
echo -e "${GREEN}🎉 TDD IMPLEMENTATION READY TO START!${NC}"
echo -e "${BLUE}===============================================${NC}"
echo ""
echo "Team Training Module 1 should begin immediately."
echo "Phase 1 Week 1 tasks can now commence."
echo ""
echo "Good luck with your TDD journey! 🚀"