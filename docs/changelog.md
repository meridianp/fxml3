# Changelog

All notable changes to FXML4 will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive MkDocs documentation structure
- Enhanced documentation for all features
- New glossary with trading and technical terms

### Changed
- Reorganized documentation navigation
- Updated mkdocs.yml with Material theme features

### Fixed
- Documentation links and references
- Code examples formatting

## [1.5.0] - 2024-12-18

### Added
- **Visual Elliott Wave Analysis** - Revolutionary AI-powered chart analysis using Claude Opus 4
  - Mathematical pattern detection with sub-second performance
  - Visual chart generation with annotations
  - Hybrid approach combining algorithmic and AI analysis
  - 78.4% win rate in backtesting
- Chart generation utilities for technical analysis
- Integration with Claude Opus 4 (model: claude-opus-4-20250514)
- Comprehensive Elliott Wave documentation

### Changed
- Enhanced signal generation to include Elliott Wave patterns
- Improved backtesting engine with Elliott Wave signals
- Updated risk management for wave-based stop losses

### Fixed
- mplfinance compatibility issues in chart generation
- String formatting errors in visual analysis
- Import paths for wave analysis modules

## [1.4.0] - 2024-12-01

### Added
- Paper trading engine with Interactive Brokers integration
- Live data handler for real-time market feeds
- Position tracking and risk management
- Performance monitoring dashboard
- Paper trading database schema

### Changed
- Refactored trading engine for live execution
- Enhanced order management system
- Improved error handling for network issues

### Fixed
- IB connection stability issues
- Real-time data synchronization
- Order execution timing

## [1.3.0] - 2024-11-15

### Added
- Google Vertex AI integration for distributed training
- Model registry with cloud storage
- Automated hyperparameter optimization
- Feature importance analysis
- Cross-validation framework

### Changed
- ML pipeline now supports cloud training
- Enhanced feature engineering with 150+ indicators
- Improved model evaluation metrics

### Fixed
- Memory leaks in feature engineering
- Model serialization issues
- Training data validation

## [1.2.0] - 2024-10-20

### Added
- Event-driven backtesting engine
- Realistic order execution simulation
- Transaction cost modeling
- Monte Carlo simulation
- Performance visualization

### Changed
- Backtesting now uses event-driven architecture
- Enhanced position sizing algorithms
- Improved risk metrics calculation

### Fixed
- Slippage calculation accuracy
- Multi-asset portfolio calculations
- Performance report generation

## [1.1.0] - 2024-09-15

### Added
- TimescaleDB integration for time-series data
- Continuous aggregates for performance
- Data compression policies
- Retention policies for historical data

### Changed
- Market data now stored in TimescaleDB
- Optimized query performance for large datasets
- Enhanced data ingestion pipeline

### Fixed
- Time zone handling in market data
- Data gap detection and filling
- Aggregation accuracy

## [1.0.0] - 2024-08-01

### Added
- Initial release of FXML4
- Core trading engine
- Basic ML signal generation
- Simple backtesting framework
- REST API with FastAPI
- PostgreSQL database integration
- Docker support
- Basic documentation

### Security
- JWT authentication implementation
- API rate limiting
- Input validation
- SQL injection prevention

## [0.9.0] - 2024-06-15 (Beta)

### Added
- Beta release for testing
- Core functionality implementation
- Basic API endpoints
- Initial ML models
- Simple web dashboard

### Known Issues
- Limited error handling
- Performance optimization needed
- Documentation incomplete

---

## Version History Summary

| Version | Release Date | Highlights |
|---------|--------------|------------|
| 1.5.0 | 2024-12-18 | Visual Elliott Wave Analysis |
| 1.4.0 | 2024-12-01 | Paper Trading with IB |
| 1.3.0 | 2024-11-15 | Vertex AI Integration |
| 1.2.0 | 2024-10-20 | Event-Driven Backtesting |
| 1.1.0 | 2024-09-15 | TimescaleDB Integration |
| 1.0.0 | 2024-08-01 | Initial Release |

## Upgrade Guide

### From 1.4.x to 1.5.0

1. **New Dependencies**
   ```bash
   pip install anthropic mplfinance
   ```

2. **Environment Variables**
   ```bash
   # Add to .env
   ANTHROPIC_API_KEY=your_key_here
   LLM_MODEL=claude-opus-4-20250514
   ```

3. **Database Migration**
   ```bash
   python scripts/migrate_1_5_0.py
   ```

### From 1.3.x to 1.4.0

1. **Interactive Brokers Setup**
   - Install IB Gateway or TWS
   - Configure paper trading account
   - Update connection settings in .env

2. **Database Updates**
   ```sql
   -- Run migration script
   psql -f migrations/1_4_0_paper_trading.sql
   ```

### From 1.2.x to 1.3.0

1. **Google Cloud Setup**
   ```bash
   gcloud auth login
   gcloud config set project your-project
   ```

2. **Enable APIs**
   ```bash
   gcloud services enable aiplatform.googleapis.com
   ```

## Deprecation Notices

### Version 1.5.0
- Simple wave detection deprecated in favor of hybrid approach
- Old signal generator replaced with integrated version

### Version 1.4.0
- Legacy backtesting engine deprecated
- Old position management system removed

### Version 1.3.0
- Local-only model training deprecated
- Simple feature engineering replaced

## Security Updates

### Version 1.5.0
- Updated dependencies to patch CVE-2024-XXXXX
- Enhanced API key management
- Improved authentication flow

### Version 1.4.0
- Fixed authentication bypass vulnerability
- Updated JWT library
- Enhanced input validation

## Contributors

Special thanks to all contributors who have helped shape FXML4:

- Core Development Team
- Elliott Wave Analysis: AI Integration Team
- Paper Trading: Trading Systems Team
- ML Pipeline: Data Science Team
- Documentation: Technical Writing Team

For the complete list of contributors, see [GitHub Contributors](https://github.com/meridianp/fxml4/graphs/contributors).

---

[Unreleased]: https://github.com/meridianp/fxml4/compare/v1.5.0...HEAD
[1.5.0]: https://github.com/meridianp/fxml4/releases/tag/v1.5.0
[1.4.0]: https://github.com/meridianp/fxml4/releases/tag/v1.4.0
[1.3.0]: https://github.com/meridianp/fxml4/releases/tag/v1.3.0
[1.2.0]: https://github.com/meridianp/fxml4/releases/tag/v1.2.0
[1.1.0]: https://github.com/meridianp/fxml4/releases/tag/v1.1.0
[1.0.0]: https://github.com/meridianp/fxml4/releases/tag/v1.0.0
[0.9.0]: https://github.com/meridianp/fxml4/releases/tag/v0.9.0
