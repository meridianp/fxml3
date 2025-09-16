# FXML4 Technical Documentation Index

This comprehensive technical documentation provides everything needed to deploy, operate, and troubleshoot the FXML4 trading platform.

## 📚 Documentation Overview

### 🔧 API Documentation
- **[OpenAPI/Swagger Specification](api-reference/swagger-spec.yaml)** - Complete API specification
- **[Interactive API Docs](http://localhost:8000/docs)** - Swagger UI (when running locally)
- **[API Reference](api-reference/)** - Detailed endpoint documentation

### 🚀 Deployment & Operations
- **[Deployment Guide](deployment/deployment-guide.md)** - Complete deployment instructions
- **[Operational Runbook](deployment/operational-runbook.md)** - Day-to-day operations procedures
- **[Environment Setup](../CLAUDE.md#environment-setup)** - Quick setup commands

### 🔍 Troubleshooting & Support
- **[Troubleshooting Guide](troubleshooting/troubleshooting-guide.md)** - Common issues and solutions
- **[FAQ](troubleshooting/faq.md)** - Frequently asked questions
- **[Performance Tuning](performance/performance-tuning-guide.md)** - Optimization recommendations

### ⚡ Performance & Scaling
- **[Performance Tuning Guide](performance/performance-tuning-guide.md)** - Comprehensive optimization guide
- **[Load Testing](performance/performance-tuning-guide.md#load-testing)** - Performance testing procedures
- **[Monitoring Setup](performance/performance-tuning-guide.md#monitoring-and-profiling)** - Metrics and alerting

## 🔗 Quick Links

### Essential Commands
```bash
# Health Check
curl http://localhost:8000/health

# API Documentation
open http://localhost:8000/docs

# Check Logs
kubectl logs -l app=fxml4-api -n fxml4-prod --tail=100

# Scale Application
kubectl scale deployment fxml4-api --replicas=5 -n fxml4-prod
```

### Key Endpoints
- **Health Check**: `GET /health`
- **Authentication**: `POST /token`
- **Market Data**: `POST /data`
- **Signal Generation**: `POST /signals`
- **Backtesting**: `POST /backtest`
- **Performance Reports**: `GET /performance/report/{backtest_id}`

### Configuration Files
- **Environment Variables**: `.env` files
- **Database Config**: `config/default.yaml`
- **Docker Compose**: `docker-compose.yml`
- **Kubernetes**: `k8s/` directory

## 📋 Documentation Sections

### 1. API Documentation

#### OpenAPI/Swagger Specification
- **File**: `docs/api-reference/swagger-spec.yaml`
- **Purpose**: Complete API specification with schemas, endpoints, and examples
- **Usage**: Import into Postman, generate client SDKs, API validation

#### Interactive Documentation
- **URL**: `http://localhost:8000/docs` (Swagger UI)
- **URL**: `http://localhost:8000/redoc` (ReDoc)
- **Features**: Try endpoints, view schemas, authentication testing

#### API Reference
```
docs/api-reference/
├── swagger-spec.yaml          # Complete OpenAPI 3.0 specification
├── api/
│   ├── endpoints.md          # Endpoint documentation
│   └── index.md             # API overview
└── examples/                # Usage examples
```

### 2. Deployment Documentation

#### Deployment Guide
- **File**: `docs/deployment/deployment-guide.md`
- **Covers**: Development, staging, and production deployments
- **Includes**:
  - Prerequisites and system requirements
  - Environment-specific configurations
  - Blue-green and rolling deployment strategies
  - Health checks and rollback procedures

#### Operational Runbook
- **File**: `docs/deployment/operational-runbook.md`
- **Covers**: Day-to-day operations and maintenance
- **Includes**:
  - Daily/weekly operational checklists
  - Monitoring and alerting procedures
  - Backup and recovery processes
  - Incident response playbooks

### 3. Troubleshooting Documentation

#### Troubleshooting Guide
- **File**: `docs/troubleshooting/troubleshooting-guide.md`
- **Covers**: Common issues and diagnostic procedures
- **Sections**:
  - Quick diagnostic steps
  - API, database, and authentication issues
  - Performance problems
  - External service integration issues

#### FAQ
- **File**: `docs/troubleshooting/faq.md`
- **Covers**: Frequently asked questions across all topics
- **Categories**:
  - General questions about FXML4
  - Installation and setup
  - API usage and integration
  - Backtesting and performance analysis

### 4. Performance Documentation

#### Performance Tuning Guide
- **File**: `docs/performance/performance-tuning-guide.md`
- **Covers**: Comprehensive performance optimization
- **Topics**:
  - Database optimization (PostgreSQL, TimescaleDB)
  - API performance tuning
  - Infrastructure scaling strategies
  - Memory management and caching
  - Load testing and benchmarking

## 🛠️ Tools and Utilities

### Development Tools
```bash
# API Testing
curl -X POST http://localhost:8000/data \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"EURUSD","timeframe":"1h"}'

# Database Testing
psql -h localhost -U postgres -d fxml4 -c "SELECT COUNT(*) FROM market_data;"

# Performance Testing
ab -n 1000 -c 10 http://localhost:8000/health
```

### Monitoring Commands
```bash
# Check Application Status
kubectl get pods -n fxml4-prod
docker-compose ps

# View Logs
kubectl logs -f deployment/fxml4-api -n fxml4-prod
docker-compose logs -f api

# Resource Usage
kubectl top pods -n fxml4-prod
docker stats
```

### Debugging Tools
```bash
# Database Connections
kubectl exec -it postgres-0 -n fxml4-prod -- \
  psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# Memory Usage
kubectl exec -it deployment/fxml4-api -n fxml4-prod -- \
  python -c "import psutil; print(f'Memory: {psutil.virtual_memory().percent}%')"

# API Health Check
curl -f http://localhost:8000/health || echo "API health check failed"
```

## 📊 Performance Targets

### Response Time Targets
| Endpoint | Target (95th percentile) | Excellent |
|----------|-------------------------|-----------|
| `/health` | < 50ms | < 20ms |
| `/data` | < 500ms | < 200ms |
| `/signals` | < 2s | < 1s |
| `/backtest` | < 5min | < 2min |

### Resource Targets
| Resource | Target | Maximum |
|----------|--------|---------|
| CPU Usage | < 70% | < 90% |
| Memory Usage | < 4GB | < 8GB |
| Database Connections | < 50 | < 100 |
| Response Rate | > 99% | > 99.9% |

## 🔐 Security Considerations

### Authentication
- JWT token-based authentication
- Configurable token expiration
- Role-based access control (RBAC)
- API key management for external services

### Network Security
- HTTPS/TLS encryption
- CORS configuration
- Rate limiting and DDoS protection
- Input validation and sanitization

### Data Protection
- Database encryption at rest
- Secure credential management
- Audit logging
- PII data handling

## 📞 Support and Contact

### Documentation Issues
- **GitHub Issues**: [Create Issue](https://github.com/meridianp/fxml4/issues)
- **Documentation Updates**: Submit pull requests

### Technical Support
- **Operations Team**: ops@fxml4.com
- **Development Team**: dev@fxml4.com
- **Security Issues**: security@fxml4.com

### Emergency Contact
- **Critical Issues**: Use PagerDuty escalation
- **Business Hours**: Slack #fxml4-support
- **After Hours**: On-call rotation

## 📝 Contributing to Documentation

### Documentation Standards
- Use Markdown format for all documentation
- Include code examples and commands
- Provide step-by-step procedures
- Update version information regularly

### Review Process
1. Create feature branch for documentation changes
2. Submit pull request with clear description
3. Technical review by team members
4. Merge after approval and testing

### Documentation Maintenance
- **Weekly**: Review and update operational procedures
- **Monthly**: Update performance targets and troubleshooting guides
- **Quarterly**: Complete documentation audit and updates

---

**Last Updated**: [Current Date]
**Version**: 1.0.0
**Next Review**: [Date + 3 months]

*This documentation is maintained by the FXML4 development team. For updates or corrections, please submit a pull request or contact the team.*
