# FXML4 Comprehensive Testing Guide

## Table of Contents
1. [Overview](#overview)
2. [Test Architecture](#test-architecture)
3. [Running Tests](#running-tests)
4. [Writing Tests](#writing-tests)
5. [CI/CD Integration](#cicd-integration)
6. [Containerized Testing](#containerized-testing)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

## Overview

The FXML4 testing infrastructure provides comprehensive coverage across multiple test types:
- **Unit Tests**: Isolated component testing
- **Integration Tests**: Component interaction testing
- **E2E Tests**: Complete user workflow validation in containers
- **Security Tests**: Authentication, authorization, and vulnerability testing
- **Performance Tests**: Load testing and performance benchmarking

### Test Philosophy
- **Test-Driven Development (TDD)**: Write tests first, then implementation
- **Containerized E2E**: All E2E tests run in Docker containers mimicking production
- **Automated Pipeline**: All tests integrated into CI/CD pipeline
- **Coverage Goals**: Minimum 80% code coverage

## Test Architecture

### Directory Structure
```
tests/
├── unit/                 # Unit tests for individual components
├── integration/          # Integration tests for component interactions
├── e2e/                  # End-to-end tests in containers
├── security/             # Security-specific tests
├── performance/          # Performance and load tests
├── auth/                 # Authentication system tests
├── fixtures/             # Shared test fixtures
├── conftest.py          # Pytest configuration
└── TESTING_GUIDE.md     # This document
```

### Test Categories (Pytest Markers)
```python
@pytest.mark.unit          # Fast, isolated unit tests
@pytest.mark.integration   # Component integration tests
@pytest.mark.e2e          # End-to-end workflow tests
@pytest.mark.security     # Security tests
@pytest.mark.auth         # Authentication tests
@pytest.mark.performance  # Performance tests
@pytest.mark.slow         # Long-running tests
@pytest.mark.requires_ib  # Requires Interactive Brokers
@pytest.mark.requires_fxcm # Requires FXCM connection
```

## Running Tests

### Quick Start
```bash
# Install dependencies
make install

# Run all tests
make test

# Run specific test categories
make test-unit
make test-integration
make test-e2e
make test-security
make test-performance
```

### Using the Makefile
The Makefile provides convenient targets for all testing needs:

```bash
# Complete test pipeline
make ci-pipeline

# Quick tests only (unit + integration)
make ci-quick

# Containerized E2E tests
make test-docker

# Run with coverage
make coverage

# Check coverage threshold
make coverage-check

# Clean test artifacts
make test-clean
```

### Using the Integrated Pipeline Script
```bash
# Run complete pipeline
./scripts/run_integrated_test_pipeline.py

# Run specific test types
./scripts/run_integrated_test_pipeline.py unit integration

# Verbose output
./scripts/run_integrated_test_pipeline.py --verbose

# Parallel execution
./scripts/run_integrated_test_pipeline.py --parallel

# CI mode with strict checking
./scripts/run_integrated_test_pipeline.py --ci
```

### Manual Pytest Commands
```bash
# Run all tests
pytest tests/

# Run with specific marker
pytest -m "unit and not slow"

# Run specific test file
pytest tests/e2e/test_auth_security_flow_e2e.py

# Run with coverage
pytest --cov=fxml4 --cov-report=html

# Verbose output with traceback
pytest -vvs --tb=long

# Run in parallel
pytest -n auto

# Stop on first failure
pytest -x
```

## Writing Tests

### Test Structure Template
```python
"""Test module description."""

import pytest
from unittest.mock import Mock, patch

class TestFeatureName:
    """Test suite for FeatureName."""

    @pytest.fixture
    def setup_data(self):
        """Prepare test data."""
        return {"key": "value"}

    @pytest.mark.unit
    def test_component_behavior(self, setup_data):
        """Test specific component behavior."""
        # Arrange
        expected = "expected_result"

        # Act
        result = function_under_test(setup_data)

        # Assert
        assert result == expected

    @pytest.mark.asyncio
    async def test_async_operation(self):
        """Test asynchronous operation."""
        result = await async_function()
        assert result is not None
```

### E2E Test Template
```python
class TestE2EWorkflow:
    """End-to-end workflow test."""

    @pytest.fixture(scope="class")
    async def docker_services(self):
        """Ensure Docker services are running."""
        # Wait for services
        await wait_for_healthy_services()

    @pytest.mark.e2e
    async def test_complete_workflow(self, docker_services, http_session):
        """Test complete user workflow."""
        # Step 1: Initial action
        response = await http_session.post("/api/endpoint", json=data)
        assert response.status == 200

        # Step 2: Verify in database
        db_record = await verify_in_database()
        assert db_record is not None

        # Step 3: Check side effects
        cache_value = await check_redis_cache()
        assert cache_value == expected
```

### Mocking Best Practices
```python
# Mock external dependencies
@patch('fxml4.brokers.ib_adapter.IBClient')
def test_with_mock_broker(mock_client):
    mock_client.return_value.connect.return_value = True
    # Test code

# Use fixtures for common mocks
@pytest.fixture
def mock_database():
    with patch('fxml4.database.get_connection') as mock:
        mock.return_value = Mock()
        yield mock
```

## CI/CD Integration

### GitHub Actions
The pipeline is configured in `.github/workflows/ci-cd-pipeline.yml`:
- Automated on push to main/develop
- Runs all test types in sequence
- Containerized E2E tests included
- Coverage reporting to Codecov

### Jenkins
Use the provided `Jenkinsfile`:
- Parallel execution of independent tests
- Docker image building for E2E
- Automatic cleanup
- Slack/email notifications

### GitLab CI
```yaml
# .gitlab-ci.yml example
test:
  stage: test
  script:
    - make ci-pipeline
  artifacts:
    reports:
      junit: test-results/*.xml
```

## Containerized Testing

### Docker Compose Test Environment
The `docker-compose.test.yml` provides:
- Isolated test database (TimescaleDB)
- Test Redis instance
- Test RabbitMQ instance
- API service container
- Test runner container

### Running Containerized Tests
```bash
# Start test environment
make docker-test-up

# Run E2E tests
make test-e2e

# View logs
docker-compose -f docker-compose.test.yml logs -f

# Clean up
make docker-test-down
```

### Container Health Checks
All services include health checks:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 10s
  timeout: 5s
  retries: 5
```

## Best Practices

### 1. Test Isolation
- Each test should be independent
- Use fixtures for setup/teardown
- Clean up after tests

### 2. Test Naming
- Descriptive test names: `test_user_can_login_with_valid_credentials`
- Group related tests in classes
- Use docstrings for complex tests

### 3. Assertions
- One logical assertion per test
- Use specific assertions: `assert result == expected` not `assert result`
- Include assertion messages for clarity

### 4. Performance
- Mark slow tests: `@pytest.mark.slow`
- Use parallel execution for independent tests
- Mock external dependencies in unit tests

### 5. Data Management
- Use factories for test data generation
- Avoid hardcoded test data
- Use fixtures for database setup

### 6. Container Testing
- Always use service names, not localhost
- Wait for services to be healthy
- Clean up containers after tests

## Troubleshooting

### Common Issues and Solutions

#### 1. Import Errors
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Install in development mode
pip install -e .
```

#### 2. Docker Connection Issues
```bash
# Check Docker daemon
docker ps

# Reset Docker environment
docker-compose -f docker-compose.test.yml down -v
docker system prune -f
```

#### 3. Database Connection Failures
```bash
# Check database is running
docker-compose -f docker-compose.test.yml ps test-db

# Check migrations
docker-compose -f docker-compose.test.yml exec test-db psql -U fxml4_test
```

#### 4. Flaky Tests
- Add proper waits for async operations
- Increase timeouts for container operations
- Use retry logic for network operations

#### 5. Coverage Issues
```bash
# Generate detailed coverage report
pytest --cov=fxml4 --cov-report=html --cov-report=term-missing

# View uncovered lines
open test-results/coverage-html/index.html
```

### Debug Mode
```bash
# Run tests with debugging
pytest -vvs --pdb

# Run specific test with full output
pytest tests/path/to/test.py::TestClass::test_method -vvs

# Keep containers running for debugging
./scripts/run_e2e_auth_tests.sh debug
```

### Logs and Reports
- Test results: `test-results/*.xml`
- Coverage reports: `test-results/coverage-html/`
- Container logs: `docker-compose -f docker-compose.test.yml logs`
- Pipeline reports: `test-results/pipeline-report.json`

## Test Metrics and Goals

### Coverage Targets
- Overall: ≥ 80%
- Critical paths: ≥ 90%
- New code: ≥ 85%

### Performance Targets
- Unit tests: < 10 seconds total
- Integration tests: < 30 seconds total
- E2E tests: < 5 minutes total
- Full pipeline: < 15 minutes

### Quality Metrics
- Zero flaky tests
- All tests pass in CI/CD
- No skipped tests without justification
- Documentation for complex tests

## Contributing

When adding new features:
1. Write tests first (TDD)
2. Ensure tests pass locally
3. Add appropriate pytest markers
4. Update this guide if needed
5. Verify CI/CD pipeline passes

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [GitHub Actions Testing](https://docs.github.com/en/actions/automating-builds-and-tests)
- [Jenkins Pipeline](https://www.jenkins.io/doc/book/pipeline/)
- [Test-Driven Development](https://en.wikipedia.org/wiki/Test-driven_development)
