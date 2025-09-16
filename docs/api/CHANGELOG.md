# API Changelog

All notable changes to the FXML4 API will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2024-01-01

### Added
- WebSocket support for real-time data streaming
- Batch operations endpoint (`/api/v2/batch`)
- Monte Carlo simulation in backtesting
- Walk-forward optimization
- Enhanced pagination with cursor support
- Advanced filtering options for all endpoints
- Signal strength metrics
- New timeframes: 3m, 2h, 6h, 12h
- New strategies: hybrid, custom, ensemble
- TypeScript type definitions
- Python async client
- GraphQL endpoint (beta)

### Changed
- Improved rate limiting with sliding window
- Enhanced error responses with detailed field validation
- Standardized pagination across all endpoints
- Unified response format with request IDs
- Better API versioning with header negotiation

### Deprecated
- API v1 endpoints (sunset date: 2024-07-01)
- Legacy authentication method
- Non-paginated list endpoints

### Security
- Added OAuth2 scopes for fine-grained permissions
- Implemented API key rotation
- Enhanced audit logging
- Added request signing for sensitive operations

## [1.5.0] - 2023-10-01

### Added
- Risk management endpoints
- Manual execution interface
- Performance metrics API
- Comparative analysis endpoint

### Fixed
- Memory leak in WebSocket connections
- Incorrect timestamp formatting in some responses
- Rate limit header accuracy

## [1.4.0] - 2023-07-01

### Added
- Support for cryptocurrency pairs
- Extended backtest reporting
- Email notifications for signals

### Changed
- Increased rate limits for Pro tier
- Improved backtest performance

### Fixed
- Timezone handling in historical data
- Rounding errors in profit calculations

## [1.3.0] - 2023-04-01

### Added
- Elliott Wave pattern detection
- Sentiment analysis integration
- Portfolio-level analytics

### Changed
- Upgraded to Python 3.11
- Improved ML model accuracy

### Deprecated
- Old signal format (use v2 format)

## [1.2.0] - 2023-01-01

### Added
- Machine learning strategy
- Advanced technical indicators
- Multi-symbol backtesting

### Fixed
- Data gap handling
- WebSocket reconnection logic

## [1.1.0] - 2022-10-01

### Added
- Basic WebSocket support
- Rate limiting
- API documentation

### Changed
- Improved response times
- Better error messages

## [1.0.0] - 2022-07-01

### Added
- Initial API release
- Market data endpoints
- Signal generation
- Basic backtesting
- Authentication system

---

## Version Support Policy

- **Current**: Full support with new features
- **Deprecated**: Security updates only, migration recommended
- **Sunset**: Read-only access, no updates
- **Retired**: No access, migration required

## Migration Guides

- [v1.x to v2.0](./guides/migration-v1-to-v2.md)
- [v0.x to v1.0](./guides/migration-v0-to-v1.md)
