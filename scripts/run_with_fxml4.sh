#!/bin/bash
# FXML4 Script Runner - ensures proper PYTHONPATH for script execution
# Usage: ./scripts/run_with_fxml4.sh scripts/script_name.py [args...]

set -e

# Get the directory of this script and the project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Set PYTHONPATH to include the project root
export PYTHONPATH="${PYTHONPATH}:${PROJECT_ROOT}"

# Load .env file if it exists (for environment variables)
if [[ -f "$PROJECT_ROOT/.env" ]]; then
    echo "Loading environment variables from .env file..."
    set -a  # automatically export all variables
    source "$PROJECT_ROOT/.env"
    set +a  # stop auto-exporting
fi

# Find the appropriate Python executable
if [[ -n "$VIRTUAL_ENV" ]]; then
    PYTHON_EXEC="$VIRTUAL_ENV/bin/python"
elif [[ -f "$PROJECT_ROOT/venv/bin/python" ]]; then
    PYTHON_EXEC="$PROJECT_ROOT/venv/bin/python"
else
    PYTHON_EXEC="python"
fi

# Execute the Python script with proper path
exec "$PYTHON_EXEC" "$@"
