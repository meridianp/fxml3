# FXML4 Production Deployment Guide

This guide provides step-by-step instructions for deploying the FXML4 forex trading system using Docker Compose for production environments.

## 🚀 Quick Start

```bash
# 1. Copy environment template
cp .env.production.template .env.production

# 2. Edit production environment variables
nano .env.production

# 3. Deploy the system
./deploy-production.sh
```

## 📋 Prerequisites

### System Requirements
- **OS**: Linux/macOS (Ubuntu 20.04+ recommended)
- **Docker**: Version 20.10+
- **Docker Compose**: Version 2.0+
- **Memory**: 4GB+ RAM available
- **Storage**: 20GB+ free disk space
- **Network**: Stable internet connection

### External Dependencies
- **Database**: PostgreSQL 14+ with TimescaleDB extension
- **API Keys**: Required for data sources (Polygon, Alpha Vantage, etc.)
- **Broker Access**: FXCM or Interactive Brokers account

## 🔧 Pre-Deployment Setup

### 1. Environment Configuration

Copy the environment template and configure it:

```bash
cp .env.production.template .env.production
```

**Critical Variables to Configure:**

```bash
# Security (MUST CHANGE)
FXML4_JWT_SECRET_KEY=your-secure-32-character-secret-key-here
FXML4_DATABASE_PASSWORD=your-secure-database-password
REDIS_PASSWORD=your-secure-redis-password
RABBITMQ_PASSWORD=your-secure-rabbitmq-password

# Database (External)
DB_HOST=your-database-host
DB_USER=your-database-user
DB_NAME=fxml4

# API Keys
POLYGON_API_KEY=your-polygon-api-key
ALPHA_VANTAGE_API_KEY=your-alpha-vantage-api-key
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key

# Trading Parameters (Conservative defaults)
FOREX_MAX_RISK_PER_TRADE=0.01  # 1% risk per trade
FOREX_ACCOUNT_LEVERAGE=10      # 10:1 leverage
FOREX_MAX_POSITIONS=3          # Max 3 positions
```

### 2. External Database Setup

Set up a PostgreSQL database with TimescaleDB extension:

```sql
-- Create database
CREATE DATABASE fxml4;

-- Connect to database
\c fxml4;

-- Create TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Create user
CREATE USER fxml4_user WITH PASSWORD 'your-secure-password';
GRANT ALL PRIVILEGES ON DATABASE fxml4 TO fxml4_user;
```

### 3. API Keys Setup

Obtain API keys from:
- **Polygon.io**: For market data
- **Alpha Vantage**: For financial data
- **OpenAI**: For LLM integration
- **Anthropic**: For Claude integration

## 🚀 Deployment Process

### Automatic Deployment

Use the provided deployment script:

```bash
./deploy-production.sh
```

This script will:
1. Check system requirements
2. Validate environment configuration
3. Create necessary directories
4. Set up monitoring
5. Configure Nginx reverse proxy
6. Build and start all services
7. Wait for services to be ready
8. Show deployment status

### Manual Deployment

If you prefer manual deployment:

```bash
# 1. Create directories
mkdir -p data/{cache,features,historical,processed}
mkdir -p models/{EURUSD,GBPUSD,USDCHF,USDJPY}
mkdir -p logs config monitoring

# 2. Build and start services
docker-compose -f docker-compose.prod.yml up -d --build

# 3. Check service status
docker-compose -f docker-compose.prod.yml ps
```

## 📊 Service Architecture

The production deployment includes:

### Core Services
- **API** (Port 8000): FastAPI trading API
- **Dashboard** (Port 8501): Streamlit web interface
- **Worker** (Background): Async task processing
- **Training** (On-demand): ML model training

### Infrastructure Services
- **Redis** (Port 6379): Caching and session storage
- **RabbitMQ** (Port 5672): Message queuing
- **Nginx** (Port 80): Reverse proxy and load balancing

### Monitoring Stack
- **Prometheus** (Port 9090): Metrics collection
- **Grafana** (Port 3000): Dashboards and visualization
- **Loki** (Port 3100): Log aggregation

## 🔍 Monitoring & Health Checks

