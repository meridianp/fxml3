# Frontend-Backend Integration Testing Guide

## Overview

This guide describes the comprehensive frontend-backend integration testing framework for FXML4, which validates complete user journeys from the React frontend through the FXML4 API to backend services.

## Architecture

### Test Environment Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React/Next.js │    │   FXML4 API     │    │   TimescaleDB   │
│   Frontend      │◄──►│   (FastAPI)     │◄──►│   Database      │
│   (Port 3000)   │    │   (Port 8002)   │    │   (Port 5433)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         ▲                       ▲                       ▲
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Playwright    │    │   RabbitMQ      │    │   Redis Cache   │
│   Browser       │    │   Message Queue │    │   Session Store │
│   Automation    │    │   (Port 5673)   │    │   (Port 6380)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Test Flow

1. **Service Orchestration**: Docker Compose starts all services
2. **Health Checks**: Verify all services are ready
3. **Browser Automation**: Playwright drives user interactions
4. **API Validation**: Verify backend responses and state
5. **Database Verification**: Confirm data persistence
6. **Security Auditing**: Validate audit trail logging
7. **Cleanup**: Tear down test environment

## Test Categories

### 1. Complete Authentication Flow
- **Frontend**: User registration, login, logout forms
- **Backend**: JWT token generation, validation, refresh
- **Database**: User creation, session storage
- **Redis**: Session caching and cleanup
- **Security**: Audit trail logging

### 2. API Error Handling
- **Frontend**: Graceful error display
- **Backend**: Proper HTTP status codes
- **Network**: Timeout and retry handling
- **Validation**: Form and API validation errors

### 3. Real-time Communication
- **WebSocket**: Connection establishment and data flow
- **Frontend**: Real-time UI updates
- **Backend**: Live data streaming
- **Resilience**: Connection recovery

### 4. Security Integration
- **Authentication**: Multi-factor authentication flows
- **Authorization**: Role-based access control
- **Audit Trail**: Complete security event logging
- **Session Management**: Secure session handling

## Getting Started

### Prerequisites

1. **Docker & Docker Compose**: For containerized testing
2. **Node.js 18+**: For frontend development
3. **Python 3.12+**: For backend and test automation
4. **Playwright**: For browser automation

### Quick Start

```bash
# Run complete integration test suite
make test-integration-frontend

# Or run directly
./scripts/run_frontend_backend_integration_tests.sh run
```

### Development Workflow

```bash
# Start services for development
make test-integration-up

# Check service status
make test-integration-status

# Run tests against running services
python -m pytest tests/e2e/test_frontend_backend_integration_e2e.py -v

# Stop services
make test-integration-down
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BASE_URL` | `http://localhost:8002` | Backend API URL |
| `FRONTEND_BASE_URL` | `http://localhost:3000` | Frontend URL |
| `DATABASE_HOST` | `localhost` | Database host |
| `DATABASE_PORT` | `5433` | Database port |
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6380` | Redis port |
| `HEADLESS` | `true` | Run browser in headless mode |
| `SLOW_MO` | `0` | Slow down browser actions (ms) |

### Docker Compose Files

- **`docker-compose.integration.yml`**: Complete integration test environment
- **`docker-compose.test.yml`**: Backend-only testing environment

## Test Structure

### Test Classes

#### `FrontendBackendIntegrationTest`
Main test class containing all integration test scenarios.

**Key Methods:**
- `test_complete_frontend_backend_auth_flow()`: Full authentication flow
- `test_frontend_api_error_handling()`: Error handling scenarios
- `test_real_time_websocket_integration()`: WebSocket communication
- `test_trading_flow_integration()`: Trading functionality
- `test_security_audit_trail_integration()`: Security logging
- `test_logout_cleanup_integration()`: Session cleanup

### Test Fixtures

```python
@pytest.fixture(scope="class")
async def playwright():
    """Initialize Playwright for browser automation."""

@pytest.fixture(scope="class")
async def browser(playwright):
    """Launch browser for testing."""

