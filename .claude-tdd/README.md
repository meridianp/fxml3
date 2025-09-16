# FXML4 Claude TDD Automation Framework

> **Phase 1 Implementation Complete** ✅
> Comprehensive Test-Driven Development automation for financial trading systems

## Overview

The FXML4 Claude TDD Automation Framework is a sophisticated system that integrates with Claude Code to provide automated Test-Driven Development capabilities for our financial trading platform. This framework follows strict Red-Green-Refactor methodology while incorporating advanced testing strategies including mutation testing, contract testing, and progress preservation.

## 🚀 Quick Start

### Basic Usage

```bash
# Discover all tests across components
python .claude-tdd/claude_tdd_main.py discover

# Run full TDD cycle for core component
python .claude-tdd/claude_tdd_main.py cycle core --category unit

# Run mutation testing
python .claude-tdd/claude_tdd_main.py mutate core

# Set up contract testing
python .claude-tdd/claude_tdd_main.py contracts

# View project status
python .claude-tdd/claude_tdd_main.py status

# Full automated workflow
python .claude-tdd/claude_tdd_main.py full-auto core
```

### Shell-based TDD Operations

```bash
# Use the TDD runner for component-specific operations
./.claude-tdd/scripts/tdd_runner.sh discover
./.claude-tdd/scripts/tdd_runner.sh test core --category unit --verbose
./.claude-tdd/scripts/tdd_runner.sh cycle frontend
./.claude-tdd/scripts/tdd_runner.sh mutate elliott_wave --dry-run
```

## 🏗️ Architecture

### Framework Components

```
.claude-tdd/
├── config.yml                    # Central configuration
├── claude_tdd_main.py            # Main entry point
├── README.md                     # This documentation
│
├── scripts/                      # Language-agnostic test discovery
│   ├── discover_tests.py         # Multi-language test discovery
│   └── tdd_runner.sh             # Unified TDD operations runner
│
├── orchestrator/                 # Claude Code integration
│   ├── tdd_orchestrator.py       # TDD cycle orchestration
│   └── claude_integration.py     # Claude Code agent interface
│
├── mutation/                     # Mutation testing framework
│   ├── mutmut_config.py          # Python mutation testing (mutmut)
│   ├── stryker_config.js         # TypeScript mutation testing (Stryker)
│   └── mutation_runner.py        # Unified mutation testing runner
│
├── pact/                         # Contract testing framework
│   ├── pact_config.py            # Contract definitions and generators
│   ├── contracts/                # Generated contract files
│   └── run_contract_tests.sh     # Contract test execution
│
└── progress/                     # Progress preservation system
    ├── progress_manager.py       # TDD progress tracking
    ├── snapshots/                # Code and test snapshots
    ├── checkpoints/              # TDD cycle checkpoints
    └── backups/                  # Automated progress backups
```

### Integration with FXML4 Components

The framework supports three main components:

- **Core** (`core/`): Python/FastAPI trading system
- **Elliott Wave** (`elliott_wave/`): Python Elliott Wave analysis
- **Frontend** (`frontend/`): TypeScript/Next.js user interface

## 📋 Features

### ✅ Implemented in Phase 1

#### 1. Language-Agnostic Test Discovery
- **Python**: pytest-based discovery with marker support
- **TypeScript**: Jest/test discovery with pattern matching
- **Categorization**: unit, integration, performance, security, ml, trading, financial
- **Metadata Extraction**: Dependencies, markers, estimated duration

#### 2. Claude Code Orchestration
- **TDD Orchestrator**: Automated Red-Green-Refactor cycles
- **Agent Integration**: Multiple specialized Claude Code agents
- **Financial Context**: Trading-specific prompts and validation
- **Error Recovery**: Rollback and retry mechanisms

#### 3. Mutation Testing
- **Python**: mutmut integration with financial-specific operators
- **TypeScript**: Stryker integration with trading UI focus
- **Quality Gates**: Configurable score thresholds
- **Reporting**: HTML and JSON mutation reports

#### 4. Contract Testing
- **API Contracts**: Core ↔ Frontend API specification
- **Service Contracts**: Core ↔ Elliott Wave integration
- **Pact Framework**: Consumer and provider test generation
- **Financial Patterns**: Trading-specific contract patterns

