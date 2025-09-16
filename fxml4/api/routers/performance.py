"""
Performance analysis routes for FXML4 API.

This module handles performance metrics retrieval and analysis for backtests.
"""

import json
import logging
import os
from typing import Any, Dict

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status

from fxml4.api.auth.auth import User, get_current_active_user

from ..schemas import (
    ComparativeAnalysisRequest,
    PerformanceMetricsRequest,
    PerformanceReportRequest,
)

# Create router
router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/performance/metrics/{backtest_id}",
    response_model=Dict[str, Any],
    tags=["performance"],
)
async def get_performance_metrics(
    backtest_id: str,
    include_trades: bool = Query(False, description="Include trade details"),
    include_equity_curve: bool = Query(False, description="Include equity curve data"),
    current_user: User = Depends(get_current_active_user),
):
    """Get performance metrics for a backtest."""
    try:
        logger.info("Performance metrics request for backtest: %s", backtest_id)

        # Get backtest results from file
        from fxml4.config import get_config

        # Get output directory
        output_dir = get_config().get(
            "backtesting.reporting.output_dir", "output/reports"
        )

        # Check if metadata file exists
        metadata_path = os.path.join(output_dir, f"{backtest_id}_metadata.json")
        if not os.path.exists(metadata_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backtest {backtest_id} not found",
            )

        # Load metadata
        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        # Check if trades file exists
        trades_path = os.path.join(output_dir, f"{backtest_id}_trades.csv")
        equity_curve_path = os.path.join(output_dir, f"{backtest_id}_equity_curve.csv")

        # Initialize result structure
        result = {
            "backtest_id": backtest_id,
            "metrics": {
                "total_return_pct": metadata.get("total_return_pct", 0.0),
                "annualized_return": metadata.get("annualized_return", 0.0),
                "sharpe_ratio": metadata.get("sharpe_ratio", 0.0),
                "sortino_ratio": metadata.get("sortino_ratio", 0.0),
                "max_drawdown_pct": metadata.get("max_drawdown_pct", 0.0),
                "win_rate": metadata.get("win_rate", 0.0),
                "profit_factor": metadata.get("profit_factor", 0.0),
                "recovery_factor": metadata.get("recovery_factor", 0.0),
                "expectancy": metadata.get("expectancy", 0.0),
                "avg_win": metadata.get("avg_win", 0.0),
                "avg_loss": metadata.get("avg_loss", 0.0),
                "num_trades": metadata.get("num_trades", 0),
                "num_winning_trades": metadata.get("num_winning_trades", 0),
                "num_losing_trades": metadata.get("num_losing_trades", 0),
                "initial_capital": metadata.get("initial_capital", 0.0),
                "final_capital": metadata.get("final_capital", 0.0),
                "start_date": metadata.get("start_date"),
                "end_date": metadata.get("end_date"),
                "duration_days": metadata.get("duration_days", 0),
                "symbol": metadata.get("symbol"),
                "timeframe": metadata.get("timeframe"),
                "strategy": metadata.get("strategy"),
            },
        }

        # Include trades if requested
        if include_trades and os.path.exists(trades_path):
            trades_df = pd.read_csv(trades_path)
            result["trades"] = trades_df.to_dict(orient="records")

        # Include equity curve if requested
        if include_equity_curve and os.path.exists(equity_curve_path):
            equity_df = pd.read_csv(equity_curve_path)
            result["equity_curve"] = equity_df.to_dict(orient="records")

        return result

    except Exception as e:
        logger.exception("Error getting performance metrics: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/performance/report/{backtest_id}", tags=["performance"])
async def get_performance_report(
    backtest_id: str, current_user: User = Depends(get_current_active_user)
):
    """Get a comprehensive performance report for a backtest."""
    try:
        logger.info("Performance report request for backtest: %s", backtest_id)

        from fxml4.config import get_config

        # Get output directory
        output_dir = get_config().get(
            "backtesting.reporting.output_dir", "output/reports"
        )

        # Check if report file exists
        report_path = os.path.join(output_dir, f"{backtest_id}_report.json")
        if not os.path.exists(report_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Performance report for backtest {backtest_id} not found",
            )

        # Load report
        with open(report_path, "r") as f:
            report = json.load(f)

        return report

    except Exception as e:
        logger.exception("Error getting performance report: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/performance/compare", response_model=Dict[str, Any], tags=["performance"]
)
async def compare_performance(
    request: ComparativeAnalysisRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Compare performance metrics across multiple backtests."""
    try:
        logger.info("Comparative analysis request: %s", request)

        from fxml4.config import get_config

        # Get output directory
        output_dir = get_config().get(
            "backtesting.reporting.output_dir", "output/reports"
        )

        # Load metadata for all requested backtests
        backtest_data = {}
        for backtest_id in request.backtest_ids:
            metadata_path = os.path.join(output_dir, f"{backtest_id}_metadata.json")
            if os.path.exists(metadata_path):
                with open(metadata_path, "r") as f:
                    backtest_data[backtest_id] = json.load(f)

        if not backtest_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No valid backtests found for comparison",
            )

        # Create comparison structure
        comparison = {
            "backtest_ids": list(backtest_data.keys()),
            "metrics": {},
            "rankings": {},
            "summary": {
                "best_total_return": None,
                "best_sharpe_ratio": None,
                "best_max_drawdown": None,
                "best_win_rate": None,
            },
        }

        # Extract metrics for comparison
        metrics_to_compare = [
            "total_return_pct",
            "annualized_return",
            "sharpe_ratio",
            "sortino_ratio",
            "max_drawdown_pct",
            "win_rate",
            "profit_factor",
            "recovery_factor",
            "expectancy",
            "num_trades",
        ]

        for metric in metrics_to_compare:
            comparison["metrics"][metric] = {}
            for backtest_id, data in backtest_data.items():
                comparison["metrics"][metric][backtest_id] = data.get(metric, 0.0)

        # Calculate rankings
        for metric in metrics_to_compare:
            values = comparison["metrics"][metric]
            if metric == "max_drawdown_pct":
                # For drawdown, lower is better
                sorted_backtests = sorted(values.items(), key=lambda x: x[1])
            else:
                # For other metrics, higher is better
                sorted_backtests = sorted(
                    values.items(), key=lambda x: x[1], reverse=True
                )

            comparison["rankings"][metric] = [bt_id for bt_id, _ in sorted_backtests]

        # Find best performers
        if comparison["rankings"].get("total_return_pct"):
            comparison["summary"]["best_total_return"] = comparison["rankings"][
                "total_return_pct"
            ][0]
        if comparison["rankings"].get("sharpe_ratio"):
            comparison["summary"]["best_sharpe_ratio"] = comparison["rankings"][
                "sharpe_ratio"
            ][0]
        if comparison["rankings"].get("max_drawdown_pct"):
            comparison["summary"]["best_max_drawdown"] = comparison["rankings"][
                "max_drawdown_pct"
            ][0]
        if comparison["rankings"].get("win_rate"):
            comparison["summary"]["best_win_rate"] = comparison["rankings"]["win_rate"][
                0
            ]

        return comparison

    except Exception as e:
        logger.exception("Error comparing performance: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
