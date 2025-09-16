# FXML4 Project Information

This file contains important information about the FXML4 project for Claude to reference.

## Project Overview
FXML4 is a merged project combining:
- FXML2: ML-based forex trading system
- FXML3: Elliott Wave analysis with LLM integration

## Common Commands

### Environment Setup
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run setup script
python setup_env.py

# Initialize git repository
bash init_git.sh
```

### Google Cloud & Vertex AI Setup
```bash
# Install Google Cloud SDK
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Login to Google Cloud
gcloud auth login

# Set default project
gcloud config set project fxml4

# Set environment variable for GCP project in .env file
echo "GCP_PROJECT=fxml4" >> .env

# Install additional packages for Vertex AI
pip install google-cloud-aiplatform google-cloud-storage gcsfs python-dotenv

# Enable required APIs
gcloud services enable aiplatform.googleapis.com \
    artifactregistry.googleapis.com \
    compute.googleapis.com \
    storage.googleapis.com

# Create GCS buckets for model storage
gsutil mb -l us-central1 gs://fxml4-models
gsutil mb -l us-central1 gs://fxml4-training

# Set Application Default Credentials for local development
gcloud auth application-default login
```

### Vertex AI Usage
```bash
# Run example with local training and upload to Vertex AI
python examples/vertex_ai_example.py --data path/to/data.csv

# Run example with cloud training (data must be in GCS)
python examples/vertex_ai_example.py --data gs://fxml4-training/data.csv --mode cloud

# Run example with local training, upload to Vertex AI, and deploy as endpoint
python examples/vertex_ai_example.py --data path/to/data.csv --deploy

# Check Vertex AI Model Registry in Google Cloud Console
# https://console.cloud.google.com/vertex-ai/model-registry
```

### Database Commands
```bash
# Initialize PostgreSQL database
python scripts/init_db.py

# Connect to PostgreSQL
psql -U postgres -d fxml4

# Run specific migration
psql -U postgres -d fxml4 -f db/migrations/001_initial_schema.sql
```

### Supabase Commands
```bash
# Login to Supabase
supabase login

# Initialize Supabase project
python scripts/setup_supabase.py

# Generate TypeScript types for Supabase
supabase gen types typescript > fxml4/api/types/supabase.ts

# Start local Supabase development
supabase start

# Stop local Supabase
supabase stop
```

### Google Cloud Commands
```bash
# Login to Google Cloud
gcloud auth login

# Set project
gcloud config set project your-project-id

# Create GKE cluster
gcloud container clusters create fxml4-cluster --num-nodes=3 --region=us-central1

# Get credentials for kubectl
gcloud container clusters get-credentials fxml4-cluster --region=us-central1

# Push Docker image to Artifact Registry
docker tag fxml4:latest us-central1-docker.pkg.dev/your-project-id/fxml4-repo/fxml4:latest
docker push us-central1-docker.pkg.dev/your-project-id/fxml4-repo/fxml4:latest
```

### Testing
```bash
# Run all tests
pytest tests/

# Run specific test module
pytest tests/test_specific_module.py

# Run with coverage
pytest --cov=fxml4 tests/
```

### Code Style
```bash
# Format code with black
black .

# Check typing with mypy
mypy .

# Sort imports
isort .
```

### Docker Commands
```bash
# Build and run containers
docker-compose up -d

# Stop containers
docker-compose down

# Build specific service
docker-compose build api

# View logs
docker-compose logs -f
```

## Development Guidelines

### Code Style
- Follow Google Python Style Guide
- Use type hints for all functions
- Write comprehensive docstrings for modules, classes, and functions
- Organize imports: standard library, third-party, local
- Use Black formatter with default settings (line length: 88)
- Use isort for import sorting
- Run mypy for type checking

### Naming Conventions
- `snake_case` for functions, methods, variables, modules, and packages
- `CamelCase` for classes
- `UPPER_CASE` for constants
- Prefixes for private variables: `_private`, `__very_private`
- Use descriptive names that reflect purpose (avoid abbreviations)

### Git Workflow
- Create feature branches from `develop`
- Use conventional commit format: `type(scope): description`
  - Types: feat, fix, docs, style, refactor, test, chore
- Write unit tests for new features
- Create focused PRs that address a single concern
- Reference issues in PR descriptions (#issue-number)

### Error Handling
- Use explicit exception handling with specific exceptions
- Include helpful error messages for debugging
- Use logging for error reporting, not print statements
- Handle errors gracefully with fallbacks when appropriate

### Data Processing
- Prefer pandas for data manipulation
- Use numpy for numerical calculations
- Always handle NaN/None values explicitly
- Create copies of DataFrames before modification
- Use appropriate data types for columns (category, datetime, etc.)

### Testing
- Write unit tests for all functions and methods
- Use pytest for testing framework
- Run tests with: `pytest -xvs tests/`
- Keep test coverage above 80%

### Linting and Formatting
```bash
# Format code
black .

