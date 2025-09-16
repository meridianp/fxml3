"""FXCM Demo Account Adapter for Paper Trading.

Integrates with the FXCM demo account using the provided credentials
and connects to the FXML4-ForexConnect bridge system.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

from ...api.account_monitoring import AccountStateManager, PositionTracker
from ...api.websocket_market_data import TickData, WebSocketMarketDataManager
from ..base_adapter import BaseBrokerAdapter


class FXCMDemoAdapter(BaseBrokerAdapter):
    """FXCM Demo Account adapter for paper trading integration."""

    def __init__(self, config_path: str = None):
        """Initialize FXCM demo adapter."""
        super().__init__()

        # Load credentials
        if config_path is None:
            config_path = (
                Path(__file__).parent.parent.parent.parent
                / "config"
                / "fxcm_demo_credentials.yaml"
            )

        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)["fxcm_demo"]

        # Connection details
        self.username = self.config["username"]
        self.password = self.config["password"]
        self.server = self.config["server"]

        # State management
        self.connected = False
        self.session_id = None
        self.account_info = {}
        self.positions = {}
        self.market_data_callbacks = []

        # Integration components
        self.account_manager = AccountStateManager()
        self.position_tracker = PositionTracker()
        self.ws_manager = WebSocketMarketDataManager()

        # Mock data for demo purposes (would be replaced with real FXCM API)
        self.mock_account_data = {
            "account_id": "FXCM_DEMO_001",
            "balance": 50000.00,
            "equity": 50000.00,
            "margin_used": 0.00,
            "margin_available": 50000.00,
            "unrealized_pl": 0.00,
            "currency": "USD",
        }

        self.mock_positions = []
        self.mock_price_data = {
            "EUR/USD": {"bid": 1.0850, "ask": 1.0852},
            "GBP/USD": {"bid": 1.2720, "ask": 1.2722},
            "USD/JPY": {"bid": 149.85, "ask": 149.87},
            "USD/CHF": {"bid": 0.8920, "ask": 0.8922},
            "AUD/USD": {"bid": 0.6580, "ask": 0.6582},
            "USD/CAD": {"bid": 1.3650, "ask": 1.3652},
            "NZD/USD": {"bid": 0.6120, "ask": 0.6122},
        }

        self.logger = logging.getLogger(__name__)
        self.logger.info(f"FXCM Demo Adapter initialized for {self.server}")

    async def connect(self) -> bool:
        """Connect to FXCM demo server."""
        try:
            self.logger.info(f"Connecting to FXCM demo server: {self.server}")
            self.logger.info(f"Username: {self.username}")

            # In a real implementation, this would use the FXCM API
            # For demo purposes, we'll simulate a successful connection
            await asyncio.sleep(1)  # Simulate connection time

            self.connected = True
            self.session_id = (
                f"FXCM_SESSION_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            )

            # Initialize account data
            self.account_info = self.mock_account_data.copy()
            self.account_info["timestamp"] = datetime.utcnow().isoformat()

            # Process initial account state
            await self.account_manager.process_forex_account_update(self.account_info)

            self.logger.info("Successfully connected to FXCM demo account")
            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to FXCM: {e}")
            self.connected = False
            return False

    async def disconnect(self) -> bool:
        """Disconnect from FXCM demo server."""
        try:
            self.logger.info("Disconnecting from FXCM demo server")

            # Cleanup resources
            self.connected = False
            self.session_id = None
            self.account_info = {}
            self.positions = {}

            self.logger.info("Successfully disconnected from FXCM")
            return True

        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
            return False

    async def get_account_info(self) -> Dict[str, Any]:
        """Get current account information."""
        if not self.connected:
            raise ConnectionError("Not connected to FXCM")

        # Update mock data with some variation
        current_time = datetime.utcnow()
        time_variation = (current_time.second % 10) - 5  # -5 to +4 variation

        self.mock_account_data["equity"] = self.mock_account_data["balance"] + (
            time_variation * 100
        )
        self.mock_account_data["unrealized_pl"] = time_variation * 100
        self.mock_account_data["timestamp"] = current_time.isoformat()

        # Process through account manager
        await self.account_manager.process_forex_account_update(self.mock_account_data)

        return self.mock_account_data.copy()

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions."""
        if not self.connected:
            raise ConnectionError("Not connected to FXCM")

        # Return mock positions (in real implementation, would query FXCM API)
        positions = []
        for pos in self.mock_positions:
            # Update position with current market prices
            symbol = pos["symbol"]
            if symbol in self.mock_price_data:
                current_price = self.mock_price_data[symbol][
                    "bid" if pos["side"] == "short" else "ask"
                ]
                pos["current_price"] = current_price

                # Calculate P&L
                price_diff = current_price - pos["open_price"]
                if pos["side"] == "short":
                    price_diff = -price_diff
                pos["unrealized_pl"] = price_diff * pos["quantity"]

                # Update timestamp
                pos["timestamp"] = datetime.utcnow().isoformat()

                # Process through position tracker
                await self.position_tracker.process_forex_position_update(pos)

            positions.append(pos)

        return positions

    async def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Place a trading order."""
        if not self.connected:
            raise ConnectionError("Not connected to FXCM")

        self.logger.info(f"Placing order: {order}")

        # Simulate order execution
        await asyncio.sleep(0.1)  # Simulate network latency

        # Create mock execution result
        execution_price = self.mock_price_data[order["symbol"]][
            "ask" if order["side"] == "buy" else "bid"
        ]

        order_result = {
            "order_id": f"FXCM_ORDER_{len(self.mock_positions) + 1:04d}",
            "status": "FILLED",
            "symbol": order["symbol"],
            "side": "long" if order["side"] == "buy" else "short",
            "quantity": order["quantity"],
            "fill_price": execution_price,
            "fill_time": datetime.utcnow().isoformat(),
            "commission": 2.50,
        }

        # Create position from order
        new_position = {
            "position_id": order_result["order_id"],
            "symbol": order["symbol"],
            "side": order_result["side"],
            "quantity": order["quantity"],
            "open_price": execution_price,
            "current_price": execution_price,
            "unrealized_pl": 0.0,
            "timestamp": datetime.utcnow().isoformat(),
        }

        self.mock_positions.append(new_position)

        # Update account balance (subtract commission)
        self.mock_account_data["balance"] -= order_result["commission"]
        self.mock_account_data["margin_used"] += (
            abs(order["quantity"]) * 0.02
        )  # 2% margin
        self.mock_account_data["margin_available"] = (
            self.mock_account_data["balance"] - self.mock_account_data["margin_used"]
        )

        # Process through position tracker
        await self.position_tracker.process_forex_position_update(new_position)

        self.logger.info(f"Order executed: {order_result}")
        return order_result

    async def close_position(self, position_id: str) -> Dict[str, Any]:
        """Close an existing position."""
        if not self.connected:
            raise ConnectionError("Not connected to FXCM")

        # Find position
        position = None
        for i, pos in enumerate(self.mock_positions):
            if pos["position_id"] == position_id:
                position = self.mock_positions.pop(i)
                break

        if not position:
            raise ValueError(f"Position {position_id} not found")

        # Calculate final P&L
        symbol = position["symbol"]
        close_price = self.mock_price_data[symbol][
            "bid" if position["side"] == "long" else "ask"
        ]

        price_diff = close_price - position["open_price"]
        if position["side"] == "short":
            price_diff = -price_diff

        realized_pl = price_diff * position["quantity"]

        # Update account balance
        self.mock_account_data["balance"] += realized_pl
        self.mock_account_data["margin_used"] -= abs(position["quantity"]) * 0.02
        self.mock_account_data["margin_available"] = (
            self.mock_account_data["balance"] - self.mock_account_data["margin_used"]
        )

        # Close position in tracker
        await self.position_tracker.close_position(
            position_id, close_price, realized_pl
        )

        close_result = {
            "position_id": position_id,
            "close_price": close_price,
            "realized_pl": realized_pl,
            "close_time": datetime.utcnow().isoformat(),
        }

        self.logger.info(f"Position closed: {close_result}")
        return close_result

    async def get_market_data(self, symbols: List[str]) -> Dict[str, Dict[str, float]]:
        """Get current market data for symbols."""
        if not self.connected:
            raise ConnectionError("Not connected to FXCM")

        # Update mock prices with small random movements
        import random

        current_time = datetime.utcnow()

        market_data = {}
        for symbol in symbols:
            if symbol in self.mock_price_data:
                # Add small random price movement
                base_bid = self.mock_price_data[symbol]["bid"]
                movement = random.uniform(-0.0005, 0.0005)  # ±0.5 pips

                new_bid = base_bid + movement
                new_ask = new_bid + 0.0002  # 2 pip spread

                self.mock_price_data[symbol] = {
                    "bid": round(new_bid, 5),
                    "ask": round(new_ask, 5),
                }

                market_data[symbol] = self.mock_price_data[symbol].copy()
                market_data[symbol]["timestamp"] = current_time.isoformat()

                # Create tick data for WebSocket broadcasting
                tick = TickData(
                    symbol=symbol, bid=new_bid, ask=new_ask, timestamp=current_time
                )

                # Broadcast to WebSocket clients
                await self.ws_manager.broadcast_to_symbol_subscribers(
                    symbol,
                    {
                        "type": "tick",
                        "symbol": symbol,
                        "bid": new_bid,
                        "ask": new_ask,
                        "mid": (new_bid + new_ask) / 2,
                        "timestamp": current_time.isoformat(),
                    },
                )

        return market_data

    async def start_market_data_stream(
        self, symbols: List[str], callback: Callable = None
    ):
        """Start real-time market data stream."""
        if not self.connected:
            raise ConnectionError("Not connected to FXCM")

        self.logger.info(f"Starting market data stream for: {symbols}")

        if callback:
            self.market_data_callbacks.append(callback)

        # Start background task for market data updates
        asyncio.create_task(self._market_data_updater(symbols))

    async def _market_data_updater(self, symbols: List[str]):
        """Background task to update market data."""
        while self.connected:
            try:
                # Get and broadcast updated market data
                market_data = await self.get_market_data(symbols)

                # Call registered callbacks
                for callback in self.market_data_callbacks:
                    try:
                        await callback(market_data)
                    except Exception as e:
                        self.logger.error(f"Market data callback error: {e}")

                # Update positions with new prices
                await self.get_positions()

                # Update account info
                await self.get_account_info()

                # Wait before next update
                await asyncio.sleep(1)  # 1 second updates

            except Exception as e:
                self.logger.error(f"Market data update error: {e}")
                await asyncio.sleep(5)  # Wait longer on error

    async def get_trading_summary(self) -> Dict[str, Any]:
        """Get comprehensive trading summary."""
        if not self.connected:
            raise ConnectionError("Not connected to FXCM")

        account_info = await self.get_account_info()
        positions = await self.get_positions()

        # Calculate summary statistics
        total_unrealized_pl = sum(pos.get("unrealized_pl", 0) for pos in positions)
        total_positions = len(positions)
        long_positions = len([p for p in positions if p["side"] == "long"])
        short_positions = len([p for p in positions if p["side"] == "short"])

        # Get account manager summary
        account_summary = self.account_manager.get_account_summary()

        # Get position tracker statistics
        position_stats = self.position_tracker.get_position_statistics()

        summary = {
            "account": account_info,
            "positions": {
                "total": total_positions,
                "long": long_positions,
                "short": short_positions,
                "unrealized_pl": total_unrealized_pl,
            },
            "fxml4_integration": {
                "account_summary": account_summary,
                "position_stats": position_stats,
                "websocket_clients": self.ws_manager.active_connections,
            },
            "connection": {
                "status": "connected" if self.connected else "disconnected",
                "server": self.server,
                "session_id": self.session_id,
                "last_update": datetime.utcnow().isoformat(),
            },
        }

        return summary


# Demo usage example
async def demo_fxcm_integration():
    """Demonstrate FXCM demo integration with FXML4."""
    print("🔗 FXCM Demo Integration with FXML4-ForexConnect Bridge")
    print("=" * 70)

    # Initialize adapter
    adapter = FXCMDemoAdapter()

    try:
        # Connect to FXCM demo
        print("\n1️⃣  Connecting to FXCM Demo Account...")
        connected = await adapter.connect()
        if not connected:
            print("❌ Failed to connect")
            return

        print(f"✅ Connected to {adapter.server}")
        print(f"📧 Account: {adapter.username}")

        # Get account information
        print("\n2️⃣  Retrieving Account Information...")
        account_info = await adapter.get_account_info()
        print(f"💰 Balance: ${account_info['balance']:,.2f}")
        print(f"💎 Equity: ${account_info['equity']:,.2f}")
        print(f"📊 Available Margin: ${account_info['margin_available']:,.2f}")

        # Start market data stream
        print("\n3️⃣  Starting Market Data Stream...")
        symbols = ["EUR/USD", "GBP/USD", "USD/JPY"]

        async def market_data_callback(data):
            for symbol, prices in data.items():
                print(f"📈 {symbol}: Bid={prices['bid']:.5f}, Ask={prices['ask']:.5f}")

        await adapter.start_market_data_stream(symbols, market_data_callback)

        # Let it run for a few updates
        print("🔄 Streaming market data for 10 seconds...")
        await asyncio.sleep(10)

        # Place a demo order
        print("\n4️⃣  Placing Demo Order...")
        order = {
            "symbol": "EUR/USD",
            "side": "buy",
            "quantity": 100000,  # 1 standard lot
            "order_type": "market",
        }

        order_result = await adapter.place_order(order)
        print(f"📋 Order Result: {order_result}")

        # Check positions
        print("\n5️⃣  Checking Positions...")
        positions = await adapter.get_positions()
        for pos in positions:
            print(
                f"🎯 Position: {pos['symbol']} {pos['side']} {pos['quantity']:,} @ {pos['open_price']:.5f}"
            )
            print(f"   Current P&L: ${pos['unrealized_pl']:,.2f}")

        # Get comprehensive summary
        print("\n6️⃣  Trading Summary...")
        summary = await adapter.get_trading_summary()

        print(f"📊 Account Balance: ${summary['account']['balance']:,.2f}")
        print(f"📈 Total Positions: {summary['positions']['total']}")
        print(f"💹 Total Unrealized P&L: ${summary['positions']['unrealized_pl']:,.2f}")
        print(
            f"🌐 WebSocket Clients: {summary['fxml4_integration']['websocket_clients']}"
        )

        # Wait a bit more for position updates
        print("\n⏱️  Monitoring for 5 more seconds...")
        await asyncio.sleep(5)

        # Close position
        if positions:
            print("\n7️⃣  Closing Position...")
            close_result = await adapter.close_position(positions[0]["position_id"])
            print(
                f"🔒 Position Closed: Realized P&L = ${close_result['realized_pl']:,.2f}"
            )

        print("\n✅ Demo Integration Complete!")

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        # Disconnect
        print("\n🔌 Disconnecting...")
        await adapter.disconnect()
        print("👋 Disconnected from FXCM demo")


if __name__ == "__main__":
    asyncio.run(demo_fxcm_integration())
