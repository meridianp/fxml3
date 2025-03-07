from setuptools import setup, find_packages

setup(
    name="fxml3",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        # Core data processing
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "pandas-ta>=0.3.14b0",
        "python-dotenv>=1.0.0",
        
        # Data acquisition
        "yfinance>=0.2.18",
        "requests>=2.28.2",
        
        # Visualization
        "matplotlib>=3.7.0",
        "plotly>=5.14.0",
        "mplfinance>=0.12.9b0",
        
        # Machine Learning
        "scikit-learn>=1.2.0",
        "tensorflow>=2.12.0",
        "torch>=2.0.0",
        "stable-baselines3>=2.0.0",
        "gymnasium>=0.28.1",
        
        # LLM & RAG
        "transformers>=4.30.0",
        "langchain>=0.0.267",
        "langchain-community>=0.0.1",
        "faiss-cpu>=1.7.4",
        "sentence-transformers>=2.2.2",
        
        # Web UI
        "streamlit>=1.22.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.3.1",
            "black>=23.3.0",
            "flake8>=6.0.0",
            "isort>=5.12.0",
            "mypy>=1.3.0",
            "backtesting>=0.3.3",
        ],
        "api": [
            "python-fxcm>=1.1.0",
            "ccxt>=3.0.0",
        ],
        "ui": [
            "dash>=2.9.3",
        ],
        "deploy": [
            "docker>=6.1.0",
            "pyyaml>=6.0",
        ],
    },
    python_requires=">=3.11",
    author="",
    author_email="",
    description="AI-Enhanced Elliott Wave Analysis for Forex",
    keywords="forex, elliott wave, machine learning, reinforcement learning, llm",
    url="",
)