#!/bin/bash
# Setup script for correlation analysis libraries

echo "Setting up correlation analysis dependencies..."

# Install required packages
./venv/bin/pip install alpha-vantage fredapi

# Test imports
echo "Testing imports..."
./venv/bin/python -c "
try:
    from alpha_vantage.foreignexchange import ForeignExchange
    from fredapi import Fred
    print('✅ Alpha Vantage import successful')
    print('✅ FRED API import successful')
except ImportError as e:
    print(f'❌ Import error: {e}')
"

echo "Setup complete!"