# Sort imports
isort .

# Check typing
mypy .

# Lint code
flake8 .
```

## Integration Notes

When integrating components from FXML2 and FXML3, remember to:
1. Harmonize naming conventions (prefer FXML3's more modular approach)
2. Maintain backwards compatibility where possible
3. Document integration decisions
4. Add tests for integrated components

## Database Schema

The main tables in our schema are:
- users: User accounts and authentication information
- symbols: Trading symbols like EURUSD, GBPUSD
- timeframes: Timeframes like 1m, 5m, 1h, 4h, 1d
- models: ML models metadata and storage paths
- signals: Trading signals generated by various strategies
- backtests: Backtest results and metrics
- backtest_trades: Individual trades from backtests
- wave_patterns: Elliott Wave patterns detected in price data
- knowledge_vectors: Vector embeddings for RAG system

## Infrastructure

Our infrastructure consists of:
1. PostgreSQL database for data storage
2. Supabase for authentication and realtime features
3. Google Cloud for deployment (GKE, Artifact Registry)
4. Docker containers for service isolation
5. GitHub Actions for CI/CD

# Implementation Status

## Phase 3.1: Enhanced Machine Learning Pipeline (Completed)

### 1. Model Training Pipeline (Completed)
- ✅ Implemented time-series cross-validation framework
- ✅ Developed proper training/validation/test splitting for financial data
- ✅ Added walk-forward testing capabilities
- ✅ Implemented hyperparameter optimization

### 2. Google Vertex AI Integration (Completed)
- ✅ Created integration with Google Cloud Vertex AI
- ✅ Added support for training in the cloud
- ✅ Established model registry with cloud storage
- ✅ Enabled deployment to Vertex AI endpoints
- ✅ Documented cloud-based workflows

### 3. Feature Selection and Engineering (Completed)
- ✅ Implemented feature importance analysis
- ✅ Created automated feature selection techniques
- ✅ Set up cross-validation for feature selection
- ✅ Added correlation-aware feature selection
- ✅ Implemented ensemble feature selection methods
- ✅ Created stability analysis for robust feature selection
- ✅ Added visualization capabilities for feature importance

## Phase 3.2: Enhanced Backtesting Framework (Completed)

### 1. Execution Realism (Completed)
- ✅ Implemented event-driven architecture
- ✅ Added sophisticated slippage modeling
- ✅ Created realistic fee structures
- ✅ Implemented market impact simulation

### 2. Risk Management (Completed)
- ✅ Added advanced position sizing algorithms
- ✅ Implemented stop-loss management
- ✅ Created drawdown control mechanisms
- ✅ Set up portfolio-level risk metrics

### 3. Multi-Asset Capabilities (Completed)
- ✅ Added support for multi-symbol backtesting
- ✅ Implemented correlation-aware position sizing
- ✅ Created portfolio-level risk constraints
- ✅ Added symbol-level performance tracking

## Phase 3.3: FXML3 Integration (In Progress)

### Elliott Wave Analysis (Completed)
- ✅ Ported ElliottWaveAnalyzer from FXML3
- ✅ Implemented FibonacciCalculator
- ✅ Created FractalDegreeHandler for multi-timeframe analysis
- ✅ Developed SentimentWaveValidator for sentiment-enhanced pattern validation
- ✅ Created EnhancedWaveSignalGenerator for backtesting integration

### LLM Integration (Completed)
- ✅ Implemented LLMClient for OpenAI and Anthropic models
- ✅ Created SentimentAnalyzer for market sentiment analysis
- ✅ Developed full RAG system with OpenAI and Pinecone
- ✅ Integrated ElliottWaveKnowledgeBase
- ✅ Ported document processing utilities

### Paper Trading Integration (Completed)
- ✅ Implemented real-time data feed connector for Interactive Brokers
- ✅ Created PaperTradingEngine with IB API integration
- ✅ Implemented position tracking and order management
- ✅ Added risk management controls
- ✅ Created database schema for trading results

### UI and Documentation (In Progress)
- ⬜ Port Streamlit components from FXML3
- ⬜ Add Elliott Wave visualization to charts
- ⬜ Create interactive wave pattern exploration interface
- ⬜ Implement dashboard for paper trading monitoring

# TimescaleDB Setup

TimescaleDB is set up and running on port 5433:

```
TIMESCALEDB_HOST=localhost
TIMESCALEDB_PORT=5433
TIMESCALEDB_USER=postgres
TIMESCALEDB_PASSWORD=postgres
TIMESCALEDB_DATABASE=fxml4
```

## TimescaleDB Commands

```bash
# Connect to TimescaleDB
docker exec -it timescaledb psql -U postgres -d fxml4

