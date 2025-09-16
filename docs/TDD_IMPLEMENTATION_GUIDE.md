# FXML4 TDD Implementation Guide for Lead Developers

## 🎯 Mission Statement
Transform FXML4 into a world-class financial trading platform through systematic Test-Driven Development, leveraging the Claude TDD Automation Framework v5.0 to achieve unprecedented quality and reliability.

## 📊 Strategic Overview

### Current State Analysis
- **Codebase Size**: 300+ Python files, 100+ TypeScript components
- **Test Coverage**: Variable (40-70% across components)
- **Critical Systems**: Trading execution, risk management, ML models
- **Tech Stack**: Python/FastAPI, React/Next.js, PostgreSQL, Redis

### Target State (20 Weeks)
- **Test Coverage**: 85% overall, 95% critical paths
- **Mutation Score**: >80% across all components
- **Performance**: <5ms latency (P95) for all trading operations
- **Quality**: 60% reduction in production defects
- **Velocity**: 25% improvement in delivery speed

## 🚀 Phase 1: Foundation & Critical Systems (Weeks 1-4)

### Week 1-2: Core Trading Infrastructure

#### Priority Components
```python
# Critical paths requiring immediate TDD coverage
CRITICAL_COMPONENTS = [
    'core/brokers/adapters/ib_adapter.py',      # IB integration
    'core/brokers/adapters/fxcm_adapter.py',    # FXCM integration
    'core/risk_management/position_manager.py',  # Position limits
    'core/risk_management/risk_calculator.py',   # Risk calculations
    'core/api/auth/auth.py',                    # Authentication
]
```

#### Implementation Steps
1. **Baseline Assessment**
   ```bash
   # Discover existing tests
   python .claude-tdd/claude_tdd_main.py discover

   # Generate coverage report
   python .claude-tdd/claude_tdd_main.py status
   ```

2. **Start TDD Cycle for IB Adapter**
   ```bash
   # Generate AI-powered test suggestions
   python .claude-tdd/claude_tdd_main.py generate-tests core \
     --test-files core/brokers/adapters/ib_adapter.py \
     --llm-provider anthropic

   # Run TDD cycle
   python .claude-tdd/claude_tdd_main.py cycle core --category unit

   # Apply mutation testing
   python .claude-tdd/claude_tdd_main.py mutate core
   ```

3. **Risk Management TDD**
   ```python
   # Example: Position Manager Test (RED phase)
   def test_position_manager_enforces_max_exposure():
       """Test that position manager rejects orders exceeding max exposure"""
       manager = PositionManager(max_exposure=100000)

       # Create order that exceeds limit
       order = Order(
           symbol="EURUSD",
           quantity=150000,
           side="BUY"
       )

       # Should reject with RiskLimitExceeded
       with pytest.raises(RiskLimitExceeded):
           manager.validate_order(order)
   ```

#### Week 1-2 Deliverables Checklist
- [ ] 85% test coverage for broker adapters
- [ ] 95% test coverage for authentication system
- [ ] Mutation score >80% for risk management
- [ ] Performance tests for order execution (<5ms)
- [ ] Property-based tests for position calculations

### Week 3-4: Order Management & Execution

#### Focus Areas
```python
ORDER_MANAGEMENT_COMPONENTS = [
    'core/api/routers/orders.py',           # Order API endpoints
    'core/trading/order_manager.py',        # Order lifecycle
    'core/trading/execution_engine.py',     # Execution logic
    'core/trading/emergency_stop.py',       # Circuit breakers
]
```

#### Advanced TDD Techniques

1. **Property-Based Testing for Orders**
   ```python
   from hypothesis import given, strategies as st

   @given(
       price=st.floats(min_value=0.00001, max_value=1000000),
       quantity=st.integers(min_value=1, max_value=1000000),
       leverage=st.integers(min_value=1, max_value=500)
   )
   def test_order_margin_calculation_properties(price, quantity, leverage):
       """Property: Margin should always be positive and <= notional"""
       order = Order(price=price, quantity=quantity, leverage=leverage)
       margin = order.calculate_margin()

       assert margin > 0
       assert margin <= (price * quantity)
       assert margin == (price * quantity) / leverage
   ```

