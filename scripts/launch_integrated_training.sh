#!/bin/bash
# Launch script for integrated forex system training

echo "========================================================================"
echo "INTEGRATED FOREX SYSTEM TRAINING LAUNCHER"
echo "========================================================================"
echo ""
echo "This script will train the complete integrated forex trading system with:"
echo "- Enhanced ML models (RF, XGBoost, LightGBM, Neural Networks)"
echo "- Elliott Wave pattern recognition"
echo "- Endogenous/exogenous variable analysis"
echo "- Correlation-based portfolio optimization"
echo "- Forex-specific position sizing ($25k min, 40:1 leverage)"
echo ""
echo "Training will use 3 years of historical data for:"
echo "EURUSD, GBPUSD, USDJPY, USDCHF"
echo ""
echo "========================================================================"

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Install any missing dependencies
echo ""
echo "Checking dependencies..."
./venv/bin/pip install -q alpha-vantage fredapi 2>/dev/null

# Create necessary directories
mkdir -p models/integrated_system
mkdir -p output/integrated_backtest
mkdir -p logs

# Set environment variables for better performance
export PYTHONWARNINGS="ignore"
export TF_CPP_MIN_LOG_LEVEL=2  # Reduce TensorFlow verbosity

# Run the training
echo ""
echo "Starting integrated system training..."
echo "This may take 30-60 minutes depending on your hardware."
echo ""
echo "Logging to: logs/integrated_training_$(date +%Y%m%d_%H%M%S).log"
echo ""

# Run training with output to both console and log file
./venv/bin/python scripts/train_integrated_system.py 2>&1 | tee logs/integrated_training_$(date +%Y%m%d_%H%M%S).log

# Check if training was successful
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo ""
    echo "✅ Training completed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Run backtest: ./venv/bin/python scripts/backtest_integrated_system.py"
    echo "2. View results: ls -la output/integrated_backtest/"
    echo "3. Start paper trading: ./venv/bin/python scripts/integrated_forex_system.py"
else
    echo ""
    echo "❌ Training failed! Check the log file for errors."
fi
