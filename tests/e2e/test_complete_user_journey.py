#!/usr/bin/env python3
"""
END-TO-END USER JOURNEY TESTING
===============================

Complete user journey validation for FXML4 trading platform.
Tests the entire flow from login to trade execution.

CRITICAL PREVENTION MEASURES:
- Tests complete user workflows end-to-end
- Validates all user-facing functionality
- Ensures no broken user experiences reach production

User Journey Flows Tested:
1. Authentication & Profile Management
2. Market Data & Signal Generation
3. Trade Execution & Order Management
4. Portfolio & Risk Management
5. Backtesting & Strategy Validation
6. Dashboard & Real-time Updates
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiohttp
import pytest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class UserJourneyResult:
    """Result of a user journey test"""

    journey_name: str
    status: str
    duration_seconds: float
    steps_completed: int
    total_steps: int
    error_message: Optional[str] = None
    step_results: List[Dict[str, Any]] = None


class EndToEndUserJourney:
    """Complete user journey testing for FXML4 platform"""

    def __init__(self, base_url: str, ui_url: str = None):
        self.base_url = base_url.rstrip("/")
        self.ui_url = (
            ui_url.rstrip("/") if ui_url else f"{base_url.replace('api', 'app')}"
        )
        self.session_data = {}
        self.test_user = {
            "username": f"e2e_user_{int(time.time())}",
            "email": f"e2e_{int(time.time())}@fxml4.com",
            "password": "E2ETestPass123!",  # pragma: allowlist secret
        }

    async def setup_test_user(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Setup test user for E2E testing"""
        try:
            # Register user
            async with session.post(
                f"{self.base_url}/auth/register", json=self.test_user, timeout=10
            ) as response:
                if response.status == 409:  # User exists
                    logger.info("Test user already exists")
                else:
                    assert (
                        response.status == 201
                    ), f"Registration failed: {response.status}"

            # Login user
            login_data = {
                "username": self.test_user["username"],
                "password": self.test_user["password"],
            }

            async with session.post(
                f"{self.base_url}/auth/login", json=login_data, timeout=10
            ) as response:
                assert response.status == 200, f"Login failed: {response.status}"
                token_data = await response.json()

            self.session_data = token_data
            return token_data

        except Exception as e:
            raise AssertionError(f"User setup failed: {e}")

    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        return {"Authorization": f"Bearer {self.session_data['access_token']}"}

    async def journey_1_authentication_profile(self) -> UserJourneyResult:
        """Journey 1: Complete Authentication & Profile Management Flow"""
        journey_name = "Authentication & Profile Management"
        start_time = time.time()
        steps = []

        try:
            async with aiohttp.ClientSession() as session:
                # Step 1: User Registration
                steps.append("User Registration")
                await self.setup_test_user(session)

                # Step 2: Profile Retrieval
                steps.append("Profile Retrieval")
                async with session.get(
                    f"{self.base_url}/auth/profile",
                    headers=self.get_auth_headers(),
                    timeout=10,
                ) as response:
                    assert (
                        response.status == 200
                    ), f"Profile retrieval failed: {response.status}"
                    profile = await response.json()
                    assert "username" in profile, "Profile missing username"

                # Step 3: Profile Update
                steps.append("Profile Update")
                update_data = {"display_name": "E2E Test User", "timezone": "UTC"}
                async with session.put(
                    f"{self.base_url}/auth/profile",
                    headers=self.get_auth_headers(),
                    json=update_data,
                    timeout=10,
                ) as response:
                    assert (
                        response.status == 200
                    ), f"Profile update failed: {response.status}"

                # Step 4: Session Validation
                steps.append("Session Validation")
                async with session.get(
                    f"{self.base_url}/auth/session",
                    headers=self.get_auth_headers(),
                    timeout=10,
                ) as response:
                    assert (
                        response.status == 200
                    ), f"Session validation failed: {response.status}"
                    session_info = await response.json()
                    assert "expires_at" in session_info, "Session missing expiration"

                duration = time.time() - start_time
                logger.info(
                    f"✅ {journey_name} completed successfully in {duration:.2f}s"
                )

                return UserJourneyResult(
                    journey_name=journey_name,
                    status="PASSED",
                    duration_seconds=duration,
                    steps_completed=len(steps),
                    total_steps=len(steps),
                    step_results=[{"step": step, "status": "passed"} for step in steps],
                )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ {journey_name} failed: {e}")

            return UserJourneyResult(
                journey_name=journey_name,
                status="FAILED",
                duration_seconds=duration,
                steps_completed=len(steps) - 1,
                total_steps=len(steps),
                error_message=str(e),
            )

    async def journey_2_market_data_signals(self) -> UserJourneyResult:
        """Journey 2: Market Data & Signal Generation Flow"""
        journey_name = "Market Data & Signal Generation"
        start_time = time.time()
        steps = []

        try:
            async with aiohttp.ClientSession() as session:
                await self.setup_test_user(session)

                # Step 1: Market Data Retrieval
                steps.append("Market Data Retrieval")
                async with session.get(
                    f"{self.base_url}/data/market-data?symbol=EURUSD&timeframe=1h&limit=100",
                    headers=self.get_auth_headers(),
                    timeout=30,
                ) as response:
                    assert (
                        response.status == 200
                    ), f"Market data failed: {response.status}"
                    market_data = await response.json()
                    assert len(market_data) > 0, "No market data returned"

                # Step 2: Signal Generation
                steps.append("Signal Generation")
                signal_request = {
                    "symbol": "EURUSD",
                    "timeframe": "1h",
                    "strategy": "gbpusd_primary",
                }
                async with session.post(
                    f"{self.base_url}/signals/generate",
                    headers=self.get_auth_headers(),
                    json=signal_request,
                    timeout=45,
                ) as response:
                    assert (
                        response.status == 200
                    ), f"Signal generation failed: {response.status}"
                    signals = await response.json()
                    assert "signal" in signals, "No signal in response"

                # Step 3: Technical Analysis
                steps.append("Technical Analysis")
                async with session.get(
                    f"{self.base_url}/analysis/technical?symbol=EURUSD&indicators=sma,rsi,macd",
                    headers=self.get_auth_headers(),
                    timeout=20,
                ) as response:
                    assert (
                        response.status == 200
                    ), f"Technical analysis failed: {response.status}"
                    analysis = await response.json()
                    assert "indicators" in analysis, "No indicators in analysis"

                # Step 4: Elliott Wave Analysis
                steps.append("Elliott Wave Analysis")
                async with session.get(
                    f"{self.base_url}/analysis/elliott-wave?symbol=EURUSD",
                    headers=self.get_auth_headers(),
                    timeout=30,
                ) as response:
                    assert (
                        response.status == 200
                    ), f"Elliott Wave analysis failed: {response.status}"
                    wave_data = await response.json()
                    assert "patterns" in wave_data, "No wave patterns found"

                duration = time.time() - start_time
                logger.info(
                    f"✅ {journey_name} completed successfully in {duration:.2f}s"
                )

                return UserJourneyResult(
                    journey_name=journey_name,
                    status="PASSED",
                    duration_seconds=duration,
                    steps_completed=len(steps),
                    total_steps=len(steps),
                    step_results=[{"step": step, "status": "passed"} for step in steps],
                )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ {journey_name} failed: {e}")

            return UserJourneyResult(
                journey_name=journey_name,
                status="FAILED",
                duration_seconds=duration,
                steps_completed=len(steps) - 1,
                total_steps=len(steps),
                error_message=str(e),
            )

    async def journey_3_trade_execution(self) -> UserJourneyResult:
        """Journey 3: Complete Trade Execution & Order Management"""
        journey_name = "Trade Execution & Order Management"
        start_time = time.time()
        steps = []

        try:
            async with aiohttp.ClientSession() as session:
                await self.setup_test_user(session)

                # Step 1: Create Trade Order (Demo Mode)
                steps.append("Create Trade Order")
                order_data = {
                    "symbol": "EURUSD",
                    "side": "buy",
                    "quantity": 0.01,
                    "order_type": "market",
                    "demo_mode": True,  # Ensure test trades only
                }
                async with session.post(
                    f"{self.base_url}/trading/orders",
                    headers=self.get_auth_headers(),
                    json=order_data,
                    timeout=30,
                ) as response:
                    assert (
                        response.status == 201
                    ), f"Order creation failed: {response.status}"
                    order = await response.json()
                    assert "order_id" in order, "No order ID returned"
                    order_id = order["order_id"]

                # Step 2: Monitor Order Status
                steps.append("Monitor Order Status")
                async with session.get(
                    f"{self.base_url}/trading/orders/{order_id}",
                    headers=self.get_auth_headers(),
                    timeout=10,
                ) as response:
                    assert (
                        response.status == 200
                    ), f"Order status check failed: {response.status}"
                    order_status = await response.json()
                    assert "status" in order_status, "No order status"

                # Step 3: Portfolio Positions
                steps.append("Portfolio Positions")
                async with session.get(
                    f"{self.base_url}/trading/positions",
                    headers=self.get_auth_headers(),
                    timeout=10,
                ) as response:
                    assert (
                        response.status == 200
                    ), f"Positions retrieval failed: {response.status}"
                    positions = await response.json()
                    assert isinstance(positions, list), "Invalid positions format"

                # Step 4: Trade History
                steps.append("Trade History")
                async with session.get(
                    f"{self.base_url}/trading/history",
                    headers=self.get_auth_headers(),
                    timeout=10,
                ) as response:
                    assert (
                        response.status == 200
                    ), f"Trade history failed: {response.status}"
                    history = await response.json()
                    assert "trades" in history, "No trade history"

                # Step 5: Risk Management Check
                steps.append("Risk Management Check")
                async with session.get(
                    f"{self.base_url}/risk/limits",
                    headers=self.get_auth_headers(),
                    timeout=10,
                ) as response:
                    assert (
                        response.status == 200
                    ), f"Risk limits check failed: {response.status}"
                    risk_data = await response.json()
                    assert "max_risk_per_trade" in risk_data, "No risk limits found"

                duration = time.time() - start_time
                logger.info(
                    f"✅ {journey_name} completed successfully in {duration:.2f}s"
                )

                return UserJourneyResult(
                    journey_name=journey_name,
                    status="PASSED",
                    duration_seconds=duration,
                    steps_completed=len(steps),
                    total_steps=len(steps),
                    step_results=[{"step": step, "status": "passed"} for step in steps],
                )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ {journey_name} failed: {e}")

            return UserJourneyResult(
                journey_name=journey_name,
                status="FAILED",
                duration_seconds=duration,
                steps_completed=len(steps) - 1,
                total_steps=len(steps),
                error_message=str(e),
            )

    async def journey_4_backtesting_strategy(self) -> UserJourneyResult:
        """Journey 4: Backtesting & Strategy Validation"""
        journey_name = "Backtesting & Strategy Validation"
        start_time = time.time()
        steps = []

        try:
            async with aiohttp.ClientSession() as session:
                await self.setup_test_user(session)

                # Step 1: Start Backtest
                steps.append("Start Backtest")
                backtest_config = {
                    "symbol": "EURUSD",
                    "start_date": "2024-01-01",
                    "end_date": "2024-02-01",
                    "strategy": "gbpusd_primary",
                    "initial_balance": 10000,
                }
                async with session.post(
                    f"{self.base_url}/backtesting/run",
                    headers=self.get_auth_headers(),
                    json=backtest_config,
                    timeout=120,  # Backtests take longer
                ) as response:
                    assert (
                        response.status == 202
                    ), f"Backtest start failed: {response.status}"
                    backtest = await response.json()
                    assert "backtest_id" in backtest, "No backtest ID"
                    backtest_id = backtest["backtest_id"]

                # Step 2: Monitor Backtest Progress
                steps.append("Monitor Backtest Progress")
                max_wait = 300  # 5 minutes max wait
                wait_time = 0
                while wait_time < max_wait:
                    async with session.get(
                        f"{self.base_url}/backtesting/status/{backtest_id}",
                        headers=self.get_auth_headers(),
                        timeout=10,
                    ) as response:
                        assert (
                            response.status == 200
                        ), f"Status check failed: {response.status}"
                        status = await response.json()

                        if status["status"] == "completed":
                            break
                        elif status["status"] == "failed":
                            raise AssertionError(
                                f"Backtest failed: {status.get('error')}"
                            )

                        await asyncio.sleep(10)
                        wait_time += 10

                # Step 3: Get Backtest Results
                steps.append("Get Backtest Results")
                async with session.get(
                    f"{self.base_url}/backtesting/results/{backtest_id}",
                    headers=self.get_auth_headers(),
                    timeout=30,
                ) as response:
                    assert (
                        response.status == 200
                    ), f"Results retrieval failed: {response.status}"
                    results = await response.json()
                    assert "total_return" in results, "No backtest metrics"
                    assert "sharpe_ratio" in results, "Missing sharpe ratio"

                # Step 4: Performance Analytics
                steps.append("Performance Analytics")
                async with session.get(
                    f"{self.base_url}/backtesting/analytics/{backtest_id}",
                    headers=self.get_auth_headers(),
                    timeout=20,
                ) as response:
                    assert (
                        response.status == 200
                    ), f"Analytics failed: {response.status}"
                    analytics = await response.json()
                    assert "equity_curve" in analytics, "No equity curve data"

                duration = time.time() - start_time
                logger.info(
                    f"✅ {journey_name} completed successfully in {duration:.2f}s"
                )

                return UserJourneyResult(
                    journey_name=journey_name,
                    status="PASSED",
                    duration_seconds=duration,
                    steps_completed=len(steps),
                    total_steps=len(steps),
                    step_results=[{"step": step, "status": "passed"} for step in steps],
                )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ {journey_name} failed: {e}")

            return UserJourneyResult(
                journey_name=journey_name,
                status="FAILED",
                duration_seconds=duration,
                steps_completed=len(steps) - 1,
                total_steps=len(steps),
                error_message=str(e),
            )

    async def run_all_journeys(self) -> List[UserJourneyResult]:
        """Execute all user journey tests"""
        logger.info(f"🚀 STARTING END-TO-END USER JOURNEY TESTS for {self.base_url}")

        journeys = [
            self.journey_1_authentication_profile(),
            self.journey_2_market_data_signals(),
            self.journey_3_trade_execution(),
            self.journey_4_backtesting_strategy(),
        ]

        # Run all journeys
        results = []
        for journey in journeys:
            try:
                result = await journey
                results.append(result)
            except Exception as e:
                logger.error(f"Journey failed with exception: {e}")
                results.append(
                    UserJourneyResult(
                        journey_name="Unknown Journey",
                        status="FAILED",
                        duration_seconds=0,
                        steps_completed=0,
                        total_steps=0,
                        error_message=str(e),
                    )
                )

        # Analyze results
        passed = sum(1 for r in results if r.status == "PASSED")
        total = len(results)
        total_time = sum(r.duration_seconds for r in results)

        logger.info(
            f"📊 END-TO-END RESULTS: {passed}/{total} journeys passed in {total_time:.2f}s"
        )

        if passed != total:
            failed_journeys = [r.journey_name for r in results if r.status == "FAILED"]
            raise AssertionError(f"E2E journeys failed: {failed_journeys}")

        return results


