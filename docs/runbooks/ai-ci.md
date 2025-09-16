# AI-Enhanced CI/CD Runbook

## Overview

This runbook describes how to use and troubleshoot the AI-enhanced CI/CD pipeline for FXML4 using OpenAI Codex.

## Prerequisites

- OpenAI Codex CLI installed: `npm install -g @openai/codex`
- OpenAI API key configured as GitHub secret `OPENAI_API_KEY`
- GitHub CLI (`gh`) installed and authenticated

## Configuration

### Environment Variables

Required environment variables for AI-enhanced CI/CD:
- `AI_PROVIDER`: `openai`
- `AI_MODEL`: `gpt-5`
- `AI_API_KEY`: OpenAI API key (stored as GitHub secret)

### Configuration Files

- `.ai/tests.yaml`: Test strategy and coverage thresholds
- `.ai/quality-gates.json`: Quality gates and enforcement rules
- `~/.codex/config.toml`: Codex CLI configuration

## Running Locally

### Basic AI-Assisted Development

```bash
# Start Codex with FXML4 CI profile
codex -p fxml4_ci

# Run AI-assisted test generation
codex -p fxml4_ci -a full-auto "Generate comprehensive tests for the new trading signal module"

# AI-powered code review
codex -p fxml4_ci -a full-auto "Review this PR for security vulnerabilities and trading system best practices"

# AI-assisted deployment planning
codex -p fxml4_ci -a full-auto "Plan safe deployment strategy for new broker integration feature"
```

### Test Generation

```bash
# Generate tests for specific modules
codex exec "Generate pytest tests for fxml4/brokers/adapters/ib_adapter.py with 90% coverage"

# Generate API tests
codex exec "Generate comprehensive API tests for all trading endpoints with security validation"

# Generate integration tests
codex exec "Generate integration tests for FIX protocol broker communication"
```

### Code Review

```bash
# AI code review for current branch
codex exec "Review all changes in current branch for trading system compliance and security"

# Security-focused review
codex exec "Perform security review focusing on OWASP Top 10 and financial data protection"

# Performance review
codex exec "Review code changes for performance impact on real-time trading operations"
```

## CI/CD Workflows

### AI-Enhanced Test Execution

The AI system automatically:
1. Detects changed modules
2. Generates or updates tests for touched code
3. Ensures coverage thresholds are met
4. Runs security and compliance checks

### Quality Gates

All PRs must pass:
- ✅ Test coverage ≥ 80% (API endpoints ≥ 94%)
- ✅ Security scans (CodeQL, dependency review)
- ✅ Linting and type checking
- ✅ AI-powered code review
- ✅ Trading system compliance checks

### Deployment Pipeline

1. **Staging Deployment**
   - Automated AI validation
   - Health checks
   - Smoke tests

2. **Production Deployment** 
   - Manual approval required
   - AI-assisted rollback planning
   - Canary deployment strategy
   - Comprehensive monitoring

## Commands Reference

### Codex CLI Commands

```bash
# Basic commands
codex --help                           # Show help
codex --version                        # Show version
codex login                           # Login to OpenAI

# AI-assisted execution
codex exec "task description"         # Non-interactive execution
codex -a full-auto "task"            # Full automation mode
codex -p fxml4_ci "task"             # Use FXML4 CI profile

# Apply AI-generated changes
codex apply                          # Apply latest AI diff

# Interactive mode
codex "start interactive session"    # Interactive AI assistant
```

### GitHub CLI Integration

```bash
# Set up GitHub secrets
gh secret set OPENAI_API_KEY --body="your-api-key"
gh secret set AI_PROVIDER --body="openai"  
gh secret set AI_MODEL --body="gpt-5"

# View workflow runs
gh run list
gh run view <run-id>

# Trigger workflows
gh workflow run ci.yml
gh workflow run security.yml
gh workflow run deploy.yml
```

## Test Execution

### Local Testing

```bash
# Run full test suite with AI enhancements
make test-ai

# Run specific test categories
pytest -m "api" --ai-enhanced
pytest -m "security" --ai-review
pytest -m "integration" --ai-generated

# Coverage with AI analysis
pytest --cov=fxml4 --ai-coverage-analysis
```

### CI Testing

Tests are automatically categorized and executed based on markers:
- `unit`: Fast unit tests (always run)
- `integration`: Integration tests (run on PR)
- `api`: API endpoint tests (run on API changes)  
- `security`: Security tests (always run)
- `slow`: Long-running tests (nightly)
- `requires_ib`: Interactive Brokers tests (manual trigger)

## Troubleshooting

### Common Issues