@pytest.fixture(scope="class")
async def page(browser):
    """Create a new browser page."""

@pytest.fixture(scope="class")
async def api_session():
    """Create HTTP session for API validation."""

@pytest.fixture(scope="class")
async def db_connection():
    """Database connection for state validation."""
```

## Test Scenarios

### Authentication Flow Test

```python
async def test_complete_frontend_backend_auth_flow(self, page, api_session, db_connection):
    """
    Complete authentication flow validation:
    1. Navigate to registration page
    2. Fill and submit registration form
    3. Verify API call and database creation
    4. Test login flow
    5. Validate JWT token storage
    6. Verify session in Redis
    7. Check security audit events
    """
```

**Verification Points:**
- ✅ Frontend form interaction
- ✅ API request/response validation
- ✅ Database user creation
- ✅ JWT token generation and storage
- ✅ Redis session creation
- ✅ Security audit logging

### Error Handling Test

```python
async def test_frontend_api_error_handling(self, page, api_session):
    """
    Test frontend gracefully handles API errors:
    1. Invalid credentials
    2. Network timeouts
    3. Server errors
    4. Validation errors
    """
```

## Browser Automation

### Playwright Configuration

```python
# Launch browser with development-friendly settings
browser = await playwright.chromium.launch(
    headless=bool(os.getenv("HEADLESS", "true") == "true"),
    slow_mo=int(os.getenv("SLOW_MO", "0")),
)

# Enable request/response logging
page.on("request", lambda req: print(f"→ {req.method} {req.url}"))
page.on("response", lambda res: print(f"← {res.status} {res.url}"))
```

### Element Selection

Use `data-testid` attributes for reliable element selection:

```html
<!-- Frontend Components -->
<form data-testid="login-form">
  <input data-testid="email-input" type="email" />
  <input data-testid="password-input" type="password" />
  <button data-testid="login-button">Login</button>
</form>

<div data-testid="error-message">Error text</div>
<div data-testid="user-menu">User Menu</div>
```

```python
# Playwright Test Code
await page.fill('[data-testid="email-input"]', user_email)
await page.click('[data-testid="login-button"]')
await page.wait_for_selector('[data-testid="user-menu"]')
```

## Database Validation

### User Creation Verification

```python
# Verify user was created in database
user_record = await db_connection.fetchrow(
    "SELECT * FROM users WHERE username = $1",
    test_user["username"]
)
assert user_record is not None
assert user_record["email"] == test_user["email"]
```

### Security Audit Trail

```python
# Verify security events were logged
audit_records = await db_connection.fetch(
    """
    SELECT * FROM security_events 
    WHERE event_type = 'user_login' 
    AND username = $1
    ORDER BY created_at DESC
    LIMIT 1
    """,
    test_user["username"]
)
assert len(audit_records) > 0
```

## Session Management

### Redis Session Validation

```python
# Verify session exists in Redis
redis_keys = await redis_client.keys(f"session:*{username}*")
assert len(redis_keys) > 0

session_data = await redis_client.get(redis_keys[0])
session_info = json.loads(session_data)
assert session_info["username"] == username
```

### JWT Token Verification

```python
# Verify JWT token in browser storage
token = await page.evaluate("""
    () => localStorage.getItem('fxml4_auth_token') || 
          sessionStorage.getItem('fxml4_auth_token')
""")
assert token is not None
```

## CI/CD Integration

### GitHub Actions

The integration tests are automatically run in the CI/CD pipeline:

```yaml
# Frontend-Backend Integration Tests
frontend-backend-integration:
  runs-on: ubuntu-latest
  needs: [e2e-tests]
  steps:
    - name: Run Frontend-Backend Integration Tests
      run: |
        ./scripts/run_frontend_backend_integration_tests.sh run
      timeout-minutes: 20
