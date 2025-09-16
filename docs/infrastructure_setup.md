# FXML4 Infrastructure Setup Guide

This document outlines the steps to set up the necessary infrastructure for FXML4, including PostgreSQL databases, Supabase integration, and Google Cloud resources.

## Database Setup

### Local PostgreSQL with TimescaleDB Setup

There are two ways to set up TimescaleDB:

#### Option 1: Docker (Recommended)

```bash
# Pull and run TimescaleDB in a Docker container
docker run -d --name timescaledb -p 5433:5432 \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=fxml4 \
  -v timescaledb_data:/var/lib/postgresql/data \
  timescale/timescaledb:latest-pg14

# Apply migrations
docker exec -i timescaledb psql -U postgres -d fxml4 < db/migrations/001_initial_schema.sql
docker exec -i timescaledb psql -U postgres -d fxml4 < db/migrations/002_add_tick_data_schema.sql

# Connect to TimescaleDB
docker exec -it timescaledb psql -U postgres -d fxml4
```

#### Option 2: Native Installation

```bash
# For MacOS
brew tap timescale/tap
brew install timescaledb
timescaledb-tune --quiet --yes

# For Ubuntu
# Add PostgreSQL repository
sudo sh -c "echo 'deb https://apt.postgresql.org/pub/repos/apt/ $(lsb_release -c -s)-pgdg main' > /etc/apt/sources.list.d/pgdg.list"
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt-get update

# Install PostgreSQL and TimescaleDB
sudo apt-get install -y postgresql-14 postgresql-14-timescaledb-2.8

# Start PostgreSQL service
sudo systemctl restart postgresql

# Create database
psql -U postgres -c "CREATE DATABASE fxml4;"
psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"

# Apply migrations
psql -U postgres -d fxml4 -f db/migrations/001_initial_schema.sql
psql -U postgres -d fxml4 -f db/migrations/002_add_tick_data_schema.sql
```

### Supabase Integration

```bash
# Install Supabase CLI if not already installed
npm install -g supabase

# Login to Supabase
supabase login

# Initialize Supabase project
supabase init

# Link to existing Supabase project
supabase link --project-ref <your-project-reference>

# Generate database types
supabase gen types typescript > fxml4/api/types/supabase.ts

# Apply migrations
supabase db push
```

## Google Cloud Setup

### Initial Setup

```bash
# Install gcloud CLI if not already installed
# https://cloud.google.com/sdk/docs/install

# Login to Google Cloud
gcloud auth login

# Set default project
gcloud config set project <your-project-id>

# Enable required APIs
gcloud services enable compute.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable container.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

### Configure Docker for GCP

```bash
# Configure Docker to use gcloud as a credential helper
gcloud auth configure-docker

# Create Artifact Registry repository
gcloud artifacts repositories create fxml4-repo \
    --repository-format=docker \
    --location=us-central1 \
    --description="FXML4 Docker repository"
```

### Set Up GKE Cluster

```bash
# Create GKE cluster
gcloud container clusters create fxml4-cluster \
    --num-nodes=3 \
    --machine-type=e2-standard-4 \
    --region=us-central1

# Get credentials for kubectl
gcloud container clusters get-credentials fxml4-cluster --region=us-central1

# Create namespace
kubectl create namespace fxml4
```

## Continuous Integration Setup

### GitHub Actions Workflow

Create `.github/workflows/ci.yml`:

```yaml
name: FXML4 CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: fxml4_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov

    - name: Test with pytest
      run: |
        pytest --cov=fxml4 --cov-report=xml

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        fail_ci_if_error: true

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && (github.ref == 'refs/heads/main' || github.ref == 'refs/heads/develop')

    steps:
    - uses: actions/checkout@v3

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v2

    - name: Login to DockerHub
      uses: docker/login-action@v2
      with:
        username: ${{ secrets.DOCKERHUB_USERNAME }}
        password: ${{ secrets.DOCKERHUB_TOKEN }}

    - name: Build and push
      uses: docker/build-push-action@v4
      with:
        context: .
        push: true
        tags: yourusername/fxml4:latest
