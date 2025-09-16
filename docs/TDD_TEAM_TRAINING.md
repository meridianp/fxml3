# FXML4 TDD Team Training Program

## 🎯 Training Objectives
Enable all team members to effectively apply Test-Driven Development using the Claude TDD Automation Framework for building a robust financial trading platform.

---

## 📚 Module 1: TDD Fundamentals (Week 0)

### Session 1.1: Introduction to TDD (2 hours)

#### Learning Outcomes
- Understand the Red-Green-Refactor cycle
- Write effective test cases before code
- Recognize the benefits of TDD in financial systems

#### Agenda
1. **Why TDD for Financial Trading?** (30 min)
   - Cost of defects in trading systems
   - Regulatory compliance requirements
   - Case study: Knight Capital Group incident

2. **The TDD Cycle** (45 min)
   ```python
   # Live Coding Example: Currency Converter

   # Step 1: RED - Write failing test
   def test_convert_eur_to_usd():
       converter = CurrencyConverter()
       result = converter.convert(100, "EUR", "USD", rate=1.0850)
       assert result == 108.50

   # Step 2: GREEN - Make it pass (minimal code)
   class CurrencyConverter:
       def convert(self, amount, from_curr, to_curr, rate):
           return amount * rate

   # Step 3: REFACTOR - Improve design
   class CurrencyConverter:
       def __init__(self, rates_provider):
           self.rates_provider = rates_provider

       def convert(self, amount: float, from_curr: str, to_curr: str) -> float:
           rate = self.rates_provider.get_rate(from_curr, to_curr)
           return round(amount * rate, 2)
   ```

3. **Hands-on Exercise** (45 min)
   - Kata: Build a Position Calculator with TDD
   - Requirements: Calculate position size, margin, and P&L

#### Practice Assignment
```python
# Assignment: Implement a Risk Calculator using TDD
# Requirements:
# 1. Calculate position risk in account currency
# 2. Validate against max risk per trade (2%)
# 3. Handle multiple currency pairs
# 4. Include commission in calculations

# Start with this test:
def test_risk_calculator_single_position():
    calculator = RiskCalculator(account_balance=10000)
    risk = calculator.calculate_risk(
        position_size=10000,
        stop_loss_pips=50,
        pip_value=1.0
    )
    assert risk == 500  # $500 risk
    assert calculator.is_within_limit(risk) == True  # 5% of account
```

### Session 1.2: Advanced Testing Concepts (2 hours)

#### Learning Outcomes
- Master different types of testing
- Understand test doubles (mocks, stubs, fakes)
- Write maintainable test suites

#### Content

1. **Testing Pyramid for Trading Systems** (30 min)
   ```
          /\
         /  \  E2E Tests (5%)
        /____\  - Full trading workflows
       /      \  Integration Tests (20%)
      /________\  - API, Database, Broker connections
     /          \  Unit Tests (75%)
    /____________\  - Business logic, calculations
   ```

2. **Test Doubles in Financial Context** (45 min)
   ```python
   # Mock: Broker Connection
   @patch('brokers.ib_adapter.IBConnection')
   def test_order_placement_with_mock(mock_connection):
       mock_connection.place_order.return_value = OrderStatus(
           id="123",
           status="FILLED",
           filled_qty=100
       )

       trader = AutoTrader(mock_connection)
       result = trader.execute_signal(Signal("BUY", "EURUSD", 100))

       assert result.status == "FILLED"
       mock_connection.place_order.assert_called_once()

   # Stub: Market Data Provider
   class StubMarketData:
       def get_price(self, symbol):
           return {"EURUSD": 1.0850, "GBPUSD": 1.2650}[symbol]

   # Fake: In-Memory Order Book
   class FakeOrderBook:
       def __init__(self):
           self.orders = []

       def add_order(self, order):
           self.orders.append(order)
           return len(self.orders)
   ```

3. **Workshop: Testing Async Trading Operations** (45 min)
   ```python
   @pytest.mark.asyncio
   async def test_concurrent_order_execution():
       async with TradingSession() as session:
           orders = [
               Order("EURUSD", "BUY", 10000),
               Order("GBPUSD", "SELL", 5000),
               Order("USDJPY", "BUY", 20000)
           ]

           results = await asyncio.gather(
               *[session.execute(order) for order in orders]
           )

           assert all(r.status == "FILLED" for r in results)
           assert session.total_exposure <= session.max_exposure
   ```

---

## 🤖 Module 2: Claude TDD Framework (Week 1)

