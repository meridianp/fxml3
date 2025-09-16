"""
FXML4 API Performance SLA Tests

TDD-style performance tests that validate API endpoints meet Phase 11 SLA requirements:
- /health: < 50ms (95th percentile)
- /data: < 500ms (95th percentile)
- /signals: < 2s (95th percentile)
- /backtest: < 5min (95th percentile)

These tests follow Test-Driven Development principles by defining performance
requirements as testable assertions that must pass.

Usage:
    pytest tests/test_api_performance_slas.py -v
    pytest tests/test_api_performance_slas.py::test_health_endpoint_sla -v
"""

import asyncio
import logging
import statistics
import time
from datetime import datetime, timedelta
from typing import List

import aiohttp
import pytest

# Use centralized event loop fixture
from tests.fixtures.event_loop_fixtures import event_loop

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test configuration
API_BASE_URL = "http://localhost:8001"
SLA_TARGETS = {
    "/health": 0.050,  # 50ms
    "/data": 0.500,  # 500ms
    "/signals": 2.000,  # 2s
    "/backtest": 300.000,  # 5min
}
TEST_ITERATIONS = 20  # Number of requests per SLA test


def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def api_session():
    """Create HTTP session for API testing"""
    timeout = aiohttp.ClientTimeout(total=600)  # 10min for backtest
    headers = {"Content-Type": "application/json", "User-Agent": "FXML4-SLA-Test/1.0"}

    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        yield session


@pytest.fixture(scope="session")
async def api_health_check(api_session):
    """Verify API is available before running performance tests"""
    try:
        async with api_session.get(f"{API_BASE_URL}/health") as response:
            assert (
                response.status == 200
            ), f"API health check failed with status {response.status}"
            logger.info("✅ API health check passed")
            return True
    except Exception as e:
        pytest.skip(f"API not available at {API_BASE_URL}: {e}")


def calculate_p95(response_times: List[float]) -> float:
    """Calculate 95th percentile response time"""
    if not response_times:
        return 0
    sorted_times = sorted(response_times)
    k = (len(sorted_times) - 1) * 0.95
    f = int(k)
    c = k - f
    if f == len(sorted_times) - 1:
        return sorted_times[f]
    return sorted_times[f] + c * (sorted_times[f + 1] - sorted_times[f])


async def measure_endpoint_performance(
    session: aiohttp.ClientSession,
    endpoint: str,
    method: str = "GET",
    payload: dict = None,
    iterations: int = TEST_ITERATIONS,
) -> List[float]:
    """
    Measure endpoint response times over multiple iterations

    Args:
        session: HTTP session
        endpoint: API endpoint to test
        method: HTTP method (GET, POST)
        payload: Request payload for POST requests
        iterations: Number of test iterations

    Returns:
        List of response times in seconds
    """
    url = f"{API_BASE_URL}{endpoint}"
    response_times = []

    for i in range(iterations):
        try:
            start_time = time.perf_counter()

            if method.upper() == "GET":
                async with session.get(url) as response:
                    await response.text()  # Consume response
                    assert (
                        response.status == 200
                    ), f"Request {i+1} failed with status {response.status}"
            else:  # POST
                async with session.post(url, json=payload) as response:
                    await response.json()  # Consume response
                    assert (
                        response.status == 200
                    ), f"Request {i+1} failed with status {response.status}"

            end_time = time.perf_counter()
            response_time = end_time - start_time
            response_times.append(response_time)

        except Exception as e:
            logger.error(f"Request {i+1} to {endpoint} failed: {e}")
            # Continue testing other requests

    return response_times


# Performance SLA Tests


@pytest.mark.asyncio
async def test_health_endpoint_sla(api_session, api_health_check):
    """
    Test that /health endpoint meets SLA requirement: < 50ms (95th percentile)

    This test validates the most basic API performance requirement.
    Health checks should be extremely fast for load balancers and monitoring.
    """
    logger.info("Testing /health endpoint SLA compliance")

    # Measure performance
    response_times = await measure_endpoint_performance(
        api_session, "/health", "GET", iterations=TEST_ITERATIONS
    )

    # Validate we got responses
    assert (
        len(response_times) >= TEST_ITERATIONS * 0.8
    ), f"Too many failed requests. Got {len(response_times)}/{TEST_ITERATIONS} successful responses"

    # Calculate metrics
    p95_time = calculate_p95(response_times)
    mean_time = statistics.mean(response_times)
    max_time = max(response_times)

    # Log performance metrics
    logger.info(f"Health endpoint performance:")
    logger.info(f"  Mean: {mean_time:.3f}s")
    logger.info(f"  P95:  {p95_time:.3f}s")
    logger.info(f"  Max:  {max_time:.3f}s")
    logger.info(f"  SLA Target: {SLA_TARGETS['/health']:.3f}s")

    # SLA Assertion
    assert (
        p95_time <= SLA_TARGETS["/health"]
    ), f"Health endpoint SLA FAILED: P95 response time {p95_time:.3f}s exceeds target {SLA_TARGETS['/health']:.3f}s"

    logger.info("✅ Health endpoint SLA PASSED")


