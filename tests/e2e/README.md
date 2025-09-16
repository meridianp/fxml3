# E2E Testing Suite

## Overview

This directory contains end-to-end (E2E) tests that validate complete user workflows across the entire FXML4 system. All E2E tests run in Docker containers to accurately simulate the production environment.

## Test Coverage

### Authentication Flow (`test_auth_security_flow_e2e.py`)
Complete authentication lifecycle testing:
- User registration
- Login with JWT token generation
- Protected resource access
- Token refresh
- Concurrent sessions
- Logout and token invalidation
- Security audit trail verification
- Rate limiting
- Session isolation

### Multi-Broker Failover (`test_multi_broker_failover_e2e.py`)
Broker connectivity and failover scenarios:
- Primary broker connection
- Automatic failover to backup brokers
- Connection recovery
- Order routing during failover

### Compliance Audit Trail (`test_compliance_audit_trail_e2e.py`)
Regulatory compliance and audit logging:
- Trade audit trail generation
- Immutable event logging
- Regulatory report generation
- Data retention policies

## Running E2E Tests

### Quick Start

Run the complete E2E authentication test suite:

```bash
./scripts/run_e2e_auth_tests.sh run
```

### Available Commands

```bash
# Run all E2E tests
./scripts/run_e2e_auth_tests.sh run

# Start containers for manual testing/debugging
./scripts/run_e2e_auth_tests.sh debug

# View container logs
./scripts/run_e2e_auth_tests.sh logs [service-name]

# Check container status
./scripts/run_e2e_auth_tests.sh status

# Stop and clean up containers
./scripts/run_e2e_auth_tests.sh stop
```

### Manual Docker Compose Commands

```bash
# Start test environment
docker-compose -f docker-compose.test.yml up -d

# Run specific test
docker-compose -f docker-compose.test.yml run --rm test-runner \
    pytest tests/e2e/test_auth_security_flow_e2e.py::TestAuthenticationE2E::test_complete_authentication_flow -v

# View logs
docker-compose -f docker-compose.test.yml logs -f test-api

# Clean up
docker-compose -f docker-compose.test.yml down -v
```

## Test Architecture

### Container Setup

The E2E tests use a dedicated Docker Compose configuration (`docker-compose.test.yml`) with the following services:

1. **test-db**: PostgreSQL/TimescaleDB for data persistence
2. **test-redis**: Redis for caching and session management
3. **test-rabbitmq**: RabbitMQ for message queuing
4. **test-api**: The FXML4 API service
5. **test-runner**: Container that executes the test suite

### Network Architecture

All containers communicate over a dedicated Docker network (`fxml4_test_network`) with service discovery:

```
test-runner
    ↓
test-api (port 8000)
    ↓
├── test-db (port 5432)
├── test-redis (port 6379)
└── test-rabbitmq (port 5672)
```

### Test Execution Flow

1. **Environment Setup**: Docker Compose starts all required services
2. **Health Checks**: Wait for all services to be healthy
3. **Database Migration**: Initialize database schema
4. **Test Execution**: Run pytest test suite in test-runner container
5. **Result Collection**: Export test results and coverage reports
6. **Cleanup**: Tear down containers and volumes

## Writing New E2E Tests

### Test Structure

```python
class TestNewFeatureE2E:
    @pytest.fixture
    async def service_client(self):
        """Create client for service under test."""
        pass

    @pytest.mark.asyncio
    async def test_complete_workflow(self):
        """Test the complete feature workflow."""
        # 1. Setup test data
        # 2. Execute workflow steps
        # 3. Verify results across all services
        # 4. Check audit trails
        pass
```

### Best Practices

1. **Container Communication**: Always use service names (e.g., `test-api`, `test-db`) not `localhost`
2. **Health Checks**: Wait for services to be ready before starting tests
3. **Cleanup**: Ensure tests clean up after themselves
4. **Idempotency**: Tests should be runnable multiple times
5. **Isolation**: Each test should be independent
6. **Timeouts**: Set appropriate timeouts for container operations

### Environment Variables

Tests can be configured via environment variables:

- `API_BASE_URL`: API service URL (default: `http://test-api:8000`)
- `DATABASE_HOST`: Database hostname (default: `test-db`)
- `REDIS_HOST`: Redis hostname (default: `test-redis`)
- `RABBITMQ_HOST`: RabbitMQ hostname (default: `test-rabbitmq`)
- `PYTEST_TIMEOUT`: Test timeout in seconds (default: `300`)

## Debugging

### Accessing Services During Debug Mode

Start services in debug mode:
```bash
./scripts/run_e2e_auth_tests.sh debug
```

Then access:
- API: http://localhost:8002
- RabbitMQ Management: http://localhost:15673 (guest/guest)
- PostgreSQL: `psql -h localhost -p 5433 -U fxml4_test -d fxml4_test`
- Redis: `redis-cli -h localhost -p 6380`

### Common Issues

1. **Container startup failures**: Check logs with `docker-compose -f docker-compose.test.yml logs [service]`
2. **Port conflicts**: Ensure ports 8002, 5433, 6380, 15673 are available
3. **Network issues**: Verify Docker network with `docker network ls`
4. **Volume permissions**: Ensure proper permissions on mounted volumes

## CI/CD Integration

### GitHub Actions

```yaml
- name: Run E2E Tests
  run: |
    ./scripts/run_e2e_auth_tests.sh run
  timeout-minutes: 10

- name: Upload Test Results
  if: always()
  uses: actions/upload-artifact@v2
  with:
    name: e2e-test-results
    path: test-results/
```

### Jenkins

```groovy
stage('E2E Tests') {
    steps {
        sh './scripts/run_e2e_auth_tests.sh run'
    }
    post {
        always {
            junit 'test-results/*.xml'
        }
    }
}
```

## Test Metrics

The E2E test suite tracks:
- **Execution Time**: Total time for complete test run
- **Container Health**: Service availability and response times
- **Coverage**: Code paths exercised by E2E tests
- **Audit Completeness**: Percentage of events properly logged
- **Performance**: Response times across container boundaries

## Future Enhancements

- [ ] Add visual regression testing for UI components
- [ ] Implement contract testing between services
- [ ] Add performance benchmarking
- [ ] Create chaos engineering tests
- [ ] Add multi-region testing scenarios
