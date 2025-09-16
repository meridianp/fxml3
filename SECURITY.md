# Security Policy

## Overview

FXML4 is an enterprise-grade forex trading platform that integrates legacy financial systems with modern security practices. This document outlines our security approach and explains dependency management policies.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.x.x   | :white_check_mark: |
| 1.x.x   | :x:                |

## Security Architecture

### Core Security Features

- **JWT Authentication** with 2FA support
- **Role-based Access Control** (RBAC) for trading operations
- **API Rate Limiting** and abuse prevention
- **Input Validation** with comprehensive sanitization
- **Audit Logging** for all trading activities
- **Encryption** at rest and in transit

### Security Testing

FXML4 implements comprehensive security testing including:

- **OWASP Top 10** vulnerability scanning
- **API Contract Validation** for 145+ endpoints
- **Security Penetration Testing** (SQL injection, XSS, CSRF)
- **Authentication Bypass Testing**
- **Rate Limiting Validation**

Current security test results: **0 critical, 0 high severity vulnerabilities**

## Dependency Management Policy

### Legacy Financial Dependencies

FXML4 integrates with several legacy financial systems that require specific dependency versions:

#### FXCM ForexConnect API
- **Status**: Legacy financial library (10+ years old)
- **Version Lock**: Intentionally maintained at specific versions
- **Reason**: Binary compatibility with FXCM trading infrastructure
- **Security Assessment**: Containerized and network-isolated
- **Risk Mitigation**:
  - Runs in isolated containers
  - Limited network exposure
  - Input validation at application boundaries
  - Regular security monitoring

#### Interactive Brokers TWS API
- **Status**: Legacy financial protocol implementation
- **Version Lock**: Required for FIX protocol compatibility
- **Security Assessment**: Protocol-level security implemented
- **Risk Mitigation**:
  - Encrypted connections (TLS 1.3)
  - Authentication tokens with expiration
  - Rate limiting and abuse detection

### Dependency Security Approach

1. **Production Dependencies**: Regularly updated security-critical packages
2. **Financial Protocol Dependencies**: Version-locked for stability
3. **Development Dependencies**: Latest secure versions
4. **Container Isolation**: Legacy dependencies run in isolated environments

## Reporting a Vulnerability

### For Security Researchers

If you discover a security vulnerability in FXML4, please help us maintain security by following responsible disclosure:

1. **Email**: security@fxml4.com (or create a private GitHub security advisory)
2. **Include**:
   - Detailed description of the vulnerability
   - Steps to reproduce the issue
   - Potential impact assessment
   - Suggested remediation (if applicable)

### Response Timeline

- **Initial Response**: Within 24 hours
- **Preliminary Assessment**: Within 72 hours
- **Resolution Timeline**:
  - Critical: 1-7 days
  - High: 1-30 days
  - Medium: 1-90 days
  - Low: Next planned release

### Vulnerability Categories

#### In-Scope Vulnerabilities

- Authentication bypass
- Authorization flaws
- Data injection attacks (SQL, NoSQL, Command)
- Cross-site scripting (XSS)
- Cross-site request forgery (CSRF)
- Server-side request forgery (SSRF)
- Insecure direct object references
- File upload vulnerabilities
- API security issues
- Trading logic manipulation

#### Out-of-Scope Vulnerabilities

- Issues in legacy forex-connect dependencies (see policy above)
- Vulnerabilities requiring physical access
- Social engineering attacks
- DoS attacks against third-party services
- Issues in development/testing environments

## Security Best Practices for Contributors

### Code Review Requirements

- All code changes require security review
- Automated security testing in CI/CD pipeline
- Static analysis with security-focused linting
- Dynamic testing for API security

### Secure Development Guidelines

1. **Input Validation**: Validate all inputs at application boundaries
2. **Output Encoding**: Properly encode outputs to prevent XSS
3. **Authentication**: Use centralized authentication mechanisms
4. **Authorization**: Implement principle of least privilege
5. **Logging**: Log security events without exposing sensitive data
6. **Error Handling**: Avoid information disclosure in error messages

