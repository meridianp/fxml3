#!/usr/bin/env python
"""Manual test for API client in isolation."""

import time
from datetime import datetime

from fxml4.ui.dashboard import ApiClient

# Create a sample HTML report for testing
def create_test_report():
    """Create a test report file."""
    report_path = "output/reports/BT-20230101-123456.html"
    with open(report_path, "w") as f:
        f.write("<html><body><h1>Test Report</h1><p>This is a test report.</p></body></html>")
    return report_path

def test_api_client():
    """Test the API client functionality."""
    # Create API client
    client = ApiClient("http://localhost:8000")
    print(f"API client initialized with base URL: {client.base_url}")
    
    # Create test report
    report_path = create_test_report()
    print(f"Created test report at {report_path}")
    
    # Test report URL generation
    report_url = client.get_performance_report_url("BT-20230101-123456", format="html")
    print(f"Report URL: {report_url}")
    
    print("Manual test completed successfully!")

if __name__ == "__main__":
    test_api_client()