# FXML4 Test Update Checklist

**Status**: Ready for Implementation
**Last Updated**: 2025-06-28

## Quick Reference

- ❌ **Needs Update**
- ✅ **Modern/Compliant**
- ⚠️ **Has Issues**
- 🔧 **Needs Dependencies**

## Test Files by Status

### API Tests
- ✅ `tests/api/test_auth.py` - Modern pytest, minor credential cleanup needed
- ✅ `tests/api/test_endpoints.py` - Modern pytest
- ✅ `tests/api/test_middleware.py` - Modern pytest
- ✅ `tests/api/test_models.py` - Modern pytest

### Unit Tests - API
- ⚠️ `tests/unit/api/auth/test_auth_comprehensive.py` - **Fix**: datetime.utcnow() usage
- ⚠️ `tests/unit/api/test_security_middleware.py` - Modern pytest but test expectations outdated

### Unit Tests - Other
- ❌ `tests/unit/test_enhanced_ml_signal_generator.py` - **Convert**: unittest → pytest
- ❌ `tests/unit/test_general_technical_analysis_llm.py` - **Convert**: unittest → pytest
- ❌ `tests/unit/test_enhanced_elliott_wave_signals.py` - **Convert**: unittest → pytest
- ❌ `tests/unit/test_enhanced_production_system_v2.py` - **Convert**: unittest → pytest
- ❌ `tests/unit/test_alpha_vantage_news.py` - **Convert**: unittest → pytest
- ❌ `tests/unit/test_ib_adapter.py` - Modern pytest structure
- ⚠️ `tests/unit/test_ib_rabbitmq_adapter.py` - **Fix**: datetime.utcnow()
- ⚠️ `tests/unit/test_data_leakage_prevention.py` - Modern pytest, performance issues

### Unit Tests - Modules
- ✅ `tests/unit/config/test_config_comprehensive.py` - Modern pytest
- ✅ `tests/unit/config/test_config.py` - Modern pytest
- ✅ `tests/unit/data_engineering/test_async_pool.py` - Modern pytest
- ✅ `tests/unit/data_engineering/test_timescaledb_client.py` - Modern pytest
- ❌ `tests/unit/ml/test_features.py` - **Convert**: unittest → pytest
- ✅ `tests/unit/strategy/test_integrated_strategy.py` - Modern pytest
- ✅ `tests/unit/backtesting/test_backtest_engine.py` - Modern pytest

### Integration Tests
- ✅ `tests/integration/test_end_to_end.py` - **Fix**: datetime.utcnow()
- ⚠️ `tests/integration/test_ib_adapter_integration.py` - **Fix**: datetime.utcnow()
- ⚠️ `tests/integration/test_ml_pipeline.py` - Modern pytest, dependency issues
- ⚠️ `tests/integration/test_multi_adapter_integration.py` - **Fix**: datetime.utcnow()
- ❌ `tests/integration/test_production_system_enhanced.py` - **Convert**: unittest → pytest
- ❌ `tests/integration/test_wave_analysis_integration.py` - **Convert**: unittest → pytest

### Broker Tests
- ⚠️ `tests/brokers/adapters/test_fix_adapter.py` - **Fix**: datetime.utcnow() (6 occurrences)

### Performance Tests
- ✅ `tests/performance/test_performance_benchmarks.py` - Modern pytest

### Security Tests
- ✅ `tests/security/test_security_vulnerabilities.py` - Modern pytest

