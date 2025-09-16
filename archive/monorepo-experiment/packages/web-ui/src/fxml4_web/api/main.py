"""
Main FastAPI application.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from fxml4_core.logging import get_logger
from fxml4_core.config import BaseConfig
from fxml4_web.api.routers import (
    auth, market, trading, backtest, analytics, websocket
)

logger = get_logger(__name__)


class APIConfig(BaseConfig):
    """API configuration."""
    api_title: str = "FXML4 Trading API"
    api_version: str = "1.0.0"
    api_description: str = "REST API for FXML4 forex trading system"
    cors_origins: list = ["http://localhost:3000", "http://localhost:8501"]
    secret_key: str = "your-secret-key-change-this"
    database_url: str = "postgresql://localhost/fxml4"
    redis_url: str = "redis://localhost:6379"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting FXML4 API...")
    
    # Initialize resources
    # TODO: Initialize database, redis, etc.
    
    yield
    
    # Shutdown
    logger.info("Shutting down FXML4 API...")
    
    # Cleanup resources
    # TODO: Close connections, cleanup


def create_app(config: APIConfig = None) -> FastAPI:
    """Create FastAPI application."""
    if config is None:
        config = APIConfig()
    
    app = FastAPI(
        title=config.api_title,
        version=config.api_version,
        description=config.api_description,
        lifespan=lifespan
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(market.router, prefix="/api/v1/market", tags=["market"])
    app.include_router(trading.router, prefix="/api/v1/trading", tags=["trading"])
    app.include_router(backtest.router, prefix="/api/v1/backtest", tags=["backtest"])
    app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
    app.include_router(websocket.router, prefix="/api/v1/ws", tags=["websocket"])
    
    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "message": "FXML4 Trading API",
            "version": config.api_version,
            "docs": "/docs",
            "redoc": "/redoc"
        }
    
    # Health check
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "service": "fxml4-api"
        }
    
    # Exception handlers
    @app.exception_handler(404)
    async def not_found_handler(request, exc):
        return JSONResponse(
            status_code=404,
            content={"detail": "Not found"}
        )
    
    @app.exception_handler(500)
    async def internal_error_handler(request, exc):
        logger.error(f"Internal error: {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )
    
    return app


# Create default app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "fxml4_web.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )