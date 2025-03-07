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
1. **Imports**: Group imports (stdlib, third-party, local) with isort
2. **Formatting**: Follow PEP 8 with black formatter (line length: 88)
3. **Type Annotations**: Use typing for function parameters and return values
4. **Naming**: snake_case for functions/variables, CamelCase for classes
5. **Documentation**: Docstrings for modules, classes and functions (Google style)
6. **Error Handling**: Use explicit exception handling with specific exceptions
7. **Agent Architecture**: Follow multi-agent design pattern described in README
8. **Data Processing**: Prefer pandas for data manipulation, numpy for calculations
9. **Visualization**: Use plotly for interactive charts, matplotlib for static exports
10. **Commits**: Use conventional commit format (feat/fix/docs/style/refactor/test/chore)