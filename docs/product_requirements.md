# FXML4 Product Requirements

This document outlines the functional and non-functional requirements for the FXML4 trading platform.

## Overview
FXML4 combines machine learning models, Elliott Wave analysis, and generative AI to generate trading signals for forex and other markets. The platform provides backtesting, optimization, and an interactive user interface.

## User Personas
- **Quantitative Trader** – designs automated strategies and requires detailed backtests.
- **Discretionary Analyst** – reviews market patterns and analytics produced by the platform.
- **Developer** – extends the system with new data sources or models.

## Functional Requirements
1. **Data Ingestion**
   - Pull historical and real-time data from multiple feeds.
   - Support instrument metadata including tick or pip size for risk calculations.
2. **Feature Engineering**
   - Generate technical, price pattern, volume, session, and wave-based features.
3. **Signal Generation**
   - Combine ML predictions, wave analysis, technical indicators, and sentiment.
   - Provide confidence scores and explainability metadata.
4. **Backtesting**
   - Simulate strategies with realistic execution costs, slippage, and commissions.
   - Calculate performance metrics including Sharpe and Sortino ratios using a configurable risk-free rate.
5. **Optimization and Reinforcement Learning**
   - Support hyper-parameter optimization and reinforcement learning for strategy tuning.
6. **API and UI**
   - Offer REST API endpoints for all major functions.
   - Provide a Streamlit-based dashboard for visualization and configuration.

## Non-Functional Requirements
- **Performance** – Capable of handling multi-year historical data on intraday time frames.
- **Reliability** – Automated tests with >99% pass rate and clear monitoring alerts.
- **Extensibility** – Modular architecture to plug in new data sources and models.
- **Security** – Authentication for API access and secure handling of credentials.

## Out of Scope
- Direct execution on live trading accounts.
- Portfolio-level risk management beyond position sizing.
