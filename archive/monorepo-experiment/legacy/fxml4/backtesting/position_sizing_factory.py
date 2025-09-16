"""Factory module for creating and managing position sizing algorithms.

This module provides a factory pattern for creating position sizing algorithms
and integrating them with the risk management system.
"""

import logging
from typing import Any, Dict, Optional, Union

from fxml4.backtesting.risk_management import (
    FixedPositionSizer,
    KellyPositionSizer,
    OptimalFPositionSizer,
    PercentagePositionSizer,
    PositionSizer,
    VolatilityPositionSizer,
)
from fxml4.backtesting.enhanced_position_sizing import (
    ConfidenceWeightedPositionSizer,
    DynamicPositionSizer,
    EnhancedKellyPositionSizer,
    PerformanceTracker,
    RiskParityPositionSizer,
    VolatilityRegimeDetector,
)

logger = logging.getLogger(__name__)


class PositionSizingFactory:
    """Factory for creating position sizing algorithms."""
    
    def __init__(self):
        """Initialize the position sizing factory."""
        self.performance_tracker = PerformanceTracker()
        self.volatility_detector = VolatilityRegimeDetector()
        self._sizers = {}
        self._register_default_sizers()
    
    def _register_default_sizers(self) -> None:
        """Register default position sizing algorithms."""
        # Original sizers
        self.register("fixed", FixedPositionSizer)
        self.register("percentage", PercentagePositionSizer)
        self.register("volatility", VolatilityPositionSizer)
        self.register("kelly", KellyPositionSizer)
        self.register("optimal_f", OptimalFPositionSizer)
        
        # Enhanced sizers
        self.register("enhanced_kelly", EnhancedKellyPositionSizer)
        self.register("confidence_weighted", ConfidenceWeightedPositionSizer)
        self.register("risk_parity", RiskParityPositionSizer)
    
    def register(self, name: str, sizer_class: type) -> None:
        """Register a position sizing algorithm.
        
        Args:
            name: Name of the algorithm.
            sizer_class: Position sizer class.
        """
        self._sizers[name] = sizer_class
        logger.info("Registered position sizer: %s", name)
    
    def create(
        self,
        algorithm: str,
        config: Optional[Dict[str, Any]] = None,
        enable_dynamic_adjustment: bool = True,
    ) -> PositionSizer:
        """Create a position sizing algorithm.
        
        Args:
            algorithm: Name of the algorithm.
            config: Configuration for the algorithm.
            enable_dynamic_adjustment: Whether to wrap with dynamic adjustment.
            
        Returns:
            Position sizer instance.
            
        Raises:
            ValueError: If algorithm is not registered.
        """
        if algorithm not in self._sizers:
            raise ValueError(f"Unknown position sizing algorithm: {algorithm}")
        
        config = config or {}
        
        # Create base sizer
        sizer_class = self._sizers[algorithm]
        
        if algorithm == "enhanced_kelly":
            base_sizer = sizer_class(
                kelly_fraction=config.get("kelly_fraction", 0.25),
                max_position_pct=config.get("max_position_pct", 0.1),
                confidence_weight=config.get("confidence_weight", 0.5),
                use_rolling_stats=config.get("use_rolling_stats", True),
                lookback_trades=config.get("lookback_trades", 50),
            )
        elif algorithm == "confidence_weighted":
            base_sizer = sizer_class(
                base_position_pct=config.get("base_position_pct", 0.02),
                min_confidence=config.get("min_confidence", 0.6),
                max_confidence=config.get("max_confidence", 0.9),
                confidence_power=config.get("confidence_power", 2.0),
            )
        elif algorithm == "risk_parity":
            base_sizer = sizer_class(
                target_risk=config.get("target_risk", 0.01),
                lookback_periods=config.get("lookback_periods", 60),
                use_correlation=config.get("use_correlation", True),
                max_position_pct=config.get("max_position_pct", 0.2),
            )
        elif algorithm == "fixed":
            base_sizer = sizer_class(
                fixed_amount=config.get("fixed_amount", 1000.0)
            )
        elif algorithm == "percentage":
            base_sizer = sizer_class(
                percentage=config.get("percentage", 0.02)
            )
        elif algorithm == "volatility":
            base_sizer = sizer_class(
                risk_per_trade=config.get("risk_per_trade", 0.01),
                atr_multiplier=config.get("atr_multiplier", 2.0),
                lookback_periods=config.get("lookback_periods", 14),
            )
        elif algorithm == "kelly":
            base_sizer = sizer_class(
                win_rate=config.get("win_rate", 0.55),
                win_loss_ratio=config.get("win_loss_ratio", 1.5),
                kelly_fraction=config.get("kelly_fraction", 0.25),
            )
        elif algorithm == "optimal_f":
            base_sizer = sizer_class(
                lookback_trades=config.get("lookback_trades", 50),
                max_f=config.get("max_f", 0.25),
            )
        else:
            # Generic creation
            base_sizer = sizer_class(**config)
        
        # Wrap with dynamic adjustment if enabled
        if enable_dynamic_adjustment and algorithm != "dynamic":
            sizer = DynamicPositionSizer(
                base_sizer=base_sizer,
                performance_tracker=self.performance_tracker,
                volatility_detector=self.volatility_detector,
                performance_weight=config.get("dynamic_performance_weight", 0.3),
                volatility_weight=config.get("dynamic_volatility_weight", 0.3),
                drawdown_weight=config.get("dynamic_drawdown_weight", 0.4),
                min_size_multiplier=config.get("min_size_multiplier", 0.5),
                max_size_multiplier=config.get("max_size_multiplier", 1.5),
            )
            logger.info("Created %s position sizer with dynamic adjustment", algorithm)
        else:
            sizer = base_sizer
            logger.info("Created %s position sizer", algorithm)
        
        return sizer
    
    def create_ensemble(
        self,
        algorithms: Dict[str, Dict[str, Any]],
        weights: Optional[Dict[str, float]] = None,
    ) -> "EnsemblePositionSizer":
        """Create an ensemble of position sizing algorithms.
        
        Args:
            algorithms: Dictionary of algorithm names to configs.
            weights: Dictionary of algorithm names to weights.
            
        Returns:
            Ensemble position sizer.
        """
        sizers = {}
        
        for name, config in algorithms.items():
            sizers[name] = self.create(name, config, enable_dynamic_adjustment=False)
        
        return EnsemblePositionSizer(sizers, weights)
    
    def update_performance(self, trade_result: Dict[str, Any]) -> None:
        """Update performance tracker with trade result.
        
        Args:
            trade_result: Trade result dictionary.
        """
        self.performance_tracker.add_trade(trade_result)
        
        # Update enhanced Kelly sizers if they exist
        for name, sizer_class in self._sizers.items():
            if name == "enhanced_kelly" and hasattr(sizer_class, "update_trade_result"):
                # This would need to be tracked per instance
                pass
    
    def update_volatility(self, symbol: str, returns: pd.Series) -> None:
        """Update volatility detector with returns data.
        
        Args:
            symbol: Trading symbol.
            returns: Series of returns.
        """
        self.volatility_detector.update_volatility(symbol, returns)
        
        # Update risk parity sizers if they exist
        for name, sizer_class in self._sizers.items():
            if name == "risk_parity" and hasattr(sizer_class, "update_returns"):
                # This would need to be tracked per instance
                pass