## Financial Industry Compliance

### Regulatory Considerations

FXML4 is designed to support compliance with:

- **MiFID II** (Markets in Financial Instruments Directive)
- **GDPR** (General Data Protection Regulation)
- **PCI DSS** (for payment processing components)
- **SOC 2 Type II** (planned certification)

### Data Protection

- **Encryption**: AES-256 for data at rest, TLS 1.3 for data in transit
- **Key Management**: Hardware Security Module (HSM) integration planned
- **Access Logging**: Comprehensive audit trails for all data access
- **Data Retention**: Configurable retention policies per regulation

## Security Testing Results

### Latest Security Assessment (2025-01-19)

- **API Endpoints Tested**: 145+
- **Security Test Categories**: 8 (OWASP Top 10 coverage)
- **Critical Vulnerabilities**: 0
- **High Severity**: 0
- **Medium Severity**: 2 (rate limiting edge cases - documented)
- **Test Coverage**: 94% for security-critical components

### Automated Security Testing

- **Daily**: Dependency vulnerability scanning (excluding legacy financial libs)
- **Per Commit**: Static analysis and security linting
- **Weekly**: Dynamic security testing of API endpoints
- **Monthly**: Comprehensive penetration testing

## Environment Variables Reference

### Required Security Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `FXML4_JWT_SECRET_KEY` | JWT signing secret (minimum 32 chars) | `your-super-secure-jwt-secret-key-here` |
| `FXML4_JWT_TOKEN_EXPIRE_MINUTES` | JWT token expiration time | `60` |
| `FXML4_DEMO_ADMIN_PASSWORD` | Demo admin user password | `secure-admin-password` |
| `FXML4_DEMO_USER_PASSWORD` | Demo user password | `secure-user-password` |

### Database Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `FXML4_DB_HOST` | Database host | `localhost` |
| `FXML4_DB_PORT` | Database port | `5433` |
| `FXML4_DB_NAME` | Database name | `fxml4` |
| `FXML4_DB_USER` | Database user | `postgres` |
| `FXML4_DB_PASSWORD` | Database password | ⚠️ **Must be set** |

### External API Keys

| Variable | Description |
|----------|-------------|
| `POLYGON_API_KEY` | Polygon.io financial data API key |
| `ALPHA_VANTAGE_API_KEY` | Alpha Vantage financial data API key |
| `FRED_API_KEY` | Federal Reserve Economic Data API key |
| `OPENAI_API_KEY` | OpenAI API key for LLM services |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude models |
| `PINECONE_API_KEY` | Pinecone vector database API key |
| `PINECONE_ENVIRONMENT` | Pinecone environment identifier |

## Security Implementation

### 1. Configuration Loading Priority

The configuration system loads values in this order (highest to lowest priority):

1. **Environment Variables** (highest priority)
2. **Configuration File** (default.yaml)
3. **Default Values** (lowest priority)

### 2. JWT Security

- JWT secrets are loaded from `FXML4_JWT_SECRET_KEY` environment variable
- Fallback to configuration file (marked as insecure)
- **Production requirement**: Set strong, unique JWT secret (minimum 32 characters)

### 3. Demo User Security

- Demo user passwords are loaded from environment variables
- Default passwords are marked as insecure
- **Production requirement**: Disable demo users or set strong passwords

### 4. Database Security

- All database credentials use environment variables
- Docker Compose supports password override
- **Production requirement**: Use strong database passwords

### 5. API Key Management

- All external API keys use environment variables
- Placeholder values in configuration files
- **Production requirement**: Set actual API keys via environment

## Contact Information

- **Security Team**: security@fxml4.com
- **General Questions**: info@fxml4.com
- **GitHub Security Advisories**: https://github.com/meridianp/fxml4/security/advisories

---

*This security policy is reviewed quarterly and updated as needed to reflect current security practices and threat landscape.*

**Last Updated**: January 19, 2025
**Policy Version**: 2.0
**Next Review**: April 19, 2025