```

## Configuration Scripts

### Database Initialization

Create `scripts/init_db.py`:

```python
#!/usr/bin/env python3
"""
Database initialization script for FXML4.

This script creates the necessary database schema for FXML4,
migrates data from FXML2 and FXML3 databases, and sets up
initial configurations.
"""

import argparse
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_connection(db_name="postgres"):
    """Get a connection to the PostgreSQL database."""
    return psycopg2.connect(
        host=os.getenv("FXML4_DATABASE_HOST", "localhost"),
        port=os.getenv("FXML4_DATABASE_PORT", "5432"),
        user=os.getenv("FXML4_DATABASE_USER", "postgres"),
        password=os.getenv("FXML4_DATABASE_PASSWORD", "postgres"),
        database=db_name
    )

def create_database():
    """Create the FXML4 database if it doesn't exist."""
    db_name = os.getenv("FXML4_DATABASE_NAME", "fxml4")

    # Connect to postgres database
    conn = get_connection()
    conn.autocommit = True
    cursor = conn.cursor()

    # Check if database exists
    cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
    exists = cursor.fetchone()

    if not exists:
        print(f"Creating database {db_name}")
        cursor.execute(f"CREATE DATABASE {db_name}")
        print(f"Database {db_name} created successfully")
    else:
        print(f"Database {db_name} already exists")

    cursor.close()
    conn.close()

