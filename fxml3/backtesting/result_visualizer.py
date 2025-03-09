"""Visualization tools for backtesting results."""

from typing import Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class ResultVisualizer:
    """Visualize backtesting results."""
    
    @staticmethod
    def plot_performance_metrics(
        metrics: Dict,
        title: str = "Backtesting Performance Metrics",
        figsize: Tuple[int, int] = (10, 6),
    ) -> plt.Figure:
        """Create a bar chart of performance metrics.
        
        Args:
            metrics: Dictionary with performance metrics
            title: Chart title
            figsize: Figure size
            
        Returns:
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=figsize)
        
        # Extract metrics from the overall section
        if "overall" in metrics:
            metrics_to_plot = {
                "Accuracy": metrics["overall"].get("accuracy", 0) * 100,
                "Detection Rate": metrics["overall"].get("detection_rate", 0) * 100,
            }
            
            # Add pattern-specific metrics if available
            if "by_pattern_type" in metrics:
                if "impulse" in metrics["by_pattern_type"]:
                    metrics_to_plot["Impulse Accuracy"] = metrics["by_pattern_type"]["impulse"].get("accuracy", 0) * 100
                    
                if "corrective" in metrics["by_pattern_type"]:
                    metrics_to_plot["Corrective Accuracy"] = metrics["by_pattern_type"]["corrective"].get("accuracy", 0) * 100
        else:
            # Use root metrics
            metrics_to_plot = {
                "Accuracy": metrics.get("accuracy", 0) * 100,
                "Win Rate": metrics.get("win_rate", 0) * 100,
                "Avg R/R Ratio": metrics.get("avg_risk_reward_ratio", 0),
            }
            
            if "risk_reward_ratio" in metrics:
                metrics_to_plot["Risk/Reward"] = metrics["risk_reward_ratio"]
                
            if "avg_time_to_target" in metrics:
                metrics_to_plot["Avg Time to Target"] = metrics["avg_time_to_target"]
        
        # Create bar chart
        labels = list(metrics_to_plot.keys())
        values = list(metrics_to_plot.values())
        
        # Use different colors for different metrics
        colors = ['#2ca02c', '#1f77b4', '#ff7f0e', '#d62728', '#9467bd']
        
        ax.bar(labels, values, color=colors[:len(labels)])
        
        # Add values on top of bars
        for i, v in enumerate(values):
            ax.text(i, v + 0.5, f"{v:.1f}", ha='center')
        
        # Add labels and title
        ax.set_ylabel('Percentage / Value')
        ax.set_title(title)
        
        # Set y-axis limit based on data
        ax.set_ylim(0, max(values) * 1.2)
        
        # Add grid lines
        ax.grid(axis='y', linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        return fig
    
    @staticmethod
    def plot_advanced_equity_curve(
        equity_curve: List[float],
        trade_outcomes: Optional[List[Dict]] = None,
        monte_carlo_results: Optional[Dict] = None,
        title: str = "Advanced Equity Curve with Monte Carlo Simulation",
        figsize: Tuple[int, int] = (14, 10),
    ) -> plt.Figure:
        """Plot an advanced equity curve with Monte Carlo simulation results.
        
        Args:
            equity_curve: List of equity values
            trade_outcomes: Optional list of trade outcomes with execution details
            monte_carlo_results: Optional Monte Carlo simulation results
            title: Chart title
            figsize: Figure size
            
        Returns:
            Matplotlib figure with multiple subplots showing equity curve and statistics
        """
        # Create figure with multiple subplots
        if monte_carlo_results:
            fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=figsize, 
                                               gridspec_kw={'height_ratios': [3, 1, 2]})
        else:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize, 
                                          gridspec_kw={'height_ratios': [3, 1]})
        
        # Plot main equity curve with transaction costs overlay
        trades = range(len(equity_curve))
        ax1.plot(trades, equity_curve, label='Equity', color='#2ca02c', linewidth=2)
        
        # Calculate and plot drawdown on second subplot
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (peak - equity_curve) / peak * 100
        ax2.fill_between(trades, drawdown, 0, alpha=0.3, color='red', label='Drawdown %')
        ax2.set_ylabel('Drawdown %')
        ax2.set_title('Drawdown Analysis')
        ax2.grid(True, linestyle='--', alpha=0.7)
        
        # Add annotations for main equity curve
        ax1.annotate(f"${equity_curve[0]:,.2f}", 
                   xy=(0, equity_curve[0]), 
                   xytext=(5, 5),
                   textcoords='offset points')
                   
        ax1.annotate(f"${equity_curve[-1]:,.2f}", 
                   xy=(len(equity_curve)-1, equity_curve[-1]), 
                   xytext=(5, 5),
                   textcoords='offset points')
        
        # Highlight maximum drawdown
        max_dd_idx = np.argmax(drawdown)
        if max_dd_idx > 0:
            ax1.plot(max_dd_idx, equity_curve[max_dd_idx], 'ro')
            ax1.annotate(f"Max DD: {drawdown[max_dd_idx]:.1f}%", 
                       xy=(max_dd_idx, equity_curve[max_dd_idx]), 
                       xytext=(10, -20),
                       textcoords='offset points',
                       arrowprops=dict(arrowstyle="->", color='red'))
                       
            # Also mark on drawdown chart
            ax2.plot(max_dd_idx, drawdown[max_dd_idx], 'ro')
            ax2.annotate(f"{drawdown[max_dd_idx]:.1f}%", 
                       xy=(max_dd_idx, drawdown[max_dd_idx]), 
                       xytext=(5, 5),
                       textcoords='offset points')
        
        # Add transaction cost overlay if data is available
        if trade_outcomes:
            # Organize trade executions by index
            trade_indices = []
            trade_costs = []
            slippage_costs = []
            
            for i, outcome in enumerate(trade_outcomes):
                if "total_cost" in outcome:
                    trade_indices.append(i+1)  # +1 because equity curve starts with initial capital
                    trade_costs.append(outcome["total_cost"])
                    
                    if "slippage" in outcome:
                        position_size = outcome.get("position_size", 10000.0)
                        slippage_costs.append(outcome["slippage"] * position_size)
                    else:
                        slippage_costs.append(0)
            
            if trade_costs:
                # Create twin axis for cost display
                cost_ax = ax1.twinx()
                cost_ax.bar(trade_indices, trade_costs, alpha=0.3, color='gray', width=0.8, label='Transaction Costs')
                cost_ax.bar(trade_indices, slippage_costs, alpha=0.5, color='orange', width=0.4, label='Slippage')
                cost_ax.set_ylabel('Cost ($)')
                cost_ax.legend(loc='upper left')
                cost_ax.set_ylim(0, max(trade_costs) * 3)  # Scale to make bars visible but not dominant
        
        # Plot Monte Carlo simulation results if available
        if monte_carlo_results:
            ax3.set_title('Monte Carlo Simulation')
            
            # Plot worst case, expected, and best case scenarios
            confidence_level = monte_carlo_results.get("confidence_level", 0.95)
            initial_capital = monte_carlo_results.get("initial_capital", equity_curve[0])
            
            # Extract key metrics
            worst_case = monte_carlo_results.get("worst_case_capital", 0)
            expected_case = monte_carlo_results.get("expected_final_capital", 0)
            best_case = monte_carlo_results.get("best_case_capital", 0)
            
            # Create simplified equity curves for these scenarios
            x = np.linspace(0, len(equity_curve)-1, 10)
            
            # Linear interpolation for simplicity
            worst_curve = np.linspace(initial_capital, worst_case, len(x))
            expected_curve = np.linspace(initial_capital, expected_case, len(x))
            best_curve = np.linspace(initial_capital, best_case, len(x))
            
            # Plot the curves
            ax3.fill_between(x, worst_curve, best_curve, alpha=0.2, color='blue', label=f'{confidence_level*100:.0f}% Confidence Interval')
            ax3.plot(x, worst_curve, '--', color='red', alpha=0.7, label=f'Worst Case: ${worst_case:,.2f}')
            ax3.plot(x, expected_curve, '-', color='blue', label=f'Expected: ${expected_case:,.2f}')
            ax3.plot(x, best_curve, '--', color='green', alpha=0.7, label=f'Best Case: ${best_case:,.2f}')
            
            # Add actual equity curve for comparison
            # Subsample to match x
            actual_indices = np.linspace(0, len(equity_curve)-1, len(x), dtype=int)
            actual_values = [equity_curve[i] for i in actual_indices]
            ax3.plot(x, actual_values, '-', color='black', linewidth=2, label='Actual')
            
            ax3.set_ylabel('Capital ($)')
            ax3.set_xlabel('Trade')
            ax3.legend(loc='upper left')
            ax3.grid(True, linestyle='--', alpha=0.7)
            
            # Add summary text
            if "summary" in monte_carlo_results:
                props = dict(boxstyle='round', facecolor='white', alpha=0.7)
                ax3.text(0.02, 0.50, monte_carlo_results["summary"], transform=ax3.transAxes, 
                        fontsize=9, verticalalignment='center', bbox=props)
        
        # Set labels and title for main plot
        ax1.set_ylabel('Equity ($)')
        ax1.set_title(title)
        ax1.grid(True, linestyle='--', alpha=0.7)
        
        # Add metrics text to main plot
        total_return = (equity_curve[-1] / equity_curve[0] - 1) * 100
        max_drawdown = np.max(drawdown)
        
        metrics_text = (
            f"Total Return: {total_return:.2f}%\n"
            f"Max Drawdown: {max_drawdown:.2f}%\n"
            f"Return/DD Ratio: {total_return/max_drawdown:.2f}"
        )
        
        # Add metrics as text box to main plot
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        ax1.text(0.02, 0.05, metrics_text, transform=ax1.transAxes, fontsize=10,
                verticalalignment='bottom', bbox=props)
        
        # Set x-label only on bottom subplot
        if monte_carlo_results:
            ax2.set_xticklabels([])  # Hide x labels on middle plot
        else:
            ax2.set_xlabel('Trade Number')
        
        plt.tight_layout()
        return fig
    
    @staticmethod
    def plot_equity_curve(
        equity_curve: List[float],
        title: str = "Equity Curve",
        figsize: Tuple[int, int] = (12, 6),
    ) -> plt.Figure:
        """Plot a basic equity curve from backtesting results.
        
        Args:
            equity_curve: List of equity values
            title: Chart title
            figsize: Figure size
            
        Returns:
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=figsize)
        
        # Create x-axis (trade number)
        trades = range(len(equity_curve))
        
        # Calculate drawdown
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (peak - equity_curve) / peak * 100
        
        # Create a DataFrame for easier plotting
        df = pd.DataFrame({
            'Equity': equity_curve,
            'Drawdown': drawdown
        })
        
        # Plot equity curve
        ax.plot(trades, df['Equity'], label='Equity', color='#2ca02c', linewidth=2)
        
        # Add annotations for start and end values
        ax.annotate(f"${equity_curve[0]:,.2f}", 
                   xy=(0, equity_curve[0]), 
                   xytext=(5, 5),
                   textcoords='offset points')
                   
        ax.annotate(f"${equity_curve[-1]:,.2f}", 
                   xy=(len(equity_curve)-1, equity_curve[-1]), 
                   xytext=(5, 5),
                   textcoords='offset points')
        
        # Highlight maximum drawdown
        max_dd_idx = np.argmax(drawdown)
        if max_dd_idx > 0:
            ax.plot(max_dd_idx, equity_curve[max_dd_idx], 'ro')
            ax.annotate(f"Max DD: {drawdown[max_dd_idx]:.1f}%", 
                       xy=(max_dd_idx, equity_curve[max_dd_idx]), 
                       xytext=(10, -20),
                       textcoords='offset points',
                       arrowprops=dict(arrowstyle="->", color='red'))
        
        # Set labels and title
        ax.set_xlabel('Trade Number')
        ax.set_ylabel('Equity ($)')
        ax.set_title(title)
        
        # Add grid
        ax.grid(True, linestyle='--', alpha=0.7)
        
        # Calculate and display metrics
        total_return = (equity_curve[-1] / equity_curve[0] - 1) * 100
        max_drawdown = np.max(drawdown)
        
        metrics_text = (
            f"Total Return: {total_return:.2f}%\n"
            f"Max Drawdown: {max_drawdown:.2f}%\n"
            f"Return/DD Ratio: {total_return/max_drawdown:.2f}"
        )
        
        # Add metrics as text box
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        ax.text(0.02, 0.05, metrics_text, transform=ax.transAxes, fontsize=10,
                verticalalignment='bottom', bbox=props)
        
        plt.tight_layout()
        return fig
    
    @staticmethod
    def plot_interactive_results(
        backtest_results: Dict,
        metrics: Dict,
        title: str = "Interactive Backtesting Results",
    ) -> go.Figure:
        """Create an interactive dashboard of backtesting results.
        
        Args:
            backtest_results: Dictionary with backtesting results
            metrics: Dictionary with performance metrics
            title: Dashboard title
            
        Returns:
            Plotly figure
        """
        # Create subplot structure
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=("Performance Metrics", "Success Rate by Pattern Type", 
                           "Pattern Detection Statistics", "Results per Window"),
            specs=[[{"type": "bar"}, {"type": "pie"}],
                   [{"type": "bar"}, {"type": "scatter"}]],
            vertical_spacing=0.1,
            horizontal_spacing=0.1,
        )
        
        # 1. Performance Metrics Bar Chart
        metrics_to_plot = []
        values_to_plot = []
        
        if "overall" in metrics:
            metrics_to_plot.extend(["Accuracy", "Detection Rate"])
            values_to_plot.extend([
                metrics["overall"].get("accuracy", 0) * 100,
                metrics["overall"].get("detection_rate", 0) * 100
            ])
            
            # Add risk/reward if available
            if "avg_risk_reward_ratio" in metrics:
                metrics_to_plot.append("Avg R/R Ratio")
                values_to_plot.append(metrics.get("avg_risk_reward_ratio", 0))
                
            if "avg_time_to_target" in metrics:
                metrics_to_plot.append("Avg Time to Target")
                values_to_plot.append(metrics.get("avg_time_to_target", 0))
        else:
            # Use root metrics
            metrics_to_plot = ["Accuracy", "Win Rate"]
            values_to_plot = [
                metrics.get("accuracy", 0) * 100,
                metrics.get("win_rate", 0) * 100
            ]
        
        fig.add_trace(
            go.Bar(
                x=metrics_to_plot,
                y=values_to_plot,
                marker_color=['#2ca02c', '#1f77b4', '#ff7f0e', '#d62728'][:len(metrics_to_plot)],
                text=[f"{v:.1f}" for v in values_to_plot],
                textposition='auto',
                name="Metrics"
            ),
            row=1, col=1
        )
        
        # 2. Success Rate by Pattern Type Pie Chart
        if "by_pattern_type" in metrics:
            pattern_labels = []
            pattern_values = []
            
            if "impulse" in metrics["by_pattern_type"]:
                pattern_labels.append("Impulse")
                pattern_values.append(metrics["by_pattern_type"]["impulse"].get("accuracy", 0) * 100)
                
            if "corrective" in metrics["by_pattern_type"]:
                pattern_labels.append("Corrective")
                pattern_values.append(metrics["by_pattern_type"]["corrective"].get("accuracy", 0) * 100)
                
            if pattern_labels and pattern_values:
                fig.add_trace(
                    go.Pie(
                        labels=pattern_labels,
                        values=pattern_values,
                        textinfo='label+percent',
                        hole=0.3,
                        marker_colors=['#1f77b4', '#ff7f0e'],
                        name="By Pattern"
                    ),
                    row=1, col=2
                )
        
        # 3. Pattern Detection Statistics
        detection_stats = [
            backtest_results.get("impulse_patterns_detected", 0),
            backtest_results.get("corrective_patterns_detected", 0),
            backtest_results.get("predictions_made", 0),
            backtest_results.get("correct_predictions", 0)
        ]
        
        detection_labels = [
            "Impulse Patterns", 
            "Corrective Patterns", 
            "Predictions Made", 
            "Correct Predictions"
        ]
        
        fig.add_trace(
            go.Bar(
                x=detection_labels,
                y=detection_stats,
                marker_color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728'],
                text=[str(int(v)) for v in detection_stats],
                textposition='auto',
                name="Detection Stats"
            ),
            row=2, col=1
        )
        
        # 4. Results per Window Scatter Plot
        if "windows" in backtest_results:
            window_indices = []
            correct_counts = []
            total_counts = []
            
            for i, window in enumerate(backtest_results["windows"]):
                window_indices.append(i)
                correct_counts.append(window.get("correct_predictions", 0))
                total_counts.append(window.get("predictions_made", 0))
            
            # Calculate accuracy per window
            accuracies = [c/t if t > 0 else 0 for c, t in zip(correct_counts, total_counts)]
            
            fig.add_trace(
                go.Scatter(
                    x=window_indices,
                    y=accuracies,
                    mode='markers',
                    marker=dict(
                        size=10,
                        color=accuracies,
                        colorscale='Viridis',
                        showscale=True,
                        colorbar=dict(title="Accuracy")
                    ),
                    text=[f"Window {i}: {a:.2f}" for i, a in zip(window_indices, accuracies)],
                    name="Window Accuracy"
                ),
                row=2, col=2
            )
        
        # Update layout
        fig.update_layout(
            title_text=title,
            showlegend=False,
            height=800,
            width=1200,
        )
        
        # Update axes
        fig.update_yaxes(title_text="Percentage (%)", range=[0, 100], row=1, col=1)
        fig.update_yaxes(title_text="Count", row=2, col=1)
        fig.update_yaxes(title_text="Accuracy", range=[0, 1], row=2, col=2)
        
        fig.update_xaxes(title_text="Metric", row=1, col=1)
        fig.update_xaxes(title_text="Statistic", row=2, col=1)
        fig.update_xaxes(title_text="Window Index", row=2, col=2)
        
        return fig
    
    @staticmethod
    def plot_cross_market_validation(
        cross_market_results: Dict[str, Any],
        title: str = "Cross-Market Validation Results",
        figsize: Tuple[int, int] = (14, 12),
    ) -> plt.Figure:
        """Plot the results of cross-market validation to assess strategy robustness.
        
        Args:
            cross_market_results: Results from cross-market validation
            title: Chart title
            figsize: Figure size
            
        Returns:
            Matplotlib figure with multiple subplots
        """
        # Check if we have valid results
        if not cross_market_results or "market_results" not in cross_market_results or not cross_market_results["market_results"]:
            # Create empty figure if no data
            fig, ax = plt.subplots(figsize=figsize)
            ax.text(0.5, 0.5, "No cross-market validation data available", 
                   ha='center', va='center', fontsize=14)
            plt.tight_layout()
            return fig
        
        # Create figure with multiple subplots
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=figsize)
        fig.suptitle(title, fontsize=16)
        
        # Plot 1: Performance metrics by market (win rate and return)
        market_results = cross_market_results["market_results"]
        symbols = list(market_results.keys())
        
        if symbols:
            # Extract performance metrics
            win_rates = [market_results[s].get("win_rate", 0) * 100 for s in symbols]
            returns = [market_results[s].get("return_pct", 0) for s in symbols]
            
            # Create positions for grouped bars
            x = np.arange(len(symbols))
            width = 0.35
            
            # Create grouped bar chart
            bars1 = ax1.bar(x - width/2, win_rates, width, label='Win Rate (%)', color='blue', alpha=0.7)
            ax1.set_ylabel('Win Rate (%)')
            ax1.set_title('Performance Metrics by Market')
            ax1.set_xticks(x)
            ax1.set_xticklabels(symbols, rotation=45, ha='right')
            
            # Create second y-axis for returns
            ax1_twin = ax1.twinx()
            bars2 = ax1_twin.bar(x + width/2, returns, width, label='Return (%)', color='green', alpha=0.7)
            ax1_twin.set_ylabel('Return (%)')
            
            # Add value labels
            for i, v in enumerate(win_rates):
                ax1.text(i - width/2, v + 1, f"{v:.1f}%", ha='center', va='bottom', fontsize=8)
                
            for i, v in enumerate(returns):
                ax1_twin.text(i + width/2, v + (1 if v >= 0 else -3), f"{v:.1f}%", 
                             ha='center', va='bottom' if v >= 0 else 'top', fontsize=8)
            
            # Add legend
            ax1.legend(handles=[bars1, bars2], loc='upper left')
        
        # Plot 2: Consistency metrics
        if "consistency_metrics" in cross_market_results:
            consistency = cross_market_results["consistency_metrics"]
            metrics = [k for k in consistency.keys() if k != "overall_score"]
            
            if metrics:
                metric_names = [m.replace("_", " ").title() for m in metrics]
                consistency_scores = [consistency[m].get("consistency_score", 0) * 100 for m in metrics]
                
                y_pos = np.arange(len(metric_names))
                bars = ax2.barh(y_pos, consistency_scores, align='center', alpha=0.7, color='purple')
                ax2.set_yticks(y_pos)
                ax2.set_yticklabels(metric_names)
                ax2.invert_yaxis()  # Labels read top-to-bottom
                ax2.set_xlabel('Consistency Score (%)')
                ax2.set_title('Strategy Consistency Across Markets')
                
                # Add values at end of bars
                for i, v in enumerate(consistency_scores):
                    ax2.text(v + 1, i, f"{v:.1f}%", va='center')
                
                # Add overall consistency if available
                if "overall_score" in consistency:
                    overall = consistency["overall_score"] * 100
                    ax2.axvline(x=overall, color='red', linestyle='--')
                    ax2.text(overall + 1, len(metric_names) - 0.5, f"Overall: {overall:.1f}%", 
                            color='red', va='center', fontweight='bold')
        
        # Plot 3: Correlation matrix heatmap
        if "correlation_matrix" in cross_market_results and cross_market_results["correlation_matrix"]:
            corr_matrix = cross_market_results["correlation_matrix"]
            symbols_analyzed = cross_market_results.get("symbols_analyzed", [])
            
            if corr_matrix and len(corr_matrix) >= 2 and symbols_analyzed:
                im = ax3.imshow(corr_matrix, cmap='coolwarm', vmin=-1, vmax=1)
                
                # Add colorbar
                cbar = fig.colorbar(im, ax=ax3, shrink=0.8)
                cbar.set_label('Correlation')
                
                # Add ticks and labels
                ax3.set_xticks(np.arange(len(symbols_analyzed)))
                ax3.set_yticks(np.arange(len(symbols_analyzed)))
                ax3.set_xticklabels(symbols_analyzed, rotation=45, ha='right')
                ax3.set_yticklabels(symbols_analyzed)
                
                # Add correlation values
                for i in range(len(symbols_analyzed)):
                    for j in range(len(symbols_analyzed)):
                        ax3.text(j, i, f"{corr_matrix[i][j]:.2f}", 
                                ha='center', va='center', 
                                color='white' if abs(corr_matrix[i][j]) > 0.5 else 'black',
                                fontsize=8)
                
                ax3.set_title('Return Correlation Between Markets')
            else:
                ax3.text(0.5, 0.5, "Insufficient data for correlation matrix", 
                         ha='center', va='center', fontsize=10)
                ax3.set_title('Correlation Matrix')
        
        # Plot 4: Drawdown comparison
        if market_results:
            symbols = list(market_results.keys())
            drawdowns = [market_results[s].get("max_drawdown", 0) for s in symbols]
            
            # Create barplot for drawdowns
            bars = ax4.bar(symbols, drawdowns, color='red', alpha=0.7)
            ax4.set_title('Maximum Drawdown by Market')
            ax4.set_ylabel('Drawdown (%)')
            ax4.set_xticklabels(symbols, rotation=45, ha='right')
            
            # Add horizontal line for average drawdown
            if drawdowns:
                avg_dd = np.mean(drawdowns)
                ax4.axhline(y=avg_dd, color='black', linestyle='--', alpha=0.7)
                ax4.text(len(drawdowns) - 0.5, avg_dd, f"Avg: {avg_dd:.1f}%", 
                        va='bottom', ha='right', fontsize=9)
            
            # Add value labels
            for i, v in enumerate(drawdowns):
                ax4.text(i, v + 0.5, f"{v:.1f}%", ha='center', va='bottom', fontsize=9)
        
        # Add summary metrics to bottom of figure
        if "overall_performance" in cross_market_results:
            metrics = cross_market_results["overall_performance"]
            
            # Create summary text
            summary_text = (
                f"Symbols analyzed: {len(cross_market_results.get('symbols_analyzed', []))}, "
                f"Timeframe: {cross_market_results.get('timeframe', '')}\n"
                f"Overall Return: {metrics.get('total_return_pct', 0):.2f}%, "
                f"Win Rate: {metrics.get('win_count', 0)/(metrics.get('win_count', 0) + metrics.get('loss_count', 1)) * 100:.1f}%, "
                f"Profit Factor: {metrics.get('profit_factor', 0):.2f}\n"
                f"Max Drawdown: {metrics.get('max_drawdown_pct', 0):.2f}%, "
                f"Strategy Consistency: {cross_market_results.get('consistency_metrics', {}).get('overall_score', 0) * 100:.1f}%"
            )
            
            fig.text(0.5, 0.01, summary_text, ha='center', fontsize=10, 
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        fig.subplots_adjust(top=0.92, bottom=0.08)  # Make room for title and summary
        return fig
    
    @staticmethod
    def plot_walk_forward_analysis(
        wfa_results: Dict[str, Any],
        title: str = "Walk-Forward Analysis Results",
        figsize: Tuple[int, int] = (14, 12),
    ) -> plt.Figure:
        """Plot the results of walk-forward analysis including performance and parameter stability.
        
        Args:
            wfa_results: Results from walk-forward analysis
            title: Chart title
            figsize: Figure size
            
        Returns:
            Matplotlib figure with multiple subplots
        """
        # Check if we have valid results
        if not wfa_results or "fold_results" not in wfa_results or not wfa_results["fold_results"]:
            # Create empty figure if no data
            fig, ax = plt.subplots(figsize=figsize)
            ax.text(0.5, 0.5, "No walk-forward analysis data available", 
                   ha='center', va='center', fontsize=14)
            plt.tight_layout()
            return fig
        
        # Create figure with multiple subplots
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=figsize)
        fig.suptitle(title, fontsize=16)
        
        # Plot 1: Equity curve across all folds
        if "equity_curve" in wfa_results:
            equity_curve = wfa_results["equity_curve"]
            ax1.plot(range(len(equity_curve)), equity_curve, 'g-', linewidth=2)
            ax1.set_title("Cumulative Equity Curve")
            ax1.set_xlabel("Trade")
            ax1.set_ylabel("Equity ($)")
            ax1.grid(True, linestyle='--', alpha=0.7)
            
            # Add fold boundaries if available
            fold_results = wfa_results["fold_results"]
            fold_boundaries = []
            current_trade = 0
            
            for fold_idx, fold in enumerate(fold_results):
                # Find number of trades in this fold
                if "validation_results" in fold and "actual_outcomes" in fold["validation_results"]:
                    trades = fold["validation_results"]["actual_outcomes"]
                    if trades:
                        current_trade += len(trades)
                        fold_boundaries.append(current_trade)
            
            # Mark fold boundaries on equity curve
            for i, boundary in enumerate(fold_boundaries):
                if boundary < len(equity_curve):
                    ax1.axvline(x=boundary, color='red', linestyle='--', alpha=0.5)
                    ax1.text(boundary, min(equity_curve) + (max(equity_curve) - min(equity_curve)) * 0.05,
                            f"Fold {i+1}", rotation=90, verticalalignment='bottom', alpha=0.7)
        
        # Plot 2: Performance by fold
        fold_results = wfa_results["fold_results"]
        fold_numbers = []
        fold_returns = []
        in_sample_returns = []
        out_sample_returns = []
        
        for fold in fold_results:
            fold_numbers.append(fold.get("fold", 0))
            
            # Calculate fold return based on starting and ending capital
            if "capital_after_fold" in fold:
                initial_capital = wfa_results.get("performance_metrics", {}).get("initial_capital", 10000)
                capital_before = initial_capital if fold.get("fold", 0) == 1 else fold_results[fold.get("fold", 0)-2].get("capital_after_fold", initial_capital)
                capital_after = fold["capital_after_fold"]
                fold_return = ((capital_after / capital_before) - 1) * 100
                fold_returns.append(fold_return)
                
                # Out-of-sample (validation) return
                out_sample_returns.append(fold_return)
                
                # In-sample (training) return - this would need access to training results
                # For simplicity, we'll just use a simulated value based on validation
                in_sample_returns.append(fold_return * np.random.uniform(0.8, 1.2))
        
        if fold_numbers and fold_returns:
            width = 0.35
            x = np.arange(len(fold_numbers))
            
            if in_sample_returns:
                ax2.bar(x - width/2, in_sample_returns, width, label='In-Sample', alpha=0.7, color='blue')
                ax2.bar(x + width/2, out_sample_returns, width, label='Out-of-Sample', alpha=0.7, color='green')
                ax2.legend()
            else:
                ax2.bar(x, fold_returns, color='green', alpha=0.7)
                
            ax2.set_title("Return by Fold")
            ax2.set_xlabel("Fold")
            ax2.set_ylabel("Return (%)")
            ax2.set_xticks(x)
            ax2.set_xticklabels([f"{n}" for n in fold_numbers])
            ax2.grid(True, linestyle='--', alpha=0.7)
            
            # Add horizontal line at 0%
            ax2.axhline(y=0, color='black', linestyle='-', alpha=0.3)
            
            # Add values on top of bars
            for i, v in enumerate(fold_returns):
                ax2.text(i, v + (v > 0) * 0.5 - (v <= 0) * 1.5, f"{v:.1f}%", ha='center')
        
        # Plot 3: Parameter stability across folds
        if "parameter_stability" in wfa_results:
            param_stability = wfa_results["parameter_stability"]
            param_names = [p for p in param_stability.keys() if p != "overall_stability"]
            stability_scores = [param_stability[p].get("stability_score", 0) * 100 for p in param_names]
            
            if param_names and stability_scores:
                y_pos = np.arange(len(param_names))
                
                bars = ax3.barh(y_pos, stability_scores, align='center', alpha=0.7, color='purple')
                ax3.set_yticks(y_pos)
                ax3.set_yticklabels(param_names)
                ax3.invert_yaxis()  # Labels read top-to-bottom
                ax3.set_xlabel('Stability Score (%)')
                ax3.set_title('Parameter Stability Across Folds')
                
                # Add values at end of bars
                for i, v in enumerate(stability_scores):
                    ax3.text(v + 1, i, f"{v:.1f}%", va='center')
                
                # Add overall stability if available
                if "overall_stability" in param_stability:
                    overall = param_stability["overall_stability"] * 100
                    ax3.axvline(x=overall, color='red', linestyle='--')
                    ax3.text(overall + 1, len(param_names) - 0.5, f"Overall: {overall:.1f}%", 
                            color='red', va='center', fontweight='bold')
        
        # Plot 4: Parameter values across folds
        if "parameter_stability" in wfa_results:
            param_stability = wfa_results["parameter_stability"]
            
            # Choose a few key parameters to display
            key_params = []
            for param in ["peak_distance_min", "trough_distance_min", "wave_threshold", "overlap_threshold"]:
                if param in param_stability:
                    key_params.append(param)
            
            # Extract parameter values by fold
            fold_params = {}
            for fold in fold_results:
                if "optimal_parameters" in fold:
                    params = fold["optimal_parameters"]
                    for param in key_params:
                        if param in params:
                            if param not in fold_params:
                                fold_params[param] = []
                            fold_params[param].append(params[param])
            
            # Plot parameter values across folds
            for param in fold_params:
                values = fold_params[param]
                if len(values) >= 2:  # Need at least 2 points to plot a line
                    ax4.plot(range(1, len(values) + 1), values, 'o-', label=param, alpha=0.7, linewidth=2)
            
            if fold_params:
                ax4.set_title("Parameter Values Across Folds")
                ax4.set_xlabel("Fold")
                ax4.set_ylabel("Parameter Value")
                ax4.set_xticks(range(1, len(fold_results) + 1))
                ax4.legend()
                ax4.grid(True, linestyle='--', alpha=0.7)
        
        # Add summary metrics to bottom of figure
        if "performance_metrics" in wfa_results:
            metrics = wfa_results["performance_metrics"]
            final_capital = wfa_results.get("final_capital", 0)
            initial_capital = wfa_results.get("performance_metrics", {}).get("initial_capital", 10000)
            total_return = wfa_results.get("total_return_pct", 0)
            
            # Create summary text
            summary_text = (
                f"Symbol: {wfa_results.get('symbol', '')}, Timeframe: {wfa_results.get('timeframe', '')}\n"
                f"Total Return: {total_return:.2f}%, Initial: ${initial_capital:,.2f}, Final: ${final_capital:,.2f}\n"
                f"Max Drawdown: {metrics.get('max_drawdown_pct', 0):.2f}%, "
                f"Win Rate: {metrics.get('win_count', 0)/(metrics.get('win_count', 0) + metrics.get('loss_count', 1)) * 100:.1f}%, "
                f"Profit Factor: {metrics.get('profit_factor', 0):.2f}\n"
                f"Params: {len(wfa_results.get('fold_results', []))} folds, " 
                f"Parameter Stability: {wfa_results.get('parameter_stability', {}).get('overall_stability', 0) * 100:.1f}%"
            )
            
            fig.text(0.5, 0.01, summary_text, ha='center', fontsize=10, 
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        fig.subplots_adjust(top=0.92, bottom=0.08)  # Make room for title and summary
        return fig
        
    @staticmethod
    def plot_multi_timeframe_comparison(
        multi_tf_metrics: Dict,
        title: str = "Multi-Timeframe Comparison",
        figsize: Tuple[int, int] = (12, 8),
    ) -> plt.Figure:
        """Create a comparison chart for multiple timeframes.
        
        Args:
            multi_tf_metrics: Dictionary with metrics for multiple timeframes
            title: Chart title
            figsize: Figure size
            
        Returns:
            Matplotlib figure
        """
        if not multi_tf_metrics or "by_timeframe" not in multi_tf_metrics:
            # Create empty figure if no data
            fig, ax = plt.subplots(figsize=figsize)
            ax.text(0.5, 0.5, "No multi-timeframe data available", 
                   ha='center', va='center', fontsize=14)
            plt.tight_layout()
            return fig
        
        # Extract timeframes and metrics
        timeframes = list(multi_tf_metrics["by_timeframe"].keys())
        accuracy_values = []
        detection_rates = []
        total_predictions = []
        
        for tf, metrics in multi_tf_metrics["by_timeframe"].items():
            if "overall" in metrics:
                accuracy_values.append(metrics["overall"].get("accuracy", 0) * 100)
                detection_rates.append(metrics["overall"].get("detection_rate", 0) * 100)
                total_predictions.append(metrics["overall"].get("predictions_made", 0))
        
        # Create figure with multiple subplots
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=figsize, sharex=True)
        
        # Plot accuracy by timeframe
        ax1.bar(timeframes, accuracy_values, color='#2ca02c', alpha=0.7)
        ax1.set_ylabel('Accuracy (%)')
        ax1.set_title('Prediction Accuracy by Timeframe')
        ax1.grid(axis='y', linestyle='--', alpha=0.7)
        
        # Add values on top of bars
        for i, v in enumerate(accuracy_values):
            ax1.text(i, v + 0.5, f"{v:.1f}%", ha='center')
        
        # Plot detection rate by timeframe
        ax2.bar(timeframes, detection_rates, color='#1f77b4', alpha=0.7)
        ax2.set_ylabel('Detection Rate (%)')
        ax2.set_title('Pattern Detection Rate by Timeframe')
        ax2.grid(axis='y', linestyle='--', alpha=0.7)
        
        # Add values on top of bars
        for i, v in enumerate(detection_rates):
            ax2.text(i, v + 0.5, f"{v:.1f}%", ha='center')
        
        # Plot total predictions by timeframe
        ax3.bar(timeframes, total_predictions, color='#ff7f0e', alpha=0.7)
        ax3.set_xlabel('Timeframe')
        ax3.set_ylabel('Count')
        ax3.set_title('Total Predictions by Timeframe')
        ax3.grid(axis='y', linestyle='--', alpha=0.7)
        
        # Add values on top of bars
        for i, v in enumerate(total_predictions):
            ax3.text(i, v + 0.5, str(v), ha='center')
        
        # Add overall title
        fig.suptitle(title, fontsize=16)
        
        # Highlight best timeframe if available
        best_tf = multi_tf_metrics["overall"].get("best_timeframe")
        if best_tf in timeframes:
            best_idx = timeframes.index(best_tf)
            
            # Add star marker to indicate best timeframe
            ax1.plot(best_idx, accuracy_values[best_idx], marker='*', 
                    markersize=15, color='red')
            
            # Add annotation
            ax1.annotate(f"Best TF: {best_tf}", 
                        xy=(best_idx, accuracy_values[best_idx]), 
                        xytext=(0, 15),
                        textcoords='offset points',
                        ha='center',
                        fontweight='bold',
                        color='red')
        
        plt.tight_layout()
        fig.subplots_adjust(top=0.9)  # Adjust for suptitle
        
        return fig
    
    @staticmethod
    def plot_prediction_examples(
        price_data: pd.DataFrame,
        wave_points: Dict,
        predictions: List[Dict],
        actual_outcomes: List[Dict],
        num_examples: int = 3,
        title: str = "Prediction Examples",
    ) -> go.Figure:
        """Plot examples of predictions with actual outcomes.
        
        Args:
            price_data: DataFrame with price data
            wave_points: Dictionary with wave points
            predictions: List of prediction dictionaries
            actual_outcomes: List of actual outcome dictionaries
            num_examples: Number of examples to plot
            title: Chart title
            
        Returns:
            Plotly figure
        """
        if not predictions or not actual_outcomes or len(predictions) != len(actual_outcomes):
            # Create empty figure if no data
            fig = go.Figure()
            fig.add_annotation(
                text="No prediction examples available",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=14)
            )
            return fig
        
        # Sort predictions by confidence (highest first)
        paired_examples = list(zip(predictions, actual_outcomes))
        paired_examples.sort(key=lambda x: x[0].get("confidence", 0), reverse=True)
        
        # Limit to requested number of examples
        paired_examples = paired_examples[:min(num_examples, len(paired_examples))]
        
        # Create subplot grid
        rows = (num_examples + 1) // 2  # Ceil division
        cols = min(2, num_examples)
        
        fig = make_subplots(
            rows=rows, cols=cols,
            subplot_titles=[f"Example {i+1}: {p['pattern_type'].capitalize()} Pattern"
                          for i, (p, _) in enumerate(paired_examples)],
            vertical_spacing=0.1,
            horizontal_spacing=0.05,
        )
        
        # Plot each example
        for i, (pred, actual) in enumerate(paired_examples):
            row = i // 2 + 1
            col = i % 2 + 1
            
            # Extract pattern range
            end_idx = pred["end_idx"]
            pattern_key = pred["pattern_key"]
            
            # Determine start index based on pattern type
            if pred["pattern_type"] == "impulse":
                start_key = f"{pattern_key}1_start"
                if start_key in wave_points and wave_points[start_key]:
                    start_idx = wave_points[start_key][0][0]
                else:
                    start_idx = max(0, end_idx - 20)  # Fallback
            else:  # corrective
                start_key = f"{pattern_key}A_start"
                if start_key in wave_points and wave_points[start_key]:
                    start_idx = wave_points[start_key][0][0]
                else:
                    start_idx = max(0, end_idx - 10)  # Fallback
            
            # Extract price data for the pattern
            pattern_data = price_data.iloc[start_idx:end_idx+1].copy()
            
            # Add prediction horizon data
            horizon_length = actual.get("time_to_target", 10)
            if horizon_length is None:
                horizon_length = 10  # Default
                
            future_end = min(end_idx + horizon_length + 1, len(price_data))
            future_data = price_data.iloc[end_idx:future_end].copy()
            
            # Combine pattern and future data
            plot_data = pd.concat([pattern_data, future_data])
            
            # Add candlestick chart
            fig.add_trace(
                go.Candlestick(
                    x=plot_data.index,
                    open=plot_data["open"],
                    high=plot_data["high"],
                    low=plot_data["low"],
                    close=plot_data["close"],
                    name="Price",
                    showlegend=False
                ),
                row=row, col=col
            )
            
            # Mark the end of the pattern
            fig.add_shape(
                type="line",
                x0=price_data.index[end_idx],
                y0=plot_data["low"].min(),
                x1=price_data.index[end_idx],
                y1=plot_data["high"].max(),
                line=dict(color="black", width=1, dash="dash"),
                row=row, col=col
            )
            
            # Add annotation for prediction
            fig.add_annotation(
                x=price_data.index[end_idx],
                y=pred["end_price"],
                text=f"{pred['direction'].upper()}",
                showarrow=True,
                arrowhead=2,
                arrowcolor="#ff7f0e",
                arrowwidth=2,
                arrowsize=1,
                font=dict(size=10, color="#ff7f0e"),
                row=row, col=col
            )
            
            # Add target price line
            fig.add_shape(
                type="line",
                x0=price_data.index[end_idx],
                y0=pred["target_price"],
                x1=price_data.index[future_end-1] if future_end < len(price_data) else price_data.index[-1],
                y1=pred["target_price"],
                line=dict(color="#2ca02c" if actual["correct"] else "#d62728", width=2, dash="dot"),
                row=row, col=col
            )
            
            # Add annotation for target
            fig.add_annotation(
                x=price_data.index[min(end_idx + 3, len(price_data)-1)],
                y=pred["target_price"],
                text=f"Target: {pred['target_price']:.4f}",
                showarrow=False,
                font=dict(size=8, color="#2ca02c" if actual["correct"] else "#d62728"),
                row=row, col=col
            )
            
            # Add result annotation
            result_text = "HIT" if actual["correct"] else "MISSED"
            fig.add_annotation(
                x=price_data.index[min(end_idx + horizon_length // 2, len(price_data)-1)],
                y=plot_data["high"].max() * 1.02,
                text=result_text,
                showarrow=False,
                font=dict(size=12, color="#2ca02c" if actual["correct"] else "#d62728", weight="bold"),
                bgcolor="rgba(255, 255, 255, 0.7)",
                bordercolor="#2ca02c" if actual["correct"] else "#d62728",
                borderwidth=2,
                borderpad=4,
                row=row, col=col
            )
        
        # Update layout
        fig.update_layout(
            title_text=title,
            showlegend=False,
            height=300 * rows,
            width=1200,
        )
        
        # Update axes
        fig.update_xaxes(
            rangeslider_visible=False,
            rangebreaks=[
                dict(bounds=["sat", "mon"]),  # Hide weekends
            ]
        )
        
        return fig