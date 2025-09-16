#!/bin/bash
# AI-Enhanced CI/CD Setup and Management Script for FXML4

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
OPENAI_MODEL="gpt-5"
AI_PROVIDER="openai"

echo -e "${BLUE}🤖 FXML4 AI-Enhanced CI/CD Setup${NC}"
echo "=================================================="

show_help() {
    cat << EOF
AI-Enhanced CI/CD Management for FXML4 Trading System

USAGE:
    $0 [COMMAND] [OPTIONS]

COMMANDS:
    setup           Initial setup of AI-enhanced CI/CD
    test-local      Test AI capabilities locally
    validate        Validate configuration and secrets
    update-secrets  Update GitHub secrets
    status          Show system status
    deploy          Trigger AI-assisted deployment
    help            Show this help message

OPTIONS:
    --api-key KEY   Set OpenAI API key
    --environment   Target environment (staging/production)
    --force         Force operations without confirmation

EXAMPLES:
    $0 setup --api-key sk-your-key-here
    $0 test-local
    $0 deploy --environment staging
    $0 validate

PREREQUISITES:
    - GitHub CLI (gh) installed and authenticated
    - OpenAI Codex CLI installed (npm install -g @openai/codex)
    - Valid OpenAI API key
    - Repository access with appropriate permissions

EOF
}

check_prerequisites() {
    echo -e "${BLUE}Checking prerequisites...${NC}"
    
    # Check GitHub CLI
    if ! command -v gh &> /dev/null; then
        echo -e "${RED}❌ GitHub CLI (gh) not found${NC}"
        echo "Install: https://cli.github.com/"
        exit 1
    fi
    
    # Check GitHub authentication
    if ! gh auth status &> /dev/null; then
        echo -e "${RED}❌ GitHub CLI not authenticated${NC}"
        echo "Run: gh auth login"
        exit 1
    fi
    
    # Check Codex CLI
    if ! command -v codex &> /dev/null; then
        echo -e "${RED}❌ OpenAI Codex CLI not found${NC}"
        echo "Install: npm install -g @openai/codex"
        exit 1
    fi
    
    # Check Node.js
    if ! command -v node &> /dev/null; then
        echo -e "${RED}❌ Node.js not found${NC}"
        echo "Install: https://nodejs.org/"
        exit 1
    fi
    
    echo -e "${GREEN}✅ All prerequisites met${NC}"
}

validate_configuration() {
    echo -e "${BLUE}Validating AI-enhanced CI/CD configuration...${NC}"
    
    # Check configuration files
    local config_files=(
        ".ai/tests.yaml"
        ".ai/quality-gates.json"
        ".github/workflows/ai-enhanced-ci.yml"
        ".github/workflows/ai-security.yml"
        ".github/workflows/ai-deployment.yml"
        "docs/runbooks/ai-ci.md"
    )
    
    for file in "${config_files[@]}"; do
        if [[ -f "$file" ]]; then
            echo -e "${GREEN}✅ $file${NC}"
        else
            echo -e "${RED}❌ $file missing${NC}"
        fi
    done
    
    # Check GitHub secrets
    echo -e "\n${BLUE}Checking GitHub secrets...${NC}"
    local required_secrets=("OPENAI_API_KEY" "AI_PROVIDER" "AI_MODEL")
    
    for secret in "${required_secrets[@]}"; do
        if gh secret list | grep -q "$secret"; then
            echo -e "${GREEN}✅ $secret configured${NC}"
        else
            echo -e "${RED}❌ $secret missing${NC}"
        fi
    done
    
    # Validate Codex configuration
    echo -e "\n${BLUE}Checking Codex CLI configuration...${NC}"
    if [[ -f "$HOME/.codex/config.toml" ]]; then
        if grep -q "gpt-5" "$HOME/.codex/config.toml"; then
            echo -e "${GREEN}✅ Codex configured for GPT-5${NC}"
        else
            echo -e "${YELLOW}⚠️ Codex not configured for GPT-5${NC}"
        fi
    else
        echo -e "${RED}❌ Codex configuration missing${NC}"
    fi
}

setup_ai_cicd() {
    local api_key="$1"
    
    echo -e "${BLUE}Setting up AI-Enhanced CI/CD...${NC}"
    
    if [[ -z "$api_key" ]]; then
        echo -e "${YELLOW}⚠️ No API key provided${NC}"
        echo "You'll need to set the OPENAI_API_KEY secret manually:"
        echo "gh secret set OPENAI_API_KEY --body 'your-api-key-here'"
    else
        echo -e "${BLUE}Setting up GitHub secrets...${NC}"
        gh secret set OPENAI_API_KEY --body "$api_key"
        echo -e "${GREEN}✅ OpenAI API key configured${NC}"
    fi
    
    # Set other required secrets
    gh secret set AI_PROVIDER --body "$AI_PROVIDER"
    gh secret set AI_MODEL --body "$OPENAI_MODEL"
    
    echo -e "${GREEN}✅ AI-Enhanced CI/CD setup complete${NC}"
    echo -e "\n${YELLOW}Next Steps:${NC}"
    echo "1. Validate configuration: $0 validate"
    echo "2. Test locally: $0 test-local"
    echo "3. Create a PR to trigger AI workflows"
}

