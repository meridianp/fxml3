#!/usr/bin/env python3
"""
Docker development environment setup script for FXML4.

This script sets up a Docker-based development environment for FXML4,
which helps avoid dependency issues across different platforms.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run_command(command, cwd=None):
    """Run a shell command and return the exit code."""
    print(f"Running: {command}")
    result = subprocess.run(command, shell=True, cwd=cwd)
    return result.returncode


def check_docker():
    """Check if Docker is installed and running."""
    result = run_command("docker --version")
    if result != 0:
        print("Docker is not installed or not in PATH. Please install Docker first.")
        return False

    result = run_command("docker info")
    if result != 0:
        print("Docker is not running. Please start Docker first.")
        return False

    return True


def check_docker_compose():
    """Check if Docker Compose is installed."""
    result = run_command("docker compose version")
    if result != 0:
        print("Docker Compose is not installed or not in PATH.")
        return False

    return True


def create_dev_dockerfile():
    """Create a development Dockerfile."""
    dockerfile_path = "Dockerfile.dev"

    if os.path.exists(dockerfile_path):
        print(f"{dockerfile_path} already exists, skipping creation")
        return True

    print(f"Creating {dockerfile_path}")

    with open(dockerfile_path, "w") as f:
        f.write(
            """# Development Dockerfile for FXML4
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    git \\
    curl \\
    postgresql-client \\
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for Supabase CLI
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \\
    && apt-get install -y nodejs \\
    && npm install -g supabase

# Install Google Cloud SDK
RUN curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-468.0.0-linux-x86_64.tar.gz \\
    && tar -xf google-cloud-cli-468.0.0-linux-x86_64.tar.gz \\
    && ./google-cloud-sdk/install.sh --quiet \\
    && rm google-cloud-cli-468.0.0-linux-x86_64.tar.gz
ENV PATH=$PATH:/google-cloud-sdk/bin

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \\
    pip install --no-cache-dir -r requirements.txt

# Create directories
RUN mkdir -p /app/data /app/logs /app/output

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Keep container running
CMD ["bash"]
"""
        )

    print(f"{dockerfile_path} created successfully")
    return True


def create_dev_compose_file():
    """Create a development docker-compose.yml file."""
    compose_path = "docker-compose.dev.yml"

    if os.path.exists(compose_path):
        print(f"{compose_path} already exists, skipping creation")
        return True

    print(f"Creating {compose_path}")

    with open(compose_path, "w") as f:
        f.write(
            """version: '3.8'

services:
  dev:
    build:
      context: .
      dockerfile: Dockerfile.dev
    volumes:
      - .:/app
    environment:
      - PYTHONPATH=/app
    ports:
      - "8000:8000"  # API
      - "8501:8501"  # Streamlit
    command: sleep infinity
    networks:
      - fxml4_network
    depends_on:
      - db

  db:
    image: postgres:14-alpine
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=fxml4
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - fxml4_network

networks:
  fxml4_network:
    driver: bridge

volumes:
  postgres_data:
"""
        )

    print(f"{compose_path} created successfully")
    return True


def create_dev_scripts():
    """Create development helper scripts."""
    scripts_dir = Path("scripts")
    scripts_dir.mkdir(exist_ok=True)

    # Create script to enter the development container
    enter_script = scripts_dir / "enter_dev.sh"
    if not enter_script.exists():
        with open(enter_script, "w") as f:
            f.write(
                """#!/bin/bash
# Enter the development container

docker compose -f docker-compose.dev.yml exec dev bash
"""
            )
        os.chmod(enter_script, 0o755)
        print(f"{enter_script} created successfully")

    # Create script to run commands in the development container
    run_script = scripts_dir / "run_in_dev.sh"
    if not run_script.exists():
        with open(run_script, "w") as f:
            f.write(
                """#!/bin/bash
# Run a command in the development container

if [ $# -eq 0 ]; then
    echo "Usage: $0 <command>"
    exit 1
fi

docker compose -f docker-compose.dev.yml exec dev $@
"""
            )
        os.chmod(run_script, 0o755)
        print(f"{run_script} created successfully")

    return True


def build_dev_environment():
    """Build the development environment."""
    result = run_command("docker compose -f docker-compose.dev.yml build")
    if result != 0:
        print("Failed to build development environment")
        return False

    print("Development environment built successfully")
    return True


def start_dev_environment():
    """Start the development environment."""
    result = run_command("docker compose -f docker-compose.dev.yml up -d")
    if result != 0:
        print("Failed to start development environment")
        return False

    print("Development environment started successfully")
    return True


def initialize_database():
    """Initialize the database within the dev environment."""
    result = run_command(
        "docker compose -f docker-compose.dev.yml exec dev python scripts/init_db.py"
    )
    if result != 0:
        print("Failed to initialize database")
        return False

    print("Database initialized successfully")
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Set up Docker development environment for FXML4"
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip building the development environment",
    )
    parser.add_argument(
        "--skip-start",
        action="store_true",
        help="Skip starting the development environment",
    )
    parser.add_argument(
        "--skip-db-init", action="store_true", help="Skip database initialization"
    )
    args = parser.parse_args()

    # Check requirements
    if not check_docker():
        return 1

    if not check_docker_compose():
        return 1

    # Create files
    if not create_dev_dockerfile():
        return 1

    if not create_dev_compose_file():
        return 1

    if not create_dev_scripts():
        return 1

    # Build and start environment
    if not args.skip_build:
        if not build_dev_environment():
            return 1

    if not args.skip_start:
        if not start_dev_environment():
            return 1

    if not args.skip_db_init:
        if not initialize_database():
            return 1

    print("\n=== Docker development environment setup completed successfully ===")
    print("\nNext steps:")
    print("1. To enter the development container: ./scripts/enter_dev.sh")
    print("2. To run a command in the container: ./scripts/run_in_dev.sh <command>")
    print("3. To stop the environment: docker compose -f docker-compose.dev.yml down")
    print("\nExample commands:")
    print("./scripts/run_in_dev.sh python -m fxml4.main")
    print("./scripts/run_in_dev.sh pytest tests/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
