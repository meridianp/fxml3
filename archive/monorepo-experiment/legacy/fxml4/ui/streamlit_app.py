"""FXML4 Streamlit Application.

This is the entry point for the FXML4 Streamlit dashboard.
"""

import sys
import traceback

import streamlit as st

def run_with_error_handling():
    """Run the dashboard with proper error handling."""
    try:
        from fxml4.ui.dashboard import main
        main()
    except Exception as e:
        st.set_page_config(page_title="FXML4 Dashboard Error", page_icon="⚠️")
        
        st.title("⚠️ Error Starting Dashboard")
        st.error(f"An error occurred while starting the dashboard: {str(e)}")
        
        st.subheader("Error Details")
        st.code(traceback.format_exc())
        
        st.subheader("Troubleshooting")
        st.markdown("""
        Please check the following:
        
        1. Make sure the API server is running on http://localhost:8000
        2. Verify that all required dependencies are installed
        3. Check the console for additional error messages
        
        You can also try running the debug app with:
        ```
        streamlit run debug_streamlit.py
        ```
        """)

if __name__ == "__main__":
    run_with_error_handling()