# Run SQL file against TimescaleDB
docker exec -i timescaledb psql -U postgres -d fxml4 < path/to/sql_file.sql

# Check continuous aggregates
docker exec timescaledb psql -U postgres -d fxml4 -c "SELECT view_name FROM timescaledb_information.continuous_aggregates;"

# Check compression policies
docker exec timescaledb psql -U postgres -d fxml4 -c "SELECT * FROM timescaledb_information.compression_settings;"

# Check retention policies
docker exec timescaledb psql -U postgres -d fxml4 -c "SELECT * FROM timescaledb_information.job_stats WHERE proc_name = 'policy_retention';"
```

# Testing Instructions

## Quick Testing Options

### Option 1: Direct Testing (Recommended for Quick Start)
```bash
# Run direct ML workflow test (no API required)
python scripts/test_ml_workflow_simple.py
```

### Option 2: Start FXML4 API and Test
```bash
# Terminal 1: Start FXML4 API on port 8001
python scripts/start_fxml4_api.py

# Terminal 2: Test the FXML4 API
python scripts/test_api_backtest.py --url http://localhost:8001
```

### Option 3: Complete Demo Workflow
```bash
# Run complete ML demo (no API required)
python scripts/test_ml_backtest_demo.py
```

### Option 4: Unit Tests
```bash
# Run integration tests
pytest tests/integration/test_ml_pipeline.py -v -s
```

### Option 5: Complete Test Suite
```bash
# This will handle API startup and run all tests
./scripts/run_ml_backtest_tests.sh
```

# MCP Server Configuration

The project includes Model Context Protocol (MCP) server configurations in `.mcp.json`:

- **sequential-thinking**: Sequential reasoning and problem-solving
- **perplexity-ask**: Perplexity AI integration for research
- **supabase**: Supabase backend integration
- **neon**: Neon database integration

# Documentation Links

## Core Documentation
- **[Technical Documentation Index](docs/technical-documentation-index.md)** - Complete technical reference
- **[FXML3 Integration Plan](FXML3_INTEGRATION_PLAN.md)** - Detailed integration roadmap
- **[Testing Instructions](TESTING_INSTRUCTIONS.md)** - Comprehensive testing guide
- **[TimescaleDB Guide](docs/timescaledb_guide.md)** - Time-series database usage

## API Documentation
- **[OpenAPI/Swagger Spec](docs/api-reference/swagger-spec.yaml)** - Complete API specification
- **Interactive API Docs**: `http://localhost:8000/docs` (when running)

## Deployment & Operations
- **[Deployment Guide](docs/deployment/deployment-guide.md)** - Production deployment
- **[Operational Runbook](docs/deployment/operational-runbook.md)** - Day-to-day operations
- **[Docker Build Guide](DOCKER_BUILD_GUIDE.md)** - Container build instructions

## Troubleshooting & Performance
- **[Troubleshooting Guide](docs/troubleshooting/troubleshooting-guide.md)** - Common issues
- **[FAQ](docs/troubleshooting/faq.md)** - Frequently asked questions
- **[Performance Tuning](docs/performance/performance-tuning-guide.md)** - Optimization guide

# Key API Endpoints

- **Health Check**: `GET /health`
- **Authentication**: `POST /token`
- **Market Data**: `POST /data`
- **Signal Generation**: `POST /signals`
- **Backtesting**: `POST /backtest`
- **Performance Reports**: `GET /performance/report/{backtest_id}`

# Performance Targets

## Response Time Targets (95th percentile)
- `/health`: < 50ms (excellent: < 20ms)
- `/data`: < 500ms (excellent: < 200ms)
- `/signals`: < 2s (excellent: < 1s)
- `/backtest`: < 5min (excellent: < 2min)

## Resource Targets
- CPU Usage: < 70% (max: < 90%)
- Memory Usage: < 4GB (max: < 8GB)
- Database Connections: < 50 (max: < 100)
- Response Rate: > 99% (target: > 99.9%)

## Commands
- You have the ability to delegate a task to a sub-agent using `codex`
- You can invoke the agent using: `codex -q -a full-auto "<task description>"`
