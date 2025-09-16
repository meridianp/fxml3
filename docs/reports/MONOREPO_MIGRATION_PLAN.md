# FXML4 Monorepo Migration Plan

## Executive Summary

This document outlines the complete migration plan for restructuring FXML4 from a dual architecture (traditional + partial monorepo) to a fully integrated monorepo structure with proper dependency management and elimination of circular dependencies.

## Current State Analysis

### 1. Dual Architecture Issues
- **Traditional structure** in `/fxml4/` directory
- **Partial monorepo** in `/fxml4-monorepo/` with incomplete migration
- **Legacy code** preserved but not properly integrated
- **Circular dependency risks** between modules

### 2. Completed Components
- ✅ `fxml4-core`: Shared utilities and configuration
- ✅ `fxml4-data-collector`: Market data collection
- ✅ `fxml4-trade-manager`: Position and risk management
- ✅ `fxml4-ml-models`: Machine learning models
- ✅ `fxml4-signal-generator`: Signal generation
- ✅ `fxml4-llm-analyzer`: LLM integration

### 3. Pending Migration
- ❌ API and web interface components
- ❌ Backtesting framework (partially migrated)
- ❌ Data engineering pipeline
- ❌ Feature engineering
- ❌ Strategy modules
- ❌ Visualization tools
- ❌ Worker services
- ❌ Wave analysis components

## Migration Strategy

### Phase 1: Architecture Design (Immediate)

#### 1.1 Final Package Structure
```
fxml4-monorepo/packages/
├── core/                    # ✅ Base utilities, config, logging
├── data-collector/          # ✅ Data ingestion services
├── data-processor/          # 🆕 Feature engineering, preprocessing
├── ml-models/               # ✅ ML training and inference
├── signal-generator/        # ✅ Trading signals
├── llm-analyzer/           # ✅ LLM integration
├── wave-analyzer/          # 🆕 Elliott Wave analysis
├── trade-manager/          # ✅ Position management
├── backtesting/            # 🔄 Event-driven backtesting
├── risk-manager/           # 🆕 Risk management service
├── api-gateway/            # 🆕 FastAPI backend
├── web-dashboard/          # 🆕 Streamlit frontend
└── worker-services/        # 🆕 Background workers
```

#### 1.2 Dependency Hierarchy
```
Level 1: core (no dependencies)
Level 2: data-collector, wave-analyzer (depend on core)
Level 3: data-processor, ml-models (depend on L2)
Level 4: signal-generator, risk-manager (depend on L3)
Level 5: trade-manager, backtesting (depend on L4)
Level 6: api-gateway, worker-services (depend on L5)
Level 7: web-dashboard (depends on api-gateway)
```

### Phase 2: Circular Dependency Resolution

#### 2.1 Identified Circular Dependencies
1. **API ↔ Trade Manager**: API imports trade manager, which imports API schemas
2. **Backtesting ↔ Strategy**: Mutual imports between strategy and backtesting
3. **Features ↔ ML Models**: Feature engineering imports models for validation

#### 2.2 Resolution Approach
1. **Use Interfaces**: Define protocols/interfaces in core package
2. **Dependency Injection**: Pass dependencies rather than importing
3. **Event-Based Communication**: Use message queue for loose coupling
4. **Shared Types**: Move shared types to core package

### Phase 3: Implementation Plan

#### 3.1 Week 1: Core Infrastructure
- [ ] Update core package with shared interfaces
- [ ] Create dependency injection framework
- [ ] Set up event bus for inter-package communication
- [ ] Define standard protocols for all services

#### 3.2 Week 2: Data Pipeline Migration
- [ ] Create `data-processor` package
- [ ] Migrate feature engineering from `/fxml4/features/`
- [ ] Migrate data engineering components
- [ ] Set up proper data flow interfaces

#### 3.3 Week 3: Analysis Components
- [ ] Create `wave-analyzer` package
- [ ] Migrate Elliott Wave analysis
- [ ] Create `risk-manager` package
- [ ] Separate risk logic from trade manager

#### 3.4 Week 4: API and UI Migration
- [ ] Create `api-gateway` package
- [ ] Migrate API routes and middleware
- [ ] Create `web-dashboard` package
- [ ] Migrate Streamlit components

#### 3.5 Week 5: Worker Services
- [ ] Create `worker-services` package
- [ ] Migrate background tasks
- [ ] Set up RabbitMQ integration
- [ ] Implement service orchestration

#### 3.6 Week 6: Testing and Validation
- [ ] Integration tests across packages
- [ ] Performance benchmarking
- [ ] Documentation updates
- [ ] Final cleanup

## Implementation Details

### 1. Shared Interfaces (core package)