#### 1. Codex Authentication Fails

```bash
# Check authentication status
codex login

# Verify API key
echo $OPENAI_API_KEY | head -c 20  # Should show sk-...
```

#### 2. Quality Gates Failing

```bash
# Check quality gate status
cat reports/ai-quality-gates.json

# View detailed failure reasons
cat reports/ai-review.md

# Fix coverage issues
codex exec "Generate tests to reach 80% coverage for failed modules"
```

#### 3. AI Test Generation Issues

```bash
# Check test configuration
cat .ai/tests.yaml

# Regenerate tests with different strategy
codex -c "ai_generation.mocking_strategy=extensive" "Regenerate tests with more mocking"

# Debug test failures
pytest -vv --ai-debug
```

#### 4. Security Scan Failures

```bash
# View security scan results
gh run view --job security

# AI-assisted remediation
codex exec "Fix security vulnerabilities identified in latest CodeQL scan"

# Check dependency vulnerabilities
npm audit --audit-level=high
pip-audit
```

### Performance Issues

#### Slow Test Execution

```bash
# Profile test performance
pytest --durations=10 --ai-profile

# Optimize slow tests
codex exec "Optimize slow running tests to under 30 seconds each"

# Parallel execution
pytest -n auto --ai-parallel
```

#### AI Response Time

```bash
# Check API latency
codex debug api-latency

# Use faster model for simple tasks
codex -c model="gpt-4" "simple task description"

# Cache frequently used responses
codex -c cache_enabled=true "task description"
```

## Monitoring and Alerts

### Key Metrics

- Test execution time
- Coverage trends
- Security scan results
- Deployment success rate
- AI assistance usage

### Dashboard Links

- Test Coverage: [Coverage Report](reports/coverage.html)
- Security: [CodeQL Results](https://github.com/owner/fxml4/security/code-scanning)
- Performance: [Performance Dashboard](reports/performance.html)
- AI Usage: [AI Analytics](reports/ai-analytics.html)

## Best Practices

### AI Prompt Engineering

1. **Be Specific**: "Generate pytest tests for trading signal validation with edge cases"
2. **Include Context**: "Review this broker integration code considering FIX protocol compliance"
3. **Set Constraints**: "Generate tests with <5 second execution time and minimal mocking"

### Security Considerations

1. Never commit API keys or secrets
2. Use GitHub secrets for sensitive configuration
3. Review AI-generated code for security issues
4. Enable branch protection rules

### Performance Optimization

1. Use parallel test execution
2. Cache dependencies in CI
3. Profile and optimize slow tests
4. Monitor resource usage

## Emergency Procedures

### Rollback AI-Generated Changes

```bash
# Rollback latest AI changes
git revert HEAD --no-edit
git push origin main

# Disable AI for emergency hotfixes  
gh workflow disable ai-enhanced-ci.yml

# Manual deployment bypass
gh workflow run deploy.yml --ref emergency-hotfix
```

### Circuit Breakers

The AI system automatically disables itself if:
- Error rate > 20%
- Response time > 30 seconds
- Security scan failures > 5
- Test failure rate > 30%

## Support and Escalation

### Self-Service Resources

1. [FXML4 Documentation](../README.md)
2. [Test Strategy Guide](.ai/tests.yaml)
3. [Quality Gates Reference](.ai/quality-gates.json)

### Escalation Path

1. **Level 1**: Check this runbook and logs
2. **Level 2**: Review AI-generated reports in `reports/`
3. **Level 3**: Contact development team with AI session logs
4. **Level 4**: Disable AI system and use manual processes

## Configuration Changes

### Updating Quality Gates

```bash
# Edit quality gates
vim .ai/quality-gates.json

# Test configuration
codex exec "Validate quality gates configuration and suggest improvements"

# Apply changes
git add .ai/quality-gates.json
git commit -m "Update AI quality gates configuration"
```

### Adding New Test Markers

```bash
# Edit test configuration  
vim .ai/tests.yaml

# Generate tests with new markers
pytest -m "new_marker" --collect-only

# Update CI workflows
vim .github/workflows/ci.yml
```

## Logs and Debugging

### AI Session Logs

```bash
# View recent AI sessions
ls -la ~/.codex/sessions/

# View specific session
cat ~/.codex/sessions/session-id.log

# Debug AI reasoning
codex debug --session-id <id> --verbose
```

### CI/CD Logs

```bash
# View workflow logs
gh run view <run-id> --log

# Download all logs
gh run download <run-id>

# Filter AI-related logs
gh run view <run-id> --log | grep -i "ai\|codex\|openai"
```