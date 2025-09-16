"""Report generator for trading performance.

This module provides functionality to generate HTML and PDF reports
from backtesting performance metrics and visualizations.
"""

import base64
import logging
import os
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    import matplotlib.pyplot as plt
    from jinja2 import Environment, FileSystemLoader, Template

    HAS_REPORT_DEPS = True
except ImportError:
    logger.warning(
        "Missing dependencies for report generation. Install jinja2 and matplotlib."
    )
    HAS_REPORT_DEPS = False


def figure_to_base64(fig: Any) -> str:
    """Convert matplotlib figure to base64 string for embedding in HTML.

    Args:
        fig: Matplotlib figure object

    Returns:
        Base64 encoded image string
    """
    if not HAS_REPORT_DEPS:
        return ""

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode("utf-8")
    buf.close()
    return img_str


def dataframe_to_html(df: pd.DataFrame, classes: str = "table table-striped") -> str:
    """Convert DataFrame to styled HTML table.

    Args:
        df: DataFrame to convert
        classes: CSS classes for the table

    Returns:
        HTML string
    """
    if df is None or df.empty:
        return "<p>No data available</p>"

    # Format floats with 2 decimal places
    formatted_df = df.copy()
    for col in formatted_df.select_dtypes(include=["float"]).columns:
        # Check if the column might be a percentage
        if "pct" in col or "rate" in col or col.endswith("_pct"):
            formatted_df[col] = formatted_df[col].map(lambda x: f"{x:.2f}%")
        else:
            formatted_df[col] = formatted_df[col].map(lambda x: f"{x:.2f}")

    # Convert to HTML with classes
    html = formatted_df.to_html(classes=classes, border=0)

    return html


def create_performance_report(
    strategy_name: str,
    metrics: Any,
    equity_curve: pd.DataFrame,
    trades: List[Dict[str, Any]],
    figures: List[Any] = None,
    additional_data: Dict[str, Any] = None,
    output_dir: str = "output/reports",
    template_path: Optional[str] = None,
) -> str:
    """Create HTML performance report.

    Args:
        strategy_name: Name of the strategy
        metrics: PerformanceMetrics object
        equity_curve: Equity curve DataFrame
        trades: List of trade dictionaries
        figures: Optional list of figure objects to include
        additional_data: Optional additional data to include
        output_dir: Directory to save the report
        template_path: Path to Jinja2 template directory

    Returns:
        Path to the generated report file
    """
    if not HAS_REPORT_DEPS:
        logger.error("Cannot create report: missing dependencies")
        return ""

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Get template directory
    if template_path is None:
        # Default template is stored inline
        template_str = DEFAULT_TEMPLATE
        template = Template(template_str)
    else:
        # Load template from file
        env = Environment(loader=FileSystemLoader(template_path))
        template = env.get_template("performance_report.html")

    # Process trades for table
    trades_df = pd.DataFrame(
        [
            {
                "entry_time": t.get("entry_time", ""),
                "exit_time": t.get("exit_time", ""),
                "symbol": t.get("symbol", ""),
                "side": t.get("side", ""),
                "pnl": t.get("pnl", 0),
                "pnl_pct": t.get("pnl_pct", 0),
            }
            for t in trades
        ]
    )

    # Sort trades by entry time
    if not trades_df.empty and "entry_time" in trades_df.columns:
        trades_df = trades_df.sort_values("entry_time", ascending=False).head(
            20
        )  # Show last 20 trades

    # Convert metrics to dictionary
    metrics_dict = metrics.to_dict() if hasattr(metrics, "to_dict") else metrics

    # Convert figures to base64 images
    figure_images = []
    if figures:
        for i, fig in enumerate(figures):
            if fig is not None:
                figure_images.append(
                    {
                        "title": f"Figure {i+1}",
                        "description": f"Visualization {i+1}",
                        "data": figure_to_base64(fig),
                    }
                )

    # Get datetime components for report
    now = datetime.now()
    report_date = now.strftime("%Y-%m-%d")
    report_time = now.strftime("%H:%M:%S")

    # Render template
    html = template.render(
        strategy_name=strategy_name,
        report_date=report_date,
        report_time=report_time,
        metrics=metrics_dict,
        trades_table=dataframe_to_html(trades_df),
        monthly_returns_table=(
            dataframe_to_html(metrics.monthly_returns)
            if hasattr(metrics, "monthly_returns")
            else ""
        ),
        figures=figure_images,
        additional_data=additional_data or {},
    )

    # Save HTML file
    filename = f"{strategy_name.replace(' ', '_')}_{report_date}.html"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w") as f:
        f.write(html)

    logger.info(f"Performance report generated: {filepath}")
    return filepath