### Session 2.1: Framework Introduction (1.5 hours)

#### Setup and Configuration
```bash
# Installation
pip install -r .claude-tdd/requirements_phase5.txt

# Configuration
export ANTHROPIC_API_KEY="your-key-here"
export OPENAI_API_KEY="your-key-here"  # Optional

# Verify installation
python .claude-tdd/claude_tdd_main.py --help
```

#### Core Commands Walkthrough
```bash
# 1. Discover existing tests
python .claude-tdd/claude_tdd_main.py discover

# 2. Run TDD cycle for a component
python .claude-tdd/claude_tdd_main.py cycle core --category unit

# 3. Generate AI-powered tests
python .claude-tdd/claude_tdd_main.py generate-tests core \
  --test-files core/trading/order_manager.py \
  --llm-provider anthropic

# 4. Run mutation testing
python .claude-tdd/claude_tdd_main.py mutate core

# 5. Performance testing
python .claude-tdd/claude_tdd_main.py performance core \
  --performance-config peak_load
```

### Session 2.2: AI-Enhanced Testing (1.5 hours)

#### Leveraging AI for Test Generation
```python
# Example: Generate tests for Elliott Wave detector
"""
Context for AI: Generate comprehensive tests for Elliott Wave pattern detection
including:
- Fibonacci ratio validation (0.382, 0.618, 1.618)
- Wave degree classification (Minor, Intermediate, Primary)
- Invalidation rules (Wave 4 cannot overlap Wave 1)
- Multi-timeframe confirmation
"""

# Command:
python .claude-tdd/claude_tdd_main.py generate-tests elliott_wave \
  --llm-provider anthropic \
  --context "Elliott Wave pattern detection with Fibonacci ratios"
```

#### ML-Enhanced Testing Features
```bash
# Prioritize tests intelligently
python .claude-tdd/claude_tdd_main.py prioritize-tests core \
  --prioritization-strategy ml_hybrid \
  --max-tests 50

# Predict quality metrics
python .claude-tdd/claude_tdd_main.py predict-quality core \
  --forecast-days 30

# Optimize test suite
python .claude-tdd/claude_tdd_main.py optimize-tests core \
  --optimization-strategy comprehensive
```

---

## 💼 Module 3: Domain-Specific Testing (Week 2)

### Session 3.1: Testing Trading Systems (2 hours)

#### Order Management Testing
```python
class TestOrderManagement:
    """Comprehensive order management test suite"""

    def test_order_validation_prevents_oversized_positions(self):
        """RED: Ensure orders exceeding position limits are rejected"""
        manager = OrderManager(max_position_size=100000)

        oversized_order = Order(
            symbol="EURUSD",
            side="BUY",
            quantity=150000,
            order_type="MARKET"
        )

        with pytest.raises(ValidationError) as exc:
            manager.validate_order(oversized_order)

        assert "exceeds maximum position size" in str(exc.value)

    def test_order_fills_update_position_correctly(self):
        """GREEN: Test position updates after order fill"""
        manager = OrderManager()
        position = Position("EURUSD", quantity=0)

        order = Order("EURUSD", "BUY", 10000)
        fill = Fill(order_id=order.id, quantity=10000, price=1.0850)

        manager.process_fill(fill, position)

        assert position.quantity == 10000
        assert position.average_price == 1.0850

    @pytest.mark.parametrize("order_type,expected_behavior", [
        ("MARKET", "immediate_execution"),
        ("LIMIT", "price_or_better"),
        ("STOP", "trigger_then_market"),
        ("STOP_LIMIT", "trigger_then_limit")
    ])
    def test_order_types_behavior(self, order_type, expected_behavior):
        """REFACTOR: Parameterized tests for order types"""
        order = Order("EURUSD", "BUY", 1000, order_type=order_type)
        result = execute_order(order)
        assert result.behavior == expected_behavior
```

#### Risk Management Testing
```python
class TestRiskManagement:
    """Risk management test scenarios"""

    def test_portfolio_var_calculation(self):
        """Test Value at Risk calculation"""
        portfolio = Portfolio([
            Position("EURUSD", 10000, entry=1.0850),
            Position("GBPUSD", -5000, entry=1.2650),
            Position("USDJPY", 20000, entry=110.50)
        ])

        var_calculator = VaRCalculator(confidence=0.95)
        daily_var = var_calculator.calculate(portfolio)

        # VaR should be negative (potential loss)
        assert daily_var < 0
        # VaR should be within reasonable bounds (1-5% of portfolio)
        assert abs(daily_var) < portfolio.total_value * 0.05

    @given(
        leverage=st.floats(min_value=1, max_value=500),
        position_size=st.floats(min_value=1000, max_value=1000000)
    )
    def test_margin_calculation_properties(self, leverage, position_size):
        """Property-based test for margin calculations"""
        margin = calculate_margin(position_size, leverage)

        # Properties that must always hold
        assert margin > 0
        assert margin == position_size / leverage
        assert margin <= position_size
```

