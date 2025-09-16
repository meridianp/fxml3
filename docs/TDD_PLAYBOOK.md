# 📘 FXML4 Test-Driven Development (TDD) Playbook

## 🎯 Purpose

This playbook establishes the TDD methodology for all FXML4 development, ensuring high code quality, comprehensive test coverage, and maintainable software architecture for our financial trading platform.

## 🔴 Red-Green-Refactor Cycle

### The Three Phases

#### 1. 🔴 RED Phase - Write a Failing Test
```python
@pytest.mark.tdd
@pytest.mark.red
def test_new_trading_feature():
    """Test should fail because feature doesn't exist yet."""
    # Arrange
    trader = TradingSystem()

    # Act
    result = trader.execute_trade("EUR/USD", "BUY", 100000)

    # Assert - This will fail initially
    assert result.status == "EXECUTED"
    assert result.order_id is not None
```

#### 2. 🟢 GREEN Phase - Write Minimal Code to Pass
```python
class TradingSystem:
    def execute_trade(self, symbol, side, quantity):
        """Minimal implementation to make test pass."""
        return TradeResult(
            status="EXECUTED",
            order_id="test_order_123"
        )
```

#### 3. 🔵 REFACTOR Phase - Improve Code Quality
```python
class TradingSystem:
    def __init__(self, broker_client, risk_manager):
        self.broker = broker_client
        self.risk = risk_manager

    def execute_trade(self, symbol: str, side: str, quantity: int) -> TradeResult:
        """Production-ready implementation with proper validation."""
        # Validate inputs
        self._validate_trade_params(symbol, side, quantity)

        # Check risk limits
        if not self.risk.check_limits(symbol, quantity):
            raise RiskLimitExceeded()

        # Execute via broker
        order = self.broker.place_order(symbol, side, quantity)

        return TradeResult(
            status="EXECUTED",
            order_id=order.id,
            executed_price=order.price
        )
```

## 📝 TDD Best Practices

### 1. Test Naming Convention
```python
def test_should_[expected_behavior]_when_[condition]:
    """
    Examples:
    - test_should_reject_trade_when_insufficient_margin
    - test_should_calculate_profit_when_position_closed
    - test_should_authenticate_user_when_valid_credentials
    """
```

### 2. Test Structure - AAA Pattern
```python
def test_margin_calculation():
    # ARRANGE - Set up test data and dependencies
    account = Account(balance=10000)
    position = Position(symbol="EUR/USD", quantity=100000)

    # ACT - Execute the code being tested
    margin = calculate_margin(account, position)

    # ASSERT - Verify the outcome
    assert margin == 2000  # 2% margin requirement
```

### 3. Test Isolation
```python
@pytest.fixture
def isolated_database():
    """Each test gets a fresh database."""
    db = create_test_database()
    yield db
    db.cleanup()

def test_trade_persistence(isolated_database):
    # Test runs in complete isolation
    trade = create_trade()
    isolated_database.save(trade)
    assert isolated_database.get_trade(trade.id) == trade
```

## 🏗️ Test Categories & Markers

### Unit Tests
```python
@pytest.mark.unit
def test_fibonacci_calculation():
    """Fast, isolated tests for individual functions."""
    assert calculate_fibonacci(1.2350, 1.2450) == [1.2388, 1.2400, 1.2412]
```

### Integration Tests
```python
@pytest.mark.integration
@pytest.mark.requires_db
async def test_order_workflow():
    """Tests interaction between components."""
    async with get_test_database() as db:
        order = await create_order(db)
        await execute_order(order)
        assert order.status == "FILLED"
```

### End-to-End Tests
```python
@pytest.mark.e2e
@pytest.mark.critical
def test_complete_trading_cycle():
    """Tests entire user journey."""
    # Login
    auth_token = authenticate("trader1", "password")

    # Place order
    order = place_order(auth_token, "EUR/USD", "BUY", 100000)

    # Monitor execution
    wait_for_execution(order.id)

    # Verify P&L
    pnl = get_position_pnl(auth_token, order.id)
    assert pnl is not None
```

## 📊 Coverage Requirements

### Minimum Thresholds
- **Overall Coverage**: 80%
- **Critical Paths**: 95%
- **API Endpoints**: 90%
- **Financial Calculations**: 100%
- **New Code**: 85%

### Coverage Configuration
```ini
# .coveragerc
[run]
fail_under = 80
branch = True

[report]
exclude_lines =
    pragma: no cover
    if TYPE_CHECKING:
    raise NotImplementedError
```

## 🛠️ TDD Workflow Commands

### 1. Start New Feature
```bash
# Create test file first
touch tests/unit/test_new_feature.py

# Write failing test
pytest tests/unit/test_new_feature.py -xvs --tb=short

# Verify it fails for the right reason
# Output should show: FAILED (expected)
```

### 2. Implement Feature
```bash
# Run test continuously while implementing
pytest tests/unit/test_new_feature.py --watch

# Stop when test passes
# Output should show: PASSED
```

