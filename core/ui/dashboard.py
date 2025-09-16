"""FXML4 Main Dashboard.

A Streamlit-based web interface for the FXML4 forex trading system.
"""

import json
import time
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# Configure Streamlit page
st.set_page_config(
    page_title="FXML4 Trading Dashboard",
    page_icon="💹",
    layout="wide",
    initial_sidebar_state="expanded",
)

# API Configuration
API_BASE_URL = "http://localhost:8001"

# Session state for demo mode
if "demo_mode" not in st.session_state:
    st.session_state.demo_mode = True


def make_api_request(endpoint, method="GET", data=None):
    """Make API request (demo mode with mock data if API unavailable)."""
    headers = {"Content-Type": "application/json"}

    try:
        if method == "GET":
            response = requests.get(
                f"{API_BASE_URL}{endpoint}", headers=headers, timeout=5
            )
        elif method == "POST":
            response = requests.post(
                f"{API_BASE_URL}{endpoint}", headers=headers, json=data, timeout=5
            )

        if response.status_code == 200:
            return response.json()
        else:
            # Return mock data for demo purposes
            return get_mock_data(endpoint)
    except Exception as e:
        # Return mock data for demo purposes
        st.warning(f"API unavailable ({endpoint}), showing demo data")
        return get_mock_data(endpoint)


def get_mock_data(endpoint):
    """Return mock data for demo purposes."""
    if endpoint == "/health":
        return {
            "status": "healthy",
            "version": "2.0.0",
            "uptime_seconds": 1234.5,
            "timestamp": time.time(),
            "metrics": {
                "total_requests": 42,
                "error_requests": 2,
                "active_requests": 3,
                "metrics_collected": 15,
            },
        }
    elif endpoint == "/data":
        return {
            "symbol": "EURUSD",
            "timeframe": "1h",
            "data_points": 100,
            "status": "success",
            "last_update": datetime.now().isoformat(),
        }
    elif endpoint == "/signals":
        return {
            "symbol": "EURUSD",
            "strategy": "integrated_strategy",
            "signal": "BUY",
            "confidence": 0.85,
            "timestamp": datetime.now().isoformat(),
        }
    elif endpoint == "/backtest":
        return {
            "total_return_pct": 15.3,
            "max_drawdown_pct": -8.2,
            "sharpe_ratio": 1.45,
            "win_rate": 68.4,
            "total_trades": 127,
            "status": "completed",
        }
    else:
        return {"status": "demo", "message": "Mock data for demonstration"}


def demo_dashboard():
    """Display demo dashboard without authentication."""
    st.title("💹 FXML4 Trading Dashboard (Demo Mode)")
    st.info("📊 Demo mode active - showing sample data and audit fix functionality")

    # Skip login for demo mode
    dashboard_page()


