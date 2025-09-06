#!/usr/bin/env python
"""
Update .env file with new variables needed for Supabase integration.
"""
import os
import secrets
from pathlib import Path

def update_env_file():
    """Update .env file with new variables."""
    # Load current .env file
    env_path = Path('.env')
    if not env_path.exists():
        print("Error: .env file not found")
        return

    with open(env_path, 'r') as f:
        lines = f.readlines()

    # Parse current env vars
    env_vars = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        try:
            key, value = line.split('=', 1)
            env_vars[key] = value
        except ValueError:
            continue

    # Add new variables if needed
    new_vars = {
        'JWT_SECRET_KEY': secrets.token_hex(32),
        'JWT_ALGORITHM': 'HS256',
        'JWT_ACCESS_TOKEN_EXPIRE_MINUTES': '60',
        'ALLOWED_ORIGINS': '*',
    }

    for key, default_value in new_vars.items():
        if key not in env_vars:
            env_vars[key] = default_value

    # Write back to .env file
    with open(env_path, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")

    print(".env file updated successfully")

if __name__ == "__main__":
    update_env_file()