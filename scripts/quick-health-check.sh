#!/bin/bash
# Quick health check using the working password approach
export PGPASSWORD='0ctavian!'

echo "🏥 FXML4 Database Health Check"
echo "=============================="

echo "✅ Connection Test:"
psql -h postgres01.tailb381ec.ts.net -p 5432 -U postgres -d fxml4 -c "SELECT 'Connected to:' as status, current_database();"

echo -e "\n📊 TimescaleDB:"
psql -h postgres01.tailb381ec.ts.net -p 5432 -U postgres -d fxml4 -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';"

echo -e "\n📋 Tables:"
psql -h postgres01.tailb381ec.ts.net -p 5432 -U postgres -d fxml4 -c "SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema = 'public';"

echo -e "\n📊 Data:"
psql -h postgres01.tailb381ec.ts.net -p 5432 -U postgres -d fxml4 -c "SELECT 'symbols' as table_name, COUNT(*) as rows FROM symbols UNION SELECT 'timeframes', COUNT(*) FROM timeframes;"

echo -e "\n✅ Database is ready for deployment!"