test_local() {
    echo -e "${BLUE}Testing AI capabilities locally...${NC}"
    
    # Test Codex CLI
    echo -e "\n${BLUE}Testing Codex CLI connection...${NC}"
    if codex --version &> /dev/null; then
        echo -e "${GREEN}✅ Codex CLI working${NC}"
        
        # Test AI model access
        echo -e "\n${BLUE}Testing AI model access...${NC}"
        cat > /tmp/test_prompt.txt << 'EOF'
Generate a simple test function for validating API health check endpoint response.
The function should:
1. Make HTTP GET request to /health endpoint
2. Verify 200 status code  
3. Check that response contains "status": "ok"
4. Return true/false for pass/fail
EOF
        
        if codex exec "$(cat /tmp/test_prompt.txt)" &> /dev/null; then
            echo -e "${GREEN}✅ AI model access working${NC}"
        else
            echo -e "${RED}❌ AI model access failed${NC}"
            echo "Check your OpenAI API key configuration"
        fi
    else
        echo -e "${RED}❌ Codex CLI test failed${NC}"
    fi
    
    # Test GitHub integration
    echo -e "\n${BLUE}Testing GitHub integration...${NC}"
    if gh repo view &> /dev/null; then
        echo -e "${GREEN}✅ GitHub repository access working${NC}"
    else
        echo -e "${RED}❌ GitHub repository access failed${NC}"
    fi
    
    echo -e "\n${BLUE}Testing workflow files...${NC}"
    local workflows=(
        ".github/workflows/ai-enhanced-ci.yml"
        ".github/workflows/ai-security.yml"
        ".github/workflows/ai-deployment.yml"
    )
    
    for workflow in "${workflows[@]}"; do
        if [[ -f "$workflow" ]]; then
            if gh workflow list | grep -q "$(basename "$workflow" .yml)"; then
                echo -e "${GREEN}✅ $workflow active${NC}"
            else
                echo -e "${YELLOW}⚠️ $workflow not recognized by GitHub${NC}"
            fi
        fi
    done
}

trigger_deployment() {
    local environment="$1"
    
    if [[ -z "$environment" ]]; then
        environment="staging"
    fi
    
    echo -e "${BLUE}Triggering AI-assisted deployment to $environment...${NC}"
    
    # Trigger deployment workflow
    gh workflow run ai-deployment.yml \
        -f environment="$environment" \
        -f deployment_strategy="blue-green" \
        -f ai_validation="true"
        
    echo -e "${GREEN}✅ Deployment workflow triggered${NC}"
    echo "Monitor progress: gh run list"
}

show_status() {
    echo -e "${BLUE}AI-Enhanced CI/CD System Status${NC}"
    echo "=================================================="
    
    # Show recent workflow runs
    echo -e "\n${BLUE}Recent Workflow Runs:${NC}"
    gh run list --limit 5
    
    # Show active workflows
    echo -e "\n${BLUE}Active Workflows:${NC}"
    gh workflow list
    
    # Show secrets (without values)
    echo -e "\n${BLUE}Configured Secrets:${NC}"
    gh secret list | grep -E "(AI_|OPENAI_)" || echo "No AI secrets found"
    
    # Show Codex status
    echo -e "\n${BLUE}Codex CLI Status:${NC}"
    if command -v codex &> /dev/null; then
        echo "Version: $(codex --version 2>/dev/null || echo 'Unknown')"
        echo "Config: $HOME/.codex/config.toml"
    else
        echo -e "${RED}Not installed${NC}"
    fi
}

update_secrets() {
    local api_key="$1"
    
    echo -e "${BLUE}Updating GitHub secrets...${NC}"
    
    if [[ -n "$api_key" ]]; then
        gh secret set OPENAI_API_KEY --body "$api_key"
        echo -e "${GREEN}✅ OpenAI API key updated${NC}"
    fi
    
    # Update other secrets
    gh secret set AI_PROVIDER --body "$AI_PROVIDER"
    gh secret set AI_MODEL --body "$OPENAI_MODEL"
    
    echo -e "${GREEN}✅ AI secrets updated${NC}"
}

# Parse command line arguments
case "${1:-help}" in
    setup)
        check_prerequisites
        setup_ai_cicd "$2"
        ;;
    test-local|test)
        check_prerequisites
        test_local
        ;;
    validate)
        validate_configuration
        ;;
    update-secrets)
        update_secrets "$2"
        ;;
    status)
        show_status
        ;;
    deploy)
        trigger_deployment "$2"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        show_help
        exit 1
        ;;
esac