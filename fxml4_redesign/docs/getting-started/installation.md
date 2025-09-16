# Installation Guide

## Prerequisites

Before installing FXML4 Redesigned, ensure you have the following:

### System Requirements

- **Operating System**: Ubuntu 20.04+ or macOS 12+
- **CPU**: 4+ cores (8+ recommended)
- **RAM**: 8GB minimum (16GB+ recommended)
- **Storage**: 50GB+ available space
- **Network**: Stable internet connection

### Software Requirements

| Software | Version | Purpose |
|----------|---------|---------|
| Docker | 20.10+ | Container runtime |
| Docker Compose | 2.0+ | Service orchestration |
| Git | 2.30+ | Version control |
| Python | 3.11+ | Development (optional) |

## Installation Methods

### Method 1: Quick Start (Recommended)

```bash
# Clone the repository
git clone https://github.com/fxml4/fxml4-redesigned.git
cd fxml4-redesigned

# Run the setup script
./scripts/setup.sh

# Start services
docker-compose up -d
```

### Method 2: Manual Installation

#### Step 1: Install Docker

**Ubuntu:**
```bash
# Update package index
sudo apt update

# Install prerequisites
sudo apt install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Add Docker's GPG key
sudo mkdir -m 0755 -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

**macOS:**
```bash
# Install Docker Desktop
brew install --cask docker

# Start Docker Desktop
open /Applications/Docker.app
```

#### Step 2: Clone Repository

```bash
# Clone with HTTPS
git clone https://github.com/fxml4/fxml4-redesigned.git

# Or clone with SSH
git clone git@github.com:fxml4/fxml4-redesigned.git

# Enter directory
cd fxml4-redesigned
```

#### Step 3: Configure Environment

```bash
# Copy example configuration
cp .env.example .env

# Edit configuration
nano .env
```

Required configuration:
```bash
# Basic Settings
ENVIRONMENT=development
LOG_LEVEL=INFO

# Database Passwords (change these!)
RABBITMQ_PASS=your_secure_password
POSTGRES_PASSWORD=your_secure_password
REDIS_PASSWORD=your_secure_password

# At least one broker
IB_ENABLED=true
IB_HOST=host.docker.internal
IB_PORT=7497
```

#### Step 4: Initialize Database

```bash
# Start database services
docker-compose up -d timescaledb

# Wait for database to be ready
sleep 10

# Run initialization scripts
docker exec -i fxml4_timescaledb psql -U postgres -d fxml4 < db/init/01_schema.sql
docker exec -i fxml4_timescaledb psql -U postgres -d fxml4 < db/init/02_timescale.sql
docker exec -i fxml4_timescaledb psql -U postgres -d fxml4 < db/init/03_indexes.sql
```

#### Step 5: Start Services

```bash
# Build images
docker-compose build

# Start all services
docker-compose up -d

# Verify services are running
docker-compose ps
```

## Broker Setup

### Interactive Brokers (TWS/Gateway)

1. **Download TWS or IB Gateway** from [Interactive Brokers](https://www.interactivebrokers.com)

2. **Configure API Settings**:
   - File → Global Configuration → API → Settings
   - Enable "Enable ActiveX and Socket Clients"
   - Enable "Allow connections from localhost only"
   - Note the port number (7497 for paper, 7496 for live)

3. **Update Configuration**:
```bash
# In .env file
IB_ENABLED=true
IB_HOST=host.docker.internal  # or your TWS machine IP
IB_PORT=7497  # Paper trading port
IB_CLIENT_ID=1
```

### Oanda

1. **Get API Credentials**:
   - Sign up at [Oanda](https://www.oanda.com)
   - Navigate to "Manage API Access"
   - Generate an API token

2. **Update Configuration**:
```bash
# In .env file
OANDA_ENABLED=true
OANDA_API_KEY=your_api_token_here
OANDA_ACCOUNT_ID=your_account_id_here
OANDA_ENVIRONMENT=practice  # or 'live'
```

### FXCM

1. **Get Trading Station Credentials**:
   - Sign up at [FXCM](https://www.fxcm.com)
   - Use your Trading Station login

2. **Update Configuration**:
```bash
# In .env file
FXCM_ENABLED=true
FXCM_USERNAME=your_username
FXCM_PASSWORD=your_password
FXCM_CONNECTION=Demo  # or 'Real'
```

## Verification

### Check Service Health

```bash
# Check all services
docker-compose ps

# Expected output:
# NAME                    STATUS              PORTS
# fxml4_data_collector    Up 2 minutes
# fxml4_monitor          Up 2 minutes        0.0.0.0:8000->8000/tcp
# fxml4_rabbitmq         Up 3 minutes        0.0.0.0:5672->5672/tcp, 0.0.0.0:15672->15672/tcp
# fxml4_redis            Up 3 minutes        0.0.0.0:6379->6379/tcp
# fxml4_timescaledb      Up 3 minutes        0.0.0.0:5432->5432/tcp
```

### Access Web Interfaces

| Service | URL | Credentials |
|---------|-----|-------------|
| RabbitMQ Management | http://localhost:15672 | admin / {RABBITMQ_PASS} |
| Monitor API | http://localhost:8000/docs | No auth (dev mode) |
| Health Check | http://localhost:8000/health | No auth |

### Test Data Flow

```bash
# Watch logs for market data
docker-compose logs -f data_collector | grep "Published market data"

# Check RabbitMQ message rates
curl -u admin:${RABBITMQ_PASS} http://localhost:15672/api/overview | jq '.message_stats'

# Query recent data
docker exec -it fxml4_timescaledb psql -U postgres -d fxml4 -c \
  "SELECT * FROM market_data ORDER BY timestamp DESC LIMIT 10;"
```

## Development Setup (Optional)

For local development without Docker:

### Python Environment

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### IDE Configuration

**VS Code**:
```json
// .vscode/settings.json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests"]
}
```

**PyCharm**:
1. File → Settings → Project → Python Interpreter
2. Add Interpreter → Existing Environment
3. Select: `venv/bin/python`

## Troubleshooting

### Docker Issues

**Permission Denied**:
```bash
# Add user to docker group
sudo usermod -aG docker $USER
# Log out and back in
```

**Port Already in Use**:
```bash
# Find process using port
sudo lsof -i :5672
# Kill process
sudo kill -9 <PID>
```

**Disk Space**:
```bash
# Clean up Docker
docker system prune -a --volumes
```

### Service Issues

**RabbitMQ Won't Start**:
```bash
# Reset RabbitMQ
docker-compose down
docker volume rm fxml4_rabbitmq_data
docker-compose up -d rabbitmq
```

**Database Connection Failed**:
```bash
# Check database logs
docker logs fxml4_timescaledb
# Test connection
docker exec -it fxml4_timescaledb psql -U postgres -d fxml4 -c "SELECT 1;"
```

### Network Issues

**Cannot Connect to Broker**:
```bash
# Test from container
docker exec -it fxml4_data_collector ping host.docker.internal
# Check firewall
sudo ufw status
```

## Next Steps

Once installation is complete:

1. [Configure the system](configuration.md) for your trading needs
2. [Run your first backtest](first-run.md)
3. [Set up monitoring](../deployment/monitoring.md)
4. [Review the architecture](../architecture/overview.md)
