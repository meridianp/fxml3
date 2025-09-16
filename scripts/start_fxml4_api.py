#!/usr/bin/env python3
"""
Start the FXML4 API server for testing.

This script starts the FXML4 API with the correct endpoints for ML and backtesting.
"""

import os

import uvicorn


def main():
    """Start the FXML4 API server."""
    # Get configuration from environment variables
    host = os.getenv("FXML4_API_HOST", "0.0.0.0")
    port = int(os.getenv("FXML4_API_PORT", "8001"))

    print("🚀 Starting FXML4 API server...")
    print(f"📍 API will be available at: http://localhost:{port}")
    print(f"📚 API docs will be available at: http://localhost:{port}/docs")
    print(f"🔗 Health check: http://localhost:{port}/health")
    print("🛑 Press Ctrl+C to stop the server")
    print("")

    try:
        # Start the FXML4 API with configurable host and port
        uvicorn.run(
            "fxml4.api.main:app", host=host, port=port, reload=True, log_level="info"
        )
    except KeyboardInterrupt:
        print("\n🛑 API server stopped")
    except Exception as e:
        print(f"❌ Error starting API server: {e}")
        print("\n💡 Troubleshooting:")
        print("1. Make sure you're in the FXML4 root directory")
        print("2. Install dependencies: pip install fastapi uvicorn")
        print("3. Activate virtual environment: source venv/bin/activate")


if __name__ == "__main__":
    main()
