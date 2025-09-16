#!/usr/bin/env python
"""Debug version of the Streamlit app.

This script runs a minimal Streamlit app to test if the basic functionality is working.
"""

import streamlit as st

def main():
    """Run a simple Streamlit app for debugging."""
    st.set_page_config(
        page_title="FXML4 Debug Dashboard",
        page_icon="🐛",
        layout="wide",
    )
    
    st.title("FXML4 Debug Dashboard")
    st.write("If you can see this, Streamlit is working correctly!")
    
    st.subheader("Testing API Connection")
    if st.button("Test API Connection"):
        try:
            import requests
            response = requests.get("http://localhost:8000/health")
            if response.status_code == 200:
                st.success(f"API connection successful! Response: {response.json()}")
            else:
                st.error(f"API connection failed with status code: {response.status_code}")
        except Exception as e:
            st.error(f"Error connecting to API: {str(e)}")
    
    st.subheader("Dashboard Components Test")
    
    # Test tabs
    tab1, tab2 = st.tabs(["Tab 1", "Tab 2"])
    
    with tab1:
        st.write("This is Tab 1")
        
    with tab2:
        st.write("This is Tab 2")
    
    # Test form
    with st.form("test_form"):
        st.selectbox("Test Dropdown", options=["Option 1", "Option 2", "Option 3"])
        st.date_input("Test Date")
        st.form_submit_button("Submit")
    
    # Test plotly
    try:
        import numpy as np
        import plotly.express as px
        
        df = pd.DataFrame({
            'x': np.arange(10),
            'y': np.random.randn(10),
        })
        
        fig = px.line(df, x='x', y='y', title="Test Plot")
        st.plotly_chart(fig)
        st.success("Plotly charts are working!")
    except Exception as e:
        st.error(f"Error creating plotly chart: {str(e)}")

if __name__ == "__main__":
    import pandas as pd
    main()