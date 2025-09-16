# TDD Plan: CI/CD Issue Resolution

## Executive Summary
Comprehensive Test-Driven Development plan to resolve CI/CD failures, focusing on database schema validation, dependency management, and test infrastructure robustness.

## Current Issues Identified
1. **Database Schema Mismatches**:
   - Missing `account_snapshots` table
   - Column name conflicts (`o.symbol_id` vs `o.symbol`)
   - Foreign key relationship issues

2. **Dependency Conflicts**:
   - Pinecone package rename (`pinecone-client` → `pinecone`)
   - Complex import chains causing test failures
   - Missing ML models in development environment

3. **Test Infrastructure Problems**:
   - Import failures preventing test execution
   - Inadequate test isolation
   - Missing test fixtures

## TDD Implementation Phases

### PHASE 1: Database Schema Testing Framework 🎯

#### RED Phase - Write Failing Tests
```python
def test_required_tables_exist():
    """Test that all required database tables exist with correct schemas."""
    assert table_exists('orders')
    assert table_exists('positions')
    assert table_exists('trades')
    assert table_exists('account_snapshots')  # Currently missing!

def test_orders_table_schema():
    """Test orders table has required columns with correct types."""
    schema = get_table_schema('orders')
    assert 'symbol' in schema  # Not symbol_id!
    assert schema['symbol']['type'] == 'VARCHAR'
    assert 'order_id' in schema

def test_foreign_key_relationships():
    """Test all foreign key relationships are properly defined."""
    assert foreign_key_exists('orders', 'account_id', 'accounts', 'id')
    assert foreign_key_exists('trades', 'order_id', 'orders', 'id')
```

#### GREEN Phase - Minimal Implementation
- Create missing `account_snapshots` table
- Fix column name mismatches in existing tables
- Add missing foreign key constraints
- Update SQL queries to match actual schema

#### REFACTOR Phase - Optimization
- Consolidate migration files
- Add proper indexing for performance
- Optimize schema design

### PHASE 2: Dependency Resolution Testing 🔧

#### RED Phase - Write Failing Tests
```python
def test_core_imports_work_without_optional_dependencies():
    """Test core modules import even when optional deps missing."""
    # Should work without pinecone, ML models, etc.
    from fxml4.api.main import app
    from fxml4.core.database import get_connection

def test_graceful_degradation_missing_ml_models():
    """Test system works when ML models not available."""
    signal_service = SignalProcessingService()
    # Should not crash, should log warnings instead

def test_optional_dependency_patterns():
    """Test proper optional import patterns."""
    # Should use try/except blocks for optional imports
```

#### GREEN Phase - Fix Dependencies
- Replace `pinecone-client` with `pinecone` package
- Add proper optional import patterns
- Create mock implementations for missing services
- Implement graceful degradation

#### REFACTOR Phase - Architecture
- Create dependency injection pattern
- Add configuration-based service loading
- Implement service registry pattern

### PHASE 3: Test Infrastructure Rebuild 🏗️

#### RED Phase - Write Test Infrastructure Tests
```python
def test_database_test_fixtures_create_clean_state():
    """Test that each test gets isolated database state."""

def test_mock_services_behave_like_real_services():
    """Test mock implementations match real service interfaces."""

def test_ci_environment_matches_local():
    """Test CI database setup matches local development."""
```

#### GREEN Phase - Build Infrastructure
- Create comprehensive database fixtures
- Implement proper test isolation
- Build mock service implementations
- Set up CI-specific configurations

#### REFACTOR Phase - Performance
- Use database transactions for isolation
- Implement parallel test execution
- Cache expensive setup operations

### PHASE 4: Integration Testing Framework 🌐

#### RED Phase - Integration Test Suite
```python
def test_complete_api_startup_with_database():
    """Test full API startup sequence works with database."""

def test_order_management_workflow_end_to_end():
    """Test complete order lifecycle from creation to execution."""

def test_trading_engine_database_integration():
    """Test trading engine persists state correctly to database."""
```

#### GREEN Phase - Fix Integration
- Ensure all services integrate properly
- Fix service startup dependencies
- Resolve any remaining schema issues

#### REFACTOR Phase - Optimization
- Improve service startup order
- Add health check dependencies
- Implement graceful shutdown

## Implementation Timeline

### Week 1: Database Foundation
- **Days 1-2**: Phase 1 RED - Write comprehensive database schema tests
- **Days 3-4**: Phase 1 GREEN - Fix all database schema issues
- **Day 5**: Phase 1 REFACTOR - Optimize database design

### Week 2: Dependencies & Testing
- **Days 1-2**: Phase 2 RED/GREEN - Fix dependency conflicts
- **Days 3-4**: Phase 3 RED/GREEN - Build test infrastructure
- **Day 5**: Integration testing

### Success Metrics
- ✅ All database schema tests pass
- ✅ CI/CD pipeline runs without import failures
- ✅ Test suite achieves >80% coverage
- ✅ API startup time <30 seconds
- ✅ Zero database migration errors

## Risk Mitigation
- **Backup current database before schema changes**
- **Run tests in isolated environment first**
- **Implement rollback procedures for each phase**
- **Document all changes for team review**

---
*Generated following TDD best practices with RED-GREEN-REFACTOR methodology*