@pytest.mark.asyncio
async def test_data_endpoint_sla(api_session, api_health_check):
    """
    Test that /data endpoint meets SLA requirement: < 500ms (95th percentile)

    This test validates market data retrieval performance with realistic payloads.
    Data endpoints are critical for real-time trading operations.
    """
    logger.info("Testing /data endpoint SLA compliance")

    # Realistic market data request
    payload = {
        "symbol": "GBPUSD",
        "timeframe": "1h",
        "start_date": (datetime.utcnow() - timedelta(days=7)).isoformat(),
        "end_date": datetime.utcnow().isoformat(),
        "limit": 168,  # 1 week of hourly data
    }

    # Measure performance
    response_times = await measure_endpoint_performance(
        api_session, "/data", "POST", payload, iterations=TEST_ITERATIONS
    )

    # Validate we got responses
    assert (
        len(response_times) >= TEST_ITERATIONS * 0.8
    ), f"Too many failed requests. Got {len(response_times)}/{TEST_ITERATIONS} successful responses"

    # Calculate metrics
    p95_time = calculate_p95(response_times)
    mean_time = statistics.mean(response_times)
    max_time = max(response_times)

    # Log performance metrics
    logger.info(f"Data endpoint performance:")
    logger.info(f"  Mean: {mean_time:.3f}s")
    logger.info(f"  P95:  {p95_time:.3f}s")
    logger.info(f"  Max:  {max_time:.3f}s")
    logger.info(f"  SLA Target: {SLA_TARGETS['/data']:.3f}s")

    # SLA Assertion
    assert (
        p95_time <= SLA_TARGETS["/data"]
    ), f"Data endpoint SLA FAILED: P95 response time {p95_time:.3f}s exceeds target {SLA_TARGETS['/data']:.3f}s"

    logger.info("✅ Data endpoint SLA PASSED")


@pytest.mark.asyncio
async def test_signals_endpoint_sla(api_session, api_health_check):
    """
    Test that /signals endpoint meets SLA requirement: < 2s (95th percentile)

    This test validates signal generation performance with ML processing.
    Signals are critical for automated trading decisions.
    """
    logger.info("Testing /signals endpoint SLA compliance")

    # Realistic signal generation request
    payload = {"symbol": "GBPUSD", "timeframe": "1h", "analysis_type": "comprehensive"}

    # Measure performance (fewer iterations due to ML processing intensity)
    response_times = await measure_endpoint_performance(
        api_session, "/signals", "POST", payload, iterations=min(TEST_ITERATIONS, 10)
    )

    # Validate we got responses
    min_expected = min(TEST_ITERATIONS, 10) * 0.7  # Lower threshold for ML processing
    assert (
        len(response_times) >= min_expected
    ), f"Too many failed requests. Got {len(response_times)}/{min(TEST_ITERATIONS, 10)} successful responses"

    # Calculate metrics
    p95_time = calculate_p95(response_times)
    mean_time = statistics.mean(response_times)
    max_time = max(response_times)

    # Log performance metrics
    logger.info(f"Signals endpoint performance:")
    logger.info(f"  Mean: {mean_time:.3f}s")
    logger.info(f"  P95:  {p95_time:.3f}s")
    logger.info(f"  Max:  {max_time:.3f}s")
    logger.info(f"  SLA Target: {SLA_TARGETS['/signals']:.3f}s")

    # SLA Assertion
    assert (
        p95_time <= SLA_TARGETS["/signals"]
    ), f"Signals endpoint SLA FAILED: P95 response time {p95_time:.3f}s exceeds target {SLA_TARGETS['/signals']:.3f}s"

    logger.info("✅ Signals endpoint SLA PASSED")


@pytest.mark.asyncio
async def test_backtest_endpoint_sla(api_session, api_health_check):
    """
    Test that /backtest endpoint meets SLA requirement: < 5min (95th percentile)

    This test validates backtesting performance with realistic historical analysis.
    Backtests are resource-intensive but must complete within reasonable time.
    """
    logger.info("Testing /backtest endpoint SLA compliance")

    # Realistic backtest request (smaller date range for testing)
    payload = {
        "symbol": "GBPUSD",
        "start_date": (
            datetime.utcnow() - timedelta(days=14)
        ).isoformat(),  # 2 weeks for faster testing
        "end_date": datetime.utcnow().isoformat(),
        "strategy": "gbpusd_ml_strategy",
        "initial_capital": 10000,
    }

    # Measure performance (very few iterations due to resource intensity)
    response_times = await measure_endpoint_performance(
        api_session, "/backtest", "POST", payload, iterations=min(TEST_ITERATIONS, 3)
    )

    # Validate we got responses
    min_expected = (
        min(TEST_ITERATIONS, 3) * 0.6
    )  # Lower threshold for backtest processing
    assert (
        len(response_times) >= min_expected
    ), f"Too many failed requests. Got {len(response_times)}/{min(TEST_ITERATIONS, 3)} successful responses"

    # Calculate metrics
    p95_time = calculate_p95(response_times)
    mean_time = statistics.mean(response_times)
    max_time = max(response_times)

    # Log performance metrics
    logger.info(f"Backtest endpoint performance:")
    logger.info(f"  Mean: {mean_time:.3f}s")
    logger.info(f"  P95:  {p95_time:.3f}s")
    logger.info(f"  Max:  {max_time:.3f}s")
    logger.info(f"  SLA Target: {SLA_TARGETS['/backtest']:.3f}s")

    # SLA Assertion
    assert (
        p95_time <= SLA_TARGETS["/backtest"]
    ), f"Backtest endpoint SLA FAILED: P95 response time {p95_time:.3f}s exceeds target {SLA_TARGETS['/backtest']:.3f}s"

    logger.info("✅ Backtest endpoint SLA PASSED")


