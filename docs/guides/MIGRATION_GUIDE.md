# FXML4 Migration Guide

This guide helps you migrate from the legacy FXML4 structure to the new monorepo organization.

## Overview of Changes

The FXML4 project has been restructured from a monolithic codebase into a modern Python monorepo with:
- Independent packages with clear boundaries
- Modern dependency management with Poetry
- Consistent testing and tooling
- Better separation of concerns

## Directory Mapping

### Old Structure → New Structure

| Old Path | New Path | Description |
|----------|----------|-------------|
| `fxml4/utils/*` | `fxml4-monorepo/packages/core/src/fxml4_core/` | Core utilities |
| `fxml4/config.py` | `fxml4-monorepo/packages/core/src/fxml4_core/config.py` | Configuration |
| `fxml4/ml/*` | `fxml4-monorepo/packages/ml-models/src/fxml4_ml/` | ML models |
| `fxml4/strategy/*` | `fxml4-monorepo/packages/signal-generator/src/fxml4_signals/` | Trading strategies |
| `fxml4/backtesting/*` | `fxml4-monorepo/packages/backtesting/src/fxml4_backtesting/` | Backtesting |
| `fxml4/llm_integration/*` | `fxml4-monorepo/packages/llm-analyzer/src/fxml4_llm/` | LLM integration |
| `fxml4/api/*` | `fxml4-monorepo/packages/web-ui/src/fxml4_web/api/` | REST API |
| `fxml4/ui/*` | `fxml4-monorepo/packages/web-ui/src/fxml4_web/ui/` | Web UI |
| `scripts/*` | `fxml4-monorepo/scripts/` | Utility scripts |
| `tests/*` | `fxml4-monorepo/packages/*/tests/` | Tests (per package) |

## Import Changes

### Before (Old Structure)
```python
from fxml4.utils.logging import get_logger
from fxml4.ml.models import MLModel
from fxml4.strategy.signals import SignalGenerator
from fxml4.config import Config
```

### After (New Structure)
```python
from fxml4_core.logging import get_logger
from fxml4_ml.models import MLModel
from fxml4_signals.generators import SignalGenerator
from fxml4_core.config import BaseConfig
```

## Step-by-Step Migration

### 1. Set Up New Environment

```bash
# Navigate to monorepo
cd fxml4-monorepo

# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install all dependencies
make install-all
```

### 2. Migrate Your Code

#### Option A: Use Migration Script
```bash
# Run migration script
python scripts/migrate_legacy.py --source ../fxml4 --update-imports

# Review migration log
cat migration_log.json
```

#### Option B: Manual Migration
1. Copy your module to the appropriate package
2. Update imports to use new namespace
3. Add tests to the package's test directory
4. Update package dependencies in `pyproject.toml`

### 3. Update Configuration

#### Old Configuration
```python
# config/default.yaml
database:
  host: localhost
  port: 5432
```

#### New Configuration
```python
# Using environment variables with Pydantic
from fxml4_core.config import BaseConfig

class MyConfig(BaseConfig):
    database_url: str

# Set via environment
FXML4_DATABASE_URL=postgresql://localhost:5432/fxml4
```

### 4. Update Tests

Tests are now co-located with their packages:

```bash
# Old location
tests/test_ml_models.py

# New location
fxml4-monorepo/packages/ml-models/tests/test_models.py
```

### 5. Update Docker Configuration

#### Old Docker Compose
```yaml
services:
  app:
    build: .
    volumes:
      - ./fxml4:/app/fxml4
```

#### New Docker Compose
```yaml
services:
  trade-manager:
    build:
      context: ../../
      dockerfile: apps/trading-system/docker/Dockerfile.service
      args:
        SERVICE: trade-manager
```

## Common Issues and Solutions

### Issue 1: Import Errors
**Problem**: `ModuleNotFoundError: No module named 'fxml4.utils'`

**Solution**: Update to new namespace:
```python
# Change from
from fxml4.utils import logger

# To
from fxml4_core.logging import logger
```

### Issue 2: Missing Dependencies
**Problem**: Package dependencies not found

**Solution**: Add to package's `pyproject.toml`:
```toml
[tool.poetry.dependencies]
fxml4-core = { path = "../core", develop = true }
```

### Issue 3: Test Discovery
**Problem**: Tests not found by pytest

**Solution**: Ensure `__init__.py` exists in test directories and run from package root:
```bash
cd packages/my-package
poetry run pytest
```

### Issue 4: Configuration Loading
**Problem**: Old YAML configs not loading

**Solution**: Migrate to Pydantic-based configuration:
```python
from fxml4_core.config import BaseConfig

class ServiceConfig(BaseConfig):
    service_name: str = "my-service"
    port: int = 8000
```

## Development Workflow

### Working on a Package
```bash
# Navigate to package
cd fxml4-monorepo/packages/my-package

# Install in development mode
poetry install

# Run tests
poetry run pytest

# Add dependency
poetry add some-package
```

### Creating New Features
1. Determine which package the feature belongs to
2. Create feature branch
3. Implement with tests
4. Update package version in `pyproject.toml`
5. Submit PR

### Building and Publishing
```bash
# Build package
cd packages/my-package
poetry build

# Publish to private PyPI (if configured)
poetry publish -r private
```

## Deployment Changes

### Old Deployment
- Single application deployment
- All services in one container
- Shared dependencies

### New Deployment
- Service-based deployment
- Each service in its own container
- Independent scaling
- Service mesh ready

## Best Practices

1. **Keep Packages Small**: Each package should have a single, clear purpose
2. **Explicit Dependencies**: Always declare dependencies in `pyproject.toml`
3. **Version Everything**: Use semantic versioning for packages
4. **Test Isolation**: Tests should not depend on other packages' internals
5. **Documentation**: Each package needs its own README

## Getting Help

- Check the [Monorepo Structure Guide](./fxml4-monorepo/docs/MONOREPO_STRUCTURE.md)
- Review package-specific READMEs
- Look at existing packages for examples
- Check the troubleshooting section above

## Rollback Plan

If you need to work with the old structure temporarily:

1. The legacy code is preserved in `fxml4-monorepo/legacy/`
2. Old scripts are in `archive/experiment-scripts/`
3. Git history is preserved for all files

Remember: The goal is to fully migrate to the new structure. The legacy code is only kept for reference during the transition period.