### Session 3.2: Testing ML Components (2 hours)

#### Feature Engineering Tests
```python
class TestFeatureEngineering:
    """ML feature engineering test suite"""

    def test_technical_indicators_calculation(self):
        """Test technical indicator features"""
        data = pd.DataFrame({
            'close': [1.0850, 1.0860, 1.0845, 1.0855, 1.0870],
            'high': [1.0860, 1.0865, 1.0850, 1.0860, 1.0875],
            'low': [1.0845, 1.0855, 1.0840, 1.0850, 1.0865],
            'volume': [1000, 1500, 1200, 1800, 2000]
        })

        features = TechnicalFeatures()
        result = features.calculate(data)

        # RSI should be between 0 and 100
        assert 0 <= result['rsi'].iloc[-1] <= 100

        # Moving averages should be calculated correctly
        expected_sma = data['close'].rolling(window=5).mean().iloc[-1]
        assert abs(result['sma_5'].iloc[-1] - expected_sma) < 0.0001

    def test_feature_scaling_preserves_relationships(self):
        """Test that scaling preserves data relationships"""
        features = np.array([[1, 100], [2, 200], [3, 300]])
        scaler = FeatureScaler()

        scaled = scaler.fit_transform(features)

        # Scaled features should preserve ordering
        assert all(scaled[i, 0] < scaled[i+1, 0] for i in range(len(scaled)-1))
        # Scaled features should be in [0, 1] or [-1, 1]
        assert scaled.min() >= -1 and scaled.max() <= 1
```

#### Model Testing
```python
class TestMLModels:
    """Machine learning model test suite"""

    def test_ensemble_model_prediction(self):
        """Test ensemble model predictions"""
        model = EnsembleModel(n_estimators=29)

        # Test data with known patterns
        X_test = create_test_features()

        predictions = model.predict(X_test)

        # Predictions should be probabilities
        assert all(0 <= p <= 1 for p in predictions)

        # Ensemble should be more stable than individual models
        individual_preds = [m.predict(X_test) for m in model.estimators]
        ensemble_std = np.std(predictions)
        individual_std = np.mean([np.std(p) for p in individual_preds])
        assert ensemble_std < individual_std

    @pytest.mark.slow
    def test_model_training_convergence(self):
        """Test that model training converges"""
        model = TradingModel()
        X_train, y_train = load_training_data()

        history = model.fit(X_train, y_train, epochs=100)

        # Loss should decrease
        assert history['loss'][-1] < history['loss'][0]
        # Model should not overfit drastically
        assert history['val_loss'][-1] < history['val_loss'][0] * 1.5
```

---

## 🛠️ Module 4: Integration Testing (Week 3)

### Session 4.1: API Testing (1.5 hours)

#### REST API Testing
```python
class TestTradingAPI:
    """Trading API integration tests"""

    @pytest.fixture
    async def client(self):
        """Test client fixture"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    async def test_place_order_endpoint(self, client):
        """Test order placement via API"""
        order_data = {
            "symbol": "EURUSD",
            "side": "BUY",
            "quantity": 10000,
            "order_type": "MARKET"
        }

        response = await client.post(
            "/api/v1/orders",
            json=order_data,
            headers={"Authorization": "Bearer test-token"}
        )

        assert response.status_code == 201
        result = response.json()
        assert result["order_id"] is not None
        assert result["status"] == "PENDING"

    async def test_websocket_price_updates(self):
        """Test WebSocket price streaming"""
        async with websockets.connect("ws://localhost:8000/ws/prices") as ws:
            # Subscribe to EURUSD
            await ws.send(json.dumps({
                "action": "subscribe",
                "symbols": ["EURUSD"]
            }))

            # Receive price updates
            for _ in range(5):
                msg = await ws.recv()
                data = json.loads(msg)

                assert data["symbol"] == "EURUSD"
                assert "bid" in data and "ask" in data
                assert data["bid"] < data["ask"]  # Spread validation
```

### Session 4.2: Database Testing (1.5 hours)

