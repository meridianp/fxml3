# Docker Compose Deployment

## Overview

FXML4 Redesigned uses Docker Compose for local development and testing. This guide covers the complete deployment process, configuration options, and management commands.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 8GB RAM minimum (16GB recommended)
- 50GB available disk space

## Quick Start

```bash
# Clone the repository
git clone https://github.com/fxml4/fxml4-redesigned.git
cd fxml4-redesigned

# Copy environment template
cp .env.example .env

# Edit configuration
nano .env

# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f
```

## Docker Compose Structure

### Main Services

```yaml
version: '3.8'

services:
  # Message Queue
  rabbitmq:
    image: rabbitmq:3.12-management-alpine
    container_name: fxml4_rabbitmq
    ports:
      - "5672:5672"     # AMQP port
      - "15672:15672"   # Management UI
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER:-admin}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASS:-admin}
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    healthcheck:
      test: rabbitmq-diagnostics -q ping
      interval: 30s
      timeout: 10s
      retries: 5

  # Time-series Database
  timescaledb:
    image: timescale/timescaledb:latest-pg15
    container_name: fxml4_timescaledb
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-fxml4}
    volumes:
      - timescale_data:/var/lib/postgresql/data
      - ./db/init:/docker-entrypoint-initdb.d
    healthcheck:
      test: pg_isready -U postgres
      interval: 10s
      timeout: 5s
      retries: 5

  # Cache
  redis:
    image: redis:7-alpine
    container_name: fxml4_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: redis-cli ping
      interval: 10s
      timeout: 5s
      retries: 5

  # Data Collector Service
  data_collector:
    build:
      context: .
      dockerfile: services/data_collector/Dockerfile
    container_name: fxml4_data_collector
    depends_on:
      rabbitmq:
        condition: service_healthy
      timescaledb:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      - SERVICE_NAME=data_collector
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - RABBITMQ_HOST=rabbitmq
      - TIMESCALE_HOST=timescaledb
      - REDIS_HOST=redis
    volumes:
      - ./config:/app/config:ro
      - ./logs/data_collector:/app/logs
    restart: unless-stopped

  # Signal Generator Service
  signal_generator:
    build:
      context: .
      dockerfile: services/signal_generator/Dockerfile
    container_name: fxml4_signal_generator
    depends_on:
      - rabbitmq
      - timescaledb
      - redis
    environment:
      - SERVICE_NAME=signal_generator
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    volumes:
      - ./config:/app/config:ro
      - ./logs/signal_generator:/app/logs
    restart: unless-stopped

  # LLM Analyzer Service
  llm_analyzer:
    build:
      context: .
      dockerfile: services/llm_analyzer/Dockerfile
    container_name: fxml4_llm_analyzer
    depends_on:
      - rabbitmq
      - timescaledb
    environment:
      - SERVICE_NAME=llm_analyzer
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - ./config:/app/config:ro
      - ./logs/llm_analyzer:/app/logs
    restart: unless-stopped

  # Monitor Service
  monitor:
    build:
      context: .
      dockerfile: services/monitor/Dockerfile
    container_name: fxml4_monitor
    ports:
      - "8000:8000"  # REST API
      - "8001:8001"  # WebSocket
    depends_on:
      - rabbitmq
      - timescaledb
    environment:
      - SERVICE_NAME=monitor
      - API_HOST=0.0.0.0
      - API_PORT=8000
    volumes:
      - ./logs/monitor:/app/logs
    restart: unless-stopped

volumes:
  rabbitmq_data:
  timescale_data:
  redis_data:

networks:
  default:
    name: fxml4_network
```

## Environment Configuration

### Required Variables

Create a `.env` file with these required settings:

```bash
# System Configuration
ENVIRONMENT=development
LOG_LEVEL=INFO

# RabbitMQ
RABBITMQ_USER=admin
RABBITMQ_PASS=secure_password
RABBITMQ_VHOST=/

# TimescaleDB
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secure_password
POSTGRES_DB=fxml4

# Redis
REDIS_PASSWORD=secure_password

# Broker Credentials (at least one required)
# Interactive Brokers
IB_ENABLED=true
IB_HOST=host.docker.internal  # For TWS on host
IB_PORT=7497  # Paper trading port
IB_CLIENT_ID=1

# Oanda
OANDA_ENABLED=false
OANDA_API_KEY=your_api_key
OANDA_ACCOUNT_ID=your_account_id
OANDA_ENVIRONMENT=practice

# FXCM
FXCM_ENABLED=false
FXCM_USERNAME=your_username
FXCM_PASSWORD=your_password

# LLM Providers (optional)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

## Service Management

### Starting Services

```bash
# Start all services
docker-compose up -d

# Start specific services
docker-compose up -d rabbitmq timescaledb redis

# Start with build
docker-compose up -d --build

# Scale services
docker-compose up -d --scale signal_generator=3
```

### Monitoring Services

```bash
# View all services
docker-compose ps

# Check service logs
docker-compose logs -f data_collector

# Follow multiple services
docker-compose logs -f data_collector signal_generator

# View last 100 lines
docker-compose logs --tail=100 llm_analyzer
```

### Stopping Services

```bash
# Stop all services
docker-compose stop

# Stop and remove containers
docker-compose down

# Remove everything including volumes
docker-compose down -v