### Root Level Tests (Legacy)
- ❌ `tests/test_fractal.py` - **Convert**: unittest → pytest
- ❌ `tests/test_tick_to_candle.py` - **Convert**: unittest → pytest
- 🔧 `tests/test_ml_models.py` - **Convert**: unittest → pytest + **Fix**: missing xgboost
- ❌ `tests/test_integration.py` - **Convert**: unittest → pytest + **Fix**: broken imports
- ❌ `tests/test_market_regimes.py` - **Convert**: unittest → pytest
- 🔧 `tests/test_performance_metrics.py` - **Convert**: unittest → pytest + **Fix**: missing seaborn
- 🔧 `tests/test_quality_storage.py` - **Convert**: unittest → pytest + **Fix**: missing seaborn
- ❌ `tests/test_sentiment_integration.py` - **Convert**: unittest → pytest
- ❌ `tests/test_auto_reporting.py` - **Convert**: unittest → pytest
- 🔧 `tests/test_backtest_performance_integration.py` - **Convert**: unittest → pytest + **Fix**: missing seaborn
- ❌ `tests/test_data_quality.py` - **Convert**: unittest → pytest
- ❌ `tests/test_economic_features.py` - **Convert**: unittest → pytest
- ❌ `tests/test_enhanced_wave_signal_generator.py` - **Convert**: unittest → pytest
- ❌ `tests/test_alpha_vantage_feed.py` - **Convert**: unittest → pytest
- ❌ `tests/test_sentiment_wave_integration.py` - **Convert**: unittest → pytest
- ❌ `tests/test_timeframe_conversion.py` - **Convert**: unittest → pytest
- ❌ `tests/test_wave_analysis.py` - **Convert**: unittest → pytest
- 🔧 `tests/test_session_features.py` - **Fix**: broken imports
- ❌ `tests/test_fred_feed.py` - **Convert**: unittest → pytest
- ❌ `tests/test_ui_components.py` - **Convert**: unittest → pytest

## Specific Update Actions

### DateTime Fixes (6 files)
Replace `datetime.utcnow()` with `datetime.now(timezone.utc)`:

```bash
# Files to update:
tests/unit/api/auth/test_auth_comprehensive.py
tests/brokers/adapters/test_fix_adapter.py
tests/integration/test_end_to_end.py
tests/integration/test_multi_adapter_integration.py
tests/integration/test_ib_adapter_integration.py
tests/unit/test_ib_rabbitmq_adapter.py
```

### Import Fixes (2 files)

**tests/test_session_features.py**:
```python
# ❌ Current
from fxml4.ml.features import FeatureEngineer

# ✅ Need to investigate - class may not exist
```

**tests/test_integration.py**:
```python
# ❌ Current
from fxml4.ml.features import create_ml_features

# ✅ Need to verify function name/location
```

### Unittest Conversions (22 files)

**Example Conversion Pattern**:
```python
# ❌ Before (unittest)
class TestExample(unittest.TestCase):
    def setUp(self):
        self.data = create_test_data()

    def test_feature(self):
        result = process(self.data)
        self.assertEqual(result, expected)

# ✅ After (pytest)
@pytest.fixture
def test_data():
    return create_test_data()

def test_feature(test_data):
    result = process(test_data)
    assert result == expected
```

### Dependency Fixes

**Add conditional imports**:
```python
# ✅ Pattern for optional dependencies
pytest = pytest.importorskip("seaborn")
xgboost = pytest.importorskip("xgboost")

# Or use skip markers
@pytest.mark.skipif(not HAS_SEABORN, reason="seaborn not installed")
def test_visualization():
    pass
```

## Update Order (Recommended)

### Phase 1: Critical (Do First)
1. Fix datetime.utcnow() - **6 files** (30 min)
2. Fix broken imports - **2 files** (1 hour)

### Phase 2: Framework Migration
1. Convert unittest files in tests/unit/ - **6 files** (4 hours)
2. Convert unittest files in tests/integration/ - **2 files** (2 hours)
3. Convert unittest files in tests/ root - **14 files** (8 hours)

### Phase 3: Dependencies & Polish
1. Add conditional imports for missing deps - **4 files** (1 hour)
2. Clean up hardcoded credentials - **15 files** (2 hours)

## Quality Assurance

**After each phase, run**:
```bash
# Check collection
pytest tests/ --collect-only

# Run fast tests
pytest tests/ -m "not slow and not requires_ib" -v

# Check for deprecation warnings
pytest tests/ -W error::DeprecationWarning
```

## Success Criteria

- [ ] All 54 test files use modern pytest patterns
- [ ] Zero datetime deprecation warnings
- [ ] 100% test collection success
- [ ] No hardcoded credentials in test files
- [ ] Missing dependencies handled gracefully
- [ ] Test execution time < 5 minutes for unit tests
