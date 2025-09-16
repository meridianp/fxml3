# FXML4 Monorepo Implementation Guide

## Current Status Summary

### ✅ Completed
- **No circular dependencies** in existing monorepo packages
- **6 packages** successfully migrated with clean architecture
- **Shared interfaces** defined in core package
- **Migration tooling** created and ready to use

### 🚧 Pending Migration
1. **API Gateway** (`/fxml4/api/`)
2. **Data Processing** (`/fxml4/features/`, `/fxml4/data_engineering/`)
3. **Wave Analysis** (`/fxml4/wave_analysis/`)
4. **Risk Management** (`/fxml4/risk_management/`)
5. **Visualization** (`/fxml4/visualization/`)
6. **Worker Services** (`/fxml4/worker/`)
7. **Backtesting Components** (partial migration needed)

## Step-by-Step Migration Instructions

### Phase 1: Data Processing Package (Week 1)

#### Day 1-2: Create data-processor package
```bash
cd /home/cnross/code/fxml4/fxml4-monorepo
python3 scripts/migrate_to_package.py --package data-processor

# Verify migration
cd packages/data-processor
poetry install
poetry run pytest
```

#### Day 3-4: Update dependencies
1. Update imports in migrated files
2. Add integration tests
3. Ensure compatibility with data-collector

#### Day 5: Integration testing
```bash
# Run integration tests
cd /home/cnross/code/fxml4/fxml4-monorepo
make test-integration
```

### Phase 2: Wave Analysis Package (Week 2)

#### Day 1-2: Create wave-analyzer package
```bash
python3 scripts/migrate_to_package.py --package wave-analyzer
```

#### Day 3-4: Refactor for clean separation
1. Extract Elliott Wave interfaces to core
2. Remove dependencies on strategy modules
3. Implement event-based pattern notifications

### Phase 3: API Gateway Package (Week 3)

#### Day 1-2: Create api-gateway package
```bash
python3 scripts/migrate_to_package.py --package api-gateway
```

#### Day 3-4: Resolve API circular dependencies
1. Move API models to separate schemas package
2. Use dependency injection for services
3. Implement API versioning

#### Day 5: API testing
1. Create API integration tests
2. Verify all endpoints work
3. Update API documentation

### Phase 4: Risk Management Package (Week 4)

#### Day 1-2: Extract from trade-manager
1. Create risk-manager package
2. Move risk logic from trade-manager
3. Define risk interfaces in core

#### Day 3-4: Integration
1. Update trade-manager to use risk-manager
2. Add risk event notifications
3. Implement risk monitoring

### Phase 5: Web Dashboard (Week 5)

#### Day 1-2: Create web-dashboard package
```bash
python3 scripts/migrate_to_package.py --package web-dashboard
```

#### Day 3-4: Frontend/Backend separation
1. Separate Streamlit UI from API calls
2. Use api-gateway for all backend communication
3. Implement WebSocket support

### Phase 6: Worker Services (Week 6)

#### Day 1-2: Create worker-services package
```bash
python3 scripts/migrate_to_package.py --package worker-services
```

#### Day 3-4: Service orchestration
1. Implement task queue integration
2. Add service discovery
3. Create worker management tools

## Circular Dependency Prevention

### 1. Use Interfaces
```python
# Bad: Direct import
from fxml4_trade_manager.position_manager import PositionManager

# Good: Interface import
from fxml4_core.interfaces import TradeExecutor
```

### 2. Dependency Injection
```python
# Bad: Hard-coded dependency
class SignalService:
    def __init__(self):
        self.trade_manager = TradeManager()

# Good: Injected dependency
class SignalService:
    def __init__(self, trade_executor: TradeExecutor):
        self.trade_executor = trade_executor
```

### 3. Event-Based Communication
```python
# Bad: Direct method call
trade_manager.execute_signal(signal)

# Good: Event publication
await event_bus.publish(SignalEvent(signal))
```

## Migration Validation Checklist

