from setuptools import setup, find_packages

setup(
    name="fxml3",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "matplotlib>=3.7.0",
        "plotly>=5.14.0",
        "scikit-learn>=1.2.0",
        "tensorflow>=2.12.0",
        "transformers>=4.30.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.3.1",
            "black>=23.3.0",
            "flake8>=6.0.0",
            "isort>=5.12.0",
            "mypy>=1.3.0",
        ],
    },
    python_requires=">=3.11",
    author="",
    author_email="",
    description="AI-Enhanced Elliott Wave Analysis for Forex",
    keywords="forex, elliott wave, machine learning, reinforcement learning, llm",
    url="",
)