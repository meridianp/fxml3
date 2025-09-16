"""
Main API application for FXML4.

This module provides the FastAPI application setup and configuration.
The route handlers have been moved to separate modules for better organization.
"""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from fxml4.api.events import setup_events
from fxml4.api.middleware.security import SecurityMiddleware
from fxml4.api.routers import (
    api_key_management_router,
    auth_tdd_router,
    backtest_router,
    core_router,
    data_router,
    legacy_auth_router,
    performance_router,
    signals_router,
    user_crud_tdd_router,
)
from fxml4.config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="FXML4 API",
    description="API for the FXML4 trading platform with versioning support",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {
            "name": "v1",
            "description": "Version 1 API (Deprecated)",
            "externalDocs": {
                "description": "V1 Migration Guide",
                "url": "https://api.fxml4.com/docs/migration/v1-to-v2",
            },
        },
        {
            "name": "v2",
            "description": "Version 2 API (Current)",
            "externalDocs": {
                "description": "V2 Documentation",
                "url": "https://api.fxml4.com/docs/v2",
            },
        },
        {"name": "authentication", "description": "Authentication endpoints"},
        {"name": "core", "description": "Core API endpoints"},
        {"name": "data", "description": "Market data endpoints"},
        {"name": "signals", "description": "Signal generation endpoints"},
        {"name": "backtest", "description": "Backtesting endpoints"},
        {"name": "performance", "description": "Performance analysis endpoints"},
        {"name": "versioning", "description": "API version information"},
        {"name": "orders", "description": "Order management endpoints"},
        {"name": "trading", "description": "Trading engine control endpoints"},
    ],
)

# Add basic CORS middleware first (before complex security middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Frontend development server
        "https://localhost:3000",  # HTTPS variant
        "http://127.0.0.1:3000",  # Alternative localhost
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add security middleware (replaces dangerous auth bypass)
app.add_middleware(SecurityMiddleware)


# Setup middleware
# Temporarily commenting out security middleware to debug CORS
# from fxml4.api.middleware import setup_security_middleware
# setup_security_middleware(app)

# Setup performance monitoring (temporarily commented out to debug CORS)
# from fxml4.monitoring.middleware import setup_monitoring_middleware
# setup_monitoring_middleware(app)

# Setup application lifecycle events
setup_events(app)

# Include routers

# Include core routes
app.include_router(core_router)

# Include legacy auth routes for backward compatibility
app.include_router(legacy_auth_router)

# Include TDD-validated authentication routes
if auth_tdd_router:
    app.include_router(auth_tdd_router)

# Include TDD-validated user CRUD routes
if user_crud_tdd_router:
    app.include_router(user_crud_tdd_router)

# Include TDD-validated API key management routes
if api_key_management_router:
    app.include_router(api_key_management_router)

# Include functional routes (only if they loaded successfully)
if data_router:
    app.include_router(data_router)
if signals_router:
    app.include_router(signals_router)
if backtest_router:
    app.include_router(backtest_router)
if performance_router:
    app.include_router(performance_router)

# Include WebSocket router for real-time data
try:
    from fxml4.api.routers.websocket import router as websocket_router

    app.include_router(websocket_router, tags=["websocket"])
    logger.info("WebSocket router loaded successfully")
except ImportError as e:
    logger.warning(f"WebSocket router not available: {e}")

# Include v1 router (deprecated) - optional
try:
    from fxml4.api.v1 import create_v1_router

    v1_router = create_v1_router()
    app.include_router(v1_router)
    logger.info("V1 API router loaded successfully")
except ImportError as e:
    logger.info(f"V1 API router not available (expected): {e}")
except Exception as e:
    logger.error(f"Error loading V1 API router: {e}")

# Include v2 router (current) - optional
try:
    from fxml4.api.v2 import create_v2_router

    v2_router = create_v2_router()
    app.include_router(v2_router)
    logger.info("V2 API router loaded successfully")
except ImportError as e:
    logger.info(f"V2 API router not available (expected): {e}")
except Exception as e:
    logger.error(f"Error loading V2 API router: {e}")

# Include versioning router - optional
try:
    from fxml4.api.versioning import create_version_router

    version_router = create_version_router()
    app.include_router(version_router, tags=["versioning"])
    logger.info("Versioning router loaded successfully")
except ImportError as e:
    logger.warning(f"Versioning router not available: {e}")
except Exception as e:
    logger.error(f"Error loading versioning router: {e}")

# Include existing specialized routers - optional
try:
    from fxml4.api.routers.monitoring import router as monitoring_router

    app.include_router(monitoring_router)
    logger.info("Monitoring router loaded successfully")
except ImportError as e:
    logger.warning(f"Monitoring router not available: {e}")
except Exception as e:
    logger.error(f"Error loading monitoring router: {e}")

try:
    from fxml4.api.routers.risk_management import router as risk_router

    app.include_router(risk_router)
    logger.info("Risk management router loaded successfully")
except ImportError as e:
    logger.warning(f"Risk management router not available: {e}")
except Exception as e:
    logger.error(f"Error loading risk management router: {e}")

try:
    from fxml4.api.routers.manual_execution import router as manual_router

    app.include_router(manual_router)
    logger.info("Manual execution router loaded successfully")
except ImportError as e:
    logger.warning(f"Manual execution router not available: {e}")
except Exception as e:
    logger.error(f"Error loading manual execution router: {e}")

# Include orders router
try:
    from fxml4.api.routers.orders import router as orders_router

    app.include_router(orders_router, tags=["orders"])
    logger.info("Orders router loaded successfully")
except ImportError as e:
    logger.warning(f"Orders router not available: {e}")

# Include trading engine router
try:
    from fxml4.api.routers.trading import router as trading_router

    app.include_router(trading_router, tags=["trading"])
    logger.info("Trading engine router loaded successfully")
except ImportError as e:
    logger.warning(f"Trading engine router not available: {e}")

# Include monitoring dashboard
try:
    from fxml4.monitoring.dashboard import create_dashboard_router

    monitoring_router = create_dashboard_router()
    app.include_router(monitoring_router)
    logger.info("Monitoring dashboard router loaded successfully")
except ImportError as e:
    logger.info(f"Monitoring dashboard router not available (optional): {e}")
except Exception as e:
    logger.error(f"Error loading monitoring dashboard router: {e}")

# Mount static files for monitoring dashboard
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


def main():
    """Main entry point for running the API server."""
    import uvicorn

    config = get_config()
    host = config.get("api.host", "0.0.0.0")
    port = config.get("api.port", 8000)
    debug = config.get("api.debug", False)

    uvicorn.run(
        "fxml4.api.main:app", host=host, port=port, reload=debug, log_level="info"
    )


if __name__ == "__main__":
    main()
