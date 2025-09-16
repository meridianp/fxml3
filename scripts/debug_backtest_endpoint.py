#!/usr/bin/env python3
"""
Debug script to identify the specific cause of the /backtest endpoint internal server error.
"""

import asyncio
import json
import traceback
from datetime import datetime, timedelta

import aiohttp

from fxml4.api.auth.uat_auth import create_uat_token


async def debug_backtest_endpoint():
    """Debug the backtest endpoint 500 error"""
    print("🔧 Debugging /backtest endpoint internal server error...")
    print("=" * 60)

    # Generate auth token
    auth_token = create_uat_token("debug_tester", scopes=["read", "write", "admin"])

    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }

    # Create valid backtest payload with timeframe field
    backtest_payload = {
        "symbol": "GBPUSD",
        "timeframe": "1h",
        "start_date": (datetime.utcnow() - timedelta(days=7)).isoformat(),
        "end_date": datetime.utcnow().isoformat(),
        "strategy": "integrated_strategy",
        "initial_capital": 10000,
    }

    print(f"📄 Testing payload:")
    print(json.dumps(backtest_payload, indent=2))
    print()

    async with aiohttp.ClientSession(
        headers=headers, timeout=aiohttp.ClientTimeout(total=10)
    ) as session:
        try:
            print("🚀 Making POST request to /backtest...")
            async with session.post(
                "http://localhost:8001/backtest", json=backtest_payload
            ) as response:
                print(f"📊 Response Status: {response.status}")
                print(f"📄 Response Headers: {dict(response.headers)}")

                # Get response text
                response_text = await response.text()
                print(f"📝 Response Body: {response_text}")

                if response.status == 500:
                    print("\n❌ Internal Server Error Details:")
                    try:
                        error_json = json.loads(response_text)
                        print(
                            f"Error Detail: {error_json.get('detail', 'No detail available')}"
                        )
                    except json.JSONDecodeError:
                        print(f"Raw error response: {response_text}")
                elif response.status == 422:
                    print("\n❌ Schema Validation Error:")
                    try:
                        error_json = json.loads(response_text)
                        print(json.dumps(error_json, indent=2))
                    except json.JSONDecodeError:
                        print(f"Raw validation error: {response_text}")
                elif response.status == 200:
                    print("\n✅ Success! Backtest endpoint is working.")
                    try:
                        result_json = json.loads(response_text)
                        print("Response keys:", list(result_json.keys()))
                    except json.JSONDecodeError:
                        pass
                else:
                    print(f"\n⚠️  Unexpected status code: {response.status}")

        except asyncio.TimeoutError:
            print("❌ Request timed out - endpoint may be hanging")
        except Exception as e:
            print(f"❌ Request failed with exception: {e}")
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_backtest_endpoint())