### For Each Package:
- [ ] All tests pass (`poetry run pytest`)
- [ ] No circular dependencies (`python3 tools/check_dependencies.py`)
- [ ] Code formatted (`poetry run black src tests`)
- [ ] Type hints validated (`poetry run mypy src`)
- [ ] Documentation updated
- [ ] Integration tests pass

### Overall System:
- [ ] All packages build successfully
- [ ] Integration tests pass
- [ ] Performance benchmarks meet targets
- [ ] No regression in functionality
- [ ] Documentation complete

## Common Migration Issues and Solutions

### Issue 1: Import Errors
**Problem**: `ModuleNotFoundError` after migration
**Solution**:
1. Update all imports using migration script
2. Check pyproject.toml dependencies
3. Run `poetry install` in package directory

### Issue 2: Circular Import Detection
**Problem**: New circular dependency introduced
**Solution**:
1. Run dependency checker
2. Extract shared code to core
3. Use interfaces instead of concrete classes

### Issue 3: Test Failures
**Problem**: Tests fail after migration
**Solution**:
1. Update test imports
2. Mock external dependencies
3. Use fixtures from conftest.py

### Issue 4: Missing Dependencies
**Problem**: Runtime errors due to missing packages
**Solution**:
1. Check pyproject.toml dependencies
2. Add missing packages with `poetry add`
3. Verify with `poetry show`

## Automation Scripts

### 1. Batch Migration
```bash
#!/bin/bash
# migrate_all.sh
packages=("data-processor" "wave-analyzer" "api-gateway" "web-dashboard" "worker-services")

for pkg in "${packages[@]}"; do
    echo "Migrating $pkg..."
    python3 scripts/migrate_to_package.py --package $pkg

    # Test the package
    cd packages/$pkg
    poetry install
    poetry run pytest
    cd ../..
done
```

### 2. Dependency Validation
```bash
#!/bin/bash
# validate_deps.sh
cd /home/cnross/code/fxml4/fxml4-monorepo

# Check for circular dependencies
python3 tools/check_dependencies.py

# Validate all packages
for dir in packages/*/; do
    if [ -f "$dir/pyproject.toml" ]; then
        echo "Validating $(basename $dir)..."
        cd "$dir"
        poetry check
        cd ../..
    fi
done
```

### 3. Integration Test Runner
```bash
#!/bin/bash
# run_integration_tests.sh
cd /home/cnross/code/fxml4/fxml4-monorepo

# Install all packages
make install-all

# Run integration tests
pytest tests/integration -v

# Run package tests
make test-all
```

## Post-Migration Tasks

### 1. Update CI/CD
- Configure GitHub Actions for monorepo
- Set up package-specific test runs
- Implement automated dependency checking

### 2. Documentation
- Update API documentation
- Create package-specific READMEs
- Update developer guides

### 3. Deployment
- Update Docker configurations
- Create Kubernetes manifests
- Configure package versioning

### 4. Monitoring
- Set up package metrics
- Implement health checks
- Create dependency dashboards

## Success Metrics

1. **Zero Circular Dependencies**: Verified by automated tools
2. **100% Test Coverage**: For all migrated packages
3. **Build Time**: < 5 minutes for full monorepo
4. **Package Independence**: Each package can be built/tested separately
5. **Documentation**: Complete for all packages

## Timeline Summary

- **Week 1**: Data processing migration
- **Week 2**: Wave analysis migration
- **Week 3**: API gateway migration
- **Week 4**: Risk management extraction
- **Week 5**: Web dashboard migration
- **Week 6**: Worker services migration
- **Week 7**: Integration and testing
- **Week 8**: Documentation and deployment

## Next Immediate Steps

1. **Start Phase 1**: Run data-processor migration
2. **Set up CI/CD**: Configure automated testing
3. **Create tracking**: Set up project board for migration tasks
4. **Daily standup**: Track progress and blockers
5. **Weekly review**: Assess architecture decisions

This guide provides a clear, actionable path to complete the monorepo migration while maintaining system stability and preventing circular dependencies.
