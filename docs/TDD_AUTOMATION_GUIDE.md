# 🤖 FXML4 TDD Automation Guide

Complete guide to using the automated Test-Driven Development infrastructure in FXML4.

## 🚀 Quick Start

### For Python/Backend Development
```bash
# Complete TDD cycle with guided workflow
make tdd-cycle

# Individual phases
make tdd-red        # Run RED phase (failing tests)
make tdd-green      # Run GREEN phase (minimal implementation)
make tdd-refactor   # Run REFACTOR phase (comprehensive testing)

# Development workflow
make tdd-quick      # Fast feedback loop
make tdd-watch      # Watch mode for active development
```

### For TypeScript/Frontend Development
```bash
# Complete TDD cycle
npm run tdd:cycle

# Individual phases
npm run tdd:red        # Run RED phase tests
npm run tdd:green      # Run GREEN phase tests
npm run tdd:refactor   # Run REFACTOR phase tests

# Development workflow
npm run tdd:quick      # Fast feedback
npm run tdd:watch      # Watch mode
```

## 📖 Complete Command Reference

### 🔧 Makefile Commands (Python/Backend)

| Command | Description | Use Case |
|---------|-------------|----------|
| `make tdd-cycle` | Complete Red-Green-Refactor cycle | New feature development |
| `make tdd-red` | Run RED phase tests (should fail) | Start of TDD cycle |
| `make tdd-green` | Run GREEN phase tests | After minimal implementation |
| `make tdd-refactor` | Run REFACTOR phase tests | After code improvements |
| `make tdd-new` | Create new TDD workflow | Starting new feature |
| `make tdd-setup` | Create test file for module | Adding tests to existing code |
| `make tdd-validate` | Check TDD compliance | Code review preparation |
| `make tdd-watch` | Watch mode for changes | Active development |
| `make tdd-quick` | Fast feedback loop | Quick validation |
| `make tdd-report` | Generate compliance report | Status assessment |
| `make ci-tdd` | CI pipeline with TDD validation | Continuous integration |

### 📦 npm Scripts (TypeScript/Frontend)

| Command | Description | Test Pattern |
|---------|-------------|--------------|
| `npm run tdd:red` | RED phase tests | Tests with 'RED:' in name |
| `npm run tdd:green` | GREEN phase tests | Tests with 'RED:' or 'GREEN:' |
| `npm run tdd:refactor` | REFACTOR phase tests | All TDD tests with coverage |
| `npm run tdd:cycle` | Complete TDD cycle | Guided workflow |
| `npm run tdd:quick` | Fast feedback | RED + GREEN phases only |
| `npm run tdd:watch` | Watch mode | All TDD tests in watch mode |

### 🐍 Python Script Commands

| Command | Description | Example |
|---------|-------------|---------|
| `python scripts/test_runner.py unit` | Run unit tests | Coverage + validation |
| `python scripts/test_runner.py all` | Run all test categories | Complete test suite |
| `python scripts/test_runner.py fast` | Run fast tests | Development workflow |
| `python scripts/tdd_helper.py create-workflow "Feature Name"` | Create TDD template | New feature setup |
| `python scripts/tdd_helper.py create-test path/to/module.py` | Create test file | Add tests to module |
| `python scripts/tdd_helper.py validate-tdd test_file.py` | Validate TDD markers | Quality check |
| `python scripts/tdd_helper.py report` | Generate coverage report | Status overview |

## 🔄 TDD Workflow Examples

### Example 1: Creating a New Trading Feature

```bash
# 1. Create TDD workflow for new feature
make tdd-new
# Enter: "Order Management System"

# 2. Start RED phase - write failing tests
make tdd-red
# ❌ Tests fail as expected

# 3. Implement minimal code to pass tests
# Edit core/trading/order_manager.py

# 4. Run GREEN phase
make tdd-green
# ✅ Tests now pass

# 5. Refactor and improve code quality
# Improve code structure, add error handling

# 6. Run REFACTOR phase
make tdd-refactor
# ✅ All tests pass with improved code
```

### Example 2: Frontend Component Development

```bash
# 1. Start TDD cycle for React component
cd frontend
npm run tdd:cycle

# 2. Write failing test (RED phase)
# Create test file: src/components/__tests__/TradingPanel.test.tsx

# 3. Implement minimal component (GREEN phase)
npm run tdd:green

# 4. Refactor and add features (REFACTOR phase)
npm run tdd:refactor
```

### Example 3: Adding Tests to Existing Code

```bash
# Create test file for existing module
python scripts/tdd_helper.py create-test core/risk/calculator.py

# Validate TDD compliance
python scripts/tdd_helper.py validate-tdd tests/unit/test_calculator.py

# Generate coverage report
make tdd-report
```

## 🎨 Test Naming Conventions

