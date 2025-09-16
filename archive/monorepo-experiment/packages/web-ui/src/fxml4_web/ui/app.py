"""
Main Streamlit application for FXML4.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import requests
import json
from typing import Dict, Any, List

# Page configuration
st.set_page_config(
    page_title="FXML4 Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API configuration
API_BASE_URL = st.secrets.get("api_url", "http://localhost:8000/api/v1")
API_TOKEN = None


def get_auth_token(username: str, password: str) -> str:
    """Authenticate and get token."""
    response = requests.post(
        f"{API_BASE_URL}/auth/token",
        data={"username": username, "password": password}
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    return None


def api_request(endpoint: str, method: str = "GET", data: Dict = None, token: str = None):
    """Make API request."""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    url = f"{API_BASE_URL}/{endpoint}"
    
    if method == "GET":
        response = requests.get(url, headers=headers, params=data)
    elif method == "POST":
        response = requests.post(url, headers=headers, json=data)
    else:
        response = requests.request(method, url, headers=headers, json=data)
    
    if response.status_code == 200:
        return response.json()
    return None


def login_page():
    """Display login page."""
    st.title("🔐 FXML4 Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            token = get_auth_token(username, password)
            if token:
                st.session_state["token"] = token
                st.session_state["username"] = username
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid credentials")


def dashboard_page():
    """Display main dashboard."""
    st.title("📊 FXML4 Trading Dashboard")
    
    # Get account summary
    summary = api_request("analytics/summary", token=st.session_state.get("token"))
    
    if summary:
        # Display key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Account Value",
                f"${summary['account_value']:,.2f}",
                f"{summary['daily_pnl_pct']:.2f}%"
            )
        
        with col2:
            st.metric(
                "Daily P&L",
                f"${summary['daily_pnl']:,.2f}",
                delta_color="normal"
            )
        
        with col3:
            st.metric(
                "Open Positions",
                summary['open_positions']
            )
        
        with col4:
            st.metric(
                "Margin Available",
                f"${summary['margin_available']:,.2f}"
            )
    
    # Equity curve
    st.subheader("📈 Equity Curve")
    
    period = st.selectbox("Period", ["1D", "1W", "1M", "3M", "6M", "1Y"], index=2)
    
    equity_data = api_request(
        f"analytics/equity-curve?period={period}",
        token=st.session_state.get("token")
    )
    
    if equity_data and equity_data.get("data"):
        df = pd.DataFrame(equity_data["data"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        
        # Create figure with secondary y-axis
        fig = go.Figure()
        
        # Add equity line
        fig.add_trace(go.Scatter(
            x=df["timestamp"],
            y=df["equity"],
            name="Equity",
            line=dict(color="blue", width=2)
        ))
        
        # Add drawdown area
        fig.add_trace(go.Scatter(
            x=df["timestamp"],
            y=df["drawdown"],
            name="Drawdown %",
            fill='tozeroy',
            fillcolor='rgba(255,0,0,0.2)',
            line=dict(color="red", width=1),
            yaxis='y2'
        ))
        
        # Update layout
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Equity ($)",
            yaxis2=dict(
                title="Drawdown (%)",
                overlaying='y',
                side='right'
            ),
            hovermode='x unified',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)


def positions_page():
    """Display positions page."""
    st.title("💼 Positions")
    
    # Get positions
    positions = api_request("trading/positions", token=st.session_state.get("token"))
    
    if positions:
        if len(positions) > 0:
            # Convert to DataFrame
            df = pd.DataFrame(positions)
            
            # Display positions table
            st.dataframe(
                df[["symbol", "side", "quantity", "entry_price", 
                    "current_price", "unrealized_pnl"]],
                use_container_width=True
            )
            
            # Position charts
            col1, col2 = st.columns(2)
            
            with col1:
                # P&L by position
                fig = px.bar(
                    df,
                    x="symbol",
                    y="unrealized_pnl",
                    color="unrealized_pnl",
                    color_continuous_scale=["red", "yellow", "green"],
                    title="Unrealized P&L by Position"
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Position sizes
                fig = px.pie(
                    df,
                    values="quantity",
                    names="symbol",
                    title="Position Sizes"
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No open positions")
    else:
        st.error("Failed to load positions")


def signals_page():
    """Display signals page."""
    st.title("🎯 Trading Signals")
    
    # Signal generation form
    with st.form("signal_form"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            symbol = st.selectbox("Symbol", ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"])
        
        with col2:
            timeframe = st.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "4h", "1d"])
        
        with col3:
            strategy = st.selectbox("Strategy", ["default", "ma_cross", "ml_ensemble"])
        
        generate = st.form_submit_button("Generate Signals")
        
        if generate:
            signals = api_request(
                "trading/signals/generate",
                method="POST",
                data={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "strategy": strategy
                },
                token=st.session_state.get("token")
            )
            
            if signals:
                st.session_state["latest_signals"] = signals
    
    # Display signals
    if "latest_signals" in st.session_state:
        signals = st.session_state["latest_signals"]
        
        for signal in signals:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if signal["signal_type"] == "BUY":
                    st.success(f"🟢 {signal['signal_type']}")
                elif signal["signal_type"] == "SELL":
                    st.error(f"🔴 {signal['signal_type']}")
                else:
                    st.info(f"⚪ {signal['signal_type']}")
            
            with col2:
                st.metric("Symbol", signal["symbol"])
            
            with col3:
                st.metric("Strength", f"{signal['strength']:.2f}")
            
            with col4:
                st.metric("Price", f"{signal['price']:.5f}")
            
            # Show metadata
            with st.expander("Signal Details"):
                st.json(signal["metadata"])


def backtest_page():
    """Display backtesting page."""
    st.title("🔄 Backtesting")
    
    tab1, tab2 = st.tabs(["Run Backtest", "Results"])
    
    with tab1:
        # Backtest configuration
        with st.form("backtest_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                strategy = st.selectbox("Strategy", ["ma_cross", "ml_signals", "elliott_wave"])
                symbols = st.multiselect(
                    "Symbols",
                    ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"],
                    default=["EURUSD"]
                )
                start_date = st.date_input(
                    "Start Date",
                    value=datetime.now() - timedelta(days=180)
                )
                end_date = st.date_input("End Date", value=datetime.now())
            
            with col2:
                initial_capital = st.number_input(
                    "Initial Capital",
                    min_value=1000,
                    value=10000,
                    step=1000
                )
                commission = st.number_input(
                    "Commission",
                    min_value=0.0,
                    value=0.001,
                    step=0.0001,
                    format="%.4f"
                )
                timeframe = st.selectbox("Timeframe", ["1h", "4h", "1d"])
            
            run_backtest = st.form_submit_button("Run Backtest")
            
            if run_backtest:
                # Start backtest
                result = api_request(
                    "backtest/run",
                    method="POST",
                    data={
                        "strategy": strategy,
                        "symbols": symbols,
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "initial_capital": initial_capital,
                        "commission": commission,
                        "timeframe": timeframe
                    },
                    token=st.session_state.get("token")
                )
                
                if result:
                    st.success(f"Backtest started: {result['backtest_id']}")
                    st.session_state["current_backtest"] = result["backtest_id"]
    
    with tab2:
        # Display results
        if "current_backtest" in st.session_state:
            backtest_id = st.session_state["current_backtest"]
            
            # Check status
            status = api_request(
                f"backtest/{backtest_id}/status",
                token=st.session_state.get("token")
            )
            
            if status:
                st.info(f"Status: {status['status']} ({status['progress']}%)")
                
                if status["status"] == "COMPLETED":
                    # Get results
                    results = api_request(
                        f"backtest/{backtest_id}",
                        token=st.session_state.get("token")
                    )
                    
                    if results:
                        # Display metrics
                        col1, col2, col3 = st.columns(3)
                        
                        metrics = results["metrics"]
                        with col1:
                            st.metric("Total Return", f"{metrics['total_return']}%")
                            st.metric("Sharpe Ratio", f"{metrics['sharpe_ratio']}")
                        
                        with col2:
                            st.metric("Max Drawdown", f"{metrics['max_drawdown']}%")
                            st.metric("Win Rate", f"{metrics['win_rate']}%")
                        
                        with col3:
                            st.metric("Total Trades", metrics['total_trades'])
                            st.metric("Profit Factor", f"{metrics['profit_factor']}")
                        
                        # Equity curve
                        if results.get("equity_curve"):
                            df = pd.DataFrame(results["equity_curve"])
                            df["timestamp"] = pd.to_datetime(df["timestamp"])
                            
                            fig = px.line(
                                df,
                                x="timestamp",
                                y="equity",
                                title="Backtest Equity Curve"
                            )
                            st.plotly_chart(fig, use_container_width=True)


def main():
    """Main application."""
    # Initialize session state
    if "token" not in st.session_state:
        st.session_state["token"] = None
    
    # Check authentication
    if st.session_state["token"] is None:
        login_page()
        return
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    st.sidebar.info(f"Logged in as: {st.session_state.get('username', 'User')}")
    
    page = st.sidebar.radio(
        "Go to",
        ["Dashboard", "Positions", "Signals", "Backtesting", "Settings"]
    )
    
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()
    
    # Display selected page
    if page == "Dashboard":
        dashboard_page()
    elif page == "Positions":
        positions_page()
    elif page == "Signals":
        signals_page()
    elif page == "Backtesting":
        backtest_page()
    elif page == "Settings":
        st.title("⚙️ Settings")
        st.info("Settings page coming soon...")


if __name__ == "__main__":
    main()