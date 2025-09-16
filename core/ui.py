"""FXML4 UI module.

This module consolidates all UI functionality including the main entry point
and Streamlit application.
"""

import subprocess
import sys
import traceback
from pathlib import Path

import streamlit as st


def main():
    """Launch the Streamlit UI."""
    # Get the path to the streamlit app
    app_path = Path(__file__).parent / "ui" / "streamlit_app.py"

    # If the old structure doesn't exist, use the dashboard directly
    if not app_path.exists():
        # Launch using the run_with_error_handling function
        run_with_error_handling()
        return

    # Launch streamlit with the old structure
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.address",
        "0.0.0.0",
        "--server.port",
        "8501",
    ]

    subprocess.run(cmd)


def run_with_error_handling():
    """Run the dashboard with proper error handling."""
    try:
        from fxml4.ui.dashboard import main as dashboard_main

        dashboard_main()
    except Exception as e:
        st.set_page_config(page_title="FXML4 Dashboard Error", page_icon="⚠️")

        st.title("⚠️ Error Starting Dashboard")
        st.error(f"An error occurred while starting the dashboard: {str(e)}")

        st.subheader("Error Details")
        st.code(traceback.format_exc())

        st.subheader("Troubleshooting")
        st.markdown(
            """
        Please check the following:

        1. Make sure the API server is running on http://localhost:8000
        2. Verify that all required dependencies are installed
        3. Check the console for additional error messages

        You can also try running the debug app with:
        ```
        streamlit run debug_streamlit.py
        ```
        """
        )


def launch_streamlit():
    """Alternative entry point for launching Streamlit."""
    run_with_error_handling()


if __name__ == "__main__":
    main()
