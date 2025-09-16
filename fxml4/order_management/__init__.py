"""
Order Management System for FXML4 Trading Platform

This module provides enterprise-grade order management capabilities that coordinate
all broker adapters (Interactive Brokers, FXCM, Manual) with intelligent routing,
real-time tracking, and comprehensive audit trails.

Key Components:
- OrderManager: Central coordinator for all order operations
- OrderState: Order lifecycle state machine with validation
- OrderRouter: Intelligent multi-broker routing logic
- OrderBook: Real-time order tracking and monitoring
- Order: Order model with validation and state management

Architecture Integration:
- RabbitMQ message routing for async coordination
- Multi-broker adapter support (IB FIX, FXCM Container, Manual)
- Comprehensive audit logging with cryptographic hashing
- Real-time performance monitoring with <100ms SLA targets
"""

from .order_manager import (
    FillData,
    Order,
    OrderBook,
    OrderManager,
    OrderRequest,
    OrderResponse,
    OrderRouter,
    OrderRoutingError,
    OrderState,
    OrderTimeoutError,
    OrderValidationError,
    RouteDecision,
)

__all__ = [
    "OrderManager",
    "OrderState",
    "OrderRouter",
    "OrderBook",
    "Order",
    "OrderRequest",
    "OrderResponse",
    "FillData",
    "RouteDecision",
    "OrderValidationError",
    "OrderRoutingError",
    "OrderTimeoutError",
]