```

### Make Targets

```bash
# Available make targets
make test-integration-frontend    # Run complete integration tests
make test-integration-up          # Start services only
make test-integration-down        # Stop services
make test-integration-status      # Check service status
make test-integration-clean       # Clean environment
```

## Debugging

### Development Mode

```bash
# Run with visible browser for debugging
export HEADLESS=false
export SLOW_MO=500
./scripts/run_frontend_backend_integration_tests.sh run
```

### Service Logs

```bash
# Check specific service logs
./scripts/run_frontend_backend_integration_tests.sh logs

# Or view individual service
docker-compose -f docker-compose.integration.yml logs frontend
docker-compose -f docker-compose.integration.yml logs integration-test-api
```

### Test Artifacts

Test results are saved to `integration-test-results/`:
- `integration-junit.xml`: JUnit test results
- `integration-test-report.md`: Comprehensive test report
- `playwright-trace/`: Browser interaction traces
- `screenshots/`: Screenshots on failure

## Best Practices

### 1. Test Data Management

```python
# Use unique identifiers for test isolation
self.unique_id = str(uuid4())[:8]
self.test_user = {
    "username": f"integration_user_{self.unique_id}",
    "email": f"integration_{self.unique_id}@fxml4test.com",
}
```

### 2. Service Health Checks

```python
# Always verify services are ready
for attempt in range(max_attempts):
    try:
        async with session.get(f"{API_BASE_URL}/health") as response:
            if response.status == 200:
                break
    except Exception:
        await asyncio.sleep(2)
```

### 3. Cleanup and Isolation

```python
# Use fixtures for proper setup/teardown
@pytest.fixture(autouse=True)
async def setup_services(self):
    # Health checks before tests
    await self._verify_services_ready()
    yield
    # Cleanup after tests
    await self._cleanup_test_data()
```

### 4. Error Handling

```python
# Graceful error handling with informative messages
try:
    await page.wait_for_selector('[data-testid="success-message"]', timeout=15000)
except Exception:
    # Check for error messages to provide context
    error_element = await page.query_selector('[data-testid="error-message"]')
    if error_element:
        error_text = await error_element.inner_text()
        pytest.fail(f"Test failed with error: {error_text}")
    raise
```

## Performance Considerations

- **Parallel Execution**: Tests run in isolated containers
- **Resource Limits**: Docker containers have defined CPU/memory limits
- **Timeout Settings**: Appropriate timeouts for different operations
- **Cleanup**: Automatic resource cleanup after tests

## Security Considerations

- **Test Credentials**: All test passwords marked with pragma allowlist
- **Network Isolation**: Tests run in isolated Docker networks
- **Data Cleanup**: Test data is automatically cleaned up
- **Audit Logging**: All test actions are logged for security validation

## Troubleshooting

### Common Issues

1. **Services Not Starting**
   ```bash
   # Check service health
   make test-integration-status
   
   # View logs
   ./scripts/run_frontend_backend_integration_tests.sh logs
   ```

2. **Browser Connection Issues**
   ```bash
   # Run in visible mode for debugging
   export HEADLESS=false
   make test-integration-frontend
   ```

3. **Database Connection Errors**
   ```bash
   # Verify database is ready
   docker-compose -f docker-compose.integration.yml ps
   ```

4. **Port Conflicts**
   ```bash
   # Check port usage
   netstat -tlnp | grep -E ':(3000|8002|5433|6380|5673)'
   ```

### Getting Help

- Check the test logs in `integration-test-results/`
- Review Docker container logs
- Verify all services show as "healthy" in status check
- Ensure no port conflicts with other running services

## Future Enhancements

1. **Cross-browser Testing**: Support for Firefox and Safari
2. **Mobile Testing**: Responsive design validation
3. **Performance Metrics**: Integration with performance monitoring
4. **Visual Regression**: Screenshot comparison testing
5. **API Contract Testing**: Schema validation and contract testing

---

This integration testing framework provides comprehensive validation of the complete FXML4 system, ensuring that all components work together seamlessly in a production-like environment.
