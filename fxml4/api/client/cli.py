#!/usr/bin/env python3
"""Command-line interface for FXML4 API."""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict

from .client import FXML4Client
from .exceptions import FXML4Error


def print_json(data: Any, indent: int = 2) -> None:
    """Pretty print JSON data."""
    print(json.dumps(data, indent=indent, default=str))


def get_client(args) -> FXML4Client:
    """Create client from arguments."""
    api_key = args.api_key or os.environ.get("FXML4_API_KEY")
    if not api_key and not (args.username and args.password):
        print("Error: API key or username/password required")
        print("Set FXML4_API_KEY environment variable or use --api-key")
        sys.exit(1)

    return FXML4Client(
        base_url=args.base_url,
        api_key=api_key,
        username=args.username,
        password=args.password,
        version=args.version,
    )


def cmd_data(args):
    """Get market data."""
    client = get_client(args)

    try:
        data = client.get_data(
            symbol=args.symbol,
            timeframe=args.timeframe,
            start_date=args.start_date,
            end_date=args.end_date,
            limit=args.limit,
            page=args.page,
            page_size=args.page_size,
        )

        if args.output == "json":
            print_json(data)
        else:
            # Simple table format
            items = data.get("items", [])
            print(f"Symbol: {args.symbol}")
            print(f"Timeframe: {args.timeframe}")
            print(f"Data points: {len(items)}")
            print(
                "\nTimestamp           | Open    | High    | Low     | Close   | Volume"
            )
            print("-" * 75)
            for item in items[:10]:  # Show first 10
                print(
                    f"{item['timestamp']} | {item['open']:.5f} | {item['high']:.5f} | {item['low']:.5f} | {item['close']:.5f} | {item['volume']:>10}"
                )
            if len(items) > 10:
                print(f"... and {len(items) - 10} more")

    except FXML4Error as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_signals(args):
    """Generate trading signals."""
    client = get_client(args)

    try:
        response = client.generate_signals(
            symbol=args.symbol,
            timeframe=args.timeframe,
            strategy=args.strategy,
            confidence_threshold=args.confidence,
            lookback_periods=args.lookback,
            page=args.page,
            page_size=args.page_size,
        )

        if args.output == "json":
            print_json(response)
        else:
            signals = response.get("signals", [])
            print(f"Symbol: {args.symbol}")
            print(f"Strategy: {args.strategy}")
            print(f"Signals found: {len(signals)}")
            print(
                "\nTimestamp           | Type       | Confidence | Price   | Description"
            )
            print("-" * 80)
            for signal in signals:
                print(
                    f"{signal['timestamp']} | {signal['signal_type']:10} | {signal['confidence']:.3f}     | {signal['price']:.5f} | {signal['description'][:30]}..."
                )

    except FXML4Error as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_backtest(args):
    """Run backtest."""
    client = get_client(args)

    # Parse parameters
    params = {}
    if args.parameters:
        for param in args.parameters:
            key, value = param.split("=", 1)
            try:
                # Try to parse as JSON
                params[key] = json.loads(value)
            except:
                # Keep as string
                params[key] = value

    try:
        result = client.run_backtest(
            symbol=args.symbol,
            timeframe=args.timeframe,
            strategy=args.strategy,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_capital=args.capital,
            commission=args.commission,
            slippage=args.slippage,
            parameters=params,
            monte_carlo=args.monte_carlo,
            walk_forward=args.walk_forward,
        )

        if args.output == "json":
            print_json(result)
        else:
            perf = result["performance"]
            stats = result["trade_statistics"]

            print(f"Backtest ID: {result['backtest_id']}")
            print(f"Symbol: {result['symbol']}")
            print(f"Strategy: {result['strategy']}")
            print(f"Period: {result['period']['start']} to {result['period']['end']}")
            print("\nPerformance Summary:")
            print(
                f"  Total Return: ${perf['total_return']:.2f} ({perf['total_return_pct']:.2f}%)"
            )
            print(f"  Sharpe Ratio: {perf['sharpe_ratio']:.2f}")
            print(f"  Max Drawdown: {perf['max_drawdown_pct']:.2f}%")
            print(f"  Win Rate: {perf['win_rate']:.1%}")
            print("\nTrade Statistics:")
            print(f"  Total Trades: {stats['total_trades']}")
            print(f"  Winning Trades: {stats['winning_trades']}")
            print(f"  Average Win: ${stats['avg_win']:.2f}")
            print(f"  Average Loss: ${stats['avg_loss']:.2f}")

            if "monte_carlo" in result:
                mc = result["monte_carlo"]
                print("\nMonte Carlo Analysis:")
                print(f"  Probability of Profit: {mc['probability_of_profit']:.1%}")
                print(
                    f"  95% Confidence Return: {mc['confidence_intervals']['return_95']}"
                )

    except FXML4Error as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_health(args):
    """Check API health."""
    client = get_client(args)

    try:
        health = client.health_check()

        if args.output == "json":
            print_json(health)
        else:
            print(f"Status: {health['status']}")
            print(f"Version: {health['version']}")
            print("Services:")
            for service, status in health.get("services", {}).items():
                print(f"  {service}: {status}")

    except FXML4Error as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_version(args):
    """Get API version info."""
    client = get_client(args)

    try:
        info = client.get_version_info()

        if args.output == "json":
            print_json(info)
        else:
            print(f"Current Version: {info['current_version']}")
            print(f"Supported Versions: {', '.join(info['supported_versions'])}")
            print("\nVersion Details:")
            for version, details in info["versions"].items():
                print(f"\n{version}:")
                print(f"  Status: {details['status']}")
                if details.get("successor"):
                    print(f"  Successor: {details['successor']}")
                if details.get("changes"):
                    print(f"  Changes: {len(details['changes'])} items")

    except FXML4Error as e:
        print(f"Error: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="FXML4 API Command Line Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get market data
  fxml4 data EURUSD --timeframe 1h --start-date 2023-01-01 --end-date 2023-12-31

  # Generate signals
  fxml4 signals EURUSD --strategy ml_strategy --confidence 0.8

  # Run backtest
  fxml4 backtest EURUSD --strategy ml_strategy --start-date 2023-01-01 --end-date 2023-12-31

  # Check API health
  fxml4 health
        """,
    )

    # Global options
    parser.add_argument("--api-key", help="API key (or set FXML4_API_KEY)")
    parser.add_argument("--username", help="Username for authentication")
    parser.add_argument("--password", help="Password for authentication")
    parser.add_argument(
        "--base-url", default="https://api.fxml4.com", help="API base URL"
    )
    parser.add_argument("--version", default="v2", help="API version")
    parser.add_argument(
        "--output", choices=["json", "table"], default="table", help="Output format"
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Data command
    data_parser = subparsers.add_parser("data", help="Get market data")
    data_parser.add_argument("symbol", help="Trading symbol (e.g., EURUSD)")
    data_parser.add_argument("--timeframe", default="1h", help="Timeframe")
    data_parser.add_argument(
        "--start-date", required=True, help="Start date (YYYY-MM-DD)"
    )
    data_parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD)")
    data_parser.add_argument("--limit", type=int, help="Limit number of results")
    data_parser.add_argument("--page", type=int, default=1, help="Page number")
    data_parser.add_argument("--page-size", type=int, default=100, help="Page size")
    data_parser.set_defaults(func=cmd_data)

    # Signals command
    signals_parser = subparsers.add_parser("signals", help="Generate trading signals")
    signals_parser.add_argument("symbol", help="Trading symbol")
    signals_parser.add_argument("--timeframe", default="1h", help="Timeframe")
    signals_parser.add_argument(
        "--strategy", default="ml_strategy", help="Strategy to use"
    )
    signals_parser.add_argument(
        "--confidence", type=float, default=0.7, help="Confidence threshold"
    )
    signals_parser.add_argument(
        "--lookback", type=int, default=500, help="Lookback periods"
    )
    signals_parser.add_argument("--page", type=int, default=1, help="Page number")
    signals_parser.add_argument("--page-size", type=int, default=20, help="Page size")
    signals_parser.set_defaults(func=cmd_signals)

    # Backtest command
    backtest_parser = subparsers.add_parser("backtest", help="Run backtest")
    backtest_parser.add_argument("symbol", help="Trading symbol")
    backtest_parser.add_argument("--timeframe", default="1h", help="Timeframe")
    backtest_parser.add_argument("--strategy", default="ml_strategy", help="Strategy")
    backtest_parser.add_argument("--start-date", required=True, help="Start date")
    backtest_parser.add_argument("--end-date", required=True, help="End date")
    backtest_parser.add_argument(
        "--capital", type=float, default=10000, help="Initial capital"
    )
    backtest_parser.add_argument(
        "--commission", type=float, default=0.0002, help="Commission rate"
    )
    backtest_parser.add_argument(
        "--slippage", type=float, default=0.0001, help="Slippage rate"
    )
    backtest_parser.add_argument(
        "--parameters", nargs="+", help="Strategy parameters (key=value)"
    )
    backtest_parser.add_argument(
        "--monte-carlo", action="store_true", help="Run Monte Carlo"
    )
    backtest_parser.add_argument(
        "--walk-forward", action="store_true", help="Use walk-forward"
    )
    backtest_parser.set_defaults(func=cmd_backtest)

    # Health command
    health_parser = subparsers.add_parser("health", help="Check API health")
    health_parser.set_defaults(func=cmd_health)

    # Version command
    version_parser = subparsers.add_parser("version", help="Get API version info")
    version_parser.set_defaults(func=cmd_version)

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute command
    args.func(args)


if __name__ == "__main__":
    main()
