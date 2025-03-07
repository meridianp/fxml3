# FXML3 - AI-Enhanced Elliott Wave Analysis for Forex

## Build & Run Commands
```bash
# Setup virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest                     # Run all tests
pytest tests/test_file.py  # Run specific test file
pytest -xvs tests/         # Verbose test output

# Lint & Format
flake8 .                   # Lint code
black .                    # Format code
isort .                    # Sort imports
mypy .                     # Type checking
```

## Git Workflow
```bash
# Create feature branch
git checkout -b feature/name

# Commit changes with descriptive message
git commit -m "type(scope): descriptive message"

# Push to remote (after setting up remote)
git push -u origin feature/name

# Create PR and merge after review
```

## Code Style Guidelines

### Imports
Group imports in the following order using isort:
1. Standard library imports
2. Related third-party imports
3. Local application/library specific imports

Example:
```python
import os
import sys
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from fxml3.data_engineering.data_feeds import create_data_feed
from fxml3.utils.helpers import format_date
```

### Formatting
- Follow PEP 8 with black formatter (line length: 88)
- Use 4 spaces for indentation (not tabs)
- Add a blank line between logical sections of code
- Keep functions and methods focused and concise
- Limit line length to 88 characters (black default)

### Type Annotations
- Use typing module for function parameters and return values
- Use Optional[] for parameters that can be None
- Use Union[] for parameters that can be multiple types
- Use TypedDict for complex dictionary structures
- Use Literal[] for parameters with specific string values

Example:
```python
from typing import Dict, List, Optional, Union

def process_data(
    symbol: str,
    start_date: Union[str, datetime],
    end_date: Optional[Union[str, datetime]] = None,
) -> pd.DataFrame:
    """Process data for a given symbol and date range."""
    # Function implementation
```

### Naming Conventions
- `snake_case` for functions, methods, variables, modules, and packages
- `CamelCase` for classes
- `UPPER_CASE` for constants
- Prefixes for special variables: `_private_variable`, `__very_private_variable`
- Descriptive names that reflect purpose (avoid abbreviations)

### Documentation
Use Google-style docstrings for modules, classes, functions, and methods. Each docstring should include:

- A one-line summary that does not use "Returns" or similar language
- A more detailed description if needed
- Args: section listing all parameters
- Returns: section describing return value(s)
- Raises: section listing all exceptions that might be raised

Example:

```python
def add_technical_indicators(
    df: pd.DataFrame,
    indicators: List[str] = None,
    periods: List[int] = None,
) -> pd.DataFrame:
    """Add technical indicators to the DataFrame.
    
    Computes various technical indicators using the pandas-ta library
    and adds them as new columns to the input DataFrame.
    
    Args:
        df: DataFrame with OHLCV data. Must contain at least 'close' column.
        indicators: List of indicators to add. Valid values include:
            'sma', 'ema', 'rsi', 'macd', 'bollinger', 'atr'.
            If None, defaults to ['sma', 'ema', 'rsi'].
        periods: List of periods to use for indicators.
            If None, defaults to [14, 20, 50, 200].
        
    Returns:
        DataFrame with added technical indicator columns.
        
    Raises:
        ValueError: If a required column is missing from the DataFrame.
        ImportError: If pandas_ta is not installed.
    """
    # Function implementation
```

### Error Handling
- Use explicit exception handling with specific exceptions
- Include error messages that are helpful for debugging
- Use logging for error reporting, not just print statements
- Handle errors gracefully with fallbacks when appropriate

Example:
```python
try:
    df = clean_data(df)
except ValueError as e:
    logger.error(f"Error cleaning data: {str(e)}")
    # Fallback to original data or raise an appropriate exception
```

### Architecture
- Follow the multi-agent design pattern described in README
- Use dependency injection for components
- Maintain separation of concerns
- Implement interfaces (abstract base classes) for interchangeable components
- Follow factory pattern for component creation

### Data Processing
- Prefer pandas for data manipulation
- Use numpy for numerical calculations
- Always handle NaN/None values explicitly
- Create copies of DataFrames before modification to avoid side effects
- Use appropriate data types for columns (category, datetime, etc.)

### Visualization
- Use plotly for interactive charts
- Use matplotlib for static exports
- Follow consistent color schemes and styling
- Include proper titles, labels, and legends
- Make visualizations accessible (color-blind friendly)

### Code Quality
- Write unit tests for all functions and methods
- Keep functions short and focused on a single task
- Use meaningful variable names
- Add comments for complex logic
- Refactor duplicate code into reusable functions

## Commits and Pull Requests
- Use conventional commit format: `type(scope): description`
- Types: feat, fix, docs, style, refactor, test, chore
- Create focused pull requests that address a single concern
- Include detailed PR descriptions with context
- Reference issues in PR descriptions (#issue-number)
- Request reviews from appropriate team members