#### TimescaleDB Testing
```python
class TestDatabaseOperations:
    """Database integration tests"""

    @pytest.fixture
    async def db(self):
        """Database connection fixture"""
        async with DatabaseConnection() as conn:
            yield conn
            # Cleanup after each test
            await conn.execute("TRUNCATE TABLE trades CASCADE")

    async def test_trade_insertion_and_retrieval(self, db):
        """Test trade data persistence"""
        trade = Trade(
            symbol="EURUSD",
            side="BUY",
            quantity=10000,
            price=1.0850,
            timestamp=datetime.now()
        )

        # Insert trade
        trade_id = await db.insert_trade(trade)
        assert trade_id is not None

        # Retrieve trade
        retrieved = await db.get_trade(trade_id)
        assert retrieved.symbol == trade.symbol
        assert retrieved.quantity == trade.quantity

    async def test_time_series_aggregation(self, db):
        """Test TimescaleDB time-series features"""
        # Insert tick data
        ticks = generate_tick_data("EURUSD", count=1000)
        await db.insert_ticks(ticks)

        # Test 1-minute candle aggregation
        candles = await db.get_candles(
            symbol="EURUSD",
            interval="1m",
            start=datetime.now() - timedelta(hours=1)
        )

        assert len(candles) > 0
        for candle in candles:
            assert candle.high >= candle.low
            assert candle.close >= candle.low
            assert candle.close <= candle.high
```

---

## 🎮 Module 5: Hands-On Workshops

### Workshop 1: Building a Trading Signal Generator with TDD

#### Objective
Build a complete trading signal generator using TDD methodology

#### Requirements
```python
"""
Signal Generator Requirements:
1. Analyze price data for patterns
2. Generate BUY/SELL signals with confidence scores
3. Include risk management (stop-loss, take-profit)
4. Support multiple timeframes
5. Backtest signal performance
"""
```

#### Step-by-Step Implementation
```python
# Step 1: Write the first failing test
def test_signal_generator_detects_bullish_pattern():
    data = create_bullish_pattern_data()
    generator = SignalGenerator()

    signal = generator.analyze(data)

    assert signal.direction == "BUY"
    assert signal.confidence >= 0.7
    assert signal.stop_loss is not None

# Step 2: Implement minimal code to pass
class SignalGenerator:
    def analyze(self, data):
        # Implement pattern detection
        if self._is_bullish_pattern(data):
            return Signal(
                direction="BUY",
                confidence=0.75,
                stop_loss=self._calculate_stop_loss(data)
            )
        return None

# Step 3: Add more tests and refactor
def test_signal_generator_handles_multiple_timeframes():
    generator = SignalGenerator(timeframes=["1H", "4H", "1D"])
    data = load_multi_timeframe_data()

    signals = generator.analyze_multi_timeframe(data)

    # Should align signals across timeframes
    assert all(s.direction == signals[0].direction for s in signals)

# Continue building features test-first...
```

### Workshop 2: Performance Testing for High-Frequency Trading

#### Creating Performance Tests
```python
import pytest
from locust import HttpUser, task, between

class TradingSystemUser(HttpUser):
    wait_time = between(0.1, 0.5)  # Simulate high-frequency

    @task(3)
    def get_market_data(self):
        """High-frequency market data requests"""
        self.client.get("/api/v1/market/EURUSD")

    @task(1)
    def place_order(self):
        """Order placement test"""
        self.client.post("/api/v1/orders", json={
            "symbol": "EURUSD",
            "quantity": 10000,
            "side": "BUY"
        })

# Run with: locust -f performance_test.py --host=http://localhost:8000
```

### Workshop 3: Mutation Testing Deep Dive

#### Understanding Mutation Testing
```python
# Original code
def calculate_profit(entry_price, exit_price, quantity):
    return (exit_price - entry_price) * quantity

# Mutant 1: Changed operator
def calculate_profit_mutant1(entry_price, exit_price, quantity):
    return (exit_price + entry_price) * quantity  # BUG!

# Mutant 2: Changed comparison
def calculate_profit_mutant2(entry_price, exit_price, quantity):
    return (exit_price * entry_price) - quantity  # BUG!

# Your tests should catch these mutations
def test_calculate_profit():
    # This test catches Mutant 1
    result = calculate_profit(1.0850, 1.0860, 10000)
    assert result == 10.0  # 10 pips * 10000 = $10

    # This test catches Mutant 2
    result = calculate_profit(1.0850, 1.0840, 10000)
    assert result == -10.0  # -10 pips * 10000 = -$10
```

