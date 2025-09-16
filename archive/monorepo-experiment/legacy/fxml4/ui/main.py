"""Main entry point for FXML4 UI.

This module launches the Streamlit dashboard for FXML4.
"""

import sys
import subprocess
from pathlib import Path


def main():
    """Launch the Streamlit UI."""
    # Get the path to the streamlit app
    app_path = Path(__file__).parent / "streamlit_app.py"
    
    # Launch streamlit
    cmd = [
        sys.executable, "-m", "streamlit", "run", 
        str(app_path),
        "--server.address", "0.0.0.0",
        "--server.port", "8501",
    ]
    
    subprocess.run(cmd)


if __name__ == "__main__":
    main()