```python
# fxml4_core/interfaces.py
from abc import ABC, abstractmethod
from typing import Protocol, Dict, List, Optional
from datetime import datetime

class DataProvider(Protocol):
    """Interface for data providers"""
    def get_market_data(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        ...

class SignalGenerator(Protocol):
    """Interface for signal generators"""
    def generate_signal(self, data: pd.DataFrame) -> Dict[str, float]:
        ...

class RiskManager(Protocol):
    """Interface for risk management"""
    def calculate_position_size(self, signal: Dict, portfolio: Portfolio) -> float:
        ...

class TradeExecutor(Protocol):
    """Interface for trade execution"""
    def execute_order(self, order: Order) -> ExecutionResult:
        ...
```

### 2. Migration Scripts

#### 2.1 Import Updater
```python
# scripts/update_imports.py
import ast
import os
from pathlib import Path

IMPORT_MAPPINGS = {
    'fxml4.utils': 'fxml4_core',
    'fxml4.ml': 'fxml4_ml',
    'fxml4.strategy': 'fxml4_signals',
    'fxml4.api': 'fxml4_api',
    # ... more mappings
}

def update_imports(file_path: Path):
    """Update imports in a Python file"""
    # Implementation to update imports
    pass
```

#### 2.2 Circular Dependency Validator
```python
# scripts/validate_dependencies.py
def validate_no_circular_deps():
    """Validate no circular dependencies exist"""
    # Run after each migration step
    pass
```

### 3. Package Templates

#### 3.1 Standard Package Structure
```
packages/new-package/
├── src/
│   └── fxml4_new_package/
│       ├── __init__.py
│       ├── interfaces.py      # Package interfaces
│       ├── models.py          # Domain models
│       ├── services.py        # Business logic
│       └── adapters.py        # External adapters
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
├── pyproject.toml
├── README.md
└── CHANGELOG.md
```

#### 3.2 Standard pyproject.toml
```toml
[tool.poetry]
name = "fxml4-new-package"
version = "0.1.0"
description = "Description of package"
authors = ["FXML4 Team"]
packages = [{include = "fxml4_new_package", from = "src"}]

[tool.poetry.dependencies]
python = "^3.8"
fxml4-core = {path = "../core", develop = true}

[tool.poetry.dev-dependencies]
pytest = "^7.0"
pytest-cov = "^4.0"
pytest-asyncio = "^0.21"
black = "^23.0"
mypy = "^1.0"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]

[tool.coverage.run]
source = ["src"]
omit = ["*/tests/*", "*/__init__.py"]

[tool.mypy]
python_version = "3.8"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
```

### 4. Migration Tools

#### 4.1 Compatibility Layer
```python
# fxml4-monorepo/legacy-compat/bridge.py
"""
Temporary compatibility layer for gradual migration
"""
import sys
from importlib import import_module

class LegacyImportBridge:
    """Redirects old imports to new packages"""

    MAPPINGS = {
        'fxml4.utils': 'fxml4_core',
        'fxml4.ml.models': 'fxml4_ml.models',
        # ... more mappings
    }

    def find_module(self, fullname, path=None):
        if fullname in self.MAPPINGS:
            return self
        return None

    def load_module(self, fullname):
        new_module_name = self.MAPPINGS[fullname]
        return import_module(new_module_name)

# Install the import hook
sys.meta_path.insert(0, LegacyImportBridge())
```

## Success Metrics

1. **Zero Circular Dependencies**: Validated by automated tools
2. **100% Test Coverage**: For migrated components
3. **Clean Package Boundaries**: Each package has clear responsibilities
4. **Performance**: No degradation from current system
5. **Developer Experience**: Simplified development workflow

## Risk Mitigation

1. **Gradual Migration**: Move one component at a time
2. **Compatibility Layer**: Support old imports temporarily
3. **Automated Testing**: Run tests after each change
4. **Rollback Plan**: Git branches for each phase
5. **Documentation**: Update docs with each migration

## Timeline

- **Week 1-2**: Core infrastructure and tooling
- **Week 3-4**: Data pipeline and analysis components
- **Week 5-6**: API, UI, and worker services
- **Week 7**: Integration testing and optimization
- **Week 8**: Documentation and deployment

## Next Steps

1. Review and approve this plan
2. Set up migration tooling
3. Begin Phase 1 implementation
4. Daily progress updates
5. Weekly architecture reviews

## Appendix: Command Reference

```bash
# Validate no circular dependencies
make validate-deps

# Run migration for a package
python scripts/migrate_package.py --package ml --target ml-models

# Update all imports
python scripts/update_imports.py --dry-run
python scripts/update_imports.py --apply

# Generate dependency graph
python scripts/generate_dep_graph.py > deps.dot
dot -Tpng deps.dot -o deps.png

# Run integration tests
make test-integration
```

This migration plan provides a clear path forward to complete the monorepo transition while maintaining system stability and improving architecture.