---

## 📋 Team Exercises & Assessments

### Exercise 1: TDD Kata - FX Position Calculator
```python
"""
Requirements:
1. Calculate position size based on risk percentage
2. Support multiple currency pairs
3. Handle account currency conversions
4. Include spread in calculations
5. Validate against minimum/maximum lot sizes

Start with these tests:
"""

def test_calculate_position_size_fixed_risk():
    calculator = PositionCalculator(
        account_balance=10000,
        risk_percentage=1.0  # 1% risk
    )

    size = calculator.calculate_size(
        stop_loss_pips=50,
        pip_value=1.0
    )

    assert size == 2000  # $100 risk / (50 pips * $1/pip)

def test_position_size_respects_max_lots():
    # Add your test here
    pass

def test_cross_currency_position_calculation():
    # Add your test here
    pass
```

### Exercise 2: Integration Test Challenge
```python
"""
Challenge: Create a complete integration test for the trading workflow:
1. Authenticate user
2. Get account balance
3. Analyze market data
4. Generate signal
5. Place order
6. Monitor position
7. Close position
8. Verify P&L
"""

@pytest.mark.integration
async def test_complete_trading_workflow():
    # Your implementation here
    pass
```

### Assessment Criteria

#### Proficiency Levels

**Level 1: Beginner**
- [ ] Understands Red-Green-Refactor cycle
- [ ] Can write basic unit tests
- [ ] Uses simple assertions
- [ ] Familiar with test fixtures

**Level 2: Intermediate**
- [ ] Writes tests before code consistently
- [ ] Uses mocks and stubs effectively
- [ ] Writes integration tests
- [ ] Understands test coverage

**Level 3: Advanced**
- [ ] Applies property-based testing
- [ ] Performs mutation testing
- [ ] Writes performance tests
- [ ] Uses AI for test generation

**Level 4: Expert**
- [ ] Designs test architectures
- [ ] Optimizes test suites
- [ ] Implements custom testing frameworks
- [ ] Mentors team on TDD practices

---

## 📚 Resources & References

### Essential Reading
1. "Test Driven Development: By Example" - Kent Beck
2. "Growing Object-Oriented Software, Guided by Tests" - Freeman & Pryce
3. "Working Effectively with Legacy Code" - Michael Feathers
4. "The Art of Unit Testing" - Roy Osherove

### Online Resources
- [Claude TDD Framework Documentation](.claude-tdd/README.md)
- [Python Testing with pytest](https://docs.pytest.org/)
- [React Testing Library](https://testing-library.com/react)
- [Mutation Testing with mutmut](https://mutmut.readthedocs.io/)

### Tools & Frameworks
```bash
# Python Testing
pip install pytest pytest-asyncio pytest-cov pytest-xdist
pip install hypothesis mutmut locust

# JavaScript Testing
npm install --save-dev jest @testing-library/react
npm install --save-dev cypress playwright

# Claude TDD Framework
pip install -r .claude-tdd/requirements_phase5.txt
```

### Quick Reference Card
```bash
# TDD Cycle Commands
alias tdd='python .claude-tdd/claude_tdd_main.py cycle'
alias tdd-gen='python .claude-tdd/claude_tdd_main.py generate-tests'
alias tdd-mutate='python .claude-tdd/claude_tdd_main.py mutate'
alias tdd-perf='python .claude-tdd/claude_tdd_main.py performance'
alias tdd-ml='python .claude-tdd/claude_tdd_main.py ml-cycle'

# Quick health check
alias tdd-health='python .claude-tdd/claude_tdd_main.py status'
```

---

## 🎯 Learning Path Progression

### Week 0-1: Foundation
- Complete Module 1 (TDD Fundamentals)
- Practice with simple katas
- Achieve 80% coverage on one component

### Week 2-3: Framework Mastery
- Complete Module 2 (Claude Framework)
- Use AI test generation
- Implement mutation testing

### Week 4-5: Domain Expertise
- Complete Module 3 (Domain Testing)
- Build trading system tests
- Practice ML component testing

### Week 6-7: Integration
- Complete Module 4 (Integration Testing)
- Build E2E test scenarios
- Performance testing

### Week 8+: Continuous Improvement
- Lead TDD sessions
- Contribute to framework
- Mentor team members

---

**Training Version**: 1.0.0
**Last Updated**: 2025-09-16
**Next Review**: After Phase 1 completion
**Feedback**: tdd-training@fxml4.com
