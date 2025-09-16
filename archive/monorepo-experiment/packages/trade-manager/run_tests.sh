#!/bin/bash

# Run tests for Trade Manager package

echo "Running Trade Manager tests..."

# Navigate to package directory
cd "$(dirname "$0")"

# Install test dependencies if needed
poetry install --with dev

# Run tests with coverage
echo "Running unit tests..."
poetry run pytest tests/ -v --cov=fxml4_trade_manager --cov-report=term-missing

# Run specific test categories
echo ""
echo "Running position manager tests..."
poetry run pytest tests/test_position_manager.py -v

echo ""
echo "Running risk monitor tests..."
poetry run pytest tests/test_risk_monitor.py -v

echo ""
echo "Running P&L tracker tests..."
poetry run pytest tests/test_pnl_tracker.py -v

echo ""
echo "Running exit strategy tests..."
poetry run pytest tests/test_exit_strategy_manager.py -v

echo ""
echo "Running integration tests..."
poetry run pytest tests/test_integration.py -v -m integration

# Generate HTML coverage report
poetry run pytest tests/ --cov=fxml4_trade_manager --cov-report=html

echo ""
echo "Test run complete! Coverage report available in htmlcov/index.html"