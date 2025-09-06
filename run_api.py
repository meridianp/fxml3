#!/usr/bin/env python
"""
Run the FXML3 API server.
"""
import os
import sys
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set default values
host = os.getenv("API_HOST", "127.0.0.1")  # Changed to localhost only
port = int(os.getenv("API_PORT", "8787"))  # Changed to an uncommon port 
reload = os.getenv("API_RELOAD", "true").lower() == "true"

def main():
    """Run the API server."""
    print(f"Starting FXML3 API server on {host}:{port}...")
    uvicorn.run(
        "fxml3.api.main:app",
        host=host,
        port=port,
        reload=reload
    )

if __name__ == "__main__":
    main()