#### 5. Progress Preservation
- **Cycle Tracking**: Complete TDD cycle state management
- **Snapshots**: Code and test result preservation
- **Checkpoints**: Rollback points for recovery
- **Incremental Synthesis**: Progressive development support

### 🔧 Configuration

#### Central Configuration (`config.yml`)

```yaml
project:
  name: "FXML4"
  version: "0.2.0"
  type: "monorepo"
  architecture: "financial-trading-system"

components:
  core:
    path: "core/"
    language: "python"
    framework: "fastapi"
    test_framework: "pytest"

  elliott_wave:
    path: "elliott_wave/"
    language: "python"
    framework: "custom"
    test_framework: "pytest"

  frontend:
    path: "frontend/"
    language: "typescript"
    framework: "nextjs"
    test_framework: "jest"

tdd:
  cycle:
    red_timeout: 30
    green_timeout: 300
    refactor_timeout: 180

mutation:
  enabled: true
  thresholds:
    minimum_score: 80
    target_score: 90

contract:
  enabled: true
  provider_verification: true
  consumer_verification: true

progress:
  enabled: true
  auto_backup: true
  backup_interval: 300
```

## 🔄 TDD Workflow

### Automated Red-Green-Refactor Cycle

1. **RED Phase**: Generate failing tests that define expected behavior
   - Claude Code agent generates comprehensive test cases
   - Tests must fail for the right reasons
   - Financial trading patterns and edge cases included

2. **GREEN Phase**: Implement minimal code to make tests pass
   - Claude Code agent implements just enough code
   - Focus on correctness over optimization
   - Maintain security and financial accuracy

3. **REFACTOR Phase**: Improve code quality while keeping tests green
   - Code review agent suggests improvements
   - Performance optimization for real-time requirements
   - DRY principle application and documentation

### Progress Preservation

Each cycle maintains:
- **Code Snapshots**: Complete file state at each phase
- **Test Results**: Detailed test execution data
- **Checkpoints**: Rollback points for error recovery
- **Metrics**: Lines of code, test coverage, duration

## 🧬 Mutation Testing

### Python Components (mutmut)

```bash
# Component-specific mutation testing
python .claude-tdd/mutation/mutation_runner.py --component core

# Full mutation testing with reporting
python .claude-tdd/mutation/mutation_runner.py
```

#### Financial-Specific Mutations

- **Arithmetic Operators**: Critical for price calculations
- **Comparison Operators**: Essential for risk thresholds
- **Constant Replacement**: Dangerous for financial constants
- **Exception Handling**: Security-critical for error paths

### TypeScript Components (Stryker)

```bash
# Frontend mutation testing
cd frontend && npx stryker run --config ../claude-tdd/mutation/stryker_config.js
```

#### Trading UI Mutations

- **State Management**: React hooks and context mutations
- **API Interactions**: Network call and data handling
- **Financial Calculations**: Client-side computation accuracy

## 📋 Contract Testing

### API-Core Contract

Defines the interface between the FastAPI backend and frontend:

- Authentication endpoints (`/auth/login`)
- Trading signals (`/signals`)
- Market data (`/data/market`)
- Order placement (`/orders`)
- Backtesting (`/backtest`)

### Elliott Wave Integration Contract

Defines the interface between core system and Elliott Wave analysis:

- Pattern analysis (`/elliott/analyze`)
- LLM sentiment analysis (`/elliott/sentiment`)
- Forecast generation with confidence scores

### Contract Execution

```bash
# Generate all contracts
python .claude-tdd/pact/pact_config.py

# Run contract tests
./.claude-tdd/pact/run_contract_tests.sh
```

## 📊 Reporting and Metrics

### Progress Reports

```bash
# Export comprehensive progress report
python .claude-tdd/progress/progress_manager.py

# View project status
python .claude-tdd/claude_tdd_main.py status
```

### Quality Metrics

- **Test Coverage**: Line and branch coverage tracking
- **Mutation Score**: Quality of test suite validation
- **Contract Compliance**: API interface verification
- **TDD Cycle Success Rate**: Development velocity tracking