### 3. Refactor with Confidence
```bash
# Run full test suite
pytest

# Check coverage
pytest --cov=core --cov-report=html

# Open coverage report
open htmlcov/index.html
```

## 🎯 TDD for Different Components

### API Endpoints
```python
@pytest.mark.tdd
class TestTradingAPI:
    def test_post_order_endpoint(self, client):
        # RED: Endpoint doesn't exist
        response = client.post("/api/v1/orders", json={
            "symbol": "EUR/USD",
            "side": "BUY",
            "quantity": 100000
        })
        assert response.status_code == 201
        assert response.json()["order_id"]
```

### Database Models
```python
@pytest.mark.tdd
def test_trade_model_validation():
    # RED: Model doesn't validate
    trade = Trade(symbol="INVALID", quantity=-100)
    with pytest.raises(ValidationError):
        trade.validate()
```

### Business Logic
```python
@pytest.mark.tdd
def test_risk_calculation():
    # RED: Risk calculator doesn't exist
    calculator = RiskCalculator()
    risk = calculator.calculate_var(portfolio, confidence=0.95)
    assert 0 < risk < portfolio.total_value * 0.1
```

### Machine Learning
```python
@pytest.mark.tdd
def test_signal_generation():
    # RED: ML model doesn't predict
    model = TradingSignalModel()
    features = generate_test_features()
    signal = model.predict(features)
    assert signal in ["BUY", "SELL", "HOLD"]
```

## 🚫 TDD Anti-Patterns to Avoid

### ❌ Writing Tests After Code
```python
# BAD: Code written first, test written to match
def calculate_profit(entry, exit, quantity):
    return (exit - entry) * quantity

def test_profit():  # Written after implementation
    assert calculate_profit(1.1, 1.2, 1000) == 100
```

### ❌ Testing Implementation Details
```python
# BAD: Testing private methods and internal state
def test_internal_cache():
    calculator = Calculator()
    calculator._cache["key"] = "value"  # Don't test private attributes
    assert calculator._get_from_cache("key") == "value"
```

### ❌ Overly Complex Tests
```python
# BAD: Test does too much
def test_everything():
    user = create_user()
    login(user)
    create_account(user)
    deposit_funds(user, 10000)
    place_trade(user)
    # ... 50 more lines
```

### ✅ Better Approach
```python
# GOOD: Focused, single-purpose tests
def test_user_creation():
    user = create_user(username="trader1")
    assert user.id is not None

def test_authentication():
    token = authenticate("trader1", "password")
    assert token.is_valid()

def test_trade_execution():
    trade = execute_trade("EUR/USD", "BUY", 100000)
    assert trade.status == "EXECUTED"
```

## 📈 Metrics & Monitoring

### Test Quality Metrics
- **Test Execution Time**: < 5 seconds for unit tests
- **Flakiness Rate**: < 1%
- **Coverage Trend**: Always increasing
- **Test-to-Code Ratio**: ~1.5:1

### Continuous Monitoring
```bash
# Daily metrics
pytest --benchmark-only

# Weekly coverage trend
coverage report --skip-covered

# Monthly test health check
pytest --dead-fixtures
pytest --unused-fixtures
```

## 🔄 CI/CD Integration

### Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: run-tests
        name: Run Tests
        entry: pytest tests/unit --fail-under=80
        language: system
        pass_filenames: false
        always_run: true
```

### GitHub Actions
```yaml
name: TDD Pipeline
on: [push, pull_request]

jobs:
  test:
    steps:
      - name: Run Tests with Coverage
        run: |
          pytest --cov=core --cov-report=xml

      - name: Enforce Coverage
        run: |
          coverage report --fail-under=80
```

## 📚 Resources & Examples

### Example Test Files
- `/core/tests/unit/api/test_authentication.py` - API endpoint testing
- `/core/tests/integration/test_trading_workflow.py` - Integration testing
- `/core/tests/fixtures/market_data.py` - Reusable test fixtures

### Testing Libraries
- **pytest**: Core testing framework
- **pytest-asyncio**: Async test support
- **pytest-mock**: Mocking utilities
- **factory-boy**: Test data generation
- **hypothesis**: Property-based testing

### Further Reading
- [Test-Driven Development by Example](https://www.amazon.com/Test-Driven-Development-Kent-Beck/dp/0321146530) - Kent Beck
- [Growing Object-Oriented Software, Guided by Tests](https://www.amazon.com/Growing-Object-Oriented-Software-Guided-Tests/dp/0321503627) - Steve Freeman
- [Python Testing with pytest](https://pragprog.com/titles/bopytest2/) - Brian Okken

## ✅ TDD Checklist

Before committing code, ensure:

- [ ] Test written before implementation
- [ ] Test fails for the right reason
- [ ] Minimal code written to pass test
- [ ] All tests passing
- [ ] Code coverage >= 80%
- [ ] No test interdependencies
- [ ] Clear test names and documentation
- [ ] Refactoring complete
- [ ] Performance acceptable
- [ ] Security considerations tested

---

*"The best test is the test you write before the code exists."* - FXML4 Development Team
