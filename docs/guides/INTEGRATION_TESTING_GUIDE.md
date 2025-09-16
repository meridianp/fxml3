# Integration Testing Guide for FIX Broker Abstraction

## Overview

This guide explains how to run integration tests for the FIX broker abstraction system, which now includes 3 working adapters: IB, FXCM, and Manual.

## Quick Start

### 1. Prerequisites

```bash
# Ensure RabbitMQ is running (optional but recommended)
docker-compose up -d rabbitmq

# Install test dependencies
pip install pytest pytest-asyncio
```

### 2. Validate Architecture

First, validate that all components are properly implemented:

```bash
python scripts/validate_architecture.py
```

This checks:
- Core infrastructure components
- Broker adapter implementations
- API integration
- Configuration files
- Test scripts

### 3. Run Integration Tests

```bash
# Run all integration tests
python scripts/test_integration.py

# Run specific test scenarios
python scripts/test_integration.py --scenario routing
python scripts/test_integration.py --scenario failover
python scripts/test_integration.py --scenario concurrent

# Include performance tests
python scripts/test_integration.py --performance
```

### 4. Test Multi-Adapter Routing

```bash
# Test routing logic with multiple adapters
python scripts/test_multi_adapter_routing.py
```

This tests:
- Size-based routing
- Symbol-based routing
- Failover scenarios
- Complex routing rules
- Load distribution

## Test Scenarios

### End-to-End Tests (`test_end_to_end.py`)

1. **Simple Order Flow**: Tests basic order submission and execution
2. **Manual Approval Flow**: Tests orders requiring human approval
3. **Multi-Broker Flow**: Tests orders going to different brokers
4. **Order Lifecycle**: Tracks complete order lifecycle with timestamps
5. **Error Handling**: Tests error scenarios and adapter recovery

### Multi-Adapter Tests (`test_multi_adapter_integration.py`)

1. **Adapter Initialization**: Verifies multiple adapters can initialize
2. **Order Routing**: Tests routing based on order characteristics
3. **Failover Routing**: Tests fallback when primary broker unavailable
4. **Concurrent Submission**: Tests parallel order submission
5. **Health Monitoring**: Monitors adapter health status

## Running Without RabbitMQ

The tests can run in mock mode without RabbitMQ:

```bash
python scripts/test_integration.py --no-rabbitmq
```

This uses in-memory message passing instead of actual message queues.

## Performance Testing

Run performance benchmarks:

```bash
# Standalone performance tests
pytest tests/integration/ -k performance -m slow -v

# Or as part of integration suite
python scripts/test_integration.py --performance
```

Metrics measured:
- Order submission throughput (orders/second)
- End-to-end latency (milliseconds)
- System capacity under load

## Debugging Failed Tests

1. **Check Adapter Registration**:
   ```python
   from fxml4.brokers.adapters.registry import BrokerRegistry
   print(BrokerRegistry.list_adapters())
   ```

2. **Enable Debug Logging**:
   ```python
   import logging
   logging.getLogger('fxml4').setLevel(logging.DEBUG)
   ```

3. **Test Individual Adapters**:
   ```bash
   python scripts/test_ib_adapter.py
   python scripts/test_manual_adapter.py
   python scripts/test_fxcm_adapter.py
   ```

## Expected Results

### Successful Test Run
```
=== Testing Size-Based Routing ===
  Small Order (10,000): Routed to ib ✓
  Medium Order (500,000): Routed to ib ✓
  Large Order (2,000,000): Routed to manual ✓

=== Testing Failover Routing ===
  Available brokers: ['ib', 'manual']
  Disconnected IB adapter
  Order routed to manual ✓ (failover worked)

ROUTING TEST SUMMARY
Total tests: 15
Passed: 15
Failed: 0
Success rate: 100.0%
```

### Performance Benchmarks
```
Performance metrics:
  - Orders submitted: 48/50
  - Duration: 2.34s
  - Throughput: 20.5 orders/sec
```

## Next Steps

### 1. Native FIX Adapter Research

Start researching FIX protocol libraries:

```bash
# Install candidate libraries
pip install quickfix simplefix

# Review implementation options
python scripts/research_fix_libraries.py
```

### 2. Risk Management Integration

Begin integrating risk checks:
- Pre-trade validation
- Position limits
- Exposure monitoring

### 3. Monitoring Dashboard

Create real-time monitoring:
- Adapter status dashboard
- Order flow visualization
- Performance metrics

### 4. Frontend UI

Build web interface for manual execution:
- React/Vue order approval UI
- WebSocket real-time updates
- Risk override interface

## Troubleshooting

### RabbitMQ Connection Issues
```bash
# Check RabbitMQ status
docker-compose ps rabbitmq

# View RabbitMQ logs
docker-compose logs rabbitmq

# Access RabbitMQ management UI
# http://localhost:15672 (guest/guest)
```

### Adapter Connection Failures
- IB: Ensure TWS/Gateway is not required (using mock mode)
- FXCM: Check Docker service if using bridge
- Manual: Always available (no external dependencies)

### Test Timeouts
Increase timeouts in test configuration:
```python
# In test files
@pytest.mark.timeout(60)  # 60 second timeout
```

## Summary

The integration testing framework validates that all components work together:

1. **Phase 3 Started**: Integration testing is now active
2. **3 Adapters Ready**: IB, Manual, and FXCM adapters operational
3. **Routing Works**: Multi-broker routing logic validated
4. **Performance Good**: System handles 20+ orders/second

Ready to proceed with:
- Native FIX adapter implementation
- Risk management integration
- Production deployment preparation
