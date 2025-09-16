# Installation

This guide walks you through the process of installing FXML4 and its dependencies.

## Prerequisites

Before installing FXML4, you need to have the following:

- Python 3.9 or later
- Git
- pip (Python package installer)
- (Optional) A virtual environment tool like venv or conda

## Installing from Source

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/fxml4.git
cd fxml4
```

### Step 2: Set Up a Virtual Environment (Recommended)

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Run the Setup Script

```bash
python setup_env.py
```

## Installing Interactive Brokers API

FXML4 uses the Interactive Brokers API for market data and trading. The API should be installed automatically as part of the dependencies, but if you need to install it manually:

```bash
# Option 1: Install from PyPI
pip install ibapi

# Option 2: Install from source (recommended for latest version)
# First, download the TWS API from Interactive Brokers website
cd /path/to/IBJts/source/pythonclient
python setup.py install
```

## Verifying the Installation

To verify that FXML4 is installed correctly, run the following command:

```bash
python -c "import fxml4; print(f'FXML4 installed successfully. Version: {fxml4.__version__}')"
```

## Setting Up for Development

If you plan to contribute to FXML4, you'll need to install additional development dependencies:

```bash
pip install -r requirements-dev.txt
```

This will install tools like:

- Black (code formatter)
- Mypy (type checker)
- Pytest (testing framework)
- Mkdocs (documentation generator)

## Troubleshooting

### ImportError: No module named 'ibapi'

This means the Interactive Brokers API is not installed correctly. Try reinstalling it:

```bash
pip uninstall ibapi
pip install ibapi
```

Or install from source as described above.

### Dependency Conflicts

If you encounter dependency conflicts, try creating a fresh virtual environment:

```bash
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Next Steps

Once you have installed FXML4, you can:

- Follow the [Quick Start Guide](quick-start.md) to begin using FXML4
- Set up the [Interactive Brokers connection](../tutorials/ib-api-integration.md)
- Explore the [Architecture](../architecture.md) to understand the system design
