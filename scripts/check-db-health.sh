#\!/bin/bash
set -e

# FXML4 Database Health Check
echo "🏥 FXML4 Database Health Check"
echo "=============================="

# Database connection parameters
DB_HOST="postgres01.tailb381ec.ts.net"
DB_PORT="5432"
DB_USER="postgres"
DB_NAME="fxml4"

# Set password directly
export PGPASSWORD='0ctavian\!'

echo "🔗 Testing Connection..."
if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c 'SELECT 1;' > /dev/null 2>&1; then
    echo "✅ Database connection successful"
else
    echo "❌ Database connection failed"
    exit 1
fi

echo -e "\n📊 Database Information:"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<EOSQL
SELECT 'PostgreSQL Version:' as info, version();
SELECT 'Current Database:' as info, current_database();
SELECT 'Current User:' as info, current_user;
SELECT 'Connection Count:' as info, count(*) FROM pg_stat_activity WHERE datname = '$DB_NAME';
EOSQL

echo -e "\n🔧 TimescaleDB Status:"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<EOSQL
SELECT 'TimescaleDB Version:' as info, extversion FROM pg_extension WHERE extname = 'timescaledb';
EOSQL

echo -e "\n📋 Tables Summary:"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<EOSQL
SELECT
    'Regular Tables' as table_type,
    COUNT(*) as count
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_type = 'BASE TABLE'
AND table_name NOT IN (
    SELECT hypertable_name
    FROM timescaledb_information.hypertables
);

SELECT
    'Hypertables' as table_type,
    COUNT(*) as count
FROM timescaledb_information.hypertables;

SELECT 'Total Tables' as table_type, COUNT(*) as count
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
EOSQL

echo -e "\n📊 Data Summary:"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<EOSQL
SELECT 'Symbols' as table_name, COUNT(*) as rows FROM symbols;
SELECT 'Timeframes' as table_name, COUNT(*) as rows FROM timeframes;
EOSQL

echo -e "\n🏥 Health Status: ✅ HEALTHY"
echo "Database is ready for FXML4 deployment\!"
EOF < /dev/null
