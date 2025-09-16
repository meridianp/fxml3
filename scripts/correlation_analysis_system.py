#!/usr/bin/env python
"""Comprehensive correlation analysis using Alpha Vantage and FRED APIs."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import os
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

import json

# Visualization
import matplotlib.pyplot as plt
import requests
import seaborn as sns

# API libraries
from alpha_vantage.foreignexchange import ForeignExchange
from alpha_vantage.techindicators import TechIndicators
from alpha_vantage.timeseries import TimeSeries
from fredapi import Fred
from scipy import stats


class CorrelationAnalysisSystem:
    """Comprehensive correlation analysis for forex trading."""

    def __init__(self):
        # API keys from environment
        self.alpha_key = os.getenv("ALPHA_VANTAGE_API_KEY", "V10FRLTU9WKTQMD9")
        self.fred_key = os.getenv("FRED_API_KEY", "5dfb1a7abe234caa5831f1a180a1bf1d")

        # Initialize API clients
        self.fred = Fred(api_key=self.fred_key)
        self.fx = ForeignExchange(key=self.alpha_key)
        self.ti = TechIndicators(key=self.alpha_key)
        self.ts = TimeSeries(key=self.alpha_key)

        # Key economic series for forex correlation
        self.fred_series = {
            # Dollar indices
            "DXY": "DTWEXAFEGS",  # Trade Weighted Dollar Index
            "DXY_BROAD": "DTWEXBGS",  # Broad Dollar Index
            # Interest rates
            "FED_RATE": "DFF",  # Federal Funds Rate
            "US_2Y": "DGS2",  # 2-Year Treasury
            "US_10Y": "DGS10",  # 10-Year Treasury
            # Volatility
            "VIX": "VIXCLS",  # VIX Index
            "MOVE": "MOVE",  # Bond volatility
            # Economic indicators
            "US_CPI": "CPIAUCSL",  # Consumer Price Index
            "US_GDP": "GDP",  # Gross Domestic Product
            "US_UNEMPLOYMENT": "UNRATE",  # Unemployment Rate
            # Commodities (via FRED)
            "GOLD": "GOLDAMGBD228NLBM",  # Gold Price
            "OIL_WTI": "DCOILWTICO",  # WTI Oil Price
            # Other currency pairs
            "EURUSD_FRED": "DEXUSEU",  # EUR/USD
            "GBPUSD_FRED": "DEXUSUK",  # GBP/USD
            "USDJPY_FRED": "DEXJPUS",  # USD/JPY
            "USDCHF_FRED": "DEXSZUS",  # USD/CHF
        }

        # Correlation groups
        self.correlation_groups = {
            "risk_on": ["SPX", "AUD", "NZD", "CAD"],
            "risk_off": ["GOLD", "JPY", "CHF", "VIX"],
            "dollar_strength": ["DXY", "EURUSD", "GBPUSD"],
            "commodity_currencies": ["AUD", "CAD", "NZD"],
            "carry_trade": ["JPY", "CHF", "AUD", "NZD"],
        }

    def fetch_fred_data(
        self, series_id: str, start_date: str, end_date: str
    ) -> pd.Series:
        """Fetch data from FRED API."""
        try:
            data = self.fred.get_series(
                series_id, observation_start=start_date, observation_end=end_date
            )
            return data
        except Exception as e:
            print(f"Error fetching {series_id}: {e}")
            return pd.Series()

    def fetch_alpha_vantage_forex(
        self, from_symbol: str, to_symbol: str, interval: str = "daily"
    ) -> pd.DataFrame:
        """Fetch forex data from Alpha Vantage."""
        try:
            if interval == "daily":
                data, _ = self.fx.get_currency_exchange_daily(
                    from_symbol, to_symbol, outputsize="full"
                )
            else:
                data, _ = self.fx.get_currency_exchange_intraday(
                    from_symbol, to_symbol, interval="60min", outputsize="full"
                )

            df = pd.DataFrame.from_dict(data, orient="index")
            df.index = pd.to_datetime(df.index)
            df = df.astype(float)
            return df.sort_index()
        except Exception as e:
            print(f"Error fetching {from_symbol}/{to_symbol}: {e}")
            return pd.DataFrame()

    def fetch_economic_indicators(
        self, start_date: str, end_date: str
    ) -> Dict[str, pd.Series]:
        """Fetch all economic indicators."""
        print("Fetching economic indicators from FRED...")
        indicators = {}

        for name, series_id in self.fred_series.items():
            print(f"  Fetching {name}...")
            data = self.fetch_fred_data(series_id, start_date, end_date)
            if not data.empty:
                indicators[name] = data

        return indicators

    def calculate_correlations(
        self, data_dict: Dict[str, pd.Series], window: int = 252
    ) -> pd.DataFrame:
        """Calculate rolling correlations between all series."""
        # Create combined dataframe
        df = pd.DataFrame(data_dict)
        df = df.ffill().dropna()

        # Calculate returns
        returns = df.pct_change().dropna()

        # Calculate correlation matrix
        corr_matrix = returns.corr()

        # Calculate rolling correlations for key pairs
        rolling_corr = {}

        # Dollar vs major currencies
        if "DXY" in returns.columns:
            for currency in ["EURUSD_FRED", "GBPUSD_FRED", "USDJPY_FRED"]:
                if currency in returns.columns:
                    rolling_corr[f"DXY_vs_{currency}"] = (
                        returns["DXY"].rolling(window).corr(returns[currency])
                    )

        # Risk on/off correlations
        if "VIX" in returns.columns and "GOLD" in returns.columns:
            rolling_corr["VIX_vs_GOLD"] = (
                returns["VIX"].rolling(window).corr(returns["GOLD"])
            )

        # Commodity currencies vs commodities
        if "OIL_WTI" in returns.columns:
            for currency in ["USDCAD_FRED", "AUDUSD_FRED"]:
                if currency in returns.columns:
                    rolling_corr[f"OIL_vs_{currency}"] = (
                        returns["OIL_WTI"].rolling(window).corr(returns[currency])
                    )

        return corr_matrix, rolling_corr

    def detect_market_regime(self, indicators: Dict[str, pd.Series]) -> pd.Series:
        """Detect market regime based on multiple indicators."""
        regime = pd.Series(
            index=indicators.get("VIX", pd.Series()).index, dtype="object"
        )

        # VIX-based regime
        if "VIX" in indicators:
            vix = indicators["VIX"]
            vix_ma = vix.rolling(20).mean()

            # Risk regimes
            high_risk = vix > 25
            medium_risk = (vix > 15) & (vix <= 25)
            low_risk = vix <= 15

            regime[high_risk] = "RISK_OFF"
            regime[medium_risk] = "NEUTRAL"
            regime[low_risk] = "RISK_ON"

        # Trend regime overlay
        if "DXY" in indicators:
            dxy = indicators["DXY"]
            dxy_sma50 = dxy.rolling(50).mean()
            dxy_sma200 = dxy.rolling(200).mean()

            dollar_bull = (dxy > dxy_sma50) & (dxy_sma50 > dxy_sma200)
            dollar_bear = (dxy < dxy_sma50) & (dxy_sma50 < dxy_sma200)

            # Combine regimes
            regime[dollar_bull & (regime == "RISK_ON")] = "DOLLAR_BULL_RISK_ON"
            regime[dollar_bull & (regime == "RISK_OFF")] = "DOLLAR_BULL_RISK_OFF"
            regime[dollar_bear & (regime == "RISK_ON")] = "DOLLAR_BEAR_RISK_ON"
            regime[dollar_bear & (regime == "RISK_OFF")] = "DOLLAR_BEAR_RISK_OFF"

        return regime.ffill()

    def calculate_correlation_signals(
        self, correlations: Dict[str, pd.Series], regime: pd.Series
    ) -> pd.DataFrame:
        """Generate trading signals based on correlations and regime."""
        signals = pd.DataFrame(index=regime.index)

        # Strategy 1: Trade correlation divergences
        for pair, corr in correlations.items():
            if not corr.empty:
                # Z-score of correlation
                corr_mean = corr.rolling(252).mean()
                corr_std = corr.rolling(252).std()
                z_score = (corr - corr_mean) / corr_std

                # Signal when correlation breaks down
                signals[f"{pair}_divergence"] = 0
                signals.loc[z_score < -2, f"{pair}_divergence"] = (
                    1  # Correlation breakdown
                )
                signals.loc[z_score > 2, f"{pair}_divergence"] = (
                    -1
                )  # Excessive correlation

        # Strategy 2: Regime-based positioning
        signals["regime_signal"] = 0

        # Risk-off: Long USD, JPY, CHF
        signals.loc[regime.str.contains("RISK_OFF", na=False), "regime_signal"] = 1

        # Risk-on: Short USD, Long commodity currencies
        signals.loc[regime.str.contains("RISK_ON", na=False), "regime_signal"] = -1

        return signals

    def create_correlation_heatmap(self, corr_matrix: pd.DataFrame, output_path: str):
        """Create correlation heatmap visualization."""
        plt.figure(figsize=(12, 10))

        # Create mask for upper triangle
        mask = np.triu(np.ones_like(corr_matrix, dtype=bool))

        # Create heatmap
        sns.heatmap(
            corr_matrix,
            mask=mask,
            cmap="coolwarm",
            center=0,
            square=True,
            linewidths=0.5,
            cbar_kws={"shrink": 0.8},
            annot=True,
            fmt=".2f",
            annot_kws={"size": 8},
        )

        plt.title("Economic Indicators & Forex Correlation Matrix", fontsize=16)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()

        print(f"✅ Correlation heatmap saved to: {output_path}")

    def analyze_forex_correlations(
        self, symbols: List[str], start_date: str, end_date: str
    ):
        """Main analysis function."""
        print("=" * 70)
        print("COMPREHENSIVE FOREX CORRELATION ANALYSIS")
        print("=" * 70)

        # Fetch economic indicators
        indicators = self.fetch_economic_indicators(start_date, end_date)
        print(f"\n✅ Fetched {len(indicators)} economic indicators")

        # Calculate correlations
        if indicators:
            corr_matrix, rolling_corr = self.calculate_correlations(indicators)

            # Detect market regime
            regime = self.detect_market_regime(indicators)
            regime_counts = regime.value_counts()

            print("\nMarket Regime Distribution:")
            for reg, count in regime_counts.items():
                pct = count / len(regime) * 100
                print(f"  {reg}: {count} days ({pct:.1f}%)")

            # Generate signals
            signals = self.calculate_correlation_signals(rolling_corr, regime)

            # Create visualizations
            output_dir = Path("output/correlation_analysis")
            output_dir.mkdir(exist_ok=True, parents=True)

            # Correlation heatmap
            self.create_correlation_heatmap(
                corr_matrix, output_dir / "correlation_heatmap.png"
            )

            # Save correlation matrix
            corr_matrix.to_csv(output_dir / "correlation_matrix.csv")

            # Key correlations for forex
            print("\nKey Forex Correlations:")
            forex_pairs = ["EURUSD_FRED", "GBPUSD_FRED", "USDJPY_FRED", "USDCHF_FRED"]

            for pair in forex_pairs:
                if pair in corr_matrix.columns:
                    # vs DXY
                    if "DXY" in corr_matrix.columns:
                        corr_dxy = corr_matrix.loc[pair, "DXY"]
                        print(f"  {pair} vs DXY: {corr_dxy:.3f}")

                    # vs VIX (risk sentiment)
                    if "VIX" in corr_matrix.columns:
                        corr_vix = corr_matrix.loc[pair, "VIX"]
                        print(f"  {pair} vs VIX: {corr_vix:.3f}")

                    # vs Gold (safe haven)
                    if "GOLD" in corr_matrix.columns:
                        corr_gold = corr_matrix.loc[pair, "GOLD"]
                        print(f"  {pair} vs GOLD: {corr_gold:.3f}")

            # Interest rate differentials
            if "US_10Y" in indicators and "US_2Y" in indicators:
                yield_curve = indicators["US_10Y"] - indicators["US_2Y"]
                print(f"\nCurrent Yield Curve (10Y-2Y): {yield_curve.iloc[-1]:.2f}%")

                # Correlation with forex
                for pair in forex_pairs:
                    if pair in indicators:
                        fx_returns = indicators[pair].pct_change()
                        yc_returns = yield_curve.pct_change()
                        corr = fx_returns.corr(yc_returns)
                        print(f"  {pair} vs Yield Curve: {corr:.3f}")

            return corr_matrix, rolling_corr, regime, signals

        return None, None, None, None


def main():
    """Run correlation analysis."""
    # Initialize system
    analyzer = CorrelationAnalysisSystem()

    # Analysis period
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=365 * 2)).strftime("%Y-%m-%d")

    # Forex symbols to analyze
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]

    # Run analysis
    corr_matrix, rolling_corr, regime, signals = analyzer.analyze_forex_correlations(
        symbols, start_date, end_date
    )

    if corr_matrix is not None:
        print("\n✅ Correlation analysis complete!")
        print("\nKey Insights:")
        print("1. Use DXY correlation to avoid overexposure to USD moves")
        print("2. Monitor VIX for risk-on/risk-off regime changes")
        print("3. Track yield curve for interest rate differential trades")
        print("4. Use commodity correlations for CAD and AUD positions")
        print("5. Watch gold correlation for safe-haven flows")

        # Trading recommendations based on correlations
        print("\nCorrelation-Based Trading Rules:")
        print("- Reduce position size when correlations are extreme (>0.8)")
        print("- Avoid same-direction trades in highly correlated pairs")
        print("- Use regime detection to adjust strategy bias")
        print("- Monitor correlation breakdowns for trading opportunities")


if __name__ == "__main__":
    main()
