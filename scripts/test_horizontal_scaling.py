#!/usr/bin/env python3
"""
Horizontal scaling validation for FXML4 API.
Target: 5+ API replicas with <100ms load balancer latency
"""

import asyncio
import json
import logging
import os
import statistics
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional

import psutil
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class HorizontalScalingTest:
    """Test horizontal scaling capabilities with load balancer."""

    def __init__(self):
        self.api_instances = []
        self.load_balancer_port = 8080
        self.api_base_ports = [8001, 8002, 8003, 8004, 8005, 8006]
        self.nginx_config_path = "/tmp/nginx_fxml4.conf"
        self.nginx_pid_path = "/tmp/nginx_fxml4.pid"
        self.test_token = None

    def generate_test_token(self) -> str:
        """Generate JWT token for testing."""
        try:
            import sys

            sys.path.insert(0, "/home/cnross/code/fxml4")
            from scripts.generate_test_token import main as generate_token

            return generate_token()
        except Exception as e:
            logger.warning(f"Could not generate test token: {e}")
            return ""

    def create_nginx_config(self, num_replicas: int) -> str:
        """Create nginx load balancer configuration."""
        upstream_servers = "\n".join(
            [
                f"        server 127.0.0.1:{port} max_fails=3 fail_timeout=30s;"
                for port in self.api_base_ports[:num_replicas]
            ]
        )

        config = f"""
events {{
    worker_connections 1024;
}}

http {{
    upstream fxml4_api {{
{upstream_servers}
    }}

    server {{
        listen {self.load_balancer_port};

        location / {{
            proxy_pass http://fxml4_api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_connect_timeout 5s;
            proxy_send_timeout 10s;
            proxy_read_timeout 30s;

            # Add timing headers for latency measurement
            add_header X-Upstream-Addr $upstream_addr always;
            add_header X-Response-Time $upstream_response_time always;
        }}
    }}

    # Access log for debugging
    access_log /tmp/nginx_fxml4_access.log;
    error_log /tmp/nginx_fxml4_error.log;
}}
"""
        return config

    def start_nginx_load_balancer(self, num_replicas: int) -> bool:
        """Start nginx load balancer."""
        try:
            # Stop any existing nginx instance
            self.stop_nginx_load_balancer()

            # Create nginx config
            config = self.create_nginx_config(num_replicas)
            with open(self.nginx_config_path, "w") as f:
                f.write(config)

            # Start nginx
            cmd = [
                "nginx",
                "-c",
                self.nginx_config_path,
                "-p",
                "/tmp/",
                "-g",
                f"pid {self.nginx_pid_path};",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info(
                    f"Nginx load balancer started on port {self.load_balancer_port}"
                )
                time.sleep(2)  # Allow nginx to fully start
                return True
            else:
                logger.error(f"Failed to start nginx: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error starting nginx load balancer: {e}")
            return False

    def stop_nginx_load_balancer(self) -> None:
        """Stop nginx load balancer."""
        try:
            # Try to read PID file and kill process
            if os.path.exists(self.nginx_pid_path):
                with open(self.nginx_pid_path, "r") as f:
                    pid = int(f.read().strip())
                try:
                    os.kill(pid, 15)  # SIGTERM
                    logger.info("Stopped nginx load balancer")
                except ProcessLookupError:
                    pass

            # Clean up files
            for file_path in [self.nginx_config_path, self.nginx_pid_path]:
                if os.path.exists(file_path):
                    os.remove(file_path)

        except Exception as e:
            logger.warning(f"Error stopping nginx: {e}")

        # Fallback: kill any nginx processes using our config
        try:
            subprocess.run(["pkill", "-f", "nginx.*fxml4"], capture_output=True)
        except:
            pass

    def start_api_replica(self, port: int) -> Optional[subprocess.Popen]:
        """Start a single API replica."""
        try:
            env = os.environ.copy()
            env["FXML4_API_PORT"] = str(port)
            env["FXML4_API_HOST"] = "0.0.0.0"

            cmd = ["./scripts/run_with_fxml4.sh", "scripts/start_fxml4_api.py"]

            process = subprocess.Popen(
                cmd,
                cwd="/home/cnross/code/fxml4",
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Wait for API to start
            max_retries = 30
            for _ in range(max_retries):
                try:
                    response = requests.get(
                        f"http://localhost:{port}/health", timeout=1.0
                    )
                    if response.status_code == 200:
                        logger.info(f"API replica started on port {port}")
                        return process
                except:
                    pass
                time.sleep(1)

            logger.error(f"API replica on port {port} failed to start")
            process.terminate()
            return None

        except Exception as e:
            logger.error(f"Error starting API replica on port {port}: {e}")
            return None

    def stop_api_replicas(self) -> None:
        """Stop all API replicas."""
        for process in self.api_instances:
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=10)
                except:
                    try:
                        process.kill()
                        process.wait(timeout=5)
                    except:
                        pass
        self.api_instances.clear()

        # Fallback: kill any remaining API processes
        for port in self.api_base_ports:
            try:
                subprocess.run(["pkill", "-f", f".*{port}.*"], capture_output=True)
            except:
                pass

    def start_replicas(self, num_replicas: int) -> bool:
        """Start specified number of API replicas."""
        logger.info(f"Starting {num_replicas} API replicas...")

        self.stop_api_replicas()  # Clean up any existing instances

        success_count = 0
        for i in range(num_replicas):
            port = self.api_base_ports[i]
            process = self.start_api_replica(port)
            if process:
                self.api_instances.append(process)
                success_count += 1
            else:
                logger.error(f"Failed to start replica {i+1} on port {port}")

        if success_count == num_replicas:
            logger.info(
                f"Successfully started {success_count}/{num_replicas} API replicas"
            )
            return True
        else:
            logger.error(f"Only started {success_count}/{num_replicas} API replicas")
            return False

    def test_load_balancer_latency(self, num_requests: int = 100) -> Dict[str, Any]:
        """Test load balancer latency and distribution."""
        logger.info(f"Testing load balancer latency with {num_requests} requests")

        latencies = []
        successful_requests = 0
        failed_requests = 0

        headers = {}
        if self.test_token:
            headers["Authorization"] = f"Bearer {self.test_token}"

        for i in range(num_requests):
            try:
                start_time = time.perf_counter()

                response = requests.get(
                    f"http://localhost:{self.load_balancer_port}/health",
                    headers=headers,
                    timeout=5.0,
                )

                end_time = time.perf_counter()
                latency = (end_time - start_time) * 1000  # Convert to milliseconds

                if response.status_code == 200:
                    latencies.append(latency)
                    successful_requests += 1
                else:
                    failed_requests += 1

            except Exception as e:
                failed_requests += 1
                logger.debug(f"Request {i+1} failed: {e}")

        if latencies:
            return {
                "successful_requests": successful_requests,
                "failed_requests": failed_requests,
                "avg_latency_ms": statistics.mean(latencies),
                "p50_latency_ms": statistics.median(latencies),
                "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95)],
                "p99_latency_ms": sorted(latencies)[int(len(latencies) * 0.99)],
                "min_latency_ms": min(latencies),
                "max_latency_ms": max(latencies),
                "latencies": latencies,
            }
        else:
            return {
                "successful_requests": 0,
                "failed_requests": failed_requests,
                "error": "No successful requests",
            }

    def test_concurrent_load(
        self, num_threads: int, requests_per_thread: int
    ) -> Dict[str, Any]:
        """Test concurrent load handling across replicas."""
        logger.info(
            f"Testing concurrent load: {num_threads} threads, {requests_per_thread} requests each"
        )

        start_time = time.perf_counter()
        successful_requests = 0
        failed_requests = 0
        latencies = []

        headers = {}
        if self.test_token:
            headers["Authorization"] = f"Bearer {self.test_token}"

        def make_requests(thread_id: int) -> Dict[str, Any]:
            thread_successful = 0
            thread_failed = 0
            thread_latencies = []

            for i in range(requests_per_thread):
                try:
                    req_start = time.perf_counter()

                    response = requests.get(
                        f"http://localhost:{self.load_balancer_port}/api/data/market_data",
                        params={"symbol": "GBPUSD", "timeframe": "1m", "limit": 10},
                        headers=headers,
                        timeout=10.0,
                    )

                    req_end = time.perf_counter()
                    latency = (req_end - req_start) * 1000

                    if response.status_code == 200:
                        thread_successful += 1
                        thread_latencies.append(latency)
                    else:
                        thread_failed += 1

                except Exception as e:
                    thread_failed += 1
                    logger.debug(f"Thread {thread_id} request {i+1} failed: {e}")

            return {
                "successful": thread_successful,
                "failed": thread_failed,
                "latencies": thread_latencies,
            }

        # Execute concurrent requests
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(make_requests, i) for i in range(num_threads)]

            for future in as_completed(futures):
                try:
                    result = future.result()
                    successful_requests += result["successful"]
                    failed_requests += result["failed"]
                    latencies.extend(result["latencies"])
                except Exception as e:
                    logger.error(f"Thread execution failed: {e}")

        end_time = time.perf_counter()
        total_time = end_time - start_time
        total_requests = successful_requests + failed_requests

        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": (
                (successful_requests / total_requests * 100)
                if total_requests > 0
                else 0
            ),
            "total_time_seconds": total_time,
            "requests_per_second": (
                successful_requests / total_time if total_time > 0 else 0
            ),
            "avg_latency_ms": statistics.mean(latencies) if latencies else 0,
            "p95_latency_ms": (
                sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0
            ),
            "p99_latency_ms": (
                sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 0
            ),
        }