### Service Health
```bash
# Check all services
docker-compose -f docker-compose.prod.yml ps

# Check specific service health
curl http://localhost:8000/health

# View service logs
docker-compose -f docker-compose.prod.yml logs -f api
```

### Key Metrics to Monitor
- **API Response Time**: < 100ms for health checks
- **Memory Usage**: < 80% of allocated resources
- **Database Connections**: < 80% of max connections
- **Trading Performance**: PnL, Sharpe ratio, drawdown

### Grafana Dashboards
Access Grafana at `http://localhost:3000`:
- **System Overview**: Resource usage, service status
- **Trading Performance**: PnL, positions, signals
- **API Metrics**: Response times, error rates
- **Database Performance**: Query times, connections

## 🔐 Security Considerations

### Network Security
- All services run in isolated Docker network
- Only necessary ports exposed to host
- Nginx reverse proxy for SSL termination

### Authentication
- JWT tokens for API authentication
- Strong passwords for all services
- Environment-based secret management

### Data Protection
- Database credentials encrypted
- API keys stored in environment variables
- Log files rotated and compressed

## 🗄️ Data Management

### Backup Strategy
```bash
# Create backup
./deploy-production.sh backup

# Restore from backup
./restore-backup.sh backup_filename.tar.gz
```

### Data Retention
- **Trading Data**: 1 year
- **Logs**: 30 days
- **Models**: Keep 5 most recent versions
- **Backups**: Weekly full, daily incremental

## 🛠️ Maintenance Operations

### Service Management
```bash
# View status
./deploy-production.sh status

# View logs
./deploy-production.sh logs

# Restart services
./deploy-production.sh restart

# Stop services
./deploy-production.sh stop
```

### Model Updates
```bash
# Start training service
docker-compose -f docker-compose.prod.yml --profile training up training

# Update models
docker-compose -f docker-compose.prod.yml exec api python -m fxml4.training.main
```

### Database Maintenance
```bash
# Connect to database
docker-compose -f docker-compose.prod.yml exec db psql -U postgres -d fxml4

# Run maintenance
VACUUM ANALYZE;
REINDEX DATABASE fxml4;
```

## 🚨 Troubleshooting

### Common Issues

**Service won't start:**
```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs service_name

# Check resource usage
docker stats

# Restart specific service
docker-compose -f docker-compose.prod.yml restart service_name
```

**Database connection issues:**
```bash
# Test database connection
docker-compose -f docker-compose.prod.yml exec api python -c "
from fxml4.config import get_config
config = get_config()
print('Database config:', config.database)
"
```

**API not responding:**
```bash
# Check API health
curl -v http://localhost:8000/health

# Check API logs
docker-compose -f docker-compose.prod.yml logs -f api
```

### Performance Issues
- Monitor resource usage with `docker stats`
- Check database query performance
- Review application logs for bottlenecks
- Scale worker processes if needed

## 📈 Scaling for Production

### Horizontal Scaling
```bash
# Scale worker processes
docker-compose -f docker-compose.prod.yml up -d --scale worker=3

# Scale API instances (requires load balancer)
docker-compose -f docker-compose.prod.yml up -d --scale api=2
```

### Resource Optimization
- Adjust memory limits in docker-compose.prod.yml
- Optimize database connection pools
- Configure Redis memory policies
- Tune Nginx worker processes

## 📞 Support

For deployment issues:
1. Check logs: `docker-compose -f docker-compose.prod.yml logs`
2. Review this guide
3. Check service health endpoints
4. Verify environment configuration

## 🔄 Updates and Maintenance

### Regular Tasks
- **Daily**: Check service health and logs
- **Weekly**: Create full system backup
- **Monthly**: Update Docker images and security patches
- **Quarterly**: Review and optimize configurations

### Update Process
1. Create backup
2. Pull latest images
3. Test in staging environment
4. Deploy to production
5. Verify all services are healthy

---

**⚠️ Important Notes:**
- Never deploy with default passwords
- Always test in staging first
- Monitor system resources continuously
- Keep API keys secure and rotate regularly
- Implement proper backup and disaster recovery procedures