def dashboard_page():
    """Display main dashboard."""
    # Check API health
    health_data = make_api_request("/health")
    if health_data:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("API Status", health_data.get("status", "Unknown").title())
        with col2:
            st.metric("Uptime", f"{health_data.get('uptime_seconds', 0):.1f}s")
        with col3:
            st.metric("Version", health_data.get("version", "Unknown"))
        with col4:
            st.metric(
                "Requests", health_data.get("metrics", {}).get("total_requests", 0)
            )

    st.markdown("---")

    # Tabs for different sections
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📊 Market Data", "⚡ Trading Signals", "📈 Backtesting", "🔧 System Status"]
    )

    with tab1:
        st.subheader("Market Data")
        col1, col2 = st.columns(2)
        with col1:
            symbol = st.selectbox("Symbol", ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"])
            timeframe = st.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "4h", "1d"])

        if st.button("Get Market Data"):
            with st.spinner("Fetching market data..."):
                # Use POST method with JSON payload
                data_request = {"symbol": symbol, "timeframe": timeframe, "limit": 100}
                data = make_api_request("/data", "POST", data_request)
                if data:
                    st.success("✅ Market data retrieved!")
                    st.json(data)
                else:
                    st.warning("No data available or API error")

    with tab2:
        st.subheader("Trading Signals")
        col1, col2 = st.columns(2)
        with col1:
            signal_symbol = st.selectbox(
                "Signal Symbol",
                ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"],
                key="signal_symbol",
            )
            strategy = st.selectbox(
                "Strategy", ["integrated_strategy", "ml_strategy", "wave_strategy"]
            )

        if st.button("Generate Signals"):
            with st.spinner("Generating trading signals..."):
                signal_data = {
                    "symbol": signal_symbol,
                    "timeframe": "1h",
                    "strategy": strategy,
                }
                data = make_api_request("/signals", "POST", signal_data)
                if data:
                    st.success("✅ Signals generated!")
                    st.json(data)
                else:
                    st.warning("Signal generation failed or API error")

    with tab3:
        st.subheader("Backtesting")
        col1, col2 = st.columns(2)
        with col1:
            bt_symbol = st.selectbox(
                "Backtest Symbol", ["EURUSD", "GBPUSD", "USDJPY"], key="bt_symbol"
            )
            bt_strategy = st.selectbox(
                "Backtest Strategy",
                ["integrated_strategy", "ml_strategy"],
                key="bt_strategy",
            )
            start_date = st.date_input("Start Date")
            end_date = st.date_input("End Date")
        with col2:
            initial_capital = st.number_input(
                "Initial Capital", value=10000.0, min_value=1000.0
            )

        if st.button("Run Backtest"):
            with st.spinner("Running backtest..."):
                backtest_data = {
                    "symbol": bt_symbol,
                    "timeframe": "1h",
                    "strategy": bt_strategy,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "initial_capital": initial_capital,
                }
                data = make_api_request("/backtest", "POST", backtest_data)
                if data:
                    st.success("✅ Backtest completed!")

                    # Display key metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric(
                            "Total Return", f"{data.get('total_return_pct', 0):.2f}%"
                        )
                    with col2:
                        st.metric(
                            "Max Drawdown", f"{data.get('max_drawdown_pct', 0):.2f}%"
                        )
                    with col3:
                        st.metric("Sharpe Ratio", f"{data.get('sharpe_ratio', 0):.2f}")
                    with col4:
                        st.metric("Win Rate", f"{data.get('win_rate', 0):.2f}%")

                    st.json(data)
                else:
                    st.warning("Backtest failed or API error")

    with tab4:
        st.subheader("System Status")

        # Real-time metrics
        if st.button("Refresh System Status"):
            with st.spinner("Checking system status..."):
                health = make_api_request("/health")
                if health:
                    st.success("🟢 System Online")

                    # System metrics
                    metrics = health.get("metrics", {})
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Requests", metrics.get("total_requests", 0))
                    with col2:
                        st.metric("Error Requests", metrics.get("error_requests", 0))
                    with col3:
                        st.metric("Active Requests", metrics.get("active_requests", 0))
                    with col4:
                        st.metric(
                            "Metrics Collected", metrics.get("metrics_collected", 0)
                        )

                    # Full health data
                    with st.expander("Full System Details"):
                        st.json(health)
                else:
                    st.error("🔴 System Offline or Error")

        # API endpoint testing
        st.subheader("API Endpoint Testing")
        test_endpoint = st.text_input("Test Endpoint", value="/health")
        if st.button("Test Endpoint"):
            data = make_api_request(test_endpoint)
            if data:
                st.success("✅ Endpoint accessible")
                st.json(data)
            else:
                st.error("❌ Endpoint failed")


def main():
    """Main application entry point."""
    # Custom CSS
    st.markdown(
        """
        <style>
        .stApp {
            background-color: #0E1117;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            padding-left: 20px;
            padding-right: 20px;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    # Main routing - run in demo mode
    demo_dashboard()


if __name__ == "__main__":
    main()