@pytest.mark.asyncio
async def test_overall_api_performance_baseline(api_session, api_health_check):
    """
    Test overall API performance baseline to establish current performance characteristics

    This test provides a comprehensive performance baseline for optimization efforts.
    """
    logger.info("Establishing overall API performance baseline")

    endpoints = [
        ("/health", "GET", None),
        (
            "/data",
            "POST",
            {
                "symbol": "GBPUSD",
                "timeframe": "1h",
                "start_date": (datetime.utcnow() - timedelta(days=3)).isoformat(),
                "end_date": datetime.utcnow().isoformat(),
                "limit": 72,
            },
        ),
        (
            "/signals",
            "POST",
            {"symbol": "GBPUSD", "timeframe": "1h", "analysis_type": "comprehensive"},
        ),
    ]

    baseline_results = {}

    for endpoint, method, payload in endpoints:
        logger.info(f"Measuring baseline for {endpoint}")

        iterations = (
            5 if endpoint == "/signals" else 10
        )  # Reduced for resource-intensive endpoints
        response_times = await measure_endpoint_performance(
            api_session, endpoint, method, payload, iterations
        )

        if response_times:
            baseline_results[endpoint] = {
                "mean": statistics.mean(response_times),
                "p95": calculate_p95(response_times),
                "max": max(response_times),
                "min": min(response_times),
                "successful_requests": len(response_times),
            }

    # Log baseline results
    logger.info("📊 API Performance Baseline Results:")
    for endpoint, metrics in baseline_results.items():
        logger.info(f"  {endpoint}:")
        logger.info(f"    Mean: {metrics['mean']:.3f}s")
        logger.info(f"    P95:  {metrics['p95']:.3f}s")
        logger.info(f"    Range: {metrics['min']:.3f}s - {metrics['max']:.3f}s")

    # Ensure all endpoints are functional
    assert len(baseline_results) >= 3, "Not all endpoints responded successfully"

    # Store baseline for comparison in optimization phases
    with open("api_performance_baseline.json", "w") as f:
        import json

        json.dump(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "baseline_results": baseline_results,
                "test_config": {
                    "api_url": API_BASE_URL,
                    "iterations_per_endpoint": iterations,
                },
            },
            f,
            indent=2,
        )

    logger.info("✅ Performance baseline established and saved")


# Resource utilization tests


@pytest.mark.asyncio
async def test_concurrent_request_handling(api_session, api_health_check):
    """
    Test API performance under concurrent load to validate resource handling

    This test ensures the API can handle multiple concurrent requests without
    significant performance degradation.
    """
    logger.info("Testing concurrent request handling")

    concurrent_requests = 10
    endpoint = "/health"  # Use lightweight endpoint

    async def single_request():
        start_time = time.perf_counter()
        async with api_session.get(f"{API_BASE_URL}{endpoint}") as response:
            await response.text()
            end_time = time.perf_counter()
            return end_time - start_time, response.status

    # Execute concurrent requests
    tasks = [single_request() for _ in range(concurrent_requests)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Analyze results
    successful_results = [r for r in results if isinstance(r, tuple) and r[1] == 200]
    response_times = [r[0] for r in successful_results]

    # Validate concurrent performance
    assert (
        len(successful_results) >= concurrent_requests * 0.9
    ), f"Too many concurrent requests failed: {len(successful_results)}/{concurrent_requests}"

    if response_times:
        mean_concurrent_time = statistics.mean(response_times)
        max_concurrent_time = max(response_times)

        logger.info(f"Concurrent request performance ({concurrent_requests} requests):")
        logger.info(f"  Mean: {mean_concurrent_time:.3f}s")
        logger.info(f"  Max:  {max_concurrent_time:.3f}s")
        logger.info(
            f"  Success Rate: {len(successful_results)/concurrent_requests*100:.1f}%"
        )

        # Performance should not degrade significantly under concurrent load
        assert (
            mean_concurrent_time <= SLA_TARGETS[endpoint] * 2
        ), f"Concurrent request performance degraded too much: {mean_concurrent_time:.3f}s"

    logger.info("✅ Concurrent request handling test PASSED")


if __name__ == "__main__":
    # Run tests directly
    import sys

    pytest.main([__file__] + sys.argv[1:])
