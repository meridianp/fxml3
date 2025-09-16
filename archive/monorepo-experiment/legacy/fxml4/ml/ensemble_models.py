"""Ensemble model implementations for forex trading.

This module provides various ensemble methods that combine predictions
from multiple models to improve accuracy and robustness.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.utils.validation import check_is_fitted

logger = logging.getLogger(__name__)


class VotingEnsemble(BaseEstimator, ClassifierMixin):
    """Voting ensemble that combines predictions from multiple models.
    
    Supports both hard voting (majority vote) and soft voting (probability averaging).
    """
    
    def __init__(
        self,
        models: List[Tuple[str, Any]],
        voting: str = 'soft',
        weights: Optional[List[float]] = None,
    ):
        """Initialize voting ensemble.
        
        Args:
            models: List of (name, model) tuples.
            voting: 'hard' for majority vote, 'soft' for probability averaging.
            weights: Optional weights for each model.
        """
        self.models = models
        self.voting = voting
        self.weights = weights
        self.fitted_models_ = []
    
    def fit(self, X: np.ndarray, y: np.ndarray) -> 'VotingEnsemble':
        """Fit all models in the ensemble.
        
        Args:
            X: Training features.
            y: Training labels.
            
        Returns:
            Self.
        """
        self.fitted_models_ = []
        self.classes_ = np.unique(y)
        
        for name, model in self.models:
            logger.info(f"Training {name}...")
            fitted_model = model.fit(X, y)
            self.fitted_models_.append((name, fitted_model))
        
        return self
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions using the ensemble.
        
        Args:
            X: Features to predict.
            
        Returns:
            Predictions.
        """
        check_is_fitted(self)
        
        if self.voting == 'hard':
            return self._predict_hard(X)
        else:
            return self._predict_soft(X)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict class probabilities.
        
        Args:
            X: Features to predict.
            
        Returns:
            Class probabilities.
        """
        check_is_fitted(self)
        
        # Collect probabilities from each model
        all_proba = []
        
        for name, model in self.fitted_models_:
            if hasattr(model, 'predict_proba'):
                proba = model.predict_proba(X)
            else:
                # For models without predict_proba, use one-hot encoding
                predictions = model.predict(X)
                proba = np.zeros((len(X), len(self.classes_)))
                for i, pred in enumerate(predictions):
                    class_idx = np.where(self.classes_ == pred)[0][0]
                    proba[i, class_idx] = 1.0
            
            all_proba.append(proba)
        
        # Apply weights if provided
        if self.weights is not None:
            weighted_proba = np.zeros_like(all_proba[0])
            for i, proba in enumerate(all_proba):
                weighted_proba += proba * self.weights[i]
            return weighted_proba / np.sum(self.weights)
        else:
            # Simple average
            return np.mean(all_proba, axis=0)
    
    def _predict_hard(self, X: np.ndarray) -> np.ndarray:
        """Hard voting prediction."""
        # Collect predictions from each model
        all_predictions = []
        
        for name, model in self.fitted_models_:
            predictions = model.predict(X)
            all_predictions.append(predictions)
        
        # Convert to numpy array
        all_predictions = np.array(all_predictions)
        
        # Apply weights if provided
        if self.weights is not None:
            # Weighted voting
            final_predictions = []
            for i in range(X.shape[0]):
                votes = {}
                for j, pred in enumerate(all_predictions[:, i]):
                    if pred not in votes:
                        votes[pred] = 0
                    votes[pred] += self.weights[j]
                final_predictions.append(max(votes, key=votes.get))
            return np.array(final_predictions)
        else:
            # Simple majority vote
            from scipy import stats
            return stats.mode(all_predictions, axis=0)[0].flatten()
    
    def _predict_soft(self, X: np.ndarray) -> np.ndarray:
        """Soft voting prediction using probabilities."""
        proba = self.predict_proba(X)
        return self.classes_[np.argmax(proba, axis=1)]


class StackingEnsemble(BaseEstimator, ClassifierMixin):
    """Stacking ensemble that uses a meta-model to combine base model predictions."""
    
    def __init__(
        self,
        base_models: List[Tuple[str, Any]],
        meta_model: Any,
        use_probabilities: bool = True,
        cv_folds: int = 5,
    ):
        """Initialize stacking ensemble.
        
        Args:
            base_models: List of (name, model) tuples for base models.
            meta_model: Meta-model to combine predictions.
            use_probabilities: Whether to use probabilities as meta-features.
            cv_folds: Number of cross-validation folds for training meta-model.
        """
        self.base_models = base_models
        self.meta_model = meta_model
        self.use_probabilities = use_probabilities
        self.cv_folds = cv_folds
        self.fitted_base_models_ = []
        self.fitted_meta_model_ = None
    
    def fit(self, X: np.ndarray, y: np.ndarray) -> 'StackingEnsemble':
        """Fit the stacking ensemble.
        
        Args:
            X: Training features.
            y: Training labels.
            
        Returns:
            Self.
        """
        from sklearn.model_selection import KFold
        
        self.classes_ = np.unique(y)
        n_classes = len(self.classes_)
        
        # Train base models and collect out-of-fold predictions
        if self.use_probabilities:
            meta_features = np.zeros((X.shape[0], len(self.base_models) * n_classes))
        else:
            meta_features = np.zeros((X.shape[0], len(self.base_models)))
        
        kf = KFold(n_splits=self.cv_folds, shuffle=True, random_state=42)
        
        for i, (name, model) in enumerate(self.base_models):
            logger.info(f"Training {name} with cross-validation...")
            
            if self.use_probabilities:
                oof_proba = np.zeros((X.shape[0], n_classes))
                
                for train_idx, val_idx in kf.split(X):
                    X_train, X_val = X[train_idx], X[val_idx]
                    y_train = y[train_idx]
                    
                    # Clone and fit model
                    from sklearn.base import clone
                    model_clone = clone(model)
                    model_clone.fit(X_train, y_train)
                    
                    # Get probabilities for validation fold
                    if hasattr(model_clone, 'predict_proba'):
                        oof_proba[val_idx] = model_clone.predict_proba(X_val)
                    else:
                        # One-hot encode predictions
                        predictions = model_clone.predict(X_val)
                        for j, pred in enumerate(predictions):
                            class_idx = np.where(self.classes_ == pred)[0][0]
                            oof_proba[val_idx[j], class_idx] = 1.0
                
                # Store probabilities as meta-features
                start_idx = i * n_classes
                end_idx = (i + 1) * n_classes
                meta_features[:, start_idx:end_idx] = oof_proba
            else:
                # Use predictions as meta-features
                oof_pred = np.zeros(X.shape[0])
                
                for train_idx, val_idx in kf.split(X):
                    X_train, X_val = X[train_idx], X[val_idx]
                    y_train = y[train_idx]
                    
                    # Clone and fit model
                    from sklearn.base import clone
                    model_clone = clone(model)
                    model_clone.fit(X_train, y_train)
                    
                    # Get predictions for validation fold
                    oof_pred[val_idx] = model_clone.predict(X_val)
                
                meta_features[:, i] = oof_pred
        
        # Train final base models on full data
        self.fitted_base_models_ = []
        for name, model in self.base_models:
            logger.info(f"Training final {name} on full data...")
            fitted_model = model.fit(X, y)
            self.fitted_base_models_.append((name, fitted_model))
        
        # Train meta-model
        logger.info("Training meta-model...")
        self.fitted_meta_model_ = self.meta_model.fit(meta_features, y)
        
        return self
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions using the stacking ensemble.
        
        Args:
            X: Features to predict.
            
        Returns:
            Predictions.
        """
        check_is_fitted(self)
        
        # Get meta-features
        meta_features = self._get_meta_features(X)
        
        # Make final prediction with meta-model
        return self.fitted_meta_model_.predict(meta_features)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict class probabilities.
        
        Args:
            X: Features to predict.
            
        Returns:
            Class probabilities.
        """
        check_is_fitted(self)
        
        # Get meta-features
        meta_features = self._get_meta_features(X)
        
        # Make final prediction with meta-model
        if hasattr(self.fitted_meta_model_, 'predict_proba'):
            return self.fitted_meta_model_.predict_proba(meta_features)
        else:
            # Return one-hot encoded predictions
            predictions = self.fitted_meta_model_.predict(meta_features)
            proba = np.zeros((len(X), len(self.classes_)))
            for i, pred in enumerate(predictions):
                class_idx = np.where(self.classes_ == pred)[0][0]
                proba[i, class_idx] = 1.0
            return proba
    
    def _get_meta_features(self, X: np.ndarray) -> np.ndarray:
        """Generate meta-features from base model predictions."""
        n_classes = len(self.classes_)
        
        if self.use_probabilities:
            meta_features = np.zeros((X.shape[0], len(self.fitted_base_models_) * n_classes))
            
            for i, (name, model) in enumerate(self.fitted_base_models_):
                if hasattr(model, 'predict_proba'):
                    proba = model.predict_proba(X)
                else:
                    # One-hot encode predictions
                    predictions = model.predict(X)
                    proba = np.zeros((len(X), n_classes))
                    for j, pred in enumerate(predictions):
                        class_idx = np.where(self.classes_ == pred)[0][0]
                        proba[j, class_idx] = 1.0
                
                start_idx = i * n_classes
                end_idx = (i + 1) * n_classes
                meta_features[:, start_idx:end_idx] = proba
        else:
            meta_features = np.zeros((X.shape[0], len(self.fitted_base_models_)))
            
            for i, (name, model) in enumerate(self.fitted_base_models_):
                meta_features[:, i] = model.predict(X)
        
        return meta_features


class BlendingEnsemble(BaseEstimator, ClassifierMixin):
    """Blending ensemble that combines models using a holdout validation set."""
    
    def __init__(
        self,
        base_models: List[Tuple[str, Any]],
        meta_model: Any,
        blend_size: float = 0.2,
        use_probabilities: bool = True,
    ):
        """Initialize blending ensemble.
        
        Args:
            base_models: List of (name, model) tuples for base models.
            meta_model: Meta-model to combine predictions.
            blend_size: Fraction of data to use for blending.
            use_probabilities: Whether to use probabilities as meta-features.
        """
        self.base_models = base_models
        self.meta_model = meta_model
        self.blend_size = blend_size
        self.use_probabilities = use_probabilities
        self.fitted_base_models_ = []
        self.fitted_meta_model_ = None
    
    def fit(self, X: np.ndarray, y: np.ndarray) -> 'BlendingEnsemble':
        """Fit the blending ensemble.
        
        Args:
            X: Training features.
            y: Training labels.
            
        Returns:
            Self.
        """
        self.classes_ = np.unique(y)
        n_classes = len(self.classes_)
        
        # Split data into train and blend sets
        blend_idx = int(len(X) * (1 - self.blend_size))
        X_train, X_blend = X[:blend_idx], X[blend_idx:]
        y_train, y_blend = y[:blend_idx], y[blend_idx:]
        
        # Train base models on train set
        self.fitted_base_models_ = []
        
        if self.use_probabilities:
            blend_features = np.zeros((X_blend.shape[0], len(self.base_models) * n_classes))
        else:
            blend_features = np.zeros((X_blend.shape[0], len(self.base_models)))
        
        for i, (name, model) in enumerate(self.base_models):
            logger.info(f"Training {name} on train set...")
            fitted_model = model.fit(X_train, y_train)
            self.fitted_base_models_.append((name, fitted_model))
            
            # Generate predictions on blend set
            if self.use_probabilities:
                if hasattr(fitted_model, 'predict_proba'):
                    proba = fitted_model.predict_proba(X_blend)
                else:
                    # One-hot encode predictions
                    predictions = fitted_model.predict(X_blend)
                    proba = np.zeros((len(X_blend), n_classes))
                    for j, pred in enumerate(predictions):
                        class_idx = np.where(self.classes_ == pred)[0][0]
                        proba[j, class_idx] = 1.0
                
                start_idx = i * n_classes
                end_idx = (i + 1) * n_classes
                blend_features[:, start_idx:end_idx] = proba
            else:
                blend_features[:, i] = fitted_model.predict(X_blend)
        
        # Train meta-model on blend set
        logger.info("Training meta-model on blend set...")
        self.fitted_meta_model_ = self.meta_model.fit(blend_features, y_blend)
        
        # Retrain base models on full data
        logger.info("Retraining base models on full data...")
        self.fitted_base_models_ = []
        for name, model in self.base_models:
            fitted_model = model.fit(X, y)
            self.fitted_base_models_.append((name, fitted_model))
        
        return self
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions using the blending ensemble.
        
        Args:
            X: Features to predict.
            
        Returns:
            Predictions.
        """
        check_is_fitted(self)
        
        # Get meta-features from base models
        meta_features = self._get_meta_features(X)
        
        # Make final prediction with meta-model
        return self.fitted_meta_model_.predict(meta_features)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict class probabilities.
        
        Args:
            X: Features to predict.
            
        Returns:
            Class probabilities.
        """
        check_is_fitted(self)
        
        # Get meta-features from base models
        meta_features = self._get_meta_features(X)
        
        # Make final prediction with meta-model
        if hasattr(self.fitted_meta_model_, 'predict_proba'):
            return self.fitted_meta_model_.predict_proba(meta_features)
        else:
            # Return one-hot encoded predictions
            predictions = self.fitted_meta_model_.predict(meta_features)
            proba = np.zeros((len(X), len(self.classes_)))
            for i, pred in enumerate(predictions):
                class_idx = np.where(self.classes_ == pred)[0][0]
                proba[i, class_idx] = 1.0
            return proba
    
    def _get_meta_features(self, X: np.ndarray) -> np.ndarray:
        """Generate meta-features from base model predictions."""
        n_classes = len(self.classes_)
        
        if self.use_probabilities:
            meta_features = np.zeros((X.shape[0], len(self.fitted_base_models_) * n_classes))
            
            for i, (name, model) in enumerate(self.fitted_base_models_):
                if hasattr(model, 'predict_proba'):
                    proba = model.predict_proba(X)
                else:
                    # One-hot encode predictions
                    predictions = model.predict(X)
                    proba = np.zeros((len(X), n_classes))
                    for j, pred in enumerate(predictions):
                        class_idx = np.where(self.classes_ == pred)[0][0]
                        proba[j, class_idx] = 1.0
                
                start_idx = i * n_classes
                end_idx = (i + 1) * n_classes
                meta_features[:, start_idx:end_idx] = proba
        else:
            meta_features = np.zeros((X.shape[0], len(self.fitted_base_models_)))
            
            for i, (name, model) in enumerate(self.fitted_base_models_):
                meta_features[:, i] = model.predict(X)
        
        return meta_features


class DynamicEnsemble(BaseEstimator, ClassifierMixin):
    """Dynamic ensemble that selects models based on recent performance."""
    
    def __init__(
        self,
        models: List[Tuple[str, Any]],
        window_size: int = 100,
        selection_method: str = 'best',
        n_select: int = 3,
    ):
        """Initialize dynamic ensemble.
        
        Args:
            models: List of (name, model) tuples.
            window_size: Window size for performance tracking.
            selection_method: 'best' to select top models, 'weighted' for weighted voting.
            n_select: Number of models to select (for 'best' method).
        """
        self.models = models
        self.window_size = window_size
        self.selection_method = selection_method
        self.n_select = n_select
        self.fitted_models_ = []
        self.performance_history_ = {}
    
    def fit(self, X: np.ndarray, y: np.ndarray) -> 'DynamicEnsemble':
        """Fit all models in the ensemble.
        
        Args:
            X: Training features.
            y: Training labels.
            
        Returns:
            Self.
        """
        self.fitted_models_ = []
        self.classes_ = np.unique(y)
        self.performance_history_ = {name: [] for name, _ in self.models}
        
        for name, model in self.models:
            logger.info(f"Training {name}...")
            fitted_model = model.fit(X, y)
            self.fitted_models_.append((name, fitted_model))
        
        return self
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions using dynamically selected models.
        
        Args:
            X: Features to predict.
            
        Returns:
            Predictions.
        """
        check_is_fitted(self)
        
        # Select models based on recent performance
        selected_models = self._select_models()
        
        if self.selection_method == 'best':
            # Use only selected models
            predictions = []
            for name, model in selected_models:
                pred = model.predict(X)
                predictions.append(pred)
            
            # Majority vote
            predictions = np.array(predictions)
            from scipy import stats
            return stats.mode(predictions, axis=0)[0].flatten()
        else:
            # Weighted voting based on performance
            weights = self._get_weights()
            predictions = []
            
            for name, model in self.fitted_models_:
                pred = model.predict(X)
                predictions.append(pred)
            
            # Weighted vote
            final_predictions = []
            predictions = np.array(predictions)
            
            for i in range(X.shape[0]):
                votes = {}
                for j, (name, _) in enumerate(self.fitted_models_):
                    pred = predictions[j, i]
                    if pred not in votes:
                        votes[pred] = 0
                    votes[pred] += weights.get(name, 0)
                final_predictions.append(max(votes, key=votes.get))
            
            return np.array(final_predictions)
    
    def update_performance(self, y_true: np.ndarray, y_pred: Dict[str, np.ndarray]) -> None:
        """Update performance history for dynamic selection.
        
        Args:
            y_true: True labels.
            y_pred: Dictionary of model predictions.
        """
        for name in self.performance_history_:
            if name in y_pred:
                accuracy = np.mean(y_true == y_pred[name])
                self.performance_history_[name].append(accuracy)
                
                # Keep only recent history
                if len(self.performance_history_[name]) > self.window_size:
                    self.performance_history_[name] = self.performance_history_[name][-self.window_size:]
    
    def _select_models(self) -> List[Tuple[str, Any]]:
        """Select models based on recent performance."""
        if not any(self.performance_history_.values()):
            # No performance history, return all models
            return self.fitted_models_[:self.n_select]
        
        # Calculate average performance
        avg_performance = {}
        for name, history in self.performance_history_.items():
            if history:
                avg_performance[name] = np.mean(history[-self.window_size:])
            else:
                avg_performance[name] = 0.5  # Default
        
        # Sort by performance
        sorted_models = sorted(
            self.fitted_models_,
            key=lambda x: avg_performance.get(x[0], 0.5),
            reverse=True
        )
        
        return sorted_models[:self.n_select]
    
    def _get_weights(self) -> Dict[str, float]:
        """Get weights based on recent performance."""
        weights = {}
        
        for name, history in self.performance_history_.items():
            if history:
                # Use exponential weighting for recent performance
                recent_perf = history[-self.window_size:]
                weights_array = np.exp(np.linspace(0, 1, len(recent_perf)))
                weights_array /= weights_array.sum()
                weights[name] = np.average(recent_perf, weights=weights_array)
            else:
                weights[name] = 0.5  # Default
        
        # Normalize weights
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}
        
        return weights