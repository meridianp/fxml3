#!/usr/bin/env python3
"""
Quick baseline performance test for FXML4 API endpoints.
Tests each endpoint with minimal load to establish performance baseline.
"""

import asyncio
import json
import os
import statistics
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import aiohttp

from fxml4.api.auth.uat_auth import create_uat_token


async def test_single_endpoint(
    session, endpoint, method="GET", payload=None, iterations=5
):
    """Test single endpoint and return metrics"""

    response_times = []
    successful_requests = 0
    errors = []

    base_url = "http://localhost:8001"
    url = f"{base_url}{endpoint}"

    for i in range(iterations):
        try:
            start_time = time.perf_counter()

            if method == "GET":
                async with session.get(url) as response:
                    await response.text()
                    end_time = time.perf_counter()
                    if response.status == 200:
                        successful_requests += 1
                        response_times.append(end_time - start_time)
                    else:
                        errors.append(f"Status {response.status}")
            else:  # POST
                async with session.post(url, json=payload) as response:
                    result = await response.text()
                    end_time = time.perf_counter()
                    if response.status == 200:
                        successful_requests += 1
                        response_times.append(end_time - start_time)
                    else:
                        errors.append(f"Status {response.status}: {result[:200]}")

        except Exception as e:
            errors.append(f"Request error: {str(e)}")

        # Brief pause between requests
        await asyncio.sleep(0.1)

    # Calculate metrics
    if response_times:
        mean_time = statistics.mean(response_times)
        p95_time = (
            sorted(response_times)[int(len(response_times) * 0.95)]
            if response_times
            else 0
        )
        max_time = max(response_times)
        min_time = min(response_times)
    else:
        mean_time = p95_time = max_time = min_time = 0

    return {
        "endpoint": endpoint,
        "method": method,
        "iterations": iterations,
        "successful_requests": successful_requests,
        "error_rate": (iterations - successful_requests) / iterations * 100,
        "mean_response_time": mean_time,
        "p95_response_time": p95_time,
        "min_response_time": min_time,
        "max_response_time": max_time,
        "errors": errors[:3],  # Keep first 3 errors for debugging
    }


async def main():
    """Run baseline performance tests"""
    print("🚀 FXML4 API Baseline Performance Test")
    print("=" * 50)

    # Generate auth token
    auth_token = create_uat_token("baseline_tester", scopes=["read", "write", "admin"])

    # Define SLA targets
    sla_targets = {
        "/health": 0.050,  # 50ms
        "/data": 0.500,  # 500ms
        "/signals": 2.000,  # 2s
        "/backtest": 300.000,  # 5min
    }

    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }

    # Test endpoints
    results = []

    async with aiohttp.ClientSession(
        headers=headers, timeout=aiohttp.ClientTimeout(total=60)
    ) as session:

        # Test /health endpoint
        print("\n📊 Testing /health endpoint...")
        health_result = await test_single_endpoint(
            session, "/health", "GET", iterations=10
        )
        results.append(health_result)

        status = (
            "✅ PASS"
            if health_result["p95_response_time"] <= sla_targets["/health"]
            else "❌ FAIL"
        )
        print(
            f"   {status} - P95: {health_result['p95_response_time']:.3f}s (Target: {sla_targets['/health']:.3f}s)"
        )

        # Test /data endpoint
        print("\n📊 Testing /data endpoint...")
        data_payload = {"symbol": "GBPUSD", "timeframe": "1h", "limit": 10}
        data_result = await test_single_endpoint(
            session, "/data", "POST", data_payload, iterations=5
        )
        results.append(data_result)

        status = (
            "✅ PASS"
            if data_result["p95_response_time"] <= sla_targets["/data"]
            else "❌ FAIL"
        )
        print(
            f"   {status} - P95: {data_result['p95_response_time']:.3f}s (Target: {sla_targets['/data']:.3f}s)"
        )
        if data_result["errors"]:
            print(f"   Errors: {data_result['errors'][0]}")

        # Test /signals endpoint
        print("\n📊 Testing /signals endpoint...")
        signals_payload = {
            "symbol": "GBPUSD",
            "timeframe": "1h",
            "strategy": "ml_strategy",
        }
        signals_result = await test_single_endpoint(
            session, "/signals", "POST", signals_payload, iterations=3
        )
        results.append(signals_result)

        status = (
            "✅ PASS"
            if signals_result["p95_response_time"] <= sla_targets["/signals"]
            else "❌ FAIL"
        )
        print(
            f"   {status} - P95: {signals_result['p95_response_time']:.3f}s (Target: {sla_targets['/signals']:.3f}s)"
        )
        if signals_result["errors"]:
            print(f"   Errors: {signals_result['errors'][0]}")

        # Test /backtest endpoint (very limited)
        print("\n📊 Testing /backtest endpoint...")
        backtest_payload = {
            "symbol": "GBPUSD",
            "timeframe": "1h",
            "start_date": (datetime.utcnow() - timedelta(days=7)).isoformat(),
            "end_date": datetime.utcnow().isoformat(),
            "strategy": "integrated_strategy",
            "initial_capital": 10000,
        }
        backtest_result = await test_single_endpoint(
            session, "/backtest", "POST", backtest_payload, iterations=1
        )
        results.append(backtest_result)

        status = (
            "✅ PASS"
            if backtest_result["p95_response_time"] <= sla_targets["/backtest"]
            else "❌ FAIL"
        )
        print(
            f"   {status} - P95: {backtest_result['p95_response_time']:.3f}s (Target: {sla_targets['/backtest']:.3f}s)"
        )
        if backtest_result["errors"]:
            print(f"   Errors: {backtest_result['errors'][0]}")

    # Summary
    print("\n" + "=" * 50)
    print("📊 BASELINE PERFORMANCE SUMMARY")
    print("=" * 50)
    print(
        f"{'Endpoint':<12} {'P95 Time':<10} {'Target':<10} {'Status':<8} {'Success%':<10}"
    )
    print("-" * 50)

    passed_endpoints = 0
    for result in results:
        endpoint = result["endpoint"]
        p95_time = result["p95_response_time"]
        target = sla_targets[endpoint]
        success_rate = (result["successful_requests"] / result["iterations"]) * 100

        if p95_time <= target and success_rate >= 80:
            status = "✅ PASS"
            passed_endpoints += 1
        else:
            status = "❌ FAIL"

        print(
            f"{endpoint:<12} {p95_time:<10.3f}s {target:<10.3f}s {status:<8} {success_rate:<10.1f}%"
        )

    overall_status = "✅ PASS" if passed_endpoints == len(results) else "❌ FAIL"
    print(f"\nOverall: {overall_status} ({passed_endpoints}/{len(results)} endpoints)")

    # Save results
    baseline_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "results": results,
        "sla_targets": sla_targets,
        "overall_pass_rate": passed_endpoints / len(results) * 100,
    }

    with open("baseline_performance_results.json", "w") as f:
        json.dump(baseline_data, f, indent=2)

    print(f"\n💾 Baseline results saved to: baseline_performance_results.json")

    return passed_endpoints == len(results)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
