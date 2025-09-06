# FXML3 Supabase Integration

## Overview

This integration adds database persistence and authentication to FXML3 using Supabase. The implementation includes:

1. **Database Schema**: A complete PostgreSQL schema with tables for storing:
   - User data and API keys
   - Wave analyses
   - Trading strategies
   - Backtests
   - Background tasks

2. **Authentication**: Support for both JWT tokens and API keys

3. **API Layer**: A REST API built with FastAPI that exposes endpoints for:
   - User authentication
   - Wave analysis creation and retrieval
   - Strategy creation and retrieval  
   - Backtest creation and retrieval
   - Task status monitoring

4. **Security**: Row Level Security (RLS) policies to ensure data isolation between users

## Files Implemented

1. **Database Migration**:
   - `/fxml3/api/db/migrations/001_initial_schema.sql` - SQL schema definition
   - `/fxml3/api/db/migrations/run_migrations.py` - Migration runner

2. **API Modules**:
   - `/fxml3/api/main.py` - FastAPI application with endpoints
   - `/fxml3/api/auth.py` - Authentication module
   - `/fxml3/api/db.py` - Database repositories
   - `/fxml3/api/tasks.py` - Async task processing

3. **Setup Scripts**:
   - `/setup_supabase.py` - Setup Supabase schema
   - `/update_env.py` - Update environment variables
   - `/test_supabase_connection.py` - Test Supabase connection
   - `/run_api.py` - Run the API server
   - `/initialize_fxml3.py` - Initialize the entire system

4. **Documentation**:
   - `/SUPABASE_SETUP.md` - Setup instructions
   - `/README_SUPABASE.md` - This file

## Setup Instructions

1. **Ensure your .env file has Supabase credentials**:
   ```
   SUPABASE_URL=https://your-project-ref.supabase.co
   SUPABASE_ANON_KEY=your-anon-key
   SUPABASE_SERVICE_KEY=your-service-key
   POSTGRES_USERNAME=postgres.your-project-ref
   POSTGRES_PASSWORD=your-postgres-password
   POSTGRES_HOST=your-postgres-host
   POSTGRES_PORT=5432
   POSTGRES_DB_NAME=postgres
   ```

2. **Run the initialization script**:
   ```bash
   python initialize_fxml3.py
   ```
   This will:
   - Update your .env file with additional variables
   - Install dependencies
   - Test Supabase connection
   - Set up the database schema

3. **Start the API server**:
   ```bash
   python run_api.py
   ```

4. **Access the API documentation**:
   Open your browser to http://127.0.0.1:8787/docs

## API Usage Examples

### Authentication

```python
import requests

# Get JWT token
response = requests.post(
    "http://127.0.0.1:8787/token",
    data={"username": "user@example.com", "password": "password"}
)
token = response.json()["access_token"]

# Use token for authenticated requests
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(
    "http://127.0.0.1:8787/api/v1/user/me",
    headers=headers
)
user_data = response.json()
```

### Create Wave Analysis

```python
response = requests.post(
    "http://127.0.0.1:8787/api/v1/analysis/waves",
    headers=headers,
    json={
        "symbol": "EURUSD",
        "timeframe": "H4",
        "start_date": "2023-01-01",
        "end_date": "2023-06-30",
        "wave_options": {
            "include_subwaves": True,
            "min_wave_points": 5,
            "confidence_threshold": 0.7
        }
    }
)
task_data = response.json()["data"]
task_id = task_data["task_id"]
```

### Check Task Status

```python
response = requests.get(
    f"http://127.0.0.1:8787/api/v1/tasks/{task_id}",
    headers=headers
)
task_status = response.json()["data"]["status"]
```

## Architecture Notes

1. **Repository Pattern**: Each entity has its own repository for database access
2. **Async Design**: All database operations are async for better performance
3. **Background Processing**: Long-running tasks are executed asynchronously
4. **Standardized Responses**: All API endpoints return standardized JSON responses

## Next Steps

1. **UI Integration**: Update the Streamlit UI to work with the API
2. **Testing**: Add integration tests for the API endpoints
3. **Deployment**: Set up Docker containers for deployment