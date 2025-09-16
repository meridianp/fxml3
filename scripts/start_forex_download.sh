#!/bin/bash
# Start the 10-year forex data download process

echo "======================================"
echo "10-Year Forex Data Download Manager"
echo "======================================"
echo ""
echo "This script will download 10 years of minute-level forex data"
echo "for 16 major currency pairs from Polygon.io"
echo ""
echo "Estimated data size: ~60-80 GB"
echo "Estimated time: 24-48 hours (with rate limits)"
echo ""

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Check for API key
if [[ -z "${POLYGON_API_KEY}" ]]; then
    echo "Loading environment variables..."
    source .env
    export POLYGON_API_KEY
fi

echo "Using API key: ${POLYGON_API_KEY:0:10}..."
echo ""

# Create log directory
mkdir -p logs

# Set log file with timestamp
LOG_FILE="logs/forex_download_$(date +%Y%m%d_%H%M%S).log"

echo "Log file: $LOG_FILE"
echo ""

# Options
echo "Select download option:"
echo "1) Test download (1 month of EURUSD)"
echo "2) Download priority pairs (EURUSD, GBPUSD, USDJPY, AUDUSD - 10 years)"
echo "3) Download all 16 pairs (10 years)"
echo "4) Resume interrupted download"
echo "5) Validate downloaded data"
echo ""

read -p "Enter option (1-5): " option

case $option in
    1)
        echo "Starting test download..."
        python scripts/download_10year_forex_data.py test --symbol EURUSD 2>&1 | tee $LOG_FILE
        ;;
    2)
        echo "Starting priority pairs download..."
        echo "This will take approximately 6-8 hours with rate limits"
        read -p "Continue? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            python scripts/download_10year_forex_data.py download \
                --symbols "EURUSD,GBPUSD,USDJPY,AUDUSD" \
                --years 10 2>&1 | tee $LOG_FILE
        fi
        ;;
    3)
        echo "Starting full download of all 16 pairs..."
        echo "This will take approximately 24-48 hours with rate limits"
        read -p "Continue? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            # Run in background with nohup for long download
            nohup python scripts/download_10year_forex_data.py download --years 10 \
                > $LOG_FILE 2>&1 &
            echo "Download started in background. PID: $!"
            echo "Monitor progress with: tail -f $LOG_FILE"
        fi
        ;;
    4)
        echo "Resuming download from saved progress..."
        python scripts/download_10year_forex_data.py resume 2>&1 | tee $LOG_FILE
        ;;
    5)
        echo "Validating downloaded data..."
        python scripts/download_10year_forex_data.py validate
        ;;
    *)
        echo "Invalid option"
        exit 1
        ;;
esac

echo ""
echo "Done!"
