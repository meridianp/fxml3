#!/bin/bash
set -e

# Add default data to FXML4 database
echo "📦 Adding Default Data to FXML4 Database"

# Database connection parameters
DB_HOST="postgres01.tailb381ec.ts.net"
DB_PORT="5432"
DB_USER="postgres"
DB_NAME="fxml4"

# Set password directly
export PGPASSWORD='0ctavian!'

echo "Adding default symbols and timeframes..."

psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<EOF
-- Insert default forex symbols
INSERT INTO symbols (name, display_name, asset_class) VALUES
    ('EURUSD', 'EUR/USD', 'forex'),
    ('GBPUSD', 'GBP/USD', 'forex'),
    ('USDJPY', 'USD/JPY', 'forex'),
    ('USDCHF', 'USD/CHF', 'forex'),
    ('AUDUSD', 'AUD/USD', 'forex'),
    ('USDCAD', 'USD/CAD', 'forex'),
    ('NZDUSD', 'NZD/USD', 'forex'),
    ('EURGBP', 'EUR/GBP', 'forex')
ON CONFLICT (name) DO NOTHING;

-- Insert default timeframes
INSERT INTO timeframes (name, minutes, display_name) VALUES
    ('1m', 1, '1 Minute'),
    ('5m', 5, '5 Minutes'),
    ('15m', 15, '15 Minutes'),
    ('30m', 30, '30 Minutes'),
    ('1h', 60, '1 Hour'),
    ('4h', 240, '4 Hours'),
    ('1d', 1440, '1 Day'),
    ('1w', 10080, '1 Week')
ON CONFLICT (name) DO NOTHING;

-- Show results
SELECT 'Symbols added:' as info, COUNT(*) as count FROM symbols;
SELECT 'Timeframes added:' as info, COUNT(*) as count FROM timeframes;
EOF

echo "✅ Default data added successfully!"