def apply_migrations():
    """Apply database migrations."""
    db_name = os.getenv("FXML4_DATABASE_NAME", "fxml4")

    # Connect to the FXML4 database
    conn = get_connection(db_name)
    conn.autocommit = True
    cursor = conn.cursor()

    # Get migration files
    project_root = Path(__file__).parent.parent
    migrations_dir = project_root / "db" / "migrations"
    migration_files = sorted([f for f in migrations_dir.glob("*.sql")])

    # Create migrations table if it doesn't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS migrations (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Get applied migrations
    cursor.execute("SELECT name FROM migrations")
    applied_migrations = {row[0] for row in cursor.fetchall()}

    # Apply migrations
    for migration_file in migration_files:
        migration_name = migration_file.name

        if migration_name in applied_migrations:
            print(f"Migration {migration_name} already applied")
            continue

        print(f"Applying migration {migration_name}")

        # Read and execute migration
        with open(migration_file, "r") as f:
            migration_sql = f.read()
            cursor.execute(migration_sql)

        # Record migration
        cursor.execute(
            "INSERT INTO migrations (name) VALUES (%s)",
            (migration_name,)
        )

        print(f"Migration {migration_name} applied successfully")

    cursor.close()
    conn.close()

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Initialize FXML4 database")
    parser.add_argument("--skip-create", action="store_true", help="Skip database creation")
    parser.add_argument("--skip-migrations", action="store_true", help="Skip migrations")
    args = parser.parse_args()

    try:
        if not args.skip_create:
            create_database()

        if not args.skip_migrations:
            apply_migrations()

        print("Database initialization completed successfully")
        return 0
    except Exception as e:
        print(f"Error initializing database: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
```

### Supabase Setup

Create `scripts/setup_supabase.py`:

```python
#!/usr/bin/env python3
"""
Supabase setup script for FXML4.

This script initializes the Supabase project for FXML4,
sets up authentication, and creates necessary tables and functions.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_command(command):
    """Run a shell command and return the output."""
    print(f"Running: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return None
    return result.stdout.strip()

def check_supabase_cli():
    """Check if Supabase CLI is installed."""
    result = run_command("supabase --version")
    if not result:
        print("Supabase CLI not found. Please install it first.")
        print("npm install -g supabase")
        return False
    return True

def login_to_supabase():
    """Log in to Supabase if not already logged in."""
    # Check if already logged in
    result = run_command("supabase projects list")
    if result:
        print("Already logged in to Supabase")
        return True

    # Get access token
    token = os.getenv("SUPABASE_ACCESS_TOKEN")
    if not token:
        print("SUPABASE_ACCESS_TOKEN not found in environment variables.")
        print("Please login manually: supabase login")
        return False

    # Login with token
    result = run_command(f"supabase login {token}")
    if not result:
        return False

    print("Logged in to Supabase successfully")
    return True

def link_project():
    """Link to existing Supabase project."""
    project_ref = os.getenv("SUPABASE_PROJECT_REF")
    if not project_ref:
        print("SUPABASE_PROJECT_REF not found in environment variables.")
        return False

    # Check if already linked
    if Path(".supabase").exists():
        print("Project already linked to Supabase")
        return True

    # Link project
    result = run_command(f"supabase link --project-ref {project_ref}")
    if not result:
        return False

    print("Project linked to Supabase successfully")
    return True

def generate_types():
    """Generate TypeScript types from Supabase schema."""
    output_dir = Path("fxml4") / "api" / "types"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "supabase.ts"

    result = run_command(f"supabase gen types typescript > {output_file}")
    if not result:
        return False

    print(f"TypeScript types generated at {output_file}")
    return True

def apply_migrations():
    """Apply migrations to Supabase project."""
    result = run_command("supabase db push")
    if not result:
        return False

    print("Migrations applied successfully")
    return True

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Set up Supabase for FXML4")
    parser.add_argument("--skip-login", action="store_true", help="Skip Supabase login")
    parser.add_argument("--skip-link", action="store_true", help="Skip project linking")
    parser.add_argument("--skip-types", action="store_true", help="Skip type generation")
    parser.add_argument("--skip-migrations", action="store_true", help="Skip migrations")
    args = parser.parse_args()

    # Check Supabase CLI
    if not check_supabase_cli():
        return 1

    # Steps to run
    steps = []

    if not args.skip_login:
        steps.append(("Login to Supabase", login_to_supabase))

    if not args.skip_link:
        steps.append(("Link Supabase project", link_project))

    if not args.skip_migrations:
        steps.append(("Apply migrations", apply_migrations))

    if not args.skip_types:
        steps.append(("Generate TypeScript types", generate_types))

    # Run steps
    for description, func in steps:
        print(f"\n=== {description} ===")
        if not func():
            print(f"Error during {description}. Exiting.")
            return 1

    print("\n=== Setup completed successfully ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### Google Cloud Setup

Create `scripts/setup_gcloud.py`:

```python
#!/usr/bin/env python3
"""
Google Cloud setup script for FXML4.

This script sets up Google Cloud resources for FXML4,
including GKE cluster, Artifact Registry, and IAM permissions.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_command(command):
    """Run a shell command and return the output."""
    print(f"Running: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return None
    return result.stdout.strip()

def check_gcloud_cli():
    """Check if gcloud CLI is installed."""
    result = run_command("gcloud --version")
    if not result:
        print("gcloud CLI not found. Please install it first.")
        print("https://cloud.google.com/sdk/docs/install")
        return False
    return True

def login_to_gcloud():
    """Log in to Google Cloud if not already logged in."""
    # Check if already logged in
    result = run_command("gcloud auth list --filter=status:ACTIVE --format='value(account)'")
    if result:
        print(f"Already logged in to Google Cloud as {result}")
        return True

    # Login interactively
    result = run_command("gcloud auth login")
    if not result:
        return False

    print("Logged in to Google Cloud successfully")
    return True

def set_project():
    """Set the default Google Cloud project."""
    project_id = os.getenv("GCLOUD_PROJECT_ID")
    if not project_id:
        print("GCLOUD_PROJECT_ID not found in environment variables.")
        return False

    result = run_command(f"gcloud config set project {project_id}")
    if not result:
        return False

    print(f"Default project set to {project_id}")
    return True

def enable_apis():
    """Enable required Google Cloud APIs."""
    apis = [
        "compute.googleapis.com",
        "containerregistry.googleapis.com",
        "container.googleapis.com",
        "artifactregistry.googleapis.com",
        "cloudbuild.googleapis.com",
    ]

    for api in apis:
        print(f"Enabling {api}")
        result = run_command(f"gcloud services enable {api}")
        if not result:
            return False

    print("APIs enabled successfully")
    return True

def create_artifact_registry():
    """Create Artifact Registry repository."""
    project_id = os.getenv("GCLOUD_PROJECT_ID")
    repo_name = os.getenv("GCLOUD_REPO_NAME", "fxml4-repo")
    location = os.getenv("GCLOUD_LOCATION", "us-central1")

    # Check if repository already exists
    result = run_command(
        f"gcloud artifacts repositories describe {repo_name} --location={location}"
    )
    if result:
        print(f"Repository {repo_name} already exists")
        return True

    # Create repository
    result = run_command(
        f"gcloud artifacts repositories create {repo_name} "
        f"--repository-format=docker --location={location} "
        f"--description='FXML4 Docker repository'"
    )
    if not result:
        return False

    print(f"Repository {repo_name} created successfully")
    return True

def create_gke_cluster():
    """Create GKE cluster."""
    project_id = os.getenv("GCLOUD_PROJECT_ID")
    cluster_name = os.getenv("GCLOUD_CLUSTER_NAME", "fxml4-cluster")
    location = os.getenv("GCLOUD_LOCATION", "us-central1")

    # Check if cluster already exists
    result = run_command(
        f"gcloud container clusters describe {cluster_name} --region={location}"
    )
    if result:
        print(f"Cluster {cluster_name} already exists")
        return True

    # Create cluster
    result = run_command(
        f"gcloud container clusters create {cluster_name} "
        f"--num-nodes=3 --machine-type=e2-standard-4 --region={location}"
    )
    if not result:
        return False

    print(f"Cluster {cluster_name} created successfully")

    # Get credentials for kubectl
    result = run_command(
        f"gcloud container clusters get-credentials {cluster_name} --region={location}"
    )
    if not result:
        return False

    # Create namespace
    result = run_command("kubectl create namespace fxml4")

    return True

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Set up Google Cloud for FXML4")
    parser.add_argument("--skip-login", action="store_true", help="Skip Google Cloud login")
    parser.add_argument("--skip-project", action="store_true", help="Skip project setting")
    parser.add_argument("--skip-apis", action="store_true", help="Skip API enabling")
    parser.add_argument("--skip-registry", action="store_true", help="Skip Artifact Registry creation")
    parser.add_argument("--skip-cluster", action="store_true", help="Skip GKE cluster creation")
    args = parser.parse_args()

    # Check gcloud CLI
    if not check_gcloud_cli():
        return 1

    # Steps to run
    steps = []

    if not args.skip_login:
        steps.append(("Login to Google Cloud", login_to_gcloud))

    if not args.skip_project:
        steps.append(("Set default project", set_project))

    if not args.skip_apis:
        steps.append(("Enable required APIs", enable_apis))

    if not args.skip_registry:
        steps.append(("Create Artifact Registry repository", create_artifact_registry))

    if not args.skip_cluster:
        steps.append(("Create GKE cluster", create_gke_cluster))

    # Run steps
    for description, func in steps:
        print(f"\n=== {description} ===")
        if not func():
            print(f"Error during {description}. Exiting.")
            return 1

    print("\n=== Setup completed successfully ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

## Database Schema

Create `db/migrations/001_initial_schema.sql`:

```sql
-- FXML4 Initial Database Schema

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE
);

-- Create symbols table
CREATE TABLE IF NOT EXISTS symbols (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create timeframes table
CREATE TABLE IF NOT EXISTS timeframes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT UNIQUE NOT NULL,
    minutes INTEGER NOT NULL,
    display_name TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create models table
CREATE TABLE IF NOT EXISTS models (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    model_type TEXT NOT NULL,
    symbol_id UUID REFERENCES symbols(id),
    timeframe_id UUID REFERENCES timeframes(id),
    metadata JSONB,
    file_path TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (name, version)
);

-- Create signals table
CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol_id UUID REFERENCES symbols(id),
    timeframe_id UUID REFERENCES timeframes(id),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    signal_type TEXT NOT NULL,
    direction TEXT NOT NULL,
    strength FLOAT NOT NULL,
    source TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create backtests table
CREATE TABLE IF NOT EXISTS backtests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    user_id UUID REFERENCES users(id),
    symbol_id UUID REFERENCES symbols(id),
    timeframe_id UUID REFERENCES timeframes(id),
    strategy TEXT NOT NULL,
    start_date TIMESTAMP WITH TIME ZONE NOT NULL,
    end_date TIMESTAMP WITH TIME ZONE NOT NULL,
    initial_capital FLOAT NOT NULL,
    final_capital FLOAT NOT NULL,
    total_return FLOAT NOT NULL,
    total_return_pct FLOAT NOT NULL,
    max_drawdown FLOAT NOT NULL,
    sharpe_ratio FLOAT NOT NULL,
    sortino_ratio FLOAT NOT NULL,
    win_rate FLOAT NOT NULL,
    parameters JSONB,
    results JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create backtest_trades table
CREATE TABLE IF NOT EXISTS backtest_trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    backtest_id UUID REFERENCES backtests(id),
    entry_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    exit_timestamp TIMESTAMP WITH TIME ZONE,
    direction TEXT NOT NULL,
    entry_price FLOAT NOT NULL,
    exit_price FLOAT,
    quantity FLOAT NOT NULL,
    pnl FLOAT,
    pnl_pct FLOAT,
    status TEXT NOT NULL,
    metadata JSONB
);

-- Create api_keys table
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    scopes TEXT[] NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE
);

-- Create RLS policies
-- Enable Row Level Security
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtests ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY user_self_access ON users
    USING (id = auth.uid());

CREATE POLICY backtest_owner_access ON backtests
    USING (user_id = auth.uid());

CREATE POLICY backtest_trades_via_backtest ON backtest_trades
    USING (backtest_id IN (SELECT id FROM backtests WHERE user_id = auth.uid()));

CREATE POLICY api_key_owner_access ON api_keys
    USING (user_id = auth.uid());

-- Create initial data
INSERT INTO timeframes (name, minutes, display_name) VALUES
    ('1m', 1, '1 Minute'),
    ('5m', 5, '5 Minutes'),
    ('15m', 15, '15 Minutes'),
    ('30m', 30, '30 Minutes'),
    ('1h', 60, '1 Hour'),
    ('4h', 240, '4 Hours'),
    ('1d', 1440, '1 Day')
ON CONFLICT (name) DO NOTHING;

INSERT INTO symbols (name, display_name, asset_class) VALUES
    ('EURUSD', 'EUR/USD', 'forex'),
    ('GBPUSD', 'GBP/USD', 'forex'),
    ('USDJPY', 'USD/JPY', 'forex'),
    ('AUDUSD', 'AUD/USD', 'forex')
ON CONFLICT (name) DO NOTHING;
```

## Updated Implementation Steps

With the infrastructure setup in mind, here's how we should update our implementation steps:

1. **Database and Infrastructure Setup**
   - Run `scripts/init_db.py` to set up PostgreSQL database
   - Run `scripts/setup_supabase.py` to configure Supabase integration
   - Run `scripts/setup_gcloud.py` to initialize Google Cloud resources

2. **Data Migration**
   - Create data migration scripts to move data from FXML2 and FXML3
   - Migrate models, signals, and backtest results
   - Migrate user data and settings

3. **API Integration**
   - Update API endpoints to work with new database schema
   - Implement authentication using Supabase Auth
   - Set up proper database access patterns

4. **Deployment Pipeline**
   - Create CI/CD workflow with GitHub Actions
   - Set up Docker image building and pushing to Artifact Registry
   - Configure Kubernetes deployment with GKE

These infrastructure components will integrate seamlessly with our existing implementation plan, providing the necessary backend services for our merged FXML4 platform.