class EnsemblePositionSizer(PositionSizer):
    """Ensemble of multiple position sizing algorithms."""
    
    def __init__(
        self,
        sizers: Dict[str, PositionSizer],
        weights: Optional[Dict[str, float]] = None,
    ):
        """Initialize ensemble position sizer.
        
        Args:
            sizers: Dictionary of name to position sizer.
            weights: Dictionary of name to weight.
        """
        self.sizers = sizers
        
        if weights is None:
            # Equal weights
            num_sizers = len(sizers)
            self.weights = {name: 1.0 / num_sizers for name in sizers}
        else:
            # Normalize weights
            total_weight = sum(weights.values())
            self.weights = {
                name: w / total_weight 
                for name, w in weights.items()
            }
    
    def calculate_position_size(
        self,
        signal: SignalEvent,
        portfolio: Any,
        current_price: float,
    ) -> float:
        """Calculate ensemble position size.
        
        Args:
            signal: Signal event.
            portfolio: Portfolio instance.
            current_price: Current price.
            
        Returns:
            Position size (quantity).
        """
        position_sizes = {}
        weighted_size = 0.0
        
        # Get position size from each algorithm
        for name, sizer in self.sizers.items():
            size = sizer.calculate_position_size(signal, portfolio, current_price)
            position_sizes[name] = size
            
            # Add weighted contribution
            weight = self.weights.get(name, 0)
            weighted_size += size * weight
        
        # Store ensemble metadata
        signal.signal_data["position_sizing"] = {
            "method": "ensemble",
            "component_sizes": position_sizes,
            "weights": self.weights,
            "final_size": weighted_size,
        }
        
        return weighted_size


# Global factory instance
position_sizing_factory = PositionSizingFactory()