### Python Tests (pytest)
```python
# RED phase tests - should fail initially
@pytest.mark.red
def test_should_calculate_position_risk_when_valid_input():
    """RED: Calculate position risk for valid trading parameters."""
    # This test should fail because function doesn't exist yet

# GREEN phase tests - minimal implementation
@pytest.mark.green
def test_minimal_risk_calculation():
    """GREEN: Verify minimal risk calculation works."""

# REFACTOR phase tests - comprehensive functionality
@pytest.mark.refactor
def test_comprehensive_risk_scenarios():
    """REFACTOR: Test all edge cases and scenarios."""
```

### TypeScript Tests (Jest)
```typescript
// RED phase tests
describe('TradingPanel Component', () => {
  test('RED: should render trading controls', () => {
    // This test should fail initially
  });

  test('GREEN: should display minimal trading interface', () => {
    // Minimal implementation test
  });

  test('REFACTOR: should handle all trading scenarios', () => {
    // Comprehensive test after refactoring
  });
});
```

## 📊 Coverage and Quality Gates

### Coverage Thresholds
- **Unit Tests**: 80% minimum coverage
- **Integration Tests**: 70% minimum coverage
- **Overall Project**: 80% minimum coverage

### Pre-commit Validation
```bash
# Automatic TDD validation on commit
git commit -m "feat: add order management"
# Runs: TDD validation, unit tests, coverage check

# Manual pre-commit check
pre-commit run --all-files
```

### CI/CD Integration
```bash
# Complete CI pipeline with TDD validation
make ci-tdd

# Quick CI check
make ci-quick
```

## 🛠️ Configuration Files

### TDD Markers Configuration (`pytest.ini`)
```ini
markers =
    tdd: TDD methodology tests
    red: RED phase tests (should fail initially)
    green: GREEN phase tests (minimal implementation)
    refactor: REFACTOR phase tests (comprehensive)
```

### Coverage Configuration (`.coveragerc`)
```ini
[run]
fail_under = 80
branch = True

[report]
show_missing = True
skip_covered = False
```

### Pre-commit Configuration (`.pre-commit-config.yaml`)
```yaml
- id: run-python-unit-tests
  name: TDD - Run Python unit tests
  entry: pytest tests/unit -x --tb=short --quiet -m "not slow"
```

## 🔍 Troubleshooting

### Common Issues

#### "Tests not found" Error
```bash
# Ensure test files follow naming convention
# ✅ Good: test_order_manager.py, order_manager.test.ts
# ❌ Bad: order_test.py, testOrderManager.ts

# Check test discovery paths
pytest --collect-only
```

#### Coverage Below Threshold
```bash
# Generate detailed coverage report
make coverage

# View HTML coverage report
open test-results/coverage-html/index.html

# Focus on untested code
pytest --cov=core --cov-report=term-missing
```

#### TDD Markers Not Found
```bash
# Validate test file has proper markers
python scripts/tdd_helper.py validate-tdd tests/unit/test_feature.py

# Check pytest configuration
pytest --markers | grep tdd
```

### Performance Issues

#### Slow Test Execution
```bash
# Use fast feedback loop
make tdd-quick

# Run only changed tests
pytest --lf  # last failed
pytest --ff  # failed first

# Parallel execution
pytest -n auto
```

#### Watch Mode Issues
```bash
# Alternative watch commands
make tdd-watch           # Makefile watch
npm run tdd:watch        # npm watch
pytest-watch            # pytest-watch tool
```

## 📚 Advanced Usage

### Custom Test Categories
```bash
# Run specific test markers
pytest -m "critical and not slow"
pytest -m "trading or risk_management"

# Custom test runner categories
python scripts/test_runner.py security    # Security tests
python scripts/test_runner.py performance # Performance tests
python scripts/test_runner.py compliance  # Compliance tests
```

### Integration with IDEs

#### VS Code Configuration
```json
// .vscode/settings.json
{
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["-m", "not slow"],
  "python.testing.autoTestDiscoverOnSaveEnabled": true
}
```

#### PyCharm Configuration
```bash
# Run Configuration
# Target: Custom
# Script path: scripts/test_runner.py
# Parameters: unit
```

### Docker Integration
```bash
# Run TDD tests in Docker
make docker-test-build
make docker-test-up
make test-e2e

# Clean up
make docker-test-down
```

## 🚀 Next Steps

1. **Start with `make tdd-cycle`** for your next feature
2. **Use `make tdd-watch`** during active development
3. **Run `make tdd-report`** before code reviews
4. **Integrate `make ci-tdd`** in your CI/CD pipeline
5. **Explore advanced markers** for specialized testing

## 💡 Pro Tips

- 🔴 **RED phase**: Write the test first, make it fail for the right reason
- 🟢 **GREEN phase**: Write minimal code, resist the urge to over-engineer
- 🔵 **REFACTOR phase**: Improve code quality while keeping tests green
- ⚡ **Use watch mode** for instant feedback during development
- 📊 **Check coverage regularly** to ensure comprehensive testing
- 🤖 **Let automation guide you** through the TDD process

---

*Happy Test-Driven Development! 🧪✨*