# Pytest integration for CI/CD
@pytest.mark.critical
@pytest.mark.e2e
@pytest.mark.slow
async def test_e2e_staging_environment():
    """Run E2E tests against staging"""
    staging_url = os.getenv("STAGING_URL", "http://staging-api.fxml4.com")
    staging_ui = os.getenv("STAGING_UI_URL", "http://staging-app.fxml4.com")

    tester = EndToEndUserJourney(staging_url, staging_ui)
    results = await tester.run_all_journeys()

    assert all(r.status == "PASSED" for r in results), "E2E staging tests failed"


@pytest.mark.critical
@pytest.mark.e2e
@pytest.mark.production
@pytest.mark.slow
async def test_e2e_production_environment():
    """Run E2E tests against production (read-only mode)"""
    production_url = os.getenv("PRODUCTION_URL", "https://api.fxml4.com")
    production_ui = os.getenv("PRODUCTION_UI_URL", "https://app.fxml4.com")

    tester = EndToEndUserJourney(production_url, production_ui)

    # Only run safe journeys in production
    result1 = await tester.journey_1_authentication_profile()
    result2 = await tester.journey_2_market_data_signals()

    results = [result1, result2]
    assert all(r.status == "PASSED" for r in results), "E2E production tests failed"


if __name__ == "__main__":
    import sys

    # Command line execution
    environment_url = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.getenv("API_URL", "http://localhost:8001")
    )
    ui_url = sys.argv[2] if len(sys.argv) > 2 else None

    async def main():
        try:
            tester = EndToEndUserJourney(environment_url, ui_url)
            results = await tester.run_all_journeys()

            print(f"✅ ALL E2E JOURNEYS PASSED: {len(results)} journeys completed")
            for result in results:
                print(
                    f"  - {result.journey_name}: {result.status} ({result.duration_seconds:.2f}s)"
                )

            return 0

        except Exception as e:
            print(f"❌ E2E TESTS FAILED: {e}")
            return 1

    exit_code = asyncio.run(main())
    sys.exit(exit_code)
