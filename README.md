

# FXML4 Unified Monorepo

**Enterprise-grade forex trading platform with machine learning, Elliott Wave analysis, and regulatory compliance**

[![CI/CD Pipeline](https://github.com/fxml/fxml4/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/fxml/fxml4/actions/workflows/ci-cd.yml)
[![Code Coverage](https://img.shields.io/badge/coverage-85%25-green)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![TypeScript](https://img.shields.io/badge/typescript-5.0+-blue.svg)](https://www.typescriptlang.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## 🏗️ Monorepo Structure

This unified repository combines four major components into a cohesive trading platform:

```
fxml4/
├── core/              # Main trading system (FastAPI backend)
│   ├── fxml4/         # Python package with ML, trading, and FIX protocol
│   ├── api/           # REST API endpoints and authentication
│   ├── brokers/       # Multi-broker integration (IB, FXCM, Manual)
│   └── ml/            # Machine learning pipeline and models
├── elliott_wave/      # Elliott Wave analysis with LLM integration
│   ├── analysis/      # Wave pattern detection and classification
│   ├── llm/           # Large Language Model integration
│   └── streamlit/     # Interactive dashboard
├── frontend/          # Next.js React application
│   ├── src/           # TypeScript source code
│   ├── components/    # Reusable React components
│   └── pages/         # Application pages and routing
├── infrastructure/    # Deployment and DevOps
│   ├── k8s/           # Kubernetes manifests
│   ├── docker/        # Container configurations
│   └── terraform/     # Infrastructure as Code
└── requirements/      # Unified dependency management
```

## 🎯 Project Objectives

### 1. **Production-Ready Trading Infrastructure**
- Multi-broker FIX protocol integration (Interactive Brokers, FXCM)
- Real-time data processing with TimescaleDB and Redis
- Enterprise-grade security with JWT authentication and 2FA
- Comprehensive risk management and compliance systems

### 2. **Advanced AI-Powered Analysis**
- Machine learning ensemble with 29+ models for signal generation
- Elliott Wave pattern detection enhanced with LLMs
- Deep reinforcement learning for strategy optimization
- Vector database integration for pattern similarity search

### 3. **Comprehensive Trading Platform**
- Real-time trading dashboard with Next.js frontend
- Event-driven backtesting framework with performance analytics
- Multi-timeframe analysis (1m, 5m, 1H, 4H, 1D)
- Automated trade execution with risk controls

### 4. **Regulatory Compliance & Security**
- SOC 2 Type II compliance preparation
- Comprehensive audit logging and trade surveillance
- Rate limiting, DDoS protection, and security headers
- Immutable audit trails for regulatory reporting

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Git

### Development Setup

```bash
# Clone the repository
git clone https://github.com/fxml/fxml4.git
cd fxml4

# Option 1: Quick setup with Makefile
make all-install    # Install all dependencies
make all-lint      # Lint all code
make all-test      # Run all tests

# Option 2: Component-specific setup
make core-install      # Core trading system only
make elliott-install   # Elliott Wave analysis only
make frontend-install  # Frontend application only

# Start services
make core-start        # http://localhost:8001 (Trading API)
make elliott-start     # http://localhost:8501 (Streamlit dashboard)
make frontend-start    # http://localhost:3000 (Next.js app)
```

### Manual Setup

```bash
# Python environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements/base.txt
pip install -r requirements/development.txt
pip install -e .

# Frontend setup
cd frontend
npm install
npm run dev
cd ..

# Start core services
python -m fxml4.api.main  # API server
```

### Docker Development

```bash
# Start full development environment
docker-compose up -d

# View logs
docker-compose logs -f

# Access services
# - API: http://localhost:8001
# - Frontend: http://localhost:3000
# - Elliott Wave Dashboard: http://localhost:8501
# - RabbitMQ Management: http://localhost:15672
# - TimescaleDB: localhost:5432
```

## 🧪 Testing

### Comprehensive Testing Suite

```bash
# Run all tests
make test              # Complete test suite
make test-unit         # Unit tests only
make test-integration  # Integration tests
make test-security     # Security tests
make test-e2e          # End-to-end tests

# Component-specific testing
make core-test         # Core system tests
make elliott-test      # Elliott Wave tests
make frontend-test     # Frontend tests

# Performance and load testing
make test-performance  # Performance regression tests
pytest tests/ -m "stress" --durations=10
```

### 🤖 AI-Enhanced TDD Framework

FXML4 includes an advanced AI-powered testing framework that provides intelligent test analysis, predictive insights, and automated optimization recommendations:

#### Quick Start with AI Testing

```bash
# Run tests with AI analysis enabled
npm test                    # Jest automatically uses AI reporter
npm run test:ai-analysis    # Generate comprehensive AI insights
npm run test:dashboard      # View AI dashboard at http://localhost:3001

# Generate AI test scenarios
npm run generate:test-scenarios    # Create AI-powered test cases
```

#### AI Framework Components

**1. Intelligent Test Analysis** (`src/ai-testing/AITestAnalyzer.ts`)
- Automatically analyzes test execution patterns
- Identifies performance degradation and reliability issues
- Generates actionable optimization recommendations
- Maintains comprehensive audit trails for financial compliance

**2. AI Test Data Generator** (`src/ai-testing/AITestDataGenerator.ts`)
- Creates sophisticated trading scenarios with realistic market conditions
- Generates edge cases based on financial domain expertise
- Produces smart test data with complex market relationships

**3. Interactive Dashboard** (`src/components/AITestDashboard.tsx`)
- Visual insights into test performance and AI recommendations
- Human-in-the-loop approval workflow for AI suggestions
- Real-time monitoring of test effectiveness metrics

**4. Safety & Compliance Framework** (`src/ai-testing/AITestSafetyFramework.ts`)
- Validates all AI-generated content against safety rules
- Ensures financial regulatory compliance
- Provides audit trails for all AI decisions and human approvals

#### AI Testing Workflow

```typescript
// 1. AI automatically collects test data via Jest reporter
// 2. Pattern analysis identifies optimization opportunities
const insights = aiTestAnalyzer.getInsights({ minConfidence: 70 });

// 3. Generate AI-powered test scenarios
const scenario = aiTestDataGenerator.generateTradingScenario({
  complexity: 7,
  riskLevel: 'high',
  duration: 45
});

// 4. Validate through safety framework
const validation = aiTestSafetyFramework.validateContent(
  'scenario_1',
  scenario,
  'scenario_generation'
);

// 5. Human approval for high-impact recommendations
if (insights.some(i => i.severity === 'critical')) {
  // Dashboard shows approval interface
  aiTestSafetyFramework.requestApproval(userId, 'insight_approval', insight);
}
```

#### Configuration

AI features are configured through `jest.config.js`:

```javascript
reporters: [
  'default',
  ['<rootDir>/src/ai-testing/JestAIReporter.ts', {
    outputPath: './ai-testing-reports',
    enableRealTimeAnalysis: true,
    minimumTestsForAnalysis: 5
  }]
]
```

#### AI Insights Dashboard

Access the AI testing dashboard at `http://localhost:3001/ai-dashboard` to:

- **View AI-Generated Insights**: Performance, reliability, and coverage recommendations
- **Approve/Reject AI Suggestions**: Human-in-the-loop validation for critical changes
- **Monitor Test Scenarios**: AI-generated trading test cases with complexity analysis
- **Track Audit Trail**: Complete history of AI decisions and human approvals
- **Performance Metrics**: Measure AI framework effectiveness over time

#### Safety & Compliance Features

- **Financial Compliance**: Ensures all AI-generated content meets regulatory standards
- **Human Oversight**: Critical recommendations require human approval
- **Audit Trails**: Complete logging of AI decisions for compliance reporting
- **Risk Assessment**: Automatic evaluation of AI suggestion impact and risks
- **Content Validation**: Multi-layered safety rules prevent inappropriate content generation

### Test Categories

- **unit**: Fast, isolated tests
- **integration**: Database and external service tests
- **security**: Authentication and authorization tests
- **performance**: Load and performance benchmarks
- **e2e**: Complete user workflow tests
- **slow**: Tests that take >5 seconds
- **requires_ib**: Tests needing Interactive Brokers connection
- **requires_fxcm**: Tests needing FXCM connection

## 📊 Architecture Overview

### Technology Stack

**Backend (Core)**
- **Framework**: FastAPI with async/await
- **Database**: TimescaleDB (PostgreSQL + time-series)
- **Cache**: Redis for session and data caching
- **Message Queue**: RabbitMQ for async processing
- **Security**: JWT with refresh tokens, 2FA support

**Frontend**
- **Framework**: Next.js 14 with App Router
- **Language**: TypeScript with strict mode
- **Styling**: Tailwind CSS with custom design system
- **State Management**: Zustand for client state
- **Charts**: TradingView widgets and Chart.js

**Elliott Wave Analysis**
- **Framework**: Streamlit for interactive dashboards
- **LLM Integration**: OpenAI, Anthropic, and local models
- **Vector Database**: Pinecone for pattern similarity
- **Analysis**: Pandas, NumPy, and custom algorithms

**Infrastructure**
- **Containerization**: Docker with multi-stage builds
- **Orchestration**: Kubernetes with Helm charts
- **CI/CD**: GitHub Actions with comprehensive testing
- **Monitoring**: Prometheus, Grafana, and structured logging

### Data Flow

```
Market Data → Data Processing → Feature Engineering → ML Models → Signal Generation → Risk Management → Order Execution
     ↑              ↓                ↓                ↓             ↓                ↓              ↓
External APIs → TimescaleDB → Real-time Cache → Model Inference → Trading Signals → Compliance → Broker APIs
```

## 🛠️ Development Guidelines

### Code Quality

```bash
# Formatting and linting
black .                # Code formatting
isort .               # Import sorting
flake8 .              # Linting
mypy core/            # Type checking

# Pre-commit hooks (recommended)
pre-commit install    # Automatic quality checks on commit
```

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes following the coding standards
4. Add tests for new functionality
5. Ensure all tests pass: `make all-test`
6. Commit your changes: `git commit -m 'Add amazing feature'`
7. Push to the branch: `git push origin feature/amazing-feature`
8. Open a Pull Request

### Testing Requirements

- All new features must include tests
- Maintain minimum 80% test coverage
- Use appropriate test markers for CI/CD optimization
- Mock external dependencies in unit tests

## 📚 Documentation

- [API Documentation](http://localhost:8001/docs) - Interactive API docs when running
- [Architecture Guide](docs/architecture.md) - Detailed system design
- [Development Guide](docs/development.md) - Setup and contribution guidelines
- [Deployment Guide](docs/deployment.md) - Production deployment instructions
- [User Manual](docs/user-guide.md) - End-user documentation

## 🔒 Security

This project implements enterprise-grade security:

- JWT authentication with refresh token rotation
- Multi-factor authentication (2FA) support
- Comprehensive input validation and sanitization
- Rate limiting and DDoS protection
- Audit logging for all trading activities
- SOC 2 Type II compliance preparation

Report security vulnerabilities to [security@fxml.io](mailto:security@fxml.io).

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Support

- **Documentation**: [docs.fxml.io](https://docs.fxml.io)
- **Issues**: [GitHub Issues](https://github.com/fxml/fxml4/issues)
- **Discussions**: [GitHub Discussions](https://github.com/fxml/fxml4/discussions)
- **Email**: [support@fxml.io](mailto:support@fxml.io)

---

## Previous Legacy Documentation

1. **Subjectivity of Elliott Waves**  
   - Manually labeling Elliott waves requires expert knowledge and is prone to human bias. Automating it helps remove inconsistencies and speeds up analysis.

2. **Complexity of Modern Markets**  
   - Large volumes of tick-by-tick data in forex require sophisticated, efficient processing that merges classical analysis (EWP) with data-driven AI insights.

3. **Bridging the Gap Between Traditional TA and AI**  
   - AI systems can be “black-box”; combining them with Elliott wave analysis can improve interpretability while leveraging AI’s adaptability and scalability.

4. **Demand for Actionable Intelligence**  
   - Traders and analysts want signals (buy/sell points, wave confirmations) grounded in both classical market theory and robust backtesting results.

---

## 3. Detailed Approach

1. **System Architecture**  
   - **Multi-Agent Design**: Inspired by the “ElliottAgents” framework.  
     - A **Data Engineer Agent** retrieves forex data (from Yahoo Finance, FXCM, or other sources).  
     - An **Elliott Wave Analyst Agent** runs wave-detection algorithms.  
     - A **Backtester Agent** uses DRL to verify wave-based signals on historical data and refine future detection.  
     - A **Tech Analysis Expert Agent** or **LLM-based Agent** references wave theory rules (via RAG or knowledge base) to validate wave labeling.  
     - An **Investment Advisor Agent** combines wave signals with risk management to produce recommended trades.  
     - A **Report/Visualization Agent** generates charts, logs, and user-facing summary documents.

2. **Elliott Wave Pattern Recognition**  
   - **Input**: Price data for the chosen forex pair (candlestick open, high, low, close, volume if available).  
   - **Wave Extraction Logic**:  
     - Implement wave-counting constraints (impulse wave vs. corrective wave, non-overlapping rules, Fibonacci retracements, etc.).  
     - Support multiple fractal degrees (short-term subwaves nested within larger waves).  
   - **Fibonacci Validation**:  
     - Check wave ratios for validation (e.g., wave 2 retraces 50–61.8% of wave 1, wave 3 extends 1.618× wave 1, etc.).  
   - **LLM-Enhanced Identification**:  
     - Prompt an LLM with RAG to cross-check wave counts, ensuring they follow standard EWP guidelines.  
     - Use LLM for textual explanations of wave structure and likely next move.

3. **Reinforcement Learning and Backtesting**  
   - **Historical Data**:  
     - For each identified wave pattern, assess subsequent price outcomes.  
     - Assign a reward/punishment based on prediction accuracy or theoretical profit/loss.  
   - **DRL Approach**:  
     - Train an RL agent to fine-tune wave-labelling thresholds, such as Fibonacci tolerances or wave validation rules, aiming to maximize cumulative “profit” or forecasting accuracy.  
   - **Incremental/Continuous Learning**:  
     - Store recognized patterns and results in a database.  
     - Periodically re-run the training with updated historical data to adapt to recent market changes.

4. **System Tools/Functions**  
   - **Data Handling**  
     - Integrate with broker APIs or data feeds (e.g., Oanda, FXCM) or use local CSV/HDF5 for offline analysis.  
     - Use `pandas` for data cleaning, resampling, and alignment.  
   - **Wave-Detection Algorithms**  
     - Core wave-counting function that locates potential peaks/troughs, labels subwaves, checks EWP constraints.  
   - **LLM & RAG**  
     - LLM prompts to interpret wave structures.  
     - Knowledge base for wave rules, EWP best practices, potential edge cases.  
   - **DRL Backtesting**  
     - Implement DQN or Policy Gradient (e.g., PPO) for evaluating the wave-labelling plus strategy.  
     - Possibly maintain an “experience replay” of wave patterns for improved training stability.  
   - **Visualization**  
     - Overlaid wave labels on candlestick charts (e.g., using `matplotlib` or `plotly`).  
     - Summary tables or dashboards with wave counts, recommended trades, risk metrics.  

5. **User Interface**    
   - **Streamlit or Dash** for a user-friendly web app.  
   - Provide real-time or near-real-time updates on wave signals, plus historical wave labeling for context.

---

## 4. Specific Logical Functions and Tasks

Below is a **high-level breakdown** of coding tasks and logical components needed:

1. **Data Pipeline**  
   - Connect to data source → Retrieve OHLC data → Clean/validate → Store in local structure (pandas DataFrame).

2. **Core Wave-Detection Module**  
   - Peak/Trough Identification: Find potential wave turning points.  
   - Pattern Labeling: Classify each wave segment with Elliott wave rules.  
   - Validation: Check each wave’s amplitude and retracement against Fibonacci rules.

3. **LLM Integration**  
   - Implement RAG storage for EWP texts, references, and examples of wave identification.  
   - Create prompts that pass current wave structure to the LLM for sanity checks or clarifications.  
   - Parse LLM output to confirm wave validity or adjust wave labeling.

4. **Backtesting + RL**  
   - Set up a rolling or incremental time window for evaluating wave predictions.  
   - Define a reward function (e.g., wave-based directional accuracy or simulated trading PnL).  
   - Train or update a DRL agent to refine wave detection parameters or strategy rules.

5. **Strategy/Signal Generation**  
   - For each recognized wave pattern, define potential trade signals (e.g., entering at the end of wave 2, wave 4, or wave 5).  
   - Attach risk management parameters (stop-loss, take-profit, trailing stops).

6. **Reporting & Visualization**  
   - Charts: Plot candlesticks with labeled waves (1-2-3-4-5, A-B-C, etc.).  
   - Text Summaries: Explanation from the LLM about the wave count, key fib levels, potential next moves.  
   - Performance Metrics: Show success rate of wave-based signals, DRL agent’s historical returns, etc.

7. **Continuous Deployment & Monitoring**  
   - Consider scheduling automatic re-training or re-analysis for new data.  
   - Possibly integrate alerts/notifications (email, Slack) when new wave patterns form.

---

## 5. Preliminary Timeline (High Level)

ASAP

---

## 6. Clarifying Questions

Before finalizing this project plan, below are some **bullet-point questions** to ensure we have all requirements:

- **Data Availability and Frequency**  
  - Which **currency pairs** are highest priority for analysis?  
  - What is the **preferred data source** for forex data (e.g., broker API vs. publicly available dataset)?  
  - Do you need **intraday analysis** (e.g., 15-minute or hourly candles) or just daily?

- **Scope of Elliott Waves**  
  - Are we focusing **only on fundamental impulsive (1-2-3-4-5) and corrective (A-B-C)** patterns, or do we need to handle **complex wave variations** (triangles, flats, zigzags, etc.)?

- **LLM and RAG**  
  - Do you have a **preferred LLM** (e.g., GPT-4) or will we use an open-source model?  
  - Is the system expected to run **fully offline** (local model) or is **API access** to a vendor (OpenAI, Azure, etc.) acceptable?  
  - How **large** is the external knowledge base for RAG? Should it be EWP references only, or also general macro/technical info?

- **DRL Objectives**  
  - What is the exact measure of “success” for the reinforcement learning agent?  
    - **Accuracy of wave detection** or **Profit/loss from trades**?  
  - Are you planning to use a **simulated trading environment** for the RL agent or purely wave-labelling feedback?

- **Reporting & Visualization**  
  - Do you envision a **web-based dashboard** (Streamlit, Dash) or is a **Jupyter notebook** interface sufficient?  
  - How detailed should the **final wave-labeled charts** be (e.g., multiple fractal layers, text notes, etc.)?

- **Deployment**  
  - Do you plan to **deploy** it on a server with frequent real-time updates, or is it a **research/offline analytics** application?  
  - Will it integrate with **live trading** execution eventually?

- **Team and Skill Sets**  
  - Do we have **in-house developers** who will maintain the code after initial deployment?  
  - Should we factor in training for end-users to interpret wave-labeled outputs or is the user base already comfortable with EWP?

- **Performance Constraints**  
  - What are the **latency** requirements for wave detection and re-labeling?  
  - Is it okay if the LLM-based wave verification step takes a few seconds, or do we need near **real-time** performance?

---
