# Data Quality Test Breakdown Plan

## Current State
- **File**: `tests/test_data_quality.py`
- **Size**: 1376 lines, 7 classes, 42 test methods
- **Purpose**: Tests core data quality assessment functionality

## Recommended Breakdown

### 1. `tests/data_quality/test_price_anomalies.py` (~300 lines)
**Classes to include:**
- `TestPriceSpikeDetection` (6 test methods)
- `TestPriceFreezeDetection` (7 test methods)

**Purpose:** Tests for abnormal price movements and static price periods

### 2. `tests/data_quality/test_data_integrity.py` (~250 lines)
**Classes to include:**
- `TestOHLCIntegrityChecks` (6 test methods)
- `TestDataCompletenessChecks` (8 test methods)

**Purpose:** Tests for data structure validation and completeness

### 3. `tests/data_quality/test_volatility_analysis.py` (~200 lines)
**Classes to include:**
- `TestVolatilityChecks` (6 test methods)

**Purpose:** Tests for volatility calculation and analysis

### 4. `tests/data_quality/test_quality_assessment.py` (~350 lines)
**Classes to include:**
- `TestIntegratedQualityAssessment` (6 test methods)

**Purpose:** Tests for overall quality scoring and assessment

### 5. `tests/data_quality/test_quality_reporting.py` (~300 lines)
**Classes to include:**
- `TestVisualizationAndReports` (3 test methods)

**Purpose:** Tests for quality report generation and visualization

### 6. `tests/data_quality/conftest.py` (~100 lines)
**Shared fixtures:**
- `normal_df()` - Standard price data
- `spike_df()` - Data with price spikes
- `freeze_df()` - Data with price freezes
- `incomplete_df()` - Data with gaps
- `invalid_ohlc_df()` - Data with OHLC errors
- `empty_df()` - Empty dataframe for edge cases

## Benefits of Breakdown

### 1. **Maintainability**
- Smaller files are easier to navigate and modify
- Clear separation of concerns
- Focused test suites for specific functionality

### 2. **Performance**
- Parallel test execution across multiple files
- Faster feedback during development
- Selective test running for specific components

### 3. **Organization**
- Logical grouping by functionality
- Shared fixtures in conftest.py
- Better code discoverability

### 4. **Development Workflow**
- Easier to work on specific quality checks
- Clearer test failure isolation
- Better documentation structure

## Implementation Approach

### Phase 1: Create Directory Structure
```bash
mkdir -p tests/data_quality
touch tests/data_quality/__init__.py
```

### Phase 2: Extract Shared Fixtures
1. Create `tests/data_quality/conftest.py`
2. Move common test data fixtures
3. Ensure proper pandas/numpy setup

### Phase 3: Split by Functionality
1. Extract each test class to appropriate file
2. Convert from unittest to pytest format
3. Update imports and fixture usage

### Phase 4: Validation
1. Run each new test file individually
2. Verify all tests pass
3. Check no duplicate or missing tests

## File Size Estimates
- `test_price_anomalies.py`: ~300 lines
- `test_data_integrity.py`: ~250 lines
- `test_volatility_analysis.py`: ~200 lines
- `test_quality_assessment.py`: ~350 lines
- `test_quality_reporting.py`: ~300 lines
- `conftest.py`: ~100 lines

**Total**: ~1500 lines (slight increase due to cleaner separation)

## Priority Order
1. **High**: Price anomalies (most critical for trading)
2. **High**: Data integrity (data structure validation)
3. **Medium**: Quality assessment (overall scoring)
4. **Medium**: Volatility analysis (market analysis)
5. **Low**: Quality reporting (visualization/reports)

## Alternative: Minimal Approach
If a full breakdown is too much work, we could:
1. Keep the current file structure
2. Just convert unittest → pytest in place
3. Extract only the most reusable fixtures to conftest.py

This would take ~30-45 minutes vs 2-3 hours for full breakdown.