2. **Performance Testing for Latency**
   ```bash
   # Run performance tests with SLA validation
   python .claude-tdd/claude_tdd_main.py performance core \
     --performance-config peak_load \
     --test-files tests/performance/test_order_execution.py
   ```

## 🤖 Phase 2: ML/AI Components (Weeks 5-8)

### Week 5-6: Elliott Wave Analysis

#### TDD for Pattern Detection
```python
# Generate specialized tests for Elliott Wave
ELLIOTT_WAVE_TESTS = """
1. Wave ratio validation (Fibonacci)
2. Pattern completion detection
3. Degree classification accuracy
4. Invalidation rule checking
5. Multi-timeframe alignment
"""

# Command sequence
python .claude-tdd/claude_tdd_main.py generate-tests elliott_wave \
  --llm-provider anthropic \
  --context "Elliott Wave pattern detection with Fibonacci ratios"

python .claude-tdd/claude_tdd_main.py property elliott_wave
```

#### Example Elliott Wave Test
```python
class TestElliottWaveDetection:
    def test_impulse_wave_fibonacci_ratios(self):
        """Test impulse wave follows Fibonacci relationships"""
        # RED: Write failing test
        wave_data = create_impulse_wave_data()
        detector = ElliottWaveDetector()

        waves = detector.detect_pattern(wave_data)

        # Wave 2 should retrace 38.2-61.8% of wave 1
        wave2_retrace = waves[2].retracement_ratio(waves[1])
        assert 0.382 <= wave2_retrace <= 0.618

        # Wave 3 should be 1.618x wave 1 (common ratio)
        wave3_extension = waves[3].extension_ratio(waves[1])
        assert abs(wave3_extension - 1.618) < 0.05
```

### Week 7-8: Machine Learning Pipeline

#### ML Model Testing Strategy
```python
ML_TEST_CATEGORIES = {
    'data_quality': ['missing_values', 'outliers', 'distribution'],
    'feature_engineering': ['scaling', 'encoding', 'selection'],
    'model_performance': ['accuracy', 'precision', 'recall', 'f1'],
    'prediction_stability': ['drift', 'confidence', 'calibration'],
}
```

#### AI-Enhanced Testing for ML
```bash
# Use AI to generate comprehensive ML tests
python .claude-tdd/claude_tdd_main.py ml-cycle core

# Specific ML testing workflow
python .claude-tdd/claude_tdd_main.py generate-tests core \
  --test-files core/ml/models/ensemble.py \
  --context "Ensemble model with 29 base estimators for forex prediction"

# Predictive quality for ML components
python .claude-tdd/claude_tdd_main.py predict-quality core \
  --forecast-days 30 \
  --component ml
```

## 📈 Phase 3: Data Pipeline & Market Integration (Weeks 9-12)

### Data Pipeline TDD Approach

```python
# Critical data pipeline components
DATA_PIPELINE = {
    'ingestion': [
        'core/data/polygon_fetcher.py',
        'core/data/ib_mtf_data_fetcher.py',
    ],
    'processing': [
        'core/data/tick_aggregator.py',
        'core/data/candle_builder.py',
    ],
    'storage': [
        'core/data/timescale_handler.py',
        'core/data/redis_cache.py',
    ]
}
```

