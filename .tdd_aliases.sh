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
