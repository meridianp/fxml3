"""Streamlit UI for FXML3."""

import json
import os
import sys
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# Add the parent directory to path so we can import fxml3
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fxml3.config import Config
from fxml3.data_engineering.data_loader import ForexDataLoader
from fxml3.wave_analysis.elliott_wave import ElliottWaveAnalyzer


# API client for FXML3
class FXML3APIClient:
    """API client for interacting with the FXML3 API."""

    def __init__(self, api_url: str = None, api_key: str = None):
        """Initialize the API client.

        Args:
            api_url: URL of the FXML3 API
            api_key: API key for authentication
        """
        # Use environment variable if not provided
        self.api_url = api_url or os.getenv("API_URL", "http://localhost:8000")
        self.api_key = api_key or os.getenv("API_KEY")
        self.token = None

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests.

        Returns:
            Dictionary of headers
        """
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        elif self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def login(self, username: str, password: str) -> bool:
        """Login to the API.

        Args:
            username: Username
            password: Password

        Returns:
            True if login was successful, False otherwise
        """
        try:
            response = requests.post(
                f"{self.api_url}/token",
                data={"username": username, "password": password},
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data["access_token"]
                return True
            return False
        except Exception as e:
            st.error(f"Login error: {str(e)}")
            return False

    def get_user_profile(self) -> Dict[str, Any]:
        """Get user profile.

        Returns:
            User profile data
        """
        try:
            response = requests.get(
                f"{self.api_url}/api/v1/user/me",
                headers=self._get_headers(),
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            st.error(f"Error getting user profile: {str(e)}")
            return None

    def create_wave_analysis(
        self,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        wave_options: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Create a wave analysis request.

        Args:
            symbol: Symbol to analyze
            timeframe: Timeframe to analyze
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            wave_options: Wave analysis options

        Returns:
            Analysis request data including task_id
        """
        try:
            data = {
                "symbol": symbol,
                "timeframe": timeframe,
                "start_date": start_date,
                "end_date": end_date,
            }

            if wave_options:
                data["wave_options"] = wave_options

            response = requests.post(
                f"{self.api_url}/api/v1/analysis/waves",
                headers=self._get_headers(),
                json=data,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    return result.get("data")

            st.error(f"Error creating wave analysis: {response.text}")
            return None
        except Exception as e:
            st.error(f"Error creating wave analysis: {str(e)}")
            return None

    def get_wave_analysis(self, analysis_id: str) -> Dict[str, Any]:
        """Get wave analysis results.

        Args:
            analysis_id: ID of the analysis

        Returns:
            Analysis results
        """
        try:
            response = requests.get(
                f"{self.api_url}/api/v1/analysis/waves/{analysis_id}",
                headers=self._get_headers(),
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    return result.get("data")

            return None
        except Exception as e:
            st.error(f"Error getting wave analysis: {str(e)}")
            return None

    def create_strategy(
        self,
        wave_analysis_id: str,
        strategy_type: str,
        risk_parameters: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Create a trading strategy.

        Args:
            wave_analysis_id: ID of the wave analysis
            strategy_type: Type of strategy to create
            risk_parameters: Risk parameters for the strategy

        Returns:
            Strategy request data including task_id
        """
        try:
            data = {
                "wave_analysis_id": wave_analysis_id,
                "strategy_type": strategy_type,
            }

            if risk_parameters:
                data["risk_parameters"] = risk_parameters

            response = requests.post(
                f"{self.api_url}/api/v1/strategies",
                headers=self._get_headers(),
                json=data,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    return result.get("data")

            return None
        except Exception as e:
            st.error(f"Error creating strategy: {str(e)}")
            return None

    def get_strategy(self, strategy_id: str) -> Dict[str, Any]:
        """Get strategy details.

        Args:
            strategy_id: ID of the strategy

        Returns:
            Strategy details
        """
        try:
            response = requests.get(
                f"{self.api_url}/api/v1/strategies/{strategy_id}",
                headers=self._get_headers(),
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    return result.get("data")

            return None
        except Exception as e:
            st.error(f"Error getting strategy: {str(e)}")
            return None

    def create_backtest(
        self,
        strategy_id: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 10000.0,
        validation_methods: List[str] = None,
        slippage_model: str = "normal",
        spread_model: str = "variable",
        commission_model: str = "fixed",
    ) -> Dict[str, Any]:
        """Create a backtest.

        Args:
            strategy_id: ID of the strategy to backtest
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            initial_capital: Initial capital
            validation_methods: List of validation methods
            slippage_model: Slippage model
            spread_model: Spread model
            commission_model: Commission model

        Returns:
            Backtest request data including task_id
        """
        try:
            data = {
                "strategy_id": strategy_id,
                "start_date": start_date,
                "end_date": end_date,
                "initial_capital": initial_capital,
                "slippage_model": slippage_model,
                "spread_model": spread_model,
                "commission_model": commission_model,
            }

            if validation_methods:
                data["validation_methods"] = validation_methods

            response = requests.post(
                f"{self.api_url}/api/v1/backtests",
                headers=self._get_headers(),
                json=data,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    return result.get("data")

            return None
        except Exception as e:
            st.error(f"Error creating backtest: {str(e)}")
            return None

    def get_backtest(self, backtest_id: str) -> Dict[str, Any]:
        """Get backtest results.

        Args:
            backtest_id: ID of the backtest

        Returns:
            Backtest results
        """
        try:
            response = requests.get(
                f"{self.api_url}/api/v1/backtests/{backtest_id}",
                headers=self._get_headers(),
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    return result.get("data")

            return None
        except Exception as e:
            st.error(f"Error getting backtest: {str(e)}")
            return None

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get task status.

        Args:
            task_id: ID of the task

        Returns:
            Task status
        """
        try:
            response = requests.get(
                f"{self.api_url}/api/v1/tasks/{task_id}",
                headers=self._get_headers(),
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    return result.get("data")

            return None
        except Exception as e:
            st.error(f"Error getting task status: {str(e)}")
            return None

    def execute_agent_workflow(
        self, workflow_name: str, tasks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute a multi-agent workflow.

        Args:
            workflow_name: Name of the workflow
            tasks: List of tasks to execute

        Returns:
            Workflow request data including task_id
        """
        try:
            data = {"workflow_name": workflow_name, "tasks": tasks}

            response = requests.post(
                f"{self.api_url}/api/v1/agents/workflow",
                headers=self._get_headers(),
                json=data,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    return result.get("data")

            return None
        except Exception as e:
            st.error(f"Error executing workflow: {str(e)}")
            return None


# Load configuration
@st.cache_resource
def load_config() -> Config:
    """Load configuration.

    Returns:
        Configuration object
    """
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "config/default.yaml",
    )
    if os.path.exists(config_path):
        return Config.from_yaml(config_path)
    return Config()


# Initialize API client
@st.cache_resource
def get_api_client():
    return FXML3APIClient()


# App title and description
st.set_page_config(
    page_title="FXML3 - Elliott Wave Analysis",
    page_icon="📊",
    layout="wide",
)

st.title("FXML3 - AI-Enhanced Elliott Wave Analysis")
st.markdown(
    """
    **FXML3** is an AI-enhanced Elliott Wave analysis tool for forex markets.

    This application helps identify Elliott Wave patterns using advanced algorithms
    and validates them with LLM and reinforcement learning techniques.
    """
)

# Initialize API client
api_client = get_api_client()

# Load configuration
config = load_config()

# Authentication section in sidebar
st.sidebar.header("Authentication")

# Authentication type
auth_type = st.sidebar.radio(
    "Authentication Method", ["API Key", "Username/Password"], index=0
)

# API Key authentication
if auth_type == "API Key":
    api_key = st.sidebar.text_input("API Key", type="password")
    if api_key:
        api_client.api_key = api_key
        st.sidebar.success("API Key set")

# Username/Password authentication
else:
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")

    if st.sidebar.button("Login"):
        if username and password:
            if api_client.login(username, password):
                st.sidebar.success("Login successful")
                st.session_state["authenticated"] = True
            else:
                st.sidebar.error("Login failed")
        else:
            st.sidebar.warning("Please enter both username and password")

# Sidebar for settings
st.sidebar.header("Settings")

# Data source selection
data_source = st.sidebar.selectbox(
    "Data Source",
    ["Yahoo Finance", "FXCM", "CSV"],
    index=0,
)

# Symbol selection
symbol = st.sidebar.selectbox(
    "Symbol",
    config.data.symbols,
    index=0,
)

# Timeframe selection
timeframe = st.sidebar.selectbox(
    "Timeframe",
    config.data.timeframes,
    index=2,  # Default to daily
)

# Date range
today = datetime.now()
start_date = st.sidebar.date_input(
    "Start Date",
    today - timedelta(days=365),
)

end_date = st.sidebar.date_input(
    "End Date",
    today,
)

# Wave detection settings
st.sidebar.header("Wave Detection")

# Minimum wave size
min_wave_points = st.sidebar.slider(
    "Minimum Wave Points",
    min_value=3,
    max_value=20,
    value=5,
    step=1,
)

# Confidence threshold
confidence_threshold = st.sidebar.slider(
    "Confidence Threshold",
    min_value=0.0,
    max_value=1.0,
    value=0.7,
    step=0.05,
)

# Backtest settings
st.sidebar.header("Backtesting")

# Initial capital
initial_capital = st.sidebar.number_input(
    "Initial Capital",
    min_value=1000.0,
    max_value=1000000.0,
    value=10000.0,
    step=1000.0,
)

# Validation methods
validation_methods = st.sidebar.multiselect(
    "Validation Methods",
    ["monte_carlo", "walk_forward", "cross_market"],
    default=["monte_carlo"],
)

# Main content area with tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Dashboard", "Wave Analysis", "Strategy", "Backtesting", "Settings"]
)

with tab1:
    st.header("Dashboard")

    # Quick actions
    st.subheader("Quick Actions")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Run Wave Analysis", key="dashboard_wave"):
            if not (api_client.api_key or st.session_state.get("authenticated")):
                st.warning("Please authenticate first")
            else:
                # Prepare wave options
                wave_options = {
                    "include_subwaves": True,
                    "min_wave_points": min_wave_points,
                    "confidence_threshold": confidence_threshold,
                }

                with st.spinner("Running wave analysis..."):
                    result = api_client.create_wave_analysis(
                        symbol=symbol,
                        timeframe=timeframe,
                        start_date=start_date.strftime("%Y-%m-%d"),
                        end_date=end_date.strftime("%Y-%m-%d"),
                        wave_options=wave_options,
                    )

                    if result:
                        st.session_state["wave_analysis_task"] = result
                        st.success(
                            f"Analysis requested. Task ID: {result.get('task_id')}"
                        )
                        st.session_state["task_id"] = result.get("task_id")
                        st.session_state["analysis_id"] = result.get("analysis_id")
                    else:
                        st.error("Failed to create wave analysis request")

    with col2:
        if st.button("Create Strategy", key="dashboard_strategy"):
            if not (api_client.api_key or st.session_state.get("authenticated")):
                st.warning("Please authenticate first")
            elif not st.session_state.get("analysis_id"):
                st.warning("Please run wave analysis first")
            else:
                with st.spinner("Creating strategy..."):
                    risk_parameters = {
                        "risk_per_trade": 0.02,
                        "max_drawdown": 0.10,
                        "profit_target_multiplier": 1.5,
                    }

                    result = api_client.create_strategy(
                        wave_analysis_id=st.session_state["analysis_id"],
                        strategy_type="impulse_wave",
                        risk_parameters=risk_parameters,
                    )

                    if result:
                        st.session_state["strategy_task"] = result
                        st.success(
                            f"Strategy requested. Task ID: {result.get('task_id')}"
                        )
                        st.session_state["strategy_id"] = result.get("strategy_id")
                    else:
                        st.error("Failed to create strategy request")

    with col3:
        if st.button("Run Backtest", key="dashboard_backtest"):
            if not (api_client.api_key or st.session_state.get("authenticated")):
                st.warning("Please authenticate first")
            elif not st.session_state.get("strategy_id"):
                st.warning("Please create a strategy first")
            else:
                with st.spinner("Running backtest..."):
                    result = api_client.create_backtest(
                        strategy_id=st.session_state["strategy_id"],
                        start_date=start_date.strftime("%Y-%m-%d"),
                        end_date=end_date.strftime("%Y-%m-%d"),
                        initial_capital=initial_capital,
                        validation_methods=validation_methods,
                    )

                    if result:
                        st.session_state["backtest_task"] = result
                        st.success(
                            f"Backtest requested. Task ID: {result.get('task_id')}"
                        )
                        st.session_state["backtest_id"] = result.get("backtest_id")
                    else:
                        st.error("Failed to create backtest request")

    # Status cards
    st.subheader("Current Status")

    status_col1, status_col2, status_col3 = st.columns(3)

    with status_col1:
        st.metric(
            "Wave Analysis",
            (
                "Complete"
                if st.session_state.get("analysis_results")
                else (
                    "In Progress"
                    if st.session_state.get("analysis_id")
                    else "Not Started"
                )
            ),
        )

    with status_col2:
        st.metric(
            "Strategy",
            (
                "Complete"
                if st.session_state.get("strategy_results")
                else (
                    "In Progress"
                    if st.session_state.get("strategy_id")
                    else "Not Started"
                )
            ),
        )

    with status_col3:
        st.metric(
            "Backtest",
            (
                "Complete"
                if st.session_state.get("backtest_results")
                else (
                    "In Progress"
                    if st.session_state.get("backtest_id")
                    else "Not Started"
                )
            ),
        )

    # Recent tasks
    st.subheader("Recent Tasks")

    if st.session_state.get("task_id"):
        if st.button("Check Task Status", key="check_task"):
            with st.spinner("Checking task status..."):
                task_status = api_client.get_task_status(st.session_state["task_id"])
                if task_status:
                    st.json(task_status)
                else:
                    st.error("Failed to get task status")

with tab2:
    st.header("Wave Analysis")

    # Analysis form
    with st.form("wave_analysis_form"):
        st.subheader("Run Wave Analysis")

        col1, col2 = st.columns(2)

        with col1:
            include_subwaves = st.checkbox("Include Subwaves", value=True)

        with col2:
            wave_confidence = st.slider(
                "Confidence Threshold",
                min_value=0.1,
                max_value=0.9,
                value=0.7,
                step=0.1,
            )

        submit_button = st.form_submit_button("Run Analysis")

        if submit_button:
            if not (api_client.api_key or st.session_state.get("authenticated")):
                st.warning("Please authenticate first")
            else:
                wave_options = {
                    "include_subwaves": include_subwaves,
                    "min_wave_points": min_wave_points,
                    "confidence_threshold": wave_confidence,
                }

                with st.spinner("Running wave analysis..."):
                    result = api_client.create_wave_analysis(
                        symbol=symbol,
                        timeframe=timeframe,
                        start_date=start_date.strftime("%Y-%m-%d"),
                        end_date=end_date.strftime("%Y-%m-%d"),
                        wave_options=wave_options,
                    )

                    if result:
                        st.session_state["wave_analysis_task"] = result
                        st.success(
                            f"Analysis requested. Task ID: {result.get('task_id')}"
                        )
                        st.session_state["task_id"] = result.get("task_id")
                        st.session_state["analysis_id"] = result.get("analysis_id")
                    else:
                        st.error("Failed to create wave analysis request")

    # Analysis results
    st.subheader("Analysis Results")

    if st.session_state.get("analysis_id") and st.button("Get Analysis Results"):
        with st.spinner("Fetching analysis results..."):
            analysis = api_client.get_wave_analysis(st.session_state["analysis_id"])

            if analysis:
                st.session_state["analysis_results"] = analysis

                # Create a candlestick chart with Plotly
                if "waves" in analysis and len(analysis["waves"]) > 0:
                    # For demonstration purposes, we'll create a sample chart
                    # In a real implementation, this would use the actual data
                    dates = pd.date_range(
                        start=analysis.get("start_date"),
                        end=analysis.get("end_date"),
                        freq="D",
                    )

                    # Create some dummy price data
                    np.random.seed(42)
                    price = 1.2
                    closes = [price]
                    for _ in range(1, len(dates)):
                        change = np.random.normal(0, 0.005)
                        price *= 1 + change
                        closes.append(price)

                    chart_data = pd.DataFrame(
                        {
                            "date": dates,
                            "close": closes,
                        }
                    )

                    chart_data["open"] = (
                        chart_data["close"].shift(1).fillna(chart_data["close"][0])
                    )
                    chart_data["high"] = chart_data["close"] * (
                        1 + np.random.uniform(0, 0.005, len(chart_data))
                    )
                    chart_data["low"] = chart_data["close"] * (
                        1 - np.random.uniform(0, 0.005, len(chart_data))
                    )

                    # Create interactive chart
                    fig = go.Figure()

                    # Add candlestick trace
                    fig.add_trace(
                        go.Candlestick(
                            x=chart_data["date"],
                            open=chart_data["open"],
                            high=chart_data["high"],
                            low=chart_data["low"],
                            close=chart_data["close"],
                            name="Price",
                        )
                    )

                    # Add wave annotations
                    for wave in analysis["waves"]:
                        # In a real implementation, this would use actual wave data
                        # Here we're just illustrating the concept
                        if wave.get("wave_type") == "impulse":
                            # Add wave labels
                            for subwave in wave.get("subwaves", []):
                                wave_num = subwave.get("wave_num")
                                end_idx = min(
                                    subwave.get("end_idx", 0), len(chart_data) - 1
                                )
                                if end_idx >= 0 and end_idx < len(chart_data):
                                    fig.add_annotation(
                                        x=chart_data["date"][end_idx],
                                        y=chart_data["high"][end_idx],
                                        text=str(wave_num),
                                        showarrow=True,
                                        arrowhead=2,
                                    )

                            # Add Fibonacci levels
                            start_idx = wave.get("start_idx", 0)
                            end_idx = min(
                                wave.get("end_idx", len(chart_data) - 1),
                                len(chart_data) - 1,
                            )
                            if start_idx >= 0 and end_idx < len(chart_data):
                                start_price = chart_data["close"][start_idx]
                                end_price = chart_data["close"][end_idx]
                                price_range = end_price - start_price

                                # Add Fibonacci retracement levels
                                for level, color in [
                                    (0.236, "red"),
                                    (0.382, "orange"),
                                    (0.5, "green"),
                                    (0.618, "blue"),
                                    (0.786, "purple"),
                                ]:
                                    retracement_price = end_price - price_range * level
                                    fig.add_shape(
                                        type="line",
                                        x0=chart_data["date"][start_idx],
                                        y0=retracement_price,
                                        x1=chart_data["date"][end_idx],
                                        y1=retracement_price,
                                        line=dict(color=color, width=1, dash="dash"),
                                    )

                    # Update layout
                    fig.update_layout(
                        title=f"{symbol} - {timeframe} with Elliott Waves",
                        xaxis_title="Date",
                        yaxis_title="Price",
                        height=600,
                    )

                    st.plotly_chart(fig, use_container_width=True)

                # Display wave details
                st.json(analysis)
            else:
                st.error(
                    "Failed to fetch analysis results or analysis not yet complete"
                )

    elif not st.session_state.get("analysis_id"):
        st.info("Run a wave analysis first")

with tab3:
    st.header("Strategy")

    # Strategy form
    with st.form("strategy_form"):
        st.subheader("Create Trading Strategy")

        # Strategy type
        strategy_type = st.selectbox(
            "Strategy Type",
            ["impulse_wave", "corrective_wave", "multi_wave", "fibonacci"],
            index=0,
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            risk_per_trade = st.slider(
                "Risk Per Trade (%)",
                min_value=0.5,
                max_value=5.0,
                value=2.0,
                step=0.5,
            )

        with col2:
            max_drawdown = st.slider(
                "Max Drawdown (%)",
                min_value=5.0,
                max_value=30.0,
                value=10.0,
                step=1.0,
            )

        with col3:
            profit_target = st.slider(
                "Profit Target Multiplier",
                min_value=1.0,
                max_value=5.0,
                value=1.5,
                step=0.5,
            )

        submit_button = st.form_submit_button("Create Strategy")

        if submit_button:
            if not (api_client.api_key or st.session_state.get("authenticated")):
                st.warning("Please authenticate first")
            elif not st.session_state.get("analysis_id"):
                st.warning("Please run a wave analysis first")
            else:
                risk_parameters = {
                    "risk_per_trade": risk_per_trade / 100,  # Convert to decimal
                    "max_drawdown": max_drawdown / 100,  # Convert to decimal
                    "profit_target_multiplier": profit_target,
                }

                with st.spinner("Creating trading strategy..."):
                    result = api_client.create_strategy(
                        wave_analysis_id=st.session_state["analysis_id"],
                        strategy_type=strategy_type,
                        risk_parameters=risk_parameters,
                    )

                    if result:
                        st.session_state["strategy_task"] = result
                        st.success(
                            f"Strategy created. Task ID: {result.get('task_id')}"
                        )
                        st.session_state["strategy_id"] = result.get("strategy_id")
                    else:
                        st.error("Failed to create strategy")

    # Strategy results
    st.subheader("Strategy Results")

    if st.session_state.get("strategy_id") and st.button("Get Strategy Results"):
        with st.spinner("Fetching strategy results..."):
            strategy = api_client.get_strategy(st.session_state["strategy_id"])

            if strategy:
                st.session_state["strategy_results"] = strategy

                # Display strategy summary
                st.subheader("Strategy Summary")
                col1, col2 = st.columns(2)

                with col1:
                    st.metric("Strategy Type", strategy.get("strategy_type", ""))
                    st.metric(
                        "Risk Per Trade",
                        f"{strategy.get('risk_parameters', {}).get('risk_per_trade', 0) * 100:.1f}%",
                    )

                with col2:
                    st.metric(
                        "Max Drawdown",
                        f"{strategy.get('risk_parameters', {}).get('max_drawdown', 0) * 100:.1f}%",
                    )
                    st.metric(
                        "Profit Target",
                        f"{strategy.get('risk_parameters', {}).get('profit_target_multiplier', 0):.1f}x",
                    )

                # Display entry signals
                st.subheader("Entry Signals")

                entry_signals = strategy.get("entry_signals", [])
                if entry_signals:
                    entries_df = pd.DataFrame(entry_signals)
                    st.dataframe(entries_df)
                else:
                    st.info("No entry signals available")

                # Display exit signals
                st.subheader("Exit Signals")

                exit_signals = strategy.get("exit_signals", [])
                if exit_signals:
                    exits_df = pd.DataFrame(exit_signals)
                    st.dataframe(exits_df)
                else:
                    st.info("No exit signals available")

                # Display raw strategy data
                with st.expander("Raw Strategy Data"):
                    st.json(strategy)
            else:
                st.error(
                    "Failed to fetch strategy results or strategy not yet complete"
                )

    elif not st.session_state.get("strategy_id"):
        st.info("Create a strategy first")

with tab4:
    st.header("Backtesting")

    # Backtest form
    with st.form("backtest_form"):
        st.subheader("Run Backtest")

        col1, col2, col3 = st.columns(3)

        with col1:
            slippage_model = st.selectbox(
                "Slippage Model",
                ["none", "fixed", "normal", "pareto"],
                index=2,
            )

        with col2:
            spread_model = st.selectbox(
                "Spread Model",
                ["fixed", "variable", "volatile"],
                index=1,
            )

        with col3:
            commission_model = st.selectbox(
                "Commission Model",
                ["none", "fixed", "percentage"],
                index=1,
            )

        validation_selections = st.multiselect(
            "Validation Methods",
            ["monte_carlo", "walk_forward", "cross_market"],
            default=["monte_carlo"],
        )

        submit_button = st.form_submit_button("Run Backtest")

        if submit_button:
            if not (api_client.api_key or st.session_state.get("authenticated")):
                st.warning("Please authenticate first")
            elif not st.session_state.get("strategy_id"):
                st.warning("Please create a strategy first")
            else:
                with st.spinner("Running backtest..."):
                    result = api_client.create_backtest(
                        strategy_id=st.session_state["strategy_id"],
                        start_date=start_date.strftime("%Y-%m-%d"),
                        end_date=end_date.strftime("%Y-%m-%d"),
                        initial_capital=initial_capital,
                        validation_methods=validation_selections,
                        slippage_model=slippage_model,
                        spread_model=spread_model,
                        commission_model=commission_model,
                    )

                    if result:
                        st.session_state["backtest_task"] = result
                        st.success(
                            f"Backtest requested. Task ID: {result.get('task_id')}"
                        )
                        st.session_state["backtest_id"] = result.get("backtest_id")
                    else:
                        st.error("Failed to create backtest request")

    # Backtest results
    st.subheader("Backtest Results")

    if st.session_state.get("backtest_id") and st.button("Get Backtest Results"):
        with st.spinner("Fetching backtest results..."):
            backtest = api_client.get_backtest(st.session_state["backtest_id"])

            if backtest:
                st.session_state["backtest_results"] = backtest

                # Display backtest summary metrics
                if backtest.get("results") and backtest.get("results").get("summary"):
                    summary = backtest["results"]["summary"]

                    st.subheader("Performance Summary")
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric(
                            "Total Return",
                            f"{summary.get('total_return', 0) * 100:.2f}%",
                        )
                        st.metric(
                            "Win Rate", f"{summary.get('win_rate', 0) * 100:.2f}%"
                        )

                    with col2:
                        st.metric(
                            "Profit Factor", f"{summary.get('profit_factor', 0):.2f}"
                        )
                        st.metric(
                            "Sharpe Ratio", f"{summary.get('sharpe_ratio', 0):.2f}"
                        )

                    with col3:
                        st.metric(
                            "Max Drawdown",
                            f"{summary.get('max_drawdown', 0) * 100:.2f}%",
                        )
                        st.metric(
                            "Final Capital", f"${summary.get('final_capital', 0):,.2f}"
                        )

                    with col4:
                        st.metric(
                            "Annualized Return",
                            f"{summary.get('annualized_return', 0) * 100:.2f}%",
                        )

                    # Equity curve
                    st.subheader("Equity Curve")

                    # Create a simple equity curve chart (in a real app, this would use actual data)
                    dates = pd.date_range(
                        start=backtest.get("start_date"),
                        end=backtest.get("end_date"),
                        freq="D",
                    )

                    # Simulate equity curve based on total return and drawdown
                    total_return = summary.get("total_return", 0)
                    max_drawdown = summary.get("max_drawdown", 0)
                    initial_capital = backtest.get("initial_capital", 10000)

                    # Create a more realistic equity curve simulation
                    np.random.seed(42)

                    # Generate a curved equity growth with a drawdown in the middle
                    equity = [initial_capital]
                    current = initial_capital
                    daily_return = (1 + total_return) ** (1 / len(dates)) - 1

                    for i in range(1, len(dates)):
                        # Simulate a drawdown in the middle
                        if i > len(dates) * 0.3 and i < len(dates) * 0.5:
                            # Drawdown phase
                            current *= 1 - max_drawdown / (len(dates) * 0.2)
                        else:
                            # Growth phase with some volatility
                            current *= (
                                1 + daily_return + np.random.normal(0, daily_return / 2)
                            )

                        equity.append(current)

                    equity_df = pd.DataFrame({"date": dates, "equity": equity})

                    # Plot equity curve
                    fig = px.line(
                        equity_df,
                        x="date",
                        y="equity",
                        title="Equity Curve",
                        labels={"date": "Date", "equity": "Account Equity"},
                    )

                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)

                    # Monte Carlo results
                    if "monte_carlo" in backtest.get("results", {}):
                        st.subheader("Monte Carlo Simulation")

                        monte_carlo = backtest["results"]["monte_carlo"]

                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.metric(
                                "5% Confidence",
                                f"${monte_carlo.get('confidence_5pct', 0):,.2f}",
                            )

                        with col2:
                            st.metric(
                                "50% Confidence",
                                f"${monte_carlo.get('confidence_50pct', 0):,.2f}",
                            )

                        with col3:
                            st.metric(
                                "95% Confidence",
                                f"${monte_carlo.get('confidence_95pct', 0):,.2f}",
                            )

                    # Trade list
                    if "trades" in backtest.get("results", {}):
                        st.subheader("Trade List")

                        trades_df = pd.DataFrame(backtest["results"]["trades"])
                        st.dataframe(trades_df)

                # Display raw backtest data
                with st.expander("Raw Backtest Data"):
                    st.json(backtest)
            else:
                st.error(
                    "Failed to fetch backtest results or backtest not yet complete"
                )

    elif not st.session_state.get("backtest_id"):
        st.info("Run a backtest first")

with tab5:
    st.header("Settings")

    st.subheader("API Settings")

    api_url = st.text_input("API URL", value=api_client.api_url)
    if st.button("Update API URL"):
        api_client.api_url = api_url
        st.success("API URL updated")

    st.subheader("Task Management")

    task_id = st.text_input("Task ID", value=st.session_state.get("task_id", ""))
    if st.button("Check Task Status", key="settings_check_task"):
        if task_id:
            with st.spinner("Checking task status..."):
                task_status = api_client.get_task_status(task_id)
                if task_status:
                    st.json(task_status)
                else:
                    st.error("Failed to get task status")
        else:
            st.warning("Please enter a Task ID")

    st.subheader("Clear Session State")

    if st.button("Clear All Session Data"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("Session state cleared")
        st.experimental_rerun()

# Footer
st.markdown("---")
st.markdown("FXML3 | AI-Enhanced Elliott Wave Analysis")
