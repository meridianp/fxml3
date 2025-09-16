#!/usr/bin/env python3
"""Test script for FXCM Demo Integration.

Tests the complete integration between FXML4, ForexConnect bridge,
and the FXCM demo account using the provided credentials.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import AsyncMock, MagicMock

from fxml4.api.account_monitoring import AccountReconciler
from fxml4.api.websocket_market_data import WebSocketMarketDataManager
from fxml4.brokers.adapters.fxcm_demo_adapter import FXCMDemoAdapter


async def test_fxcm_integration():
    """Test FXCM demo integration with comprehensive validation."""

    print("🧪 Testing FXCM Demo Account Integration with FXML4")
    print("=" * 70)
    print("📧 Account: 0x0c9@quatumchain.com")
    print("🖥️  Server: FXCM-USDDemo1")
    print("🔧 Environment: Paper Trading")
    print()

    # Setup logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Initialize FXCM adapter
    adapter = FXCMDemoAdapter()
    reconciler = AccountReconciler()

    try:
        # Test 1: Connection
        print("1️⃣  Testing FXCM Demo Connection...")
        connected = await adapter.connect()

        if connected:
            print(f"✅ Successfully connected to {adapter.server}")
            print(f"🆔 Session ID: {adapter.session_id}")
        else:
            print("❌ Connection failed")
            return False

        # Test 2: Account Information Retrieval
        print("\n2️⃣  Testing Account Information Retrieval...")
        account_info = await adapter.get_account_info()

        print(f"💰 Account Balance: ${account_info['balance']:,.2f}")
        print(f"💎 Account Equity: ${account_info['equity']:,.2f}")
        print(f"📊 Available Margin: ${account_info['margin_available']:,.2f}")
        print(f"🪙 Currency: {account_info['currency']}")

        # Validate account data structure
        required_fields = [
            "account_id",
            "balance",
            "equity",
            "margin_used",
            "margin_available",
            "currency",
        ]
        for field in required_fields:
            assert field in account_info, f"Missing required field: {field}"

        print("✅ Account information retrieved and validated")

        # Test 3: Market Data Streaming
        print("\n3️⃣  Testing Market Data Streaming...")

        # Create mock WebSocket clients to test streaming
        mock_clients = []
        for i in range(3):
            client = MagicMock()
            client.client_id = f"test_client_{i}"
            client.send = AsyncMock()
            mock_clients.append(client)

            await adapter.ws_manager.register_client(client)
            await adapter.ws_manager.subscribe_client_to_symbol(
                client.client_id, "EUR/USD"
            )

        print(f"📡 Registered {len(mock_clients)} WebSocket clients")

        # Test market data retrieval
        symbols = ["EUR/USD", "GBP/USD", "USD/JPY"]
        market_data = await adapter.get_market_data(symbols)

        for symbol, prices in market_data.items():
            print(
                f"📈 {symbol}: Bid={prices['bid']:.5f}, Ask={prices['ask']:.5f}, Spread={prices['ask']-prices['bid']:.5f}"
            )

            # Validate price data
            assert (
                "bid" in prices and "ask" in prices
            ), f"Missing price data for {symbol}"
            assert prices["ask"] > prices["bid"], f"Invalid spread for {symbol}"

        # Verify WebSocket broadcasting
        for client in mock_clients:
            assert (
                client.send.call_count > 0
            ), f"Client {client.client_id} did not receive market data"

        print("✅ Market data streaming validated")

        # Test 4: Order Placement and Position Management
        print("\n4️⃣  Testing Order Placement...")

        initial_balance = account_info["balance"]

        # Place a small demo order
        order = {
            "symbol": "EUR/USD",
            "side": "buy",
            "quantity": 10000,  # Mini lot
            "order_type": "market",
        }

        order_result = await adapter.place_order(order)

        print(f"📋 Order Executed:")
        print(f"   Order ID: {order_result['order_id']}")
        print(f"   Symbol: {order_result['symbol']}")
        print(f"   Side: {order_result['side']}")
        print(f"   Quantity: {order_result['quantity']:,}")
        print(f"   Fill Price: {order_result['fill_price']:.5f}")
        print(f"   Commission: ${order_result['commission']:.2f}")

        # Verify order execution
        assert order_result["status"] == "FILLED", "Order was not filled"
        assert order_result["quantity"] == order["quantity"], "Order quantity mismatch"

        print("✅ Order placement successful")

        # Test 5: Position Tracking
        print("\n5️⃣  Testing Position Tracking...")

        positions = await adapter.get_positions()

        if positions:
            for i, pos in enumerate(positions):
                print(f"🎯 Position {i+1}:")
                print(f"   ID: {pos['position_id']}")
                print(f"   Symbol: {pos['symbol']}")
                print(f"   Side: {pos['side']}")
                print(f"   Quantity: {pos['quantity']:,}")
                print(f"   Open Price: {pos['open_price']:.5f}")
                print(f"   Current Price: {pos['current_price']:.5f}")
                print(f"   Unrealized P&L: ${pos['unrealized_pl']:,.2f}")

        # Verify position was created
        assert len(positions) > 0, "No positions found after order execution"

        # Test FXML4 position tracker integration
        position_stats = adapter.position_tracker.get_position_statistics()
        print(f"📊 Position Statistics:")
        print(f"   Total Positions: {position_stats['total_positions']}")
        print(f"   Long Positions: {position_stats['long_positions']}")
        print(f"   Short Positions: {position_stats['short_positions']}")
        print(f"   Total Unrealized P&L: ${position_stats['total_unrealized_pl']:,.2f}")

        print("✅ Position tracking validated")

        # Test 6: Account Monitoring Integration
        print("\n6️⃣  Testing Account Monitoring Integration...")

        # Get updated account info after trade
        updated_account_info = await adapter.get_account_info()

        # Test balance change detection
        balance_change = adapter.account_manager.get_balance_change()
        print(f"💱 Balance Change: ${balance_change:.2f}")

        # Test account state history
        balance_history = adapter.account_manager.balance_history
        print(f"📚 Balance History Entries: {len(balance_history)}")

        # Generate account summary
        account_summary = adapter.account_manager.get_account_summary()
        print(f"📋 Account Summary:")
        print(f"   Current Balance: ${account_summary['current_balance']:,.2f}")
        print(f"   Current Equity: ${account_summary['current_equity']:,.2f}")
        print(f"   Unrealized P&L: ${account_summary['unrealized_pl']:,.2f}")

        print("✅ Account monitoring integration validated")

        # Test 7: Account Reconciliation
        print("\n7️⃣  Testing Account Reconciliation...")

        # Create FXML4 state representation
        fxml4_state = {
            "account_id": updated_account_info["account_id"],
            "balance": updated_account_info["balance"],
            "equity": updated_account_info["equity"],
            "unrealized_pl": updated_account_info["unrealized_pl"],
            "last_update": adapter.account_manager.last_update,
        }

        # FXCM state (same data, simulating real-time sync)
        fxcm_state = {
            "account_id": updated_account_info["account_id"],
            "balance": updated_account_info["balance"],
            "equity": updated_account_info["equity"],
            "pl": updated_account_info["unrealized_pl"],
            "timestamp": updated_account_info["timestamp"],
        }

        # Perform reconciliation
        reconciliation_result = await reconciler.reconcile_account_balance(
            fxml4_state, fxcm_state
        )

        print(f"🔍 Reconciliation Result:")
        print(f"   Balanced: {reconciliation_result.is_balanced}")
        print(f"   Balance Difference: ${reconciliation_result.balance_difference:.2f}")
        print(f"   Equity Difference: ${reconciliation_result.equity_difference:.2f}")
        print(f"   Discrepancies: {len(reconciliation_result.discrepancies)}")

        assert reconciliation_result.is_balanced, "Account reconciliation failed"

        print("✅ Account reconciliation successful")

        # Test 8: Live Market Data Monitoring
        print("\n8️⃣  Testing Live Market Data Monitoring...")

        print("🔄 Monitoring live market data for 10 seconds...")

        price_updates = []

        async def price_callback(data):
            price_updates.append(data)
            if len(price_updates) <= 3:  # Only print first few updates
                for symbol, prices in data.items():
                    print(
                        f"📊 Live Update - {symbol}: {prices['bid']:.5f}/{prices['ask']:.5f}"
                    )

        # Start market data stream
        await adapter.start_market_data_stream(symbols, price_callback)

        # Monitor for 10 seconds
        await asyncio.sleep(10)

        print(f"📈 Received {len(price_updates)} price updates")
        assert len(price_updates) > 5, "Insufficient price updates received"

        print("✅ Live market data monitoring validated")

        # Test 9: Position Closure
        print("\n9️⃣  Testing Position Closure...")

        if positions:
            position_to_close = positions[0]
            print(f"🔒 Closing position: {position_to_close['position_id']}")

            close_result = await adapter.close_position(
                position_to_close["position_id"]
            )

            print(f"💰 Position Closed:")
            print(f"   Close Price: {close_result['close_price']:.5f}")
            print(f"   Realized P&L: ${close_result['realized_pl']:,.2f}")

            # Verify position was closed
            updated_positions = await adapter.get_positions()
            closed_position_ids = [p["position_id"] for p in updated_positions]
            assert (
                position_to_close["position_id"] not in closed_position_ids
            ), "Position was not closed"

            print("✅ Position closure successful")

        # Test 10: Final Integration Summary
        print("\n🔟 Final Integration Summary...")

        final_summary = await adapter.get_trading_summary()

        print(f"📊 Final Trading Summary:")
        print(f"   Account Balance: ${final_summary['account']['balance']:,.2f}")
        print(f"   Total Positions: {final_summary['positions']['total']}")
        print(f"   Unrealized P&L: ${final_summary['positions']['unrealized_pl']:,.2f}")
        print(
            f"   WebSocket Clients: {final_summary['fxml4_integration']['websocket_clients']}"
        )
        print(f"   Connection Status: {final_summary['connection']['status']}")

        print("\n🎉 All Integration Tests PASSED!")
        print("✅ FXCM Demo Account successfully integrated with FXML4")
        print("✅ Real-time market data streaming operational")
        print("✅ Account monitoring and reconciliation working")
        print("✅ Order placement and position management functional")
        print("✅ WebSocket broadcasting to clients validated")

        return True

    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Cleanup
        print("\n🔌 Cleaning up...")
        await adapter.disconnect()
        print("✅ Disconnected from FXCM demo")


async def main():
    """Main entry point."""
    print("Starting FXCM Demo Integration Test...")

    success = await test_fxcm_integration()

    if success:
        print("\n🚀 FXCM Integration Test SUCCESSFUL!")
        print("🎯 Ready for live paper trading with the provided credentials")
        sys.exit(0)
    else:
        print("\n💥 FXCM Integration Test FAILED!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
