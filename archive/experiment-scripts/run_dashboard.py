#!/usr/bin/env python
"""Run the FXML4 Dashboard.

This script launches both the API server and the Streamlit UI in separate processes.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml


def load_config():
    """Load configuration from default.yaml."""
    config_path = Path("config/default.yaml")
    if not config_path.exists():
        print(f"Error: Config file not found at {config_path}")
        sys.exit(1)
    
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    return config


def run_api(host=None, port=None, debug=None):
    """Run the FastAPI server."""
    config = load_config()
    
    # Use provided values or fall back to config
    api_host = host or config.get("api", {}).get("host", "0.0.0.0")
    api_port = port or config.get("api", {}).get("port", 8000)
    api_debug = debug or config.get("api", {}).get("debug", False)
    
    cmd = [
        sys.executable, "-m", "fxml4.api.main",
    ]
    
    env = os.environ.copy()
    env["API_HOST"] = str(api_host)
    env["API_PORT"] = str(api_port)
    env["API_DEBUG"] = str(api_debug).lower()
    
    print(f"Starting API server on {api_host}:{api_port}")
    
    # Add more verbose output
    process = subprocess.Popen(
        cmd, 
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Check if process started successfully
    time.sleep(2)
    if process.poll() is not None:
        # Process terminated, print stderr
        _, stderr = process.communicate()
        print(f"Error starting API server:\n{stderr}")
        raise RuntimeError(f"API server failed to start: {stderr}")
    
    print("API server started successfully")
    
    return process


def run_ui(host=None, port=None):
    """Run the Streamlit UI."""
    config = load_config()
    
    # Use provided values or fall back to config
    ui_host = host or config.get("ui", {}).get("host", "0.0.0.0")
    ui_port = port or config.get("ui", {}).get("port", 8501)
    
    cmd = [
        sys.executable, "-m", "streamlit", "run", 
        "fxml4/ui/streamlit_app.py",
        "--server.address", str(ui_host),
        "--server.port", str(ui_port),
    ]
    
    print(f"Starting UI server on {ui_host}:{ui_port}")
    
    # Add more verbose output
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Check if process started successfully
    time.sleep(5)
    if process.poll() is not None:
        # Process terminated, print stderr
        _, stderr = process.communicate()
        print(f"Error starting UI server:\n{stderr}")
        raise RuntimeError(f"UI server failed to start: {stderr}")
    
    print("UI server started successfully. Dashboard available at:")
    print(f"http://{ui_host if ui_host != '0.0.0.0' else 'localhost'}:{ui_port}")
    
    return process


def main():
    """Run the dashboard (API + UI)."""
    parser = argparse.ArgumentParser(description="Run the FXML4 Dashboard")
    parser.add_argument("--api-host", help="API server host", default=None)
    parser.add_argument("--api-port", type=int, help="API server port", default=None)
    parser.add_argument("--ui-host", help="UI server host", default=None)
    parser.add_argument("--ui-port", type=int, help="UI server port", default=None)
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    try:
        # Start API server
        api_process = run_api(
            host=args.api_host,
            port=args.api_port,
            debug=args.debug
        )
        
        # Give API server time to start
        time.sleep(2)
        
        # Start UI server
        ui_process = run_ui(
            host=args.ui_host,
            port=args.ui_port
        )
        
        print("\nDashboard is now running!")
        print("API server URL: http://localhost:8000")
        print("UI server URL:  http://localhost:8501")
        print("\nPress Ctrl+C to stop both servers.")
        
        # Wait for both processes
        api_process.wait()
        ui_process.wait()
        
    except KeyboardInterrupt:
        print("\nShutting down...")
        
        # Stop processes gracefully
        if 'api_process' in locals():
            api_process.terminate()
            api_process.wait(timeout=5)
            
        if 'ui_process' in locals():
            ui_process.terminate()
            ui_process.wait(timeout=5)
            
        print("Dashboard stopped.")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()