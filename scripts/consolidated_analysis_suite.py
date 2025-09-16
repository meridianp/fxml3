#!/usr/bin/env python3
"""
Consolidated Analysis Suite for FXML4
Combines functionality from multiple analysis scripts into a single interface.
"""

import argparse
import json
import logging
import os
import sys
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

warnings.filterwarnings("ignore")

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fxml4.backtesting.performance_metrics import PerformanceMetrics
from fxml4.data.data_loader import DataLoader
from fxml4.ml.model_loader import ModelLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConsolidatedAnalysisSuite:
    """Consolidated analysis suite for comprehensive system analysis."""

    def __init__(self):
        self.analysis_methods = {
            "backtest_results": self.analyze_backtest_results,
            "data_gaps": self.analyze_data_gaps,
            "eurusd_signals": self.analyze_eurusd_signals,
            "features_real_data": self.analyze_features_real_data,
            "ib_account_constraints": self.analyze_ib_account_constraints,
            "model_performance": self.analyze_model_performance,
            "model_predictions": self.analyze_model_predictions,
            "position_sizing_impact": self.analyze_position_sizing_impact,
            "why_low_returns": self.analyze_why_low_returns,
            "comprehensive": self.comprehensive_analysis,
        }

    def analyze_backtest_results(self, results_path, **kwargs):
        """Analyze backtest results from JSON files."""
        logger.info(f"Analyzing backtest results from {results_path}")

        results_path = Path(results_path)
        analysis = {
            "summary": {},
            "performance_metrics": {},
            "trade_analysis": {},
            "risk_analysis": {},
            "recommendations": [],
        }

        # Load results
        if results_path.is_file():
            with open(results_path, "r") as f:
                results = json.load(f)
        else:
            # Load multiple result files
            results = {}
            for file in results_path.glob("*.json"):
                with open(file, "r") as f:
                    results[file.stem] = json.load(f)

        # Analyze each backtest
        for name, result in results.items():
            if "performance" in result:
                perf = result["performance"]
                analysis["performance_metrics"][name] = {
                    "total_return": perf.get("total_return", 0),
                    "annualized_return": perf.get("annualized_return", 0),
                    "sharpe_ratio": perf.get("sharpe_ratio", 0),
                    "max_drawdown": perf.get("max_drawdown", 0),
                    "win_rate": perf.get("win_rate", 0),
                    "profit_factor": perf.get("profit_factor", 0),
                }

        # Generate summary statistics
        if analysis["performance_metrics"]:
            metrics_df = pd.DataFrame(analysis["performance_metrics"]).T
            analysis["summary"] = {
                "best_strategy": metrics_df["sharpe_ratio"].idxmax(),
                "worst_strategy": metrics_df["sharpe_ratio"].idxmin(),
                "avg_return": metrics_df["total_return"].mean(),
                "avg_sharpe": metrics_df["sharpe_ratio"].mean(),
                "avg_drawdown": metrics_df["max_drawdown"].mean(),
            }

        # Generate recommendations
        if analysis["summary"]["avg_sharpe"] < 1.0:
            analysis["recommendations"].append(
                "Consider improving risk-adjusted returns"
            )

        if analysis["summary"]["avg_drawdown"] > 0.2:
            analysis["recommendations"].append("Implement better drawdown control")

        return analysis

    def analyze_data_gaps(self, symbol, timeframe="4h", **kwargs):
        """Analyze data gaps and quality issues."""
        logger.info(f"Analyzing data gaps for {symbol} on {timeframe}")

        # Load data
        data_loader = DataLoader()
        data = data_loader.load_data(symbol, timeframe=timeframe)

        analysis = {
            "data_info": {
                "symbol": symbol,
                "timeframe": timeframe,
                "total_records": len(data),
                "date_range": {
                    "start": data.index.min().isoformat(),
                    "end": data.index.max().isoformat(),
                },
            },
            "gaps": [],
            "missing_data": {},
            "quality_issues": [],
            "recommendations": [],
        }

        # Check for time gaps
        expected_freq = {"1h": "1H", "4h": "4H", "daily": "D"}[timeframe]
        expected_index = pd.date_range(
            start=data.index.min(), end=data.index.max(), freq=expected_freq
        )

        missing_timestamps = expected_index.difference(data.index)

        if len(missing_timestamps) > 0:
            analysis["gaps"] = [
                ts.isoformat() for ts in missing_timestamps[:10]
            ]  # Show first 10
            analysis["missing_data"]["total_missing"] = len(missing_timestamps)
            analysis["missing_data"]["percentage"] = (
                len(missing_timestamps) / len(expected_index)
            ) * 100

        # Check for missing values in columns
        for col in data.columns:
            missing_count = data[col].isna().sum()
            if missing_count > 0:
                analysis["missing_data"][col] = {
                    "count": missing_count,
                    "percentage": (missing_count / len(data)) * 100,
                }

        # Check for quality issues
        for col in ["open", "high", "low", "close"]:
            if col in data.columns:
                # Check for zero values
                zero_count = (data[col] == 0).sum()
                if zero_count > 0:
                    analysis["quality_issues"].append(
                        {"type": "zero_values", "column": col, "count": zero_count}
                    )

                # Check for outliers
                Q1 = data[col].quantile(0.25)
                Q3 = data[col].quantile(0.75)
                IQR = Q3 - Q1
                outliers = data[
                    (data[col] < (Q1 - 1.5 * IQR)) | (data[col] > (Q3 + 1.5 * IQR))
                ]

                if len(outliers) > 0:
                    analysis["quality_issues"].append(
                        {"type": "outliers", "column": col, "count": len(outliers)}
                    )

        # Generate recommendations
        if analysis["missing_data"].get("percentage", 0) > 5:
            analysis["recommendations"].append(
                "Significant data gaps detected - consider data source improvement"
            )

        if len(analysis["quality_issues"]) > 0:
            analysis["recommendations"].append(
                "Quality issues detected - implement data cleaning"
            )

        return analysis

    def analyze_eurusd_signals(self, start_date=None, end_date=None, **kwargs):
        """Analyze EURUSD signal generation and quality."""
        logger.info("Analyzing EURUSD signals")

        # Load EURUSD data
        data_loader = DataLoader()
        data = data_loader.load_data("EURUSD", timeframe="4h")

        if start_date:
            data = data[data.index >= start_date]
        if end_date:
            data = data[data.index <= end_date]

        # Load signal generator
        from fxml4.strategy.integrated_signal_generator import IntegratedSignalGenerator

        signal_generator = IntegratedSignalGenerator("EURUSD")

        # Generate signals
        signals = signal_generator.generate_signals(data)

        analysis = {
            "signal_stats": {
                "total_signals": len(signals),
                "buy_signals": len(signals[signals["signal"] == 1]),
                "sell_signals": len(signals[signals["signal"] == -1]),
                "neutral_signals": len(signals[signals["signal"] == 0]),
            },
            "signal_quality": {},
            "performance": {},
            "recommendations": [],
        }

        # Analyze signal quality
        if len(signals) > 0:
            # Signal distribution
            signal_counts = signals["signal"].value_counts()
            analysis["signal_quality"]["distribution"] = signal_counts.to_dict()

            # Signal strength analysis
            if "signal_strength" in signals.columns:
                analysis["signal_quality"]["avg_strength"] = signals[
                    "signal_strength"
                ].mean()
                analysis["signal_quality"]["strength_std"] = signals[
                    "signal_strength"
                ].std()

            # Signal timing analysis
            signal_changes = signals["signal"].diff()
            analysis["signal_quality"]["signal_changes"] = len(
                signal_changes[signal_changes != 0]
            )

            # Performance of signals
            if "future_return" in signals.columns:
                buy_returns = signals[signals["signal"] == 1]["future_return"]
                sell_returns = signals[signals["signal"] == -1]["future_return"]

                analysis["performance"]["buy_signals"] = {
                    "avg_return": buy_returns.mean(),
                    "win_rate": (buy_returns > 0).mean(),
                    "count": len(buy_returns),
                }

                analysis["performance"]["sell_signals"] = {
                    "avg_return": sell_returns.mean(),
                    "win_rate": (sell_returns < 0).mean(),
                    "count": len(sell_returns),
                }

        # Generate recommendations
        if analysis["signal_stats"]["total_signals"] == 0:
            analysis["recommendations"].append(
                "No signals generated - check signal generation logic"
            )

        if analysis["signal_quality"].get("avg_strength", 0) < 0.5:
            analysis["recommendations"].append(
                "Low signal strength - consider improving signal quality"
            )

        return analysis

    def analyze_features_real_data(self, symbol, **kwargs):
        """Analyze features using real market data."""
        logger.info(f"Analyzing features for {symbol} using real data")

        # Load real data
        data_loader = DataLoader()
        data = data_loader.load_real_data(symbol, timeframe="4h")

        # Engineer features
        from fxml4.features.feature_engineering import FeatureEngineer

        feature_engineer = FeatureEngineer(timeframe="4h")
        features = feature_engineer.engineer_features(data)

        analysis = {
            "feature_stats": {},
            "correlations": {},
            "feature_importance": {},
            "quality_metrics": {},
            "recommendations": [],
        }

        # Basic feature statistics
        for col in features.columns:
            if pd.api.types.is_numeric_dtype(features[col]):
                analysis["feature_stats"][col] = {
                    "mean": features[col].mean(),
                    "std": features[col].std(),
                    "min": features[col].min(),
                    "max": features[col].max(),
                    "missing_pct": (features[col].isna().sum() / len(features)) * 100,
                }

        # Correlation analysis
        if "future_return" in features.columns:
            correlations = features.corr()["future_return"].sort_values(ascending=False)
            analysis["correlations"]["with_target"] = correlations.to_dict()

        # Feature importance (if model available)
        try:
            model_loader = ModelLoader()
            model = model_loader.load_model(symbol, timeframe="4h")
            if hasattr(model, "feature_importances_"):
                feature_names = [
                    col for col in features.columns if col != "future_return"
                ]
                importance_dict = dict(zip(feature_names, model.feature_importances_))
                analysis["feature_importance"] = dict(
                    sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)[
                        :10
                    ]
                )
        except:
            logger.warning("Could not load model for feature importance analysis")

        # Quality metrics
        analysis["quality_metrics"] = {
            "total_features": len(features.columns),
            "missing_features": sum(
                1 for col in features.columns if features[col].isna().sum() > 0
            ),
            "zero_variance_features": sum(
                1
                for col in features.columns
                if pd.api.types.is_numeric_dtype(features[col])
                and features[col].var() == 0
            ),
        }

        # Generate recommendations
        if analysis["quality_metrics"]["missing_features"] > 0:
            analysis["recommendations"].append(
                "Some features have missing values - consider imputation"
            )

        if analysis["quality_metrics"]["zero_variance_features"] > 0:
            analysis["recommendations"].append(
                "Some features have zero variance - consider removal"
            )

        return analysis

    def analyze_ib_account_constraints(self, **kwargs):
        """Analyze Interactive Brokers account constraints."""
        logger.info("Analyzing IB account constraints")

        analysis = {"account_info": {}, "constraints": {}, "recommendations": []}

        # This would typically connect to IB API
        # For now, we'll simulate the analysis
        analysis["account_info"] = {
            "account_type": "Margin",
            "base_currency": "USD",
            "net_liquidation": 100000,
            "buying_power": 200000,
        }

        analysis["constraints"] = {
            "max_leverage": 50,
            "min_trade_size": 1000,
            "max_trade_size": 1000000,
            "overnight_margin": 0.02,
            "intraday_margin": 0.01,
        }

        # Generate recommendations
        analysis["recommendations"].append(
            "Consider account constraints in position sizing"
        )
        analysis["recommendations"].append("Implement margin monitoring")

        return analysis

    def analyze_model_performance(self, symbol, model_type="rf", **kwargs):
        """Analyze model performance comprehensively."""
        logger.info(f"Analyzing {model_type} model performance for {symbol}")

        try:
            # Load model
            model_loader = ModelLoader()
            model = model_loader.load_model(
                symbol, timeframe="4h", model_type=model_type
            )

            # Load test data
            data_loader = DataLoader()
            data = data_loader.load_data(symbol, timeframe="4h")

            # Split data
            split_date = pd.Timestamp("2023-01-01")
            test_data = data[data.index >= split_date]

            # Make predictions
            predictions = model.predict(test_data)

            analysis = {
                "model_info": {
                    "symbol": symbol,
                    "model_type": model_type,
                    "test_period": f"{test_data.index.min()} to {test_data.index.max()}",
                    "test_samples": len(test_data),
                },
                "performance_metrics": {},
                "prediction_analysis": {},
                "recommendations": [],
            }

            # Calculate performance metrics
            if "future_return" in test_data.columns:
                actual = test_data["future_return"]

                from sklearn.metrics import (
                    mean_absolute_error,
                    mean_squared_error,
                    r2_score,
                )

                analysis["performance_metrics"] = {
                    "mse": mean_squared_error(actual, predictions),
                    "mae": mean_absolute_error(actual, predictions),
                    "r2": r2_score(actual, predictions),
                    "correlation": np.corrcoef(actual, predictions)[0, 1],
                }

            # Prediction analysis
            analysis["prediction_analysis"] = {
                "prediction_mean": np.mean(predictions),
                "prediction_std": np.std(predictions),
                "prediction_range": [np.min(predictions), np.max(predictions)],
            }

            # Generate recommendations
            if analysis["performance_metrics"].get("r2", 0) < 0.1:
                analysis["recommendations"].append(
                    "Low R² score - consider model improvement"
                )

            if analysis["performance_metrics"].get("correlation", 0) < 0.3:
                analysis["recommendations"].append(
                    "Low correlation - review feature engineering"
                )

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing model performance: {e}")
            return {"error": str(e)}

    def analyze_model_predictions(self, symbol, **kwargs):
        """Analyze model predictions in detail."""
        logger.info(f"Analyzing model predictions for {symbol}")

        try:
            # Load model and data
            model_loader = ModelLoader()
            model = model_loader.load_model(symbol, timeframe="4h")

            data_loader = DataLoader()
            data = data_loader.load_data(symbol, timeframe="4h")

            # Generate predictions
            predictions = model.predict(data)

            analysis = {
                "prediction_stats": {
                    "mean": np.mean(predictions),
                    "std": np.std(predictions),
                    "min": np.min(predictions),
                    "max": np.max(predictions),
                    "skewness": stats.skew(predictions),
                    "kurtosis": stats.kurtosis(predictions),
                },
                "prediction_distribution": {},
                "temporal_analysis": {},
                "recommendations": [],
            }

            # Prediction distribution
            hist, bin_edges = np.histogram(predictions, bins=20)
            analysis["prediction_distribution"] = {
                "bins": bin_edges.tolist(),
                "counts": hist.tolist(),
            }

            # Temporal analysis
            if len(data) > 0:
                pred_series = pd.Series(predictions, index=data.index)
                analysis["temporal_analysis"] = {
                    "trend": (
                        "increasing"
                        if pred_series.iloc[-1] > pred_series.iloc[0]
                        else "decreasing"
                    ),
                    "volatility": pred_series.rolling(100).std().mean(),
                    "autocorrelation": pred_series.autocorr(),
                }

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing predictions: {e}")
            return {"error": str(e)}

    def analyze_position_sizing_impact(self, symbol, **kwargs):
        """Analyze the impact of different position sizing strategies."""
        logger.info(f"Analyzing position sizing impact for {symbol}")

        # Load data
        data_loader = DataLoader()
        data = data_loader.load_data(symbol, timeframe="4h")

        # Simulate different position sizing strategies
        strategies = {
            "fixed": self._fixed_position_sizing,
            "percentage": self._percentage_position_sizing,
            "volatility": self._volatility_position_sizing,
            "kelly": self._kelly_position_sizing,
        }

        analysis = {"strategies": {}, "comparison": {}, "recommendations": []}

        # Analyze each strategy
        for name, strategy_func in strategies.items():
            try:
                result = strategy_func(data)
                analysis["strategies"][name] = result
            except Exception as e:
                logger.error(f"Error analyzing {name} strategy: {e}")
                analysis["strategies"][name] = {"error": str(e)}

        # Compare strategies
        if len(analysis["strategies"]) > 1:
            returns = {
                name: result.get("total_return", 0)
                for name, result in analysis["strategies"].items()
                if "total_return" in result
            }

            if returns:
                best_strategy = max(returns, key=returns.get)
                analysis["comparison"] = {
                    "best_strategy": best_strategy,
                    "best_return": returns[best_strategy],
                    "returns": returns,
                }

        return analysis

    def analyze_why_low_returns(self, symbol, **kwargs):
        """Analyze why returns might be low."""
        logger.info(f"Analyzing why returns are low for {symbol}")

        analysis = {
            "potential_causes": [],
            "data_issues": [],
            "model_issues": [],
            "strategy_issues": [],
            "recommendations": [],
        }

        # Check data quality
        data_analysis = self.analyze_data_gaps(symbol)
        if data_analysis["missing_data"].get("percentage", 0) > 5:
            analysis["data_issues"].append("Significant data gaps detected")

        # Check model performance
        model_analysis = self.analyze_model_performance(symbol)
        if model_analysis.get("performance_metrics", {}).get("r2", 0) < 0.1:
            analysis["model_issues"].append("Low model predictive power")

        # Check signal quality
        signal_analysis = self.analyze_eurusd_signals()
        if signal_analysis["signal_stats"]["total_signals"] == 0:
            analysis["strategy_issues"].append("No signals generated")

        # Generate recommendations
        if analysis["data_issues"]:
            analysis["recommendations"].append("Fix data quality issues")

        if analysis["model_issues"]:
            analysis["recommendations"].append("Improve model performance")

        if analysis["strategy_issues"]:
            analysis["recommendations"].append("Review signal generation strategy")

        return analysis

    def comprehensive_analysis(self, symbol, **kwargs):
        """Run comprehensive analysis combining all methods."""
        logger.info(f"Running comprehensive analysis for {symbol}")

        analysis = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "data_analysis": {},
            "model_analysis": {},
            "signal_analysis": {},
            "performance_analysis": {},
            "overall_recommendations": [],
        }

        # Run all analyses
        try:
            analysis["data_analysis"] = self.analyze_data_gaps(symbol)
        except Exception as e:
            logger.error(f"Data analysis failed: {e}")
            analysis["data_analysis"] = {"error": str(e)}

        try:
            analysis["model_analysis"] = self.analyze_model_performance(symbol)
        except Exception as e:
            logger.error(f"Model analysis failed: {e}")
            analysis["model_analysis"] = {"error": str(e)}

        try:
            analysis["signal_analysis"] = self.analyze_eurusd_signals()
        except Exception as e:
            logger.error(f"Signal analysis failed: {e}")
            analysis["signal_analysis"] = {"error": str(e)}

        # Generate overall recommendations
        analysis["overall_recommendations"] = self._generate_overall_recommendations(
            analysis
        )

        return analysis

    def _fixed_position_sizing(self, data):
        """Analyze fixed position sizing strategy."""
        # Simulate fixed position sizing
        position_size = 0.01  # 1% of account
        returns = data["close"].pct_change()
        portfolio_returns = returns * position_size

        return {
            "strategy": "fixed",
            "position_size": position_size,
            "total_return": portfolio_returns.sum(),
            "volatility": portfolio_returns.std(),
            "sharpe_ratio": (
                portfolio_returns.mean() / portfolio_returns.std()
                if portfolio_returns.std() > 0
                else 0
            ),
        }

    def _percentage_position_sizing(self, data):
        """Analyze percentage-based position sizing."""
        # Variable position sizing based on account percentage
        returns = data["close"].pct_change()
        portfolio_returns = returns * 0.02  # 2% of account

        return {
            "strategy": "percentage",
            "avg_position_size": 0.02,
            "total_return": portfolio_returns.sum(),
            "volatility": portfolio_returns.std(),
            "sharpe_ratio": (
                portfolio_returns.mean() / portfolio_returns.std()
                if portfolio_returns.std() > 0
                else 0
            ),
        }

    def _volatility_position_sizing(self, data):
        """Analyze volatility-based position sizing."""
        returns = data["close"].pct_change()
        volatility = returns.rolling(20).std()

        # Inverse volatility sizing
        position_sizes = 0.01 / volatility
        position_sizes = position_sizes.fillna(0.01)

        portfolio_returns = returns * position_sizes

        return {
            "strategy": "volatility",
            "avg_position_size": position_sizes.mean(),
            "total_return": portfolio_returns.sum(),
            "volatility": portfolio_returns.std(),
            "sharpe_ratio": (
                portfolio_returns.mean() / portfolio_returns.std()
                if portfolio_returns.std() > 0
                else 0
            ),
        }

    def _kelly_position_sizing(self, data):
        """Analyze Kelly criterion position sizing."""
        returns = data["close"].pct_change()

        # Simplified Kelly sizing
        win_rate = (returns > 0).mean()
        avg_win = returns[returns > 0].mean()
        avg_loss = returns[returns < 0].mean()

        if avg_loss != 0:
            kelly_fraction = (win_rate * avg_win + (1 - win_rate) * avg_loss) / (
                avg_win * abs(avg_loss)
            )
            kelly_fraction = max(0, min(0.25, kelly_fraction))  # Cap at 25%
        else:
            kelly_fraction = 0.01

        portfolio_returns = returns * kelly_fraction

        return {
            "strategy": "kelly",
            "kelly_fraction": kelly_fraction,
            "total_return": portfolio_returns.sum(),
            "volatility": portfolio_returns.std(),
            "sharpe_ratio": (
                portfolio_returns.mean() / portfolio_returns.std()
                if portfolio_returns.std() > 0
                else 0
            ),
        }

    def _generate_overall_recommendations(self, analysis):
        """Generate overall recommendations based on comprehensive analysis."""
        recommendations = []

        # Data quality recommendations
        if analysis["data_analysis"].get("missing_data", {}).get("percentage", 0) > 5:
            recommendations.append(
                "HIGH: Fix data quality issues - over 5% missing data"
            )

        # Model performance recommendations
        if analysis["model_analysis"].get("performance_metrics", {}).get("r2", 0) < 0.1:
            recommendations.append("HIGH: Improve model performance - R² below 0.1")

        # Signal generation recommendations
        if (
            analysis["signal_analysis"].get("signal_stats", {}).get("total_signals", 0)
            == 0
        ):
            recommendations.append(
                "CRITICAL: No signals generated - review signal logic"
            )

        # General recommendations
        recommendations.append(
            "MEDIUM: Consider ensemble methods for better predictions"
        )
        recommendations.append("LOW: Implement A/B testing for strategy comparison")

        return recommendations

    def run_analysis_method(self, method_name, **kwargs):
        """Run a specific analysis method."""
        if method_name not in self.analysis_methods:
            raise ValueError(f"Unknown analysis method: {method_name}")

        return self.analysis_methods[method_name](**kwargs)

    def list_analysis_methods(self):
        """List available analysis methods."""
        return list(self.analysis_methods.keys())


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(description="FXML4 Consolidated Analysis Suite")
    parser.add_argument("--method", required=True, help="Analysis method to run")
    parser.add_argument("--symbol", help="Trading symbol")
    parser.add_argument("--results-path", help="Path to backtest results")
    parser.add_argument("--start-date", help="Start date for analysis")
    parser.add_argument("--end-date", help="End date for analysis")
    parser.add_argument(
        "--list-methods", action="store_true", help="List available analysis methods"
    )
    parser.add_argument("--output", help="Output file for results")

    args = parser.parse_args()

    suite = ConsolidatedAnalysisSuite()

    if args.list_methods:
        print("Available analysis methods:")
        for method in suite.list_analysis_methods():
            print(f"  - {method}")
        return

    # Run analysis method
    kwargs = {
        "symbol": args.symbol,
        "results_path": args.results_path,
        "start_date": args.start_date,
        "end_date": args.end_date,
    }

    logger.info(f"Running analysis method: {args.method}")
    result = suite.run_analysis_method(args.method, **kwargs)

    # Save results
    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, default=str)
        logger.info(f"Results saved to {args.output}")
    else:
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