def export_to_pdf(
    html_path: str,
    output_path: Optional[str] = None,
) -> str:
    """Export HTML report to PDF.

    Args:
        html_path: Path to HTML report
        output_path: Path for PDF output (if None, uses HTML path with PDF extension)

    Returns:
        Path to the generated PDF file
    """
    try:
        import weasyprint
    except ImportError:
        logger.error("Cannot export to PDF: WeasyPrint not installed")
        return ""

    if output_path is None:
        output_path = html_path.replace(".html", ".pdf")

    try:
        weasyprint.HTML(filename=html_path).write_pdf(output_path)
        logger.info(f"PDF report generated: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        return ""


# Default HTML template for performance reports
DEFAULT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ strategy_name }} - Performance Report</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid #eee;
        }
        .metrics-card {
            margin-bottom: 20px;
        }
        .metrics-group {
            margin-bottom: 30px;
        }
        .figure-container {
            margin: 30px 0;
            text-align: center;
        }
        .figure-container img {
            max-width: 100%;
            height: auto;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th, td {
            padding: 8px;
            text-align: left;
        }
        .footer {
            margin-top: 50px;
            text-align: center;
            font-size: 0.8em;
            color: #777;
        }
        .good {
            color: green;
        }
        .bad {
            color: red;
        }
        .neutral {
            color: orange;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{ strategy_name }}</h1>
        <p>Performance Report | Generated on {{ report_date }} at {{ report_time }}</p>
    </div>

    <div class="container">
        <div class="row">
            <div class="col-md-6">
                <div class="card metrics-card">
                    <div class="card-header">
                        <h3>Return Metrics</h3>
                    </div>
                    <div class="card-body">
                        <table class="table table-striped">
                            <tr>
                                <td>Total Return</td>
                                <td>{{ "%.2f"|format(metrics.total_return_pct) }}%</td>
                            </tr>
                            <tr>
                                <td>Annualized Return</td>
                                <td>{{ "%.2f"|format(metrics.annualized_return) }}%</td>
                            </tr>
                            <tr>
                                <td>Sharpe Ratio</td>
                                <td>{{ "%.2f"|format(metrics.sharpe_ratio) }}</td>
                            </tr>
                            <tr>
                                <td>Sortino Ratio</td>
                                <td>{{ "%.2f"|format(metrics.sortino_ratio) }}</td>
                            </tr>
                            <tr>
                                <td>Calmar Ratio</td>
                                <td>{{ "%.2f"|format(metrics.calmar_ratio) }}</td>
                            </tr>
                            {% if metrics.alpha is not none %}
                            <tr>
                                <td>Alpha</td>
                                <td>{{ "%.4f"|format(metrics.alpha) }}</td>
                            </tr>
                            {% endif %}
                            {% if metrics.beta is not none %}
                            <tr>
                                <td>Beta</td>
                                <td>{{ "%.2f"|format(metrics.beta) }}</td>
                            </tr>
                            {% endif %}
                        </table>
                    </div>
                </div>
            </div>

            <div class="col-md-6">
                <div class="card metrics-card">
                    <div class="card-header">
                        <h3>Risk Metrics</h3>
                    </div>
                    <div class="card-body">
                        <table class="table table-striped">
                            <tr>
                                <td>Maximum Drawdown</td>
                                <td class="bad">{{ "%.2f"|format(metrics.max_drawdown_pct) }}%</td>
                            </tr>
                            <tr>
                                <td>Average Drawdown</td>
                                <td>{{ "%.2f"|format(metrics.avg_drawdown * 100) }}%</td>
                            </tr>
                            <tr>
                                <td>Volatility</td>
                                <td>{{ "%.2f"|format(metrics.volatility) }}%</td>
                            </tr>
                            <tr>
                                <td>Value at Risk (95%)</td>
                                <td>{{ "%.2f"|format(metrics.var_95) }}%</td>
                            </tr>
                            <tr>
                                <td>Conditional VaR (95%)</td>
                                <td>{{ "%.2f"|format(metrics.cvar_95) }}%</td>
                            </tr>
                            <tr>
                                <td>Ulcer Index</td>
                                <td>{{ "%.4f"|format(metrics.ulcer_index) }}</td>
                            </tr>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-md-6">
                <div class="card metrics-card">
                    <div class="card-header">
                        <h3>Trade Metrics</h3>
                    </div>
                    <div class="card-body">
                        <table class="table table-striped">
                            <tr>
                                <td>Number of Trades</td>
                                <td>{{ metrics.num_trades }}</td>
                            </tr>
                            <tr>
                                <td>Win Rate</td>
                                <td>{{ "%.2f"|format(metrics.win_rate * 100) }}%</td>
                            </tr>
                            <tr>
                                <td>Profit Factor</td>
                                <td>{{ "%.2f"|format(metrics.profit_factor) }}</td>
                            </tr>
                            <tr>
                                <td>Average Profit</td>
                                <td class="good">${{ "%.2f"|format(metrics.avg_profit_per_trade) }}</td>
                            </tr>
                            <tr>
                                <td>Average Loss</td>
                                <td class="bad">${{ "%.2f"|format(metrics.avg_loss_per_trade) }}</td>
                            </tr>
                            <tr>
                                <td>Max Consecutive Wins</td>
                                <td>{{ metrics.max_consecutive_wins }}</td>
                            </tr>
                            <tr>
                                <td>Max Consecutive Losses</td>
                                <td>{{ metrics.max_consecutive_losses }}</td>
                            </tr>
                            {% if metrics.expectancy is not none %}
                            <tr>
                                <td>Expectancy</td>
                                <td>{{ "%.4f"|format(metrics.expectancy) }}</td>
                            </tr>
                            {% endif %}
                            {% if metrics.kelly_percentage is not none %}
                            <tr>
                                <td>Kelly Percentage</td>
                                <td>{{ "%.2f"|format(metrics.kelly_percentage) }}%</td>
                            </tr>
                            {% endif %}
                        </table>
                    </div>
                </div>
            </div>

            <div class="col-md-6">
                <div class="card metrics-card">
                    <div class="card-header">
                        <h3>Cost Analysis</h3>
                    </div>
                    <div class="card-body">
                        <table class="table table-striped">
                            {% if metrics.total_fees is not none %}
                            <tr>
                                <td>Total Fees</td>
                                <td>${{ "%.2f"|format(metrics.total_fees) }}</td>
                            </tr>
                            {% endif %}
                            {% if metrics.total_slippage is not none %}
                            <tr>
                                <td>Total Slippage</td>
                                <td>${{ "%.2f"|format(metrics.total_slippage) }}</td>
                            </tr>
                            {% endif %}
                            {% if metrics.cost_per_trade is not none %}
                            <tr>
                                <td>Cost per Trade</td>
                                <td>${{ "%.2f"|format(metrics.cost_per_trade) }}</td>
                            </tr>
                            {% endif %}
                            {% if metrics.cost_as_pct_of_profit is not none %}
                            <tr>
                                <td>Cost % of Profit</td>
                                <td>{{ "%.2f"|format(metrics.cost_as_pct_of_profit) }}%</td>
                            </tr>
                            {% endif %}
                        </table>
                    </div>
                </div>
            </div>
        </div>

        {% if figures %}
        <div class="row">
            <div class="col-md-12">
                <h2>Visualizations</h2>
                {% for figure in figures %}
                <div class="figure-container">
                    <h4>{{ figure.title }}</h4>
                    <p>{{ figure.description }}</p>
                    <img src="data:image/png;base64,{{ figure.data }}" alt="{{ figure.title }}">
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}

        {% if monthly_returns_table %}
        <div class="row">
            <div class="col-md-12">
                <h2>Monthly Returns</h2>
                {{ monthly_returns_table|safe }}
            </div>
        </div>
        {% endif %}

        {% if trades_table %}
        <div class="row">
            <div class="col-md-12">
                <h2>Recent Trades</h2>
                {{ trades_table|safe }}
            </div>
        </div>
        {% endif %}

        {% if additional_data %}
        <div class="row">
            <div class="col-md-12">
                <h2>Additional Information</h2>
                {% for key, value in additional_data.items() %}
                <div class="card mb-3">
                    <div class="card-header">
                        <h3>{{ key }}</h3>
                    </div>
                    <div class="card-body">
                        {% if value is mapping %}
                            <table class="table table-striped">
                            {% for k, v in value.items() %}
                                <tr>
                                    <td>{{ k }}</td>
                                    <td>{{ v }}</td>
                                </tr>
                            {% endfor %}
                            </table>
                        {% elif value is string %}
                            <p>{{ value }}</p>
                        {% else %}
                            <p>{{ value }}</p>
                        {% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}
    </div>

    <div class="footer">
        <p>Generated by FXML4 Performance Analysis System</p>
    </div>
</body>
</html>
"""
