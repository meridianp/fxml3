# Supabase Integration for FXML3

This document explains how to set up and use the Supabase integration for FXML3.

## Overview

FXML3 uses [Supabase](https://supabase.com) for:

1. User authentication
2. Data persistence for wave analyses, strategies, and backtests
3. API key management
4. Asynchronous task processing

## Setup Instructions

Follow these steps to set up the Supabase integration:

### 1. Environment Variables

Ensure the following environment variables are set in your `.env` file:

```
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key
POSTGRES_USERNAME=postgres.your-project-ref
POSTGRES_PASSWORD=your-postgres-password
POSTGRES_HOST=your-postgres-host
POSTGRES_PORT=5432
POSTGRES_DB_NAME=postgres
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
ALLOWED_ORIGINS=*
```

You can use the `update_env.py` script to add the JWT-related variables to your `.env` file:

```bash
python update_env.py
```

### 2. Database Setup

Run the database setup script to create the necessary tables in your Supabase instance:

```bash
python setup_supabase.py
```

This will run the migrations in the `fxml3/api/db/migrations/` directory.

### 3. Test Connection

You can test your connection to Supabase with:

```bash
python test_supabase_connection.py
```

## Database Schema

The Supabase integration creates the following tables in a dedicated `fxml3` schema:

1. `api_keys` - Stores API keys for authentication
2. `wave_analyses` - Stores wave analyses
3. `strategies` - Stores trading strategies
4. `backtests` - Stores backtest results
5. `tasks` - Stores background task status and results

## Using the API

The API is built with FastAPI and provides endpoints for:

- User authentication (JWT tokens and API keys)
- Wave analysis creation and retrieval
- Strategy creation and retrieval
- Backtest creation and retrieval
- Task status monitoring

You can interact with the API using the SwaggerUI at `/docs` when the API is running.

## Running the API

To run the API server:

```bash
python run_api.py
```

This will start the server on http://127.0.0.1:8787 by default. You can change the host and port in the .env file:

```
API_HOST=127.0.0.1
API_PORT=8787
API_RELOAD=true
```

## Security

The Supabase integration uses Row Level Security (RLS) to ensure that users can only access their own data. Each table has RLS policies that restrict access based on the authenticated user's ID.