async def test_horizontal_scaling():
    """Comprehensive horizontal scaling test."""

    print("🔧 Testing Horizontal Scaling & Load Balancing")
    print("=" * 60)
    print("Target: 5+ API replicas with <100ms load balancer latency")
    print()

    scaler = HorizontalScalingTest()

    # Generate test token
    scaler.test_token = scaler.generate_test_token()
    logger.info("Generated test authentication token")

    # Test scenarios with increasing replica counts
    test_scenarios = [
        {"replicas": 2, "description": "Baseline Scaling"},
        {"replicas": 3, "description": "Moderate Scaling"},
        {"replicas": 5, "description": "Target Scaling"},
        {"replicas": 6, "description": "Extended Scaling"},
    ]

    results = {}

    try:
        for scenario in test_scenarios:
            replicas = scenario["replicas"]
            description = scenario["description"]

            print(f"\n📊 Testing {description} ({replicas} replicas)")
            print("-" * 50)

            # Start API replicas
            if not scaler.start_replicas(replicas):
                print(f"   ❌ FAIL - Could not start {replicas} replicas")
                continue

            # Start load balancer
            if not scaler.start_nginx_load_balancer(replicas):
                print(f"   ❌ FAIL - Could not start load balancer")
                continue

            # Wait for stabilization
            time.sleep(5)

            # Test load balancer latency
            latency_results = scaler.test_load_balancer_latency(100)

            if "error" in latency_results:
                print(f"   ❌ FAIL - Load balancer latency test failed")
                continue

            # Test concurrent load handling
            concurrent_results = scaler.test_concurrent_load(
                20, 10
            )  # 20 threads, 10 requests each

            # Evaluate results
            latency_target_met = latency_results["p95_latency_ms"] < 100
            success_rate_good = concurrent_results["success_rate"] > 95

            overall_pass = latency_target_met and success_rate_good

            results[description] = {
                "replicas": replicas,
                "latency_results": latency_results,
                "concurrent_results": concurrent_results,
                "latency_target_met": latency_target_met,
                "success_rate_good": success_rate_good,
                "overall_pass": overall_pass,
            }

            # Display results
            status = "✅ PASS" if overall_pass else "❌ FAIL"
            print(
                f"   {status} - Load Balancer Latency P95: {latency_results['p95_latency_ms']:.1f}ms (target <100ms)"
            )
            print(
                f"   {status} - Concurrent Success Rate: {concurrent_results['success_rate']:.1f}% ({concurrent_results['successful_requests']}/{concurrent_results['total_requests']})"
            )
            print(
                f"   Requests/Second: {concurrent_results['requests_per_second']:.1f}"
            )
            print(
                f"   Concurrent Load P95: {concurrent_results['p95_latency_ms']:.1f}ms"
            )

            # Clean up for next scenario
            scaler.stop_nginx_load_balancer()
            scaler.stop_api_replicas()
            time.sleep(3)  # Cool down between tests

        # Overall assessment
        print("\n" + "=" * 60)
        print("📊 HORIZONTAL SCALING SUMMARY")
        print("=" * 60)
        print(
            f"{'Scenario':<18} {'Replicas':<9} {'LB P95':<10} {'Success%':<10} {'Status':<8}"
        )
        print("-" * 62)

        overall_system_pass = True
        target_met = False

        for description, result in results.items():
            status = "✅ PASS" if result["overall_pass"] else "❌ FAIL"
            print(
                f"{description:<18} {result['replicas']:<9} {result['latency_results']['p95_latency_ms']:<10.1f}ms {result['concurrent_results']['success_rate']:<10.1f}% {status:<8}"
            )

            overall_system_pass = overall_system_pass and result["overall_pass"]
            if result["replicas"] >= 5 and result["overall_pass"]:
                target_met = True

        final_status = "✅ PASS" if target_met else "❌ FAIL"
        print(f"\nHorizontal Scaling (5+ replicas): {final_status}")

        # Performance insights
        print(f"\n💡 SCALING INSIGHTS")
        for description, result in results.items():
            lr = result["latency_results"]
            cr = result["concurrent_results"]
            print(f"\n{description} ({result['replicas']} replicas):")
            print(
                f"  Load Balancer: Avg {lr['avg_latency_ms']:.1f}ms, P95 {lr['p95_latency_ms']:.1f}ms"
            )
            print(
                f"  Throughput: {cr['requests_per_second']:.1f} req/s with {cr['success_rate']:.1f}% success"
            )
            print(f"  Concurrent Load: P95 {cr['p95_latency_ms']:.1f}ms latency")

        return target_met

    except Exception as e:
        logger.error(f"Horizontal scaling test failed: {e}")
        return False

    finally:
        # Clean up
        try:
            scaler.stop_nginx_load_balancer()
            scaler.stop_api_replicas()
            logger.info("Test cleanup completed")
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")


async def main():
    """Run horizontal scaling validation tests."""
    success = await test_horizontal_scaling()
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
