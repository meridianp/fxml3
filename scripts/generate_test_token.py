#!/usr/bin/env python3
"""
Generate JWT token for API performance testing
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from fxml4.api.auth.uat_auth import create_uat_token


def main():
    """Generate UAT token for performance testing"""
    token = create_uat_token(
        username="performance_tester", scopes=["read", "write", "admin"]
    )

    print(token)
    return token


if __name__ == "__main__":
    main()