# Stop specific service
docker-compose stop signal_generator
```

## Health Checks

### Service Health Endpoints

| Service | Health Check URL | Expected Response |
|---------|------------------|-------------------|
| RabbitMQ | http://localhost:15672/api/health/checks/virtual-hosts | 200 OK |
| TimescaleDB | `pg_isready -h localhost -p 5432` | accepting connections |
| Redis | `redis-cli ping` | PONG |
| Monitor | http://localhost:8000/health | {"status": "healthy"} |

### Docker Health Status

```bash
# Check health status
docker-compose ps

# Detailed health info
docker inspect fxml4_rabbitmq --format='{{json .State.Health}}'

# Monitor health in real-time
watch -n 2 docker-compose ps
```

## Networking

### Service Discovery

Services communicate using Docker's internal DNS:

```python
# Inside containers, use service names as hostnames
rabbitmq_url = "amqp://admin:admin@rabbitmq:5672/"
timescale_url = "postgresql://postgres:postgres@timescaledb:5432/fxml4"
redis_url = "redis://redis:6379/0"
```

### Port Mapping

| Service | Internal Port | External Port | Purpose |
|---------|--------------|---------------|---------|
| RabbitMQ | 5672 | 5672 | AMQP protocol |
| RabbitMQ | 15672 | 15672 | Management UI |
| TimescaleDB | 5432 | 5432 | PostgreSQL |
| Redis | 6379 | 6379 | Redis protocol |
| Monitor | 8000 | 8000 | REST API |
| Monitor | 8001 | 8001 | WebSocket |

## Data Persistence

### Volume Management

```bash
# List volumes
docker volume ls | grep fxml4

# Inspect volume
docker volume inspect fxml4_timescale_data

# Backup TimescaleDB
docker exec fxml4_timescaledb pg_dump -U postgres fxml4 > backup.sql

# Restore TimescaleDB
docker exec -i fxml4_timescaledb psql -U postgres fxml4 < backup.sql

# Backup Redis
docker exec fxml4_redis redis-cli BGSAVE

# Copy Redis backup
docker cp fxml4_redis:/data/dump.rdb ./redis_backup.rdb
```

### Data Directories

```
fxml4-redesigned/
├── data/
│   ├── rabbitmq/     # RabbitMQ persistent data
│   ├── timescale/    # TimescaleDB data files
│   └── redis/        # Redis snapshots
├── logs/
│   ├── data_collector/
│   ├── signal_generator/
│   └── monitor/
└── config/
    ├── symbols.yaml
    └── strategies.yaml
```

## Performance Tuning

### Resource Limits

```yaml
services:
  signal_generator:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
```

### Optimizations

```bash
# Increase Docker daemon resources (Docker Desktop)
# Settings > Resources > Advanced

# Recommended settings:
# CPUs: 4+
# Memory: 8GB+
# Swap: 2GB
# Disk image size: 100GB+
```

## Troubleshooting

### Common Issues

#### Services Won't Start

```bash
# Check for port conflicts
sudo lsof -i :5672
sudo lsof -i :5432

# Check Docker daemon
docker info

# Reset everything
docker-compose down -v
docker system prune -a
docker-compose up -d
```

#### Connection Issues

```bash
# Test from inside container
docker exec -it fxml4_data_collector bash
ping rabbitmq
nc -zv rabbitmq 5672

# Check network
docker network inspect fxml4_network
```

#### Performance Issues

```bash
# Monitor resource usage
docker stats

# Check container logs for errors
docker-compose logs --tail=1000 | grep ERROR

# Increase logging
docker-compose down
LOG_LEVEL=DEBUG docker-compose up
```

### Debug Commands

```bash
# Enter container shell
docker exec -it fxml4_data_collector bash

# Run Python shell in container
docker exec -it fxml4_data_collector python

# Copy files from container
docker cp fxml4_monitor:/app/logs/error.log ./

# Stream logs to file
docker-compose logs -f > debug.log 2>&1
```

## Security Considerations

### Production Hardening

1. **Change default passwords** in `.env`
2. **Use secrets management** for API keys
3. **Enable TLS** for RabbitMQ and Redis
4. **Restrict port exposure** in production
5. **Use read-only volumes** where possible
6. **Run containers as non-root**

### Network Security

```yaml
# Create internal network
networks:
  internal:
    internal: true
  external:
    internal: false

services:
  timescaledb:
    networks:
      - internal  # Not exposed externally

  monitor:
    networks:
      - internal
      - external  # API access
```

## Backup and Recovery

### Automated Backups

```bash
#!/bin/bash
# backup.sh

# Backup databases
docker exec fxml4_timescaledb pg_dump -U postgres fxml4 | gzip > backups/timescale_$(date +%Y%m%d).sql.gz
docker exec fxml4_redis redis-cli BGSAVE

# Backup configurations
tar -czf backups/config_$(date +%Y%m%d).tar.gz config/

# Backup volumes
docker run --rm -v fxml4_timescale_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/timescale_volume_$(date +%Y%m%d).tar.gz /data
```

### Restore Procedure

```bash
# Stop services
docker-compose stop

# Restore database
gunzip < backups/timescale_20250115.sql.gz | docker exec -i fxml4_timescaledb psql -U postgres fxml4

# Restore Redis
docker cp redis_backup.rdb fxml4_redis:/data/dump.rdb
docker restart fxml4_redis

# Start services
docker-compose start
```

## Next Steps

- Review [production deployment](production.md) for cloud setup
- Configure [monitoring](monitoring.md) dashboards
- Set up [broker connections](../brokers/overview.md)
- Implement [backup strategies](../deployment/production.md#backup-strategy)
