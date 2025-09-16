"""Manual Adapter API Setup.

This module shows how to integrate the manual adapter with the FastAPI application.
"""

from fastapi import FastAPI

from fxml4.api.routers import manual_execution
from fxml4.brokers.adapters.base import AdapterConfig
from fxml4.brokers.adapters.manual_rabbitmq_adapter import ManualRabbitMQAdapter


def setup_manual_adapter(app: FastAPI) -> ManualRabbitMQAdapter:
    """Set up manual adapter for the API.

    Args:
        app: FastAPI application instance.

    Returns:
        Configured manual adapter instance.
    """
    # Create adapter configuration
    config = AdapterConfig(
        broker_type="manual",
        adapter_type="manual_rabbitmq",
        connection_params={
            "rabbitmq": {
                "host": "rabbitmq",  # Docker service name
                "port": 5672,
                "username": "guest",
                "password": "guest",
            }
        },
        features={
            "auto_reject_timeout": 300,  # 5 minutes
            "require_two_factor": False,
            "allow_risk_override": True,
            "simulate_execution": True,
            "simulated_fill_delay": 2,
            "approval_levels": {"standard": 0, "senior": 100000, "executive": 1000000},
            "audit_trail": True,
        },
        limits={"max_override_amount": 10000000},
    )

    # Create adapter instance
    adapter = ManualRabbitMQAdapter(config)

    # Set adapter reference in router
    manual_execution.manual_adapter = adapter

    # Include router in app
    app.include_router(manual_execution.router)

    return adapter


# Example usage in main.py:
#
# from fastapi import FastAPI
# from fxml4.api.manual_adapter_setup import setup_manual_adapter
#
# app = FastAPI(title="FXML4 API")
#
# @app.on_event("startup")
# async def startup_event():
#     # Set up manual adapter
#     adapter = setup_manual_adapter(app)
#     await adapter.connect()
#
# @app.on_event("shutdown")
# async def shutdown_event():
#     # Disconnect adapter
#     if manual_execution.manual_adapter:
#         await manual_execution.manual_adapter.disconnect()