### Real-time Data Testing
```python
@pytest.mark.asyncio
async def test_websocket_tick_processing():
    """Test real-time tick data processing"""
    # Setup WebSocket mock
    ws_mock = AsyncMock()
    ws_mock.recv.side_effect = [
        '{"symbol":"EURUSD","bid":1.0850,"ask":1.0851,"timestamp":1234567890}',
        '{"symbol":"EURUSD","bid":1.0852,"ask":1.0853,"timestamp":1234567891}',
    ]

    # Process ticks
    processor = TickProcessor()
    ticks = []
    async for tick in processor.process_stream(ws_mock):
        ticks.append(tick)
        if len(ticks) >= 2:
            break

    # Validate tick sequence
    assert ticks[1].timestamp > ticks[0].timestamp
    assert ticks[1].bid > ticks[0].bid
```

## 👥 Phase 4: Frontend & User Experience (Weeks 13-16)

### Frontend TDD with React Testing Library

```typescript
// Trading Dashboard Component Test
describe('TradingDashboard', () => {
  it('should update positions in real-time via WebSocket', async () => {
    // Arrange
    const { getByTestId } = render(<TradingDashboard />);
    const ws = new WS('ws://localhost:8000/ws');

    // Act - Send position update
    await ws.send({
      type: 'POSITION_UPDATE',
      data: {
        symbol: 'EURUSD',
        quantity: 10000,
        pnl: 150.50
      }
    });

    // Assert
    await waitFor(() => {
      expect(getByTestId('position-EURUSD-pnl')).toHaveTextContent('$150.50');
    });
  });
});
```

### Integration Testing Commands
```bash
# Frontend component testing
npm test -- --coverage --watchAll=false

# E2E testing with Playwright
npx playwright test

# Integration with backend
python .claude-tdd/claude_tdd_main.py contracts
```

## 🚢 Phase 5: CI/CD & Production Readiness (Weeks 17-20)

### CI/CD Pipeline Configuration

```yaml
# .github/workflows/tdd-pipeline.yml
name: TDD Pipeline
on: [push, pull_request]

jobs:
  tdd-validation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run TDD Cycle
        run: |
          python .claude-tdd/claude_tdd_main.py cycle core --dry-run

      - name: Mutation Testing
        run: |
          python .claude-tdd/claude_tdd_main.py mutate core

      - name: Performance Validation
        run: |
          python .claude-tdd/claude_tdd_main.py performance core \
            --performance-config peak_load

      - name: ML Quality Prediction
        run: |
          python .claude-tdd/claude_tdd_main.py predict-quality core

      - name: Deploy to Staging
        if: github.ref == 'refs/heads/main'
        run: |
          python .claude-tdd/claude_tdd_main.py deploy core \
            --environment staging \
            --deployment-strategy blue-green
```

## 📊 Metrics & Monitoring

### Key Performance Indicators (KPIs)

```python
TDD_METRICS = {
    'coverage': {
        'target': 85,
        'critical_paths': 95,
        'query': 'SELECT avg(coverage) FROM test_metrics WHERE component = ?'
    },
    'mutation_score': {
        'target': 80,
        'query': 'SELECT mutation_score FROM mutation_results WHERE date = ?'
    },
    'test_execution_time': {
        'target': '< 5 minutes',
        'query': 'SELECT avg(duration) FROM test_runs WHERE type = "unit"'
    },
    'defect_rate': {
        'target': '< 0.1%',
        'query': 'SELECT count(*) FROM production_issues WHERE severity = "critical"'
    }
}
```

### Dashboard Setup
```bash
# Generate quality metrics dashboard
python .claude-tdd/claude_tdd_main.py ml-analytics

# Export metrics for Grafana
python .claude-tdd/claude_tdd_main.py status --output json > metrics.json
```

## 🎓 Team Training Program

### Week 0: TDD Fundamentals
```markdown
## Session 1: Red-Green-Refactor (2 hours)
- TDD philosophy and benefits
- Writing effective test cases
- Hands-on exercise: Calculator kata

## Session 2: Advanced Testing (2 hours)
- Mutation testing concepts
- Property-based testing
- Performance testing strategies
```

### Component-Specific Training
```python
# Generate component-specific training materials
TRAINING_MODULES = {
    'trading_team': ['broker_adapters', 'order_management', 'risk'],
    'ml_team': ['feature_engineering', 'model_testing', 'validation'],
    'frontend_team': ['react_testing', 'e2e_testing', 'visual_testing'],
}

for team, modules in TRAINING_MODULES.items():
    for module in modules:
        # Generate AI-powered training examples
        os.system(f"""
            python .claude-tdd/claude_tdd_main.py generate-tests {module} \
              --llm-provider anthropic \
              --context "Training examples for {team}"
        """)
```

## 🔧 Troubleshooting Guide

### Common Issues and Solutions

#### Issue: Slow Test Execution
```bash
# Optimize test execution
python .claude-tdd/claude_tdd_main.py optimize-tests core \
  --optimization-strategy fast

# Run tests in parallel
python .claude-tdd/claude_tdd_main.py cycle core --parallel --workers 4
```

#### Issue: Flaky Tests
```python
# Use test prioritization to identify flaky tests
python .claude-tdd/claude_tdd_main.py prioritize-tests core \
  --prioritization-strategy ml_hybrid \
  --context "Identify flaky tests"
```

#### Issue: Low Mutation Score
```bash
# Generate stronger tests
python .claude-tdd/claude_tdd_main.py generate-tests core \
  --context "Improve mutation testing score" \
  --focus "edge cases and boundary conditions"
```

## 📋 Implementation Checklist

### Pre-Launch Checklist
- [ ] Install Claude TDD Framework v5.0
- [ ] Configure API keys for AI test generation
- [ ] Set up CI/CD pipeline integration
- [ ] Train team on TDD principles
- [ ] Establish baseline metrics

### Weekly Progress Tracking
```python
# Weekly progress report generation
def generate_weekly_report(week_number):
    """Generate TDD implementation progress report"""

    metrics = {
        'coverage': get_coverage_metrics(),
        'mutation_score': get_mutation_scores(),
        'tests_added': count_new_tests(),
        'defects_prevented': estimate_prevented_defects(),
    }

    report = f"""
    Week {week_number} TDD Progress Report
    =====================================
    Coverage: {metrics['coverage']:.1f}% (Target: 85%)
    Mutation Score: {metrics['mutation_score']:.1f}% (Target: 80%)
    Tests Added: {metrics['tests_added']}
    Estimated Defects Prevented: {metrics['defects_prevented']}
    """

    return report
```

## 🚀 Quick Reference Commands

```bash
# Daily TDD workflow
alias tdd-cycle='python .claude-tdd/claude_tdd_main.py ml-cycle'
alias tdd-status='python .claude-tdd/claude_tdd_main.py status'
alias tdd-quality='python .claude-tdd/claude_tdd_main.py predict-quality'

# Component-specific commands
alias tdd-trading='python .claude-tdd/claude_tdd_main.py cycle core --category unit'
alias tdd-ml='python .claude-tdd/claude_tdd_main.py cycle elliott_wave --include-property'
alias tdd-frontend='cd frontend && npm test -- --coverage'

# Quality gates
alias tdd-mutate='python .claude-tdd/claude_tdd_main.py mutate'
alias tdd-perf='python .claude-tdd/claude_tdd_main.py performance --performance-config peak_load'

# Deployment
alias tdd-deploy-staging='python .claude-tdd/claude_tdd_main.py deploy --environment staging'
alias tdd-deploy-prod='python .claude-tdd/claude_tdd_main.py deploy --environment production --force-deployment'
```

## 📚 Additional Resources

- [Claude TDD Framework Documentation](.claude-tdd/README.md)
- [FXML4 Architecture Guide](docs/ARCHITECTURE.md)
- [Trading System Best Practices](docs/TRADING_BEST_PRACTICES.md)
- [ML Testing Strategies](docs/ML_TESTING.md)

---

**Document Version**: 1.0.0
**Last Updated**: 2025-09-16
**Owner**: Lead Development Team
**Next Review**: Week 4 Progress Review