## 🔍 Usage Examples

### Example 1: Complete TDD Cycle for Core Component

```bash
# Start full automated TDD workflow
python .claude-tdd/claude_tdd_main.py full-auto core

# This will:
# 1. Discover all core component tests
# 2. Execute Red-Green-Refactor cycle
# 3. Run mutation testing for quality validation
# 4. Set up contract testing with frontend
# 5. Generate comprehensive progress report
```

### Example 2: Contract Testing Setup

```bash
# Set up contract testing for all components
python .claude-tdd/claude_tdd_main.py contracts

# Run contract verification
./.claude-tdd/pact/run_contract_tests.sh
```

### Example 3: Mutation Testing Analysis

```bash
# Comprehensive mutation testing
python .claude-tdd/claude_tdd_main.py mutate

# Component-specific mutation testing
python .claude-tdd/claude_tdd_main.py mutate elliott_wave
```

## 🚧 Future Phases

### Phase 2: Monorepo Integration (Weeks 2-3)
- Multi-component dependency management
- Cross-component test orchestration
- Unified CI/CD pipeline integration

### Phase 3: Financial Trading Specialization (Weeks 3-4)
- Risk management test patterns
- Compliance testing automation
- Real-time performance validation

### Phase 4: Advanced Automation Features (Weeks 4-5)
- Machine learning model testing
- Broker integration testing
- Security vulnerability scanning

### Phase 5: Integration and Optimization (Weeks 5-6)
- Performance optimization
- Advanced reporting dashboards
- Production deployment automation

## 🔧 Troubleshooting

### Common Issues

1. **Claude Code Agent Timeout**
   ```bash
   # Increase timeout in config.yml
   tdd:
     cycle:
       green_timeout: 600  # 10 minutes
   ```

2. **Mutation Testing Memory Issues**
   ```bash
   # Reduce concurrency in mutation config
   mutation:
     concurrency: 2
   ```

3. **Contract Test Failures**
   ```bash
   # Ensure services are running
   python scripts/start_fxml4_api.py &
   ./.claude-tdd/pact/run_contract_tests.sh
   ```

### Debug Mode

```bash
# Run with verbose output
python .claude-tdd/claude_tdd_main.py cycle core --verbose

# Check progress logs
cat .claude-tdd/logs/tdd-automation.log
```

## 📚 Documentation

- **Technical Specification**: `docs/CLAUDE_TDD.md`
- **API Documentation**: Generated contract files in `.claude-tdd/pact/contracts/`
- **Progress Reports**: `.claude-tdd/progress/` directory
- **Mutation Reports**: `.claude-tdd/mutation/reports/` directory

## 🎯 Integration with FXML4 Development

### Pre-commit Hooks

The framework integrates with existing pre-commit hooks:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: claude-tdd-validation
        name: Claude TDD Quality Gates
        entry: python .claude-tdd/claude_tdd_main.py
        args: [status]
        language: system
        pass_filenames: false
```

### GitHub Actions Integration

```yaml
# .github/workflows/claude-tdd.yml
name: Claude TDD Automation
on: [push, pull_request]
jobs:
  tdd-validation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run TDD Cycle
        run: python .claude-tdd/claude_tdd_main.py cycle core
      - name: Mutation Testing
        run: python .claude-tdd/claude_tdd_main.py mutate
      - name: Contract Testing
        run: ./.claude-tdd/pact/run_contract_tests.sh
```

## 🏁 Conclusion

Phase 1 of the FXML4 Claude TDD Automation Framework provides a comprehensive foundation for automated Test-Driven Development in financial trading systems. The framework successfully integrates:

- **Language-agnostic testing** across Python and TypeScript
- **Claude Code orchestration** for automated development cycles
- **Advanced testing strategies** including mutation and contract testing
- **Progress preservation** for incremental synthesis and recovery
- **Financial trading focus** with specialized patterns and validations

This implementation establishes FXML4 as a cutting-edge TDD-automated trading platform development environment, ensuring high-quality, well-tested code while accelerating development velocity.

---

**Generated by FXML4 Claude TDD Automation Framework**
*Phase 1 Implementation - January 2025*
