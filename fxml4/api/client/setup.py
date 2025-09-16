"""Setup script for FXML4 API Client SDK."""

from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="fxml4-api-client",
    version="2.0.0",
    author="FXML4 Team",
    author_email="api-support@fxml4.com",
    description="Official Python client for FXML4 Trading Platform API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/fxml4/python-client",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial :: Investment",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.28.0",
        "aiohttp>=3.8.0",
        "pydantic>=2.0.0",
        "python-dateutil>=2.8.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "mypy>=1.0.0",
            "flake8>=6.0.0",
        ],
        "cli": [
            "click>=8.0.0",
            "rich>=13.0.0",
            "tabulate>=0.9.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "fxml4=fxml4_api_client.cli:main",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/fxml4/python-client/issues",
        "Source": "https://github.com/fxml4/python-client",
        "Documentation": "https://api.fxml4.com/docs",
    },
)
