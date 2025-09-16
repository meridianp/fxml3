# FXML4 Monorepo Structure Guide

## Overview

The FXML4 project has been restructured as a modern Python monorepo following current best practices. This guide explains the new structure and how to work with it.

## Directory Structure

```
fxml4-monorepo/
├── packages/               # Independent, publishable packages
│   ├── core/              # Shared utilities and base classes
│   ├── data-collector/    # Market data collection service
│   ├── ml-models/         # Machine learning models and training
│   ├── signal-generator/  # Trading signal generation
│   ├── llm-analyzer/      # LLM integration for analysis
│   ├── entry-manager/     # Trade entry management
│   ├── trade-manager/     # Position and risk management
│   ├── backtesting/       # Backtesting framework
│   └── web-ui/           # Web interface and API
│
├── apps/                  # Deployable applications
│   ├── trading-system/    # Main trading application
│   └── backtest-runner/   # Standalone backtesting app
│
├── libs/                  # Internal shared libraries
│   ├── broker-adapters/   # Broker integrations (IB, FXCM, etc.)
│   ├── database/         # Database schemas and utilities
│   └── messaging/        # RabbitMQ messaging utilities
│
├── infrastructure/        # Infrastructure as Code
│   ├── docker/           # Docker configurations
│   ├── kubernetes/       # K8s manifests
│   └── terraform/        # Cloud infrastructure
│
├── docs/                 # Documentation
├── scripts/              # Development and utility scripts
├── tools/                # Build and development tools
└── legacy/               # Legacy code (temporary)
```

## Package Structure

Each package follows a consistent structure:

```
packages/package-name/
├── src/
│   └── fxml4_package_name/
│       ├── __init__.py
│       └── ...modules...
├── tests/
│   ├── conftest.py
│   └── test_*.py
├── pyproject.toml
└── README.md
```

## Key Improvements

### 1. **Modularity**
- Each package is independently versioned and deployable
- Clear separation of concerns
- Explicit dependencies between packages

### 2. **Namespace Packages**
- All packages use the `fxml4_*` namespace
- Prevents naming conflicts
- Easy to identify project packages

### 3. **Dependency Management**
- Poetry for modern dependency management
- Lock files ensure reproducible builds
- Development dependencies separated

### 4. **Testing**
- Unit tests co-located with packages
- Integration tests in the apps directory
- Consistent test structure

### 5. **Development Workflow**
- Makefile for common commands
- Pre-commit hooks for code quality
- Consistent tooling across packages

## Working with the Monorepo

### Installing Dependencies

```bash
# Install all dependencies
make install-all

# Or using Poetry directly
poetry install
```

### Running Tests

```bash
# Run all tests
make test-all

# Test specific package
cd packages/core && poetry run pytest

# Run with coverage
poetry run pytest --cov=fxml4_core
```

### Building Packages

```bash
# Build all packages
make build-all

# Build specific package
cd packages/core && poetry build
```

### Adding New Dependencies

```bash
# Add to specific package
cd packages/trade-manager
poetry add some-package

# Add dev dependency
poetry add --dev pytest-mock
```

### Creating New Packages

1. Create package structure:
```bash
mkdir -p packages/new-package/{src/fxml4_new_package,tests}
```

2. Create `pyproject.toml`:
```toml
[tool.poetry]
name = "fxml4-new-package"
version = "0.1.0"
packages = [{include = "fxml4_new_package", from = "src"}]

[tool.poetry.dependencies]
python = "^3.8"
fxml4-core = {path = "../core", develop = true}
```

3. Add package code and tests

## Migration from Legacy Structure

### Import Changes

Old imports:
```python
from fxml4.utils import logger
from fxml4.ml.models import MLModel
```

New imports:
```python
from fxml4_core.logging import logger
from fxml4_ml.models import MLModel
```

### Path Changes

| Old Path | New Path |
|----------|----------|
| `fxml4/utils/*` | `packages/core/src/fxml4_core/*` |
| `fxml4/ml/*` | `packages/ml-models/src/fxml4_ml/*` |
| `fxml4/strategy/*` | `packages/signal-generator/src/fxml4_signals/*` |
| `fxml4/api/*` | `packages/web-ui/src/fxml4_web/api/*` |

### Using the Migration Script

```bash
# Dry run to see what would be migrated
python scripts/migrate_legacy.py --dry-run

# Perform migration
python scripts/migrate_legacy.py --update-imports

# Migrate from specific source
python scripts/migrate_legacy.py --source ../old-fxml4
```

## Development Best Practices

### 1. **Package Independence**
- Packages should be loosely coupled
- Use interfaces/protocols for dependencies
- Avoid circular dependencies

### 2. **Versioning**
- Follow semantic versioning
- Update version in `pyproject.toml`
- Tag releases with `package-name-v1.2.3`

### 3. **Documentation**
- Each package must have a README
- Document public APIs
- Include usage examples

### 4. **Testing**
- Minimum 80% test coverage
- Test public interfaces thoroughly
- Use mocks for external dependencies

### 5. **Code Quality**
- Run pre-commit hooks
- Follow PEP 8 and project conventions
- Type hints for all public functions

## Deployment

### Docker Images

Each service can be built as a Docker image:

```bash
# Build specific service
docker build -f apps/trading-system/docker/Dockerfile.service \
  --build-arg SERVICE=trade-manager \
  -t fxml4/trade-manager:latest .
```

### Docker Compose

For local development:

```bash
cd apps/trading-system
docker-compose up -d
```

### Kubernetes

Deploy to K8s:

```bash
kubectl apply -f infrastructure/kubernetes/
```

## CI/CD

The monorepo supports several CI/CD patterns:

1. **Affected Testing**: Only test packages that changed
2. **Independent Releases**: Each package can be released separately
3. **Coordinated Releases**: Release multiple packages together

## Troubleshooting

### Common Issues

1. **Import Errors**
   - Ensure package is installed: `poetry install`
   - Check namespace: use `fxml4_*` not `fxml4.*`

2. **Dependency Conflicts**
   - Update lock file: `poetry lock --no-update`
   - Check version constraints in `pyproject.toml`

3. **Test Discovery**
   - Ensure `__init__.py` in test directories
   - Use `pytest` not `python -m unittest`

## Next Steps

1. Complete migration of remaining components
2. Set up CI/CD pipelines
3. Create package documentation
4. Deploy to staging environment
5. Performance optimization

## Resources

- [Poetry Documentation](https://python-poetry.org/docs/)
- [Python Packaging Guide](https://packaging.python.org/)
- [Monorepo Best Practices](https://monorepo.tools/)
- [Semantic Versioning](https://semver.org/)