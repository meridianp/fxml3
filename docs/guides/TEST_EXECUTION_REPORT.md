# FXML4 Test Suite Execution Report

Generated: 2025-06-28 21:03:20

## Executive Summary


### Unit Tests (Fast)
```
collecting ... collected 167 items / 1 error
```

### API Tests
```
  /home/cnross/code/fxml4/fxml4/api/schemas/api_models.py:57: PydanticDeprecatedSince20: Pydantic V1 style `@validator` validators are deprecated. You should migrate to Pydantic V2 style `@field_validator` validators, see the migration guide for more details. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.11/migration/
```

### Security Tests
```
  /home/cnross/code/fxml4/fxml4/api/schemas/api_models.py:57: PydanticDeprecatedSince20: Pydantic V1 style `@validator` validators are deprecated. You should migrate to Pydantic V2 style `@field_validator` validators, see the migration guide for more details. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.11/migration/
```

### Config Tests
```
  /home/cnross/code/fxml4/fxml4/api/schemas/api_models.py:57: PydanticDeprecatedSince20: Pydantic V1 style `@validator` validators are deprecated. You should migrate to Pydantic V2 style `@field_validator` validators, see the migration guide for more details. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.11/migration/
```

### Data Engineering Tests
```
  /home/cnross/code/fxml4/fxml4/api/schemas/api_models.py:57: PydanticDeprecatedSince20: Pydantic V1 style `@validator` validators are deprecated. You should migrate to Pydantic V2 style `@field_validator` validators, see the migration guide for more details. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.11/migration/
```

## Recommendations

1. **Environment Setup Required**: Tests need a proper Python environment with all dependencies installed
2. **Database Connection**: Many tests require database connections (TimescaleDB/PostgreSQL)
3. **External Services**: Some tests need RabbitMQ, Redis, and other services running
4. **Missing Dependencies**: Install all requirements.txt dependencies for full test execution

## Next Steps

1. Set up Docker services: `docker-compose up -d timescaledb redis rabbitmq`
2. Install all dependencies: `pip install -r requirements.txt`
3. Run specific test categories to isolate issues
4. Fix import errors and missing dependencies
