"""Interactive performance dashboard for FXML4.

This module provides a Streamlit-based interactive dashboard for analyzing trading performance.
It consumes the FXML4 API to display performance metrics, charts, and reports.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd
import requests
import streamlit as st
from pandas import DataFrame, Series
from plotly import express as px
from plotly import figure_factory as ff
from plotly import graph_objects as go

from fxml4.config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ApiClient:
    """API client for FXML4 API."""
    
    def __init__(self, base_url: Optional[str] = None):
        """Initialize the API client.
        
        Args:
            base_url: Base URL for the API. If not provided, it will be read from the config.
        """
        # Get API base URL from config if not provided
        if base_url is None:
            host = get_config("api.host", "localhost")
            port = int(get_config("api.port", 8000))
            base_url = f"http://{host}:{port}"
        
        self.base_url = base_url
        logger.info("Initialized API client with base URL: %s", self.base_url)
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict] = None, 
        data: Optional[Dict] = None
    ) -> Dict:
        """Make a request to the API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            params: Query parameters
            data: Request body
            
        Returns:
            Response data
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, params=params)
            elif method.upper() == "POST":
                response = requests.post(url, params=params, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error("API request error: %s", str(e))
            raise
    
    def get_health(self) -> Dict:
        """Check API health.
        
        Returns:
            Health status
        """
        return self._make_request("GET", "/health")
    
    def get_market_data(
        self, 
        symbol: str, 
        timeframe: str, 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None, 
        limit: Optional[int] = None
    ) -> Dict:
        """Get market data.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            start_date: Start date
            end_date: End date
            limit: Number of data points to return
            
        Returns:
            Market data
        """
        data = {
            "symbol": symbol,
            "timeframe": timeframe,
            "start_date": start_date,
            "end_date": end_date,
            "limit": limit,
        }
        return self._make_request("POST", "/data", data=data)
    
    def run_backtest(
        self,
        symbol: str,
        timeframe: str,
        strategy: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 10000.0,
        parameters: Optional[Dict] = None,
        auto_report: bool = True,
    ) -> Dict:
        """Run a backtest.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            strategy: Strategy name
            start_date: Start date
            end_date: End date
            initial_capital: Initial capital
            parameters: Strategy parameters
            auto_report: Whether to auto-generate a report
            
        Returns:
            Backtest results
        """
        data = {
            "symbol": symbol,
            "timeframe": timeframe,
            "strategy": strategy,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": initial_capital,
            "parameters": parameters or {},
            "auto_report": auto_report,
        }
        return self._make_request("POST", "/backtest", data=data)
    
    def get_performance_metrics(
        self,
        backtest_id: str,
        include_trades: bool = False,
        include_equity_curve: bool = False,
    ) -> Dict:
        """Get performance metrics for a backtest.
        
        Args:
            backtest_id: Backtest ID
            include_trades: Whether to include trade details
            include_equity_curve: Whether to include equity curve data
            
        Returns:
            Performance metrics
        """
        params = {
            "include_trades": include_trades,
            "include_equity_curve": include_equity_curve,
        }
        return self._make_request(
            "GET", 
            f"/performance/metrics/{backtest_id}", 
            params=params
        )
    
    def get_performance_report_url(self, backtest_id: str, format: str = "html") -> str:
        """Get the URL for a performance report.
        
        Args:
            backtest_id: Backtest ID
            format: Report format (html or pdf)
            
        Returns:
            Report URL
        """
        return f"{self.base_url}/performance/report/{backtest_id}?format={format}"
    
    def compare_backtests(
        self,
        backtest_ids: List[str],
        metrics: Optional[List[str]] = None,
    ) -> Dict:
        """Compare multiple backtests.
        
        Args:
            backtest_ids: List of backtest IDs to compare
            metrics: Metrics to compare
            
        Returns:
            Comparison results
        """
        data = {
            "backtest_ids": backtest_ids,
            "metrics": metrics or ["total_return_pct", "max_drawdown_pct", "sharpe_ratio"],
        }
        return self._make_request("POST", "/performance/compare", data=data)


class Dashboard:
    """Interactive performance dashboard for FXML4."""
    
    def __init__(self):
        """Initialize the dashboard."""
        self.api_client = ApiClient()
        
        # Initialize session state for storing data
        if "backtest_history" not in st.session_state:
            st.session_state.backtest_history = []
        
        if "performance_metrics" not in st.session_state:
            st.session_state.performance_metrics = {}
        
        if "comparison_results" not in st.session_state:
            st.session_state.comparison_results = None
    
    def run(self):
        """Run the dashboard application."""
        st.set_page_config(
            page_title="FXML4 Performance Dashboard",
            page_icon="📊",
            layout="wide",
            initial_sidebar_state="expanded",
        )
        
        # Add title and description
        st.title("FXML4 Performance Dashboard")
        st.markdown(
            """
            This dashboard provides interactive visualization and analysis of trading performance.
            Use the sidebar to navigate between different views.
            """
        )
        
        # Check API connection
        api_connected = False
        try:
            health = self.api_client.get_health()
            st.sidebar.success("Connected to FXML4 API")
            api_connected = True
        except Exception as e:
            st.sidebar.error(f"Error connecting to API: {str(e)}")
            st.error(
                "Unable to connect to the FXML4 API. Please check if the API server is running.\n\n"
                "You can start the API server with: `python -m fxml4.api.main`"
            )
            
            # Add a retry button
            if st.button("Retry Connection"):
                st.experimental_rerun()
                
            # Continue anyway for demonstration purposes
            st.warning(
                "Continuing with limited functionality for demonstration purposes. "
                "Some features will not work without API connection."
            )
        
        # Sidebar navigation
        st.sidebar.title("Navigation")
        page = st.sidebar.radio(
            "Select a page",
            ["Backtest Runner", "Performance Analysis", "Strategy Comparison", "Reports"]
        )
        
        # Display the selected page
        if page == "Backtest Runner":
            if not api_connected:
                st.info("This page requires API connection for full functionality. Some features will be disabled.")
            self.show_backtest_runner(api_connected)
        elif page == "Performance Analysis":
            if not api_connected:
                st.info("This page requires API connection for full functionality. Some features will be disabled.")
            self.show_performance_analysis(api_connected)
        elif page == "Strategy Comparison":
            if not api_connected:
                st.info("This page requires API connection for full functionality. Some features will be disabled.")
            self.show_strategy_comparison(api_connected)
        elif page == "Reports":
            if not api_connected:
                st.info("This page requires API connection for full functionality. Some features will be disabled.")
            self.show_reports(api_connected)
    
    def show_backtest_runner(self, api_connected=True):
        """Show the backtest runner page.
        
        Args:
            api_connected: Whether the API is connected and available.
        """
        st.header("Backtest Runner")
        st.markdown(
            """
            Run backtests for different strategies and analyze their performance.
            """
        )
        
        # Create form for backtest parameters
        with st.form("backtest_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                symbol = st.selectbox(
                    "Symbol",
                    options=get_config("data.symbols", ["EURUSD", "GBPUSD"]),
                    help="Trading symbol to backtest",
                )
                
                timeframe = st.selectbox(
                    "Timeframe",
                    options=get_config("data.timeframes", ["1m", "5m", "15m", "1h", "4h", "1d"]),
                    help="Timeframe for backtesting",
                )
                
                strategy = st.selectbox(
                    "Strategy",
                    options=["ml_strategy", "wave_strategy", "integrated_strategy"],
                    help="Trading strategy to backtest",
                )
            
            with col2:
                start_date = st.date_input(
                    "Start Date",
                    value=pd.to_datetime(get_config("backtesting.start_date", "2023-01-01")),
                    help="Start date for backtesting",
                )
                
                end_date = st.date_input(
                    "End Date",
                    value=pd.to_datetime(get_config("backtesting.end_date", "2023-12-31")),
                    help="End date for backtesting",
                )
                
                initial_capital = st.number_input(
                    "Initial Capital",
                    value=float(get_config("backtesting.initial_capital", 10000)),
                    min_value=1000.0,
                    help="Initial capital for backtesting",
                )
            
            # Advanced parameters (collapsible)
            with st.expander("Advanced Parameters"):
                st.markdown("These parameters will be passed to the strategy.")
                
                if strategy == "ml_strategy":
                    param_model = st.selectbox(
                        "Model",
                        options=["random_forest", "xgboost", "ensemble"],
                        help="ML model to use",
                    )
                    
                    param_features = st.multiselect(
                        "Features",
                        options=["technical", "price_patterns", "volatility", "sentiment", "economic"],
                        default=["technical", "volatility"],
                        help="Features to use in the model",
                    )
                elif strategy == "wave_strategy":
                    param_strictness = st.slider(
                        "Rule Strictness",
                        min_value=0.0,
                        max_value=1.0,
                        value=0.5,
                        step=0.1,
                        help="Strictness of Elliott Wave rules",
                    )
                    
                    param_wave_validation = st.checkbox(
                        "LLM Wave Validation",
                        value=True,
                        help="Use LLM for wave validation",
                    )
                elif strategy == "integrated_strategy":
                    param_ml_weight = st.slider(
                        "ML Signal Weight",
                        min_value=0.0,
                        max_value=1.0,
                        value=0.5,
                        step=0.1,
                        help="Weight of ML signals",
                    )
                    
                    param_wave_weight = st.slider(
                        "Wave Signal Weight",
                        min_value=0.0,
                        max_value=1.0,
                        value=0.3,
                        step=0.1,
                        help="Weight of wave signals",
                    )
                    
                    param_sentiment_weight = st.slider(
                        "Sentiment Weight",
                        min_value=0.0,
                        max_value=1.0,
                        value=0.2,
                        step=0.1,
                        help="Weight of sentiment signals",
                    )
            
            # Collect parameters based on strategy
            parameters = {}
            if strategy == "ml_strategy":
                parameters = {
                    "model": param_model,
                    "features": param_features,
                }
            elif strategy == "wave_strategy":
                parameters = {
                    "strictness": param_strictness,
                    "wave_validation": param_wave_validation,
                }
            elif strategy == "integrated_strategy":
                parameters = {
                    "ml_weight": param_ml_weight,
                    "wave_weight": param_wave_weight,
                    "sentiment_weight": param_sentiment_weight,
                }
            
            auto_report = st.checkbox(
                "Auto Generate Report",
                value=True,
                help="Automatically generate a performance report",
            )
            
            # Submit button
            submit_button = st.form_submit_button("Run Backtest")
            
            if submit_button:
                if not api_connected:
                    st.error("Cannot run backtest: API is not connected. Please start the API server and try again.")
                    return
                    
                with st.spinner("Running backtest..."):
                    try:
                        # Format dates for API request
                        start_date_str = start_date.strftime("%Y-%m-%d")
                        end_date_str = end_date.strftime("%Y-%m-%d")
                        
                        # Run backtest
                        result = self.api_client.run_backtest(
                            symbol=symbol,
                            timeframe=timeframe,
                            strategy=strategy,
                            start_date=start_date_str,
                            end_date=end_date_str,
                            initial_capital=initial_capital,
                            parameters=parameters,
                            auto_report=auto_report,
                        )
                        
                        # Add to backtest history
                        result["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        st.session_state.backtest_history.append(result)
                        
                        # Show success message
                        st.success(f"Backtest completed successfully! Backtest ID: {result['backtest_id']}")
                        
                        # Show summary
                        st.subheader("Backtest Summary")
                        col1, col2, col3, col4 = st.columns(4)
                        
                        col1.metric(
                            "Total Return",
                            f"{result['total_return_pct']:.2f}%",
                            delta=f"{result['total_return_pct']:.2f}%",
                        )
                        
                        col2.metric(
                            "Final Capital",
                            f"${result['final_capital']:,.2f}",
                            delta=f"${result['total_return']:,.2f}",
                        )
                        
                        col3.metric(
                            "Max Drawdown",
                            f"{result['max_drawdown_pct']:.2f}%",
                            delta=f"-{result['max_drawdown_pct']:.2f}%",
                            delta_color="inverse",
                        )
                        
                        col4.metric(
                            "Total Trades",
                            f"{result['trade_count']}",
                        )
                        
                        # Show report link if available
                        if result.get("report_url"):
                            st.markdown(f"[View Full Report]({result['report_url']})")
                        
                        # Fetch detailed metrics
                        with st.spinner("Loading detailed metrics..."):
                            metrics = self.api_client.get_performance_metrics(
                                backtest_id=result["backtest_id"],
                                include_equity_curve=True,
                            )
                            
                            # Store in session state
                            st.session_state.performance_metrics[result["backtest_id"]] = metrics
                            
                            # Show key charts
                            if "equity_curve" in metrics:
                                equity_data = pd.DataFrame(metrics["equity_curve"])
                                equity_data["timestamp"] = pd.to_datetime(equity_data["timestamp"])
                                
                                fig = go.Figure()
                                fig.add_trace(
                                    go.Scatter(
                                        x=equity_data["timestamp"],
                                        y=equity_data["equity"],
                                        mode="lines",
                                        name="Equity Curve",
                                        line=dict(color="#1f77b4", width=2),
                                    )
                                )
                                
                                fig.update_layout(
                                    title="Equity Curve",
                                    xaxis_title="Date",
                                    yaxis_title="Equity ($)",
                                    hovermode="x unified",
                                )
                                
                                st.plotly_chart(fig, use_container_width=True)
                            
                            # Show monthly returns
                            if "monthly_returns" in metrics:
                                monthly_data = pd.Series(metrics["monthly_returns"])
                                monthly_data.index = pd.to_datetime(monthly_data.index + "-01")
                                
                                fig = go.Figure()
                                colors = ["#1f77b4" if x >= 0 else "#d62728" for x in monthly_data.values]
                                
                                fig.add_trace(
                                    go.Bar(
                                        x=monthly_data.index,
                                        y=monthly_data.values,
                                        marker_color=colors,
                                    )
                                )
                                
                                fig.update_layout(
                                    title="Monthly Returns (%)",
                                    xaxis_title="Month",
                                    yaxis_title="Return (%)",
                                    hovermode="x unified",
                                )
                                
                                st.plotly_chart(fig, use_container_width=True)
                    
                    except Exception as e:
                        st.error(f"Error running backtest: {str(e)}")
        
        # Show backtest history
        if st.session_state.backtest_history:
            st.header("Backtest History")
            
            # Convert to DataFrame for easier display
            history_df = pd.DataFrame(st.session_state.backtest_history)
            
            # Sort by timestamp (most recent first)
            history_df = history_df.sort_values("timestamp", ascending=False)
            
            # Display as a table
            st.dataframe(
                history_df[["timestamp", "backtest_id", "symbol", "timeframe", "strategy", 
                           "total_return_pct", "max_drawdown_pct", "trade_count"]],
                use_container_width=True,
            )
    
    def show_performance_analysis(self, api_connected=True):
        """Show the performance analysis page.
        
        Args:
            api_connected: Whether the API is connected and available.
        """
        st.header("Performance Analysis")
        st.markdown(
            """
            Detailed analysis of backtest results. Select a backtest to view its performance metrics.
            """
        )
        
        # Check if there are any backtests
        if not st.session_state.backtest_history:
            st.info("No backtests have been run yet. Go to the Backtest Runner page to run one.")
            return
        
        # Select backtest to analyze
        backtest_options = {
            f"{b['timestamp']} - {b['strategy']} ({b['symbol']} {b['timeframe']})": b["backtest_id"]
            for b in st.session_state.backtest_history
        }
        
        selected_backtest_name = st.selectbox(
            "Select Backtest",
            options=list(backtest_options.keys()),
        )
        
        selected_backtest_id = backtest_options[selected_backtest_name]
        
        # Load metrics if not already in session state
        if selected_backtest_id not in st.session_state.performance_metrics:
            with st.spinner("Loading performance metrics..."):
                try:
                    metrics = self.api_client.get_performance_metrics(
                        backtest_id=selected_backtest_id,
                        include_trades=True,
                        include_equity_curve=True,
                    )
                    st.session_state.performance_metrics[selected_backtest_id] = metrics
                except Exception as e:
                    st.error(f"Error loading metrics: {str(e)}")
                    return
        
        metrics = st.session_state.performance_metrics[selected_backtest_id]
        
        # Display metrics in tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Overview", "Returns", "Drawdowns", "Trade Analysis", "Monte Carlo"
        ])
        
        with tab1:
            st.subheader("Performance Overview")
            
            # Metrics in cards
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Return", f"{metrics['metrics']['total_return_pct']:.2f}%")
                st.metric("Annualized Return", f"{metrics['metrics']['annualized_return']:.2f}%")
                st.metric("Win Rate", f"{metrics['metrics']['win_rate'] * 100:.2f}%")
                st.metric("Profit Factor", f"{metrics['metrics']['profit_factor']:.2f}")
            
            with col2:
                st.metric("Sharpe Ratio", f"{metrics['metrics']['sharpe_ratio']:.2f}")
                st.metric("Sortino Ratio", f"{metrics['metrics']['sortino_ratio']:.2f}")
                st.metric("Recovery Factor", f"{metrics['metrics']['recovery_factor']:.2f}")
                st.metric("Expectancy", f"{metrics['metrics']['expectancy']:.2f}")
            
            with col3:
                st.metric("Max Drawdown", f"{metrics['metrics']['max_drawdown_pct']:.2f}%")
                st.metric("Avg Win", f"${metrics['metrics']['avg_win']:.2f}")
                st.metric("Avg Loss", f"${metrics['metrics']['avg_loss']:.2f}")
                st.metric("Risk of Ruin", f"{metrics['metrics']['risk_of_ruin']:.2%}")
            
            # Equity curve
            if "equity_curve" in metrics:
                equity_data = pd.DataFrame(metrics["equity_curve"])
                equity_data["timestamp"] = pd.to_datetime(equity_data["timestamp"])
                
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=equity_data["timestamp"],
                        y=equity_data["equity"],
                        mode="lines",
                        name="Equity Curve",
                        line=dict(color="#1f77b4", width=2),
                    )
                )
                
                fig.update_layout(
                    title="Equity Curve",
                    xaxis_title="Date",
                    yaxis_title="Equity ($)",
                    hovermode="x unified",
                )
                
                st.plotly_chart(fig, use_container_width=True)
        
        with tab2:
            st.subheader("Returns Analysis")
            
            # Monthly returns heatmap
            if "monthly_returns" in metrics:
                # Convert to DataFrame
                monthly_returns = pd.Series(metrics["monthly_returns"])
                monthly_returns.index = pd.to_datetime(monthly_returns.index + "-01")
                
                # Extract year and month
                monthly_df = pd.DataFrame({
                    "Year": monthly_returns.index.year,
                    "Month": monthly_returns.index.month,
                    "Return": monthly_returns.values
                })
                
                # Pivot for heatmap
                pivot_df = monthly_df.pivot(index="Year", columns="Month", values="Return")
                
                # Create heatmap
                fig = go.Figure(data=go.Heatmap(
                    z=pivot_df.values,
                    x=pivot_df.columns,
                    y=pivot_df.index,
                    colorscale="RdBu",
                    zmid=0,
                    text=[[f"{val:.2f}%" for val in row] for row in pivot_df.values],
                    texttemplate="%{text}",
                    textfont={"size": 12},
                ))
                
                fig.update_layout(
                    title="Monthly Returns Heatmap (%)",
                    xaxis_title="Month",
                    yaxis_title="Year",
                    xaxis=dict(
                        tickmode="array",
                        tickvals=list(range(1, 13)),
                        ticktext=["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                    ),
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Monthly returns bar chart
                fig = go.Figure()
                colors = ["#1f77b4" if x >= 0 else "#d62728" for x in monthly_returns.values]
                
                fig.add_trace(
                    go.Bar(
                        x=monthly_returns.index,
                        y=monthly_returns.values,
                        marker_color=colors,
                    )
                )
                
                fig.update_layout(
                    title="Monthly Returns (%)",
                    xaxis_title="Month",
                    yaxis_title="Return (%)",
                    hovermode="x unified",
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Monthly statistics
                monthly_stats = pd.DataFrame({
                    "Average": monthly_df.groupby("Month")["Return"].mean(),
                    "Median": monthly_df.groupby("Month")["Return"].median(),
                    "Best": monthly_df.groupby("Month")["Return"].max(),
                    "Worst": monthly_df.groupby("Month")["Return"].min(),
                    "% Positive": monthly_df.groupby("Month")["Return"].apply(
                        lambda x: (x > 0).mean() * 100
                    ),
                })
                
                # Add month names
                month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                monthly_stats.index = [month_names[i-1] for i in monthly_stats.index]
                
                # Format percentages
                for col in monthly_stats.columns:
                    monthly_stats[col] = monthly_stats[col].apply(lambda x: f"{x:.2f}%")
                
                st.subheader("Monthly Statistics")
                st.dataframe(monthly_stats, use_container_width=True)
                
        with tab3:
            st.subheader("Drawdown Analysis")
            
            # Drawdown table
            if "drawdowns" in metrics:
                drawdowns = pd.DataFrame(metrics["drawdowns"])
                
                # Format dates
                date_columns = ["start_date", "end_date", "recovery_date"]
                for col in date_columns:
                    if col in drawdowns.columns:
                        drawdowns[col] = pd.to_datetime(drawdowns[col])
                
                # Format percentages
                if "depth_pct" in drawdowns.columns:
                    drawdowns["depth_pct"] = drawdowns["depth_pct"].apply(lambda x: f"{x:.2f}%")
                
                st.subheader("Top Drawdowns")
                st.dataframe(drawdowns, use_container_width=True)
                
                # Plot drawdowns
                if "equity_curve" in metrics:
                    equity_data = pd.DataFrame(metrics["equity_curve"])
                    equity_data["timestamp"] = pd.to_datetime(equity_data["timestamp"])
                    
                    # Calculate underwater curve
                    equity_data["peak"] = equity_data["equity"].cummax()
                    equity_data["drawdown_pct"] = (equity_data["equity"] - equity_data["peak"]) / equity_data["peak"] * 100
                    
                    fig = go.Figure()
                    fig.add_trace(
                        go.Scatter(
                            x=equity_data["timestamp"],
                            y=equity_data["drawdown_pct"],
                            mode="lines",
                            name="Drawdown",
                            line=dict(color="#d62728", width=2),
                            fill="tozeroy",
                        )
                    )
                    
                    fig.update_layout(
                        title="Underwater Curve (%)",
                        xaxis_title="Date",
                        yaxis_title="Drawdown (%)",
                        yaxis=dict(autorange="reversed"),  # Invert y-axis
                        hovermode="x unified",
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
        
        with tab4:
            st.subheader("Trade Analysis")
            
            # Trade statistics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Trades", metrics["metrics"].get("trades_per_month", 0) * 12)
                st.metric("Win Rate", f"{metrics['metrics']['win_rate'] * 100:.2f}%")
                st.metric("Profit Factor", f"{metrics['metrics']['profit_factor']:.2f}")
            
            with col2:
                st.metric("Avg Win", f"${metrics['metrics']['avg_win']:.2f}")
                st.metric("Avg Loss", f"${metrics['metrics']['avg_loss']:.2f}")
                st.metric("Expectancy", f"${metrics['metrics']['expectancy']:.2f}")
            
            with col3:
                st.metric("Max Consecutive Wins", metrics["metrics"]["max_consecutive_wins"])
                st.metric("Max Consecutive Losses", metrics["metrics"]["max_consecutive_losses"])
                st.metric("Trades Per Month", f"{metrics['metrics']['trades_per_month']:.1f}")
            
            # Trade list
            if "trades" in metrics:
                trades = pd.DataFrame(metrics["trades"])
                
                # Format dates
                if "entry_time" in trades.columns:
                    trades["entry_time"] = pd.to_datetime(trades["entry_time"])
                
                if "exit_time" in trades.columns:
                    trades["exit_time"] = pd.to_datetime(trades["exit_time"])
                
                # Calculate trade duration
                if "entry_time" in trades.columns and "exit_time" in trades.columns:
                    trades["duration"] = (trades["exit_time"] - trades["entry_time"]).apply(
                        lambda x: f"{x.days}d {x.seconds // 3600}h"
                    )
                
                # Format money values
                for col in ["pnl", "entry_price", "exit_price"]:
                    if col in trades.columns:
                        trades[col] = trades[col].apply(lambda x: f"{x:.5f}")
                
                if "pnl_pct" in trades.columns:
                    trades["pnl_pct"] = trades["pnl_pct"].apply(lambda x: f"{x:.2f}%")
                
                st.subheader("Trade List")
                st.dataframe(trades, use_container_width=True)
                
                # Plot trade P&L distribution
                if "pnl" in trades.columns:
                    # Convert back to numeric for plotting
                    pnl_values = pd.to_numeric(trades["pnl"].str.replace('$', '').str.replace(',', ''))
                    
                    fig = go.Figure()
                    fig.add_trace(
                        go.Histogram(
                            x=pnl_values,
                            marker_color=["#1f77b4" if x >= 0 else "#d62728" for x in pnl_values],
                            nbinsx=20,
                        )
                    )
                    
                    fig.update_layout(
                        title="Trade P&L Distribution",
                        xaxis_title="P&L ($)",
                        yaxis_title="Count",
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
        
        with tab5:
            st.subheader("Monte Carlo Simulation")
            
            if "monte_carlo" in metrics:
                mc_data = metrics["monte_carlo"]
                
                # Key statistics
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Mean Return", f"{mc_data['mean_return']:.2f}%")
                    st.metric("Worst Case", f"{mc_data['worst_case']:.2f}%")
                
                with col2:
                    st.metric("Median Return", f"{mc_data['median_return']:.2f}%")
                    st.metric("Best Case", f"{mc_data['best_case']:.2f}%")
                
                with col3:
                    st.metric("Probability of Profit", f"{mc_data['probability_of_profit']:.2%}")
                    st.metric("Probability of >10% Drawdown", f"{mc_data['probability_of_10pct_drawdown']:.2%}")
                
                # Percentile table
                st.subheader("Return Percentiles")
                
                percentiles_df = pd.DataFrame({
                    "Percentile": list(mc_data["percentiles"].keys()),
                    "Return (%)": list(mc_data["percentiles"].values()),
                })
                
                st.dataframe(percentiles_df, use_container_width=True)
                
                # TODO: Add Monte Carlo simulation chart when available from API
                st.info("Monte Carlo simulation chart will be available in a future update.")
    
    def show_strategy_comparison(self, api_connected=True):
        """Show the strategy comparison page.
        
        Args:
            api_connected: Whether the API is connected and available.
        """
        st.header("Strategy Comparison")
        st.markdown(
            """
            Compare performance across multiple backtests to identify the best strategies.
            """
        )
        
        # Check if there are enough backtests to compare
        if len(st.session_state.backtest_history) < 2:
            st.info("At least two backtests are needed for comparison. Run more backtests in the Backtest Runner page.")
            return
        
        # Select backtests to compare
        backtest_options = {
            f"{b['timestamp']} - {b['strategy']} ({b['symbol']} {b['timeframe']})": b["backtest_id"]
            for b in st.session_state.backtest_history
        }
        
        selected_backtests = st.multiselect(
            "Select Backtests to Compare",
            options=list(backtest_options.keys()),
            default=list(backtest_options.keys())[:min(3, len(backtest_options))],
        )
        
        if not selected_backtests:
            st.warning("Please select at least two backtests to compare.")
            return
        
        selected_backtest_ids = [backtest_options[name] for name in selected_backtests]
        
        # Select metrics to compare
        metrics_options = [
            "total_return_pct", "annualized_return", "sharpe_ratio", "sortino_ratio",
            "max_drawdown_pct", "win_rate", "profit_factor", "expectancy",
        ]
        
        selected_metrics = st.multiselect(
            "Select Metrics to Compare",
            options=metrics_options,
            default=["total_return_pct", "max_drawdown_pct", "sharpe_ratio"],
        )
        
        if not selected_metrics:
            st.warning("Please select at least one metric to compare.")
            return
        
        # Compare button
        if st.button("Compare Strategies"):
            with st.spinner("Comparing strategies..."):
                try:
                    # Call API to compare backtests
                    comparison = self.api_client.compare_backtests(
                        backtest_ids=selected_backtest_ids,
                        metrics=selected_metrics,
                    )
                    
                    # Store in session state
                    st.session_state.comparison_results = comparison
                    
                    # Create a lookup for backtest display names
                    backtest_names = {}
                    for name, bid in backtest_options.items():
                        if bid in selected_backtest_ids:
                            # Shorten the display name for charts
                            strategy = name.split(" - ")[1].split(" (")[0]
                            symbol_tf = name.split("(")[1].replace(")", "")
                            backtest_names[bid] = f"{strategy} ({symbol_tf})"
                    
                    # Display comparison results
                    st.subheader("Performance Comparison")
                    
                    # Metrics table
                    metrics_df = pd.DataFrame()
                    
                    for metric in selected_metrics:
                        if metric in comparison["metrics"]:
                            # Get values for each backtest
                            metric_values = comparison["metrics"][metric]
                            
                            # Create a series for this metric
                            metric_series = pd.Series(
                                {backtest_names[bid]: val for bid, val in metric_values.items()},
                                name=metric,
                            )
                            
                            # Add to dataframe
                            metrics_df = pd.concat([metrics_df, metric_series.to_frame().T])
                    
                    # Format metrics
                    formatted_df = metrics_df.copy()
                    
                    # Format percentages
                    pct_metrics = ["total_return_pct", "annualized_return", "max_drawdown_pct", "win_rate"]
                    for metric in pct_metrics:
                        if metric in formatted_df.index:
                            formatted_df.loc[metric] = formatted_df.loc[metric].apply(lambda x: f"{x:.2f}%")
                    
                    # Format other metrics
                    for metric in formatted_df.index:
                        if metric not in pct_metrics:
                            formatted_df.loc[metric] = formatted_df.loc[metric].apply(lambda x: f"{x:.2f}")
                    
                    # Display the table
                    st.dataframe(formatted_df, use_container_width=True)
                    
                    # Create radar chart for comparison
                    categories = selected_metrics
                    
                    # Normalize metrics for radar chart (0-1 scale)
                    radar_df = metrics_df.copy()
                    
                    # Invert metrics where lower is better
                    invert_metrics = ["max_drawdown_pct"]
                    for metric in invert_metrics:
                        if metric in radar_df.index:
                            radar_df.loc[metric] = radar_df.loc[metric].max() - radar_df.loc[metric]
                    
                    # Normalize each metric from 0 to 1
                    for metric in radar_df.index:
                        min_val = radar_df.loc[metric].min()
                        max_val = radar_df.loc[metric].max()
                        
                        if max_val > min_val:
                            radar_df.loc[metric] = (radar_df.loc[metric] - min_val) / (max_val - min_val)
                        else:
                            radar_df.loc[metric] = 0
                    
                    # Transpose for plotting
                    radar_df = radar_df.T
                    
                    # Create radar chart
                    fig = go.Figure()
                    
                    for backtest in radar_df.index:
                        fig.add_trace(go.Scatterpolar(
                            r=radar_df.loc[backtest].values,
                            theta=categories,
                            fill="toself",
                            name=backtest,
                        ))
                    
                    fig.update_layout(
                        polar=dict(
                            radialaxis=dict(
                                visible=True,
                                range=[0, 1]
                            )
                        ),
                        title="Strategy Performance Comparison",
                        showlegend=True
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Create bar charts for individual metrics
                    for metric in selected_metrics:
                        if metric in comparison["metrics"]:
                            metric_values = comparison["metrics"][metric]
                            
                            # Create a dataframe for this metric
                            metric_df = pd.DataFrame({
                                "Strategy": [backtest_names[bid] for bid in metric_values.keys()],
                                "Value": list(metric_values.values()),
                            })
                            
                            # Sort by value
                            metric_df = metric_df.sort_values("Value", ascending=False)
                            
                            # Create bar chart
                            fig = go.Figure()
                            fig.add_trace(go.Bar(
                                x=metric_df["Strategy"],
                                y=metric_df["Value"],
                                marker_color="#1f77b4",
                            ))
                            
                            # Format y-axis
                            y_title = metric
                            if metric in pct_metrics:
                                y_title += " (%)"
                            
                            fig.update_layout(
                                title=f"{metric.replace('_', ' ').title()}",
                                xaxis_title="Strategy",
                                yaxis_title=y_title,
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
                    
                    # Show correlation matrix if available
                    if "correlation_matrix" in comparison:
                        st.subheader("Strategy Correlation Matrix")
                        
                        # Convert to DataFrame
                        corr_df = pd.DataFrame(comparison["correlation_matrix"])
                        
                        # Use backtest display names
                        corr_df.index = [backtest_names[bid] for bid in corr_df.index]
                        corr_df.columns = [backtest_names[bid] for bid in corr_df.columns]
                        
                        # Create heatmap
                        fig = go.Figure(data=go.Heatmap(
                            z=corr_df.values,
                            x=corr_df.columns,
                            y=corr_df.index,
                            colorscale="Viridis",
                            text=[[f"{val:.2f}" for val in row] for row in corr_df.values],
                            texttemplate="%{text}",
                            textfont={"size": 12},
                        ))
                        
                        fig.update_layout(
                            title="Strategy Return Correlation",
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                        
                        st.info(
                            "Lower correlation between strategies indicates greater diversification "
                            "potential. Strategies with correlation below 0.5 are good candidates "
                            "for portfolio inclusion."
                        )
                
                except Exception as e:
                    st.error(f"Error comparing strategies: {str(e)}")
    
    def show_reports(self, api_connected=True):
        """Show the reports page.
        
        Args:
            api_connected: Whether the API is connected and available.
        """
        st.header("Performance Reports")
        st.markdown(
            """
            Access and download detailed performance reports for your backtests.
            """
        )
        
        # Check if there are any backtests
        if not st.session_state.backtest_history:
            st.info("No backtests have been run yet. Go to the Backtest Runner page to run one.")
            return
        
        # Filter to backtests with reports
        backtests_with_reports = [
            b for b in st.session_state.backtest_history
            if "report_url" in b and b["report_url"]
        ]
        
        if not backtests_with_reports:
            st.info(
                "No reports found. Make sure to enable 'Auto Generate Report' when running backtests, "
                "or generate reports manually from the Performance Analysis page."
            )
            return
        
        # Display reports
        for backtest in backtests_with_reports:
            with st.expander(
                f"{backtest['timestamp']} - {backtest['strategy']} ({backtest['symbol']} {backtest['timeframe']})"
            ):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write("**Backtest ID:**", backtest["backtest_id"])
                    st.write("**Strategy:**", backtest["strategy"])
                    st.write("**Symbol/Timeframe:**", f"{backtest['symbol']} {backtest['timeframe']}")
                    st.write("**Period:**", f"{backtest['start_date']} to {backtest['end_date']}")
                    st.write("**Total Return:**", f"{backtest['total_return_pct']:.2f}%")
                    st.write("**Max Drawdown:**", f"{backtest['max_drawdown_pct']:.2f}%")
                
                with col2:
                    html_url = f"{backtest['report_url']}"
                    pdf_url = f"{backtest['report_url']}?format=pdf"
                    
                    st.markdown(f"[View HTML Report]({html_url})")
                    st.markdown(f"[Download PDF Report]({pdf_url})")


def main():
    """Run the dashboard application."""
    dashboard = Dashboard()
    dashboard.run()


if __name__ == "__main__":
    main()