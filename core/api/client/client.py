"""Synchronous client for FXML4 API."""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from .exceptions import (
    AuthenticationError,
    FXML4Error,
    RateLimitError,
    ServerError,
    ValidationError,
    VersionError,
)

logger = logging.getLogger(__name__)


class FXML4Client:
    """Synchronous client for interacting with FXML4 API.

    Example:
        ```python
        from fxml4.api.client import FXML4Client

        # Initialize client
        client = FXML4Client(
            base_url="https://api.fxml4.com",
            api_key="your-api-key",
            version="v2"
        )

        # Get market data
        data = client.get_data(
            symbol="EURUSD",
            timeframe="1h",
            start_date="2023-01-01",
            end_date="2023-12-31"
        )

        # Generate signals
        signals = client.generate_signals(
            symbol="EURUSD",
            timeframe="1h",
            strategy="ml_strategy"
        )

        # Run backtest
        result = client.run_backtest(
            symbol="EURUSD",
            timeframe="1h",
            strategy="ml_strategy",
            start_date="2023-01-01",
            end_date="2023-12-31"
        )
        ```
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        version: str = "v2",
        timeout: int = 30,
        retry_count: int = 3,
        retry_backoff: float = 0.3,
    ):
        """Initialize FXML4 API client.

        Args:
            base_url: Base URL of the API
            api_key: API key for authentication
            username: Username for authentication (if not using API key)
            password: Password for authentication (if not using API key)
            version: API version to use
            timeout: Request timeout in seconds
            retry_count: Number of retries for failed requests
            retry_backoff: Backoff factor for retries
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.username = username
        self.password = password
        self.version = version
        self.timeout = timeout

        # Set up session with retry logic
        self.session = requests.Session()

        retry_strategy = Retry(
            total=retry_count,
            backoff_factor=retry_backoff,
            status_forcelist=[429, 500, 502, 503, 504],
            method_whitelist=[
                "HEAD",
                "GET",
                "PUT",
                "DELETE",
                "OPTIONS",
                "TRACE",
                "POST",
            ],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set default headers
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": f"application/vnd.fxml4.{version}+json",
                "User-Agent": f"FXML4-Python-Client/{version}",
            }
        )

        # Authenticate if credentials provided
        self._token = None
        if username and password:
            self._authenticate()
        elif api_key:
            self.session.headers["Authorization"] = f"Bearer {api_key}"

    def _authenticate(self) -> None:
        """Authenticate with username and password."""
        try:
            response = self.session.post(
                f"{self.base_url}/token",
                data={
                    "username": self.username,
                    "password": self.password,
                    "grant_type": "password",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()

            data = response.json()
            self._token = data["access_token"]
            self.session.headers["Authorization"] = f"Bearer {self._token}"

        except requests.exceptions.RequestException as e:
            raise AuthenticationError(f"Authentication failed: {str(e)}")

    def _build_url(self, endpoint: str) -> str:
        """Build full URL for endpoint."""
        if endpoint.startswith("/"):
            endpoint = endpoint[1:]

        # Add version prefix if not already present
        if not endpoint.startswith(f"api/{self.version}"):
            endpoint = f"api/{self.version}/{endpoint}"

        return urljoin(self.base_url, endpoint)

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response and raise appropriate exceptions."""
        try:
            data = response.json()
        except json.JSONDecodeError:
            data = {"message": response.text}

        if response.status_code == 401:
            raise AuthenticationError(
                "Authentication failed", status_code=401, response=data
            )
        elif response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                "Rate limit exceeded",
                retry_after=int(retry_after) if retry_after else None,
                status_code=429,
                response=data,
            )
        elif response.status_code == 400:
            raise ValidationError(
                data.get("message", "Validation error"),
                errors=data.get("details", []),
                status_code=400,
                response=data,
            )
        elif response.status_code >= 500:
            raise ServerError(
                data.get("message", "Server error"),
                status_code=response.status_code,
                response=data,
            )
        elif response.status_code >= 400:
            raise FXML4Error(
                data.get("message", "Request failed"),
                status_code=response.status_code,
                response=data,
            )

        return data

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Make HTTP request to API."""
        url = self._build_url(endpoint)

        logger.debug(f"{method} {url}")

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                timeout=self.timeout,
                **kwargs,
            )

            return self._handle_response(response)

        except requests.exceptions.Timeout:
            raise FXML4Error(f"Request timed out after {self.timeout} seconds")
        except requests.exceptions.ConnectionError:
            raise FXML4Error("Connection error")
        except requests.exceptions.RequestException as e:
            raise FXML4Error(f"Request failed: {str(e)}")

    # Data endpoints
    def get_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        limit: Optional[int] = None,
        source: Optional[str] = None,
        include_indicators: Optional[List[str]] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """Get market data.

        Args:
            symbol: Trading symbol (e.g., 'EURUSD')
            timeframe: Timeframe (e.g., '1h', '1d')
            start_date: Start date
            end_date: End date
            limit: Maximum number of data points
            source: Data source
            include_indicators: Technical indicators to include
            page: Page number for pagination
            page_size: Items per page

        Returns:
            Dictionary with data and metadata
        """
        # Convert dates to ISO format if needed
        if isinstance(start_date, datetime):
            start_date = start_date.isoformat()
        if isinstance(end_date, datetime):
            end_date = end_date.isoformat()

        data = {
            "symbol": symbol,
            "timeframe": timeframe,
            "start_date": start_date,
            "end_date": end_date,
        }

        if limit:
            data["limit"] = limit
        if source:
            data["source"] = source
        if include_indicators:
            data["include_indicators"] = include_indicators

        params = {"page": page, "page_size": page_size}

        response = self._request("POST", "/data", json_data=data, params=params)
        return response.get("data", {})

    # Signal endpoints
    def generate_signals(
        self,
        symbol: str,
        timeframe: str,
        strategy: str,
        lookback_periods: int = 500,
        confidence_threshold: float = 0.7,
        parameters: Optional[Dict[str, Any]] = None,
        real_time: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Generate trading signals.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe for analysis
            strategy: Strategy to use
            lookback_periods: Number of periods to analyze
            confidence_threshold: Minimum confidence for signals
            parameters: Strategy-specific parameters
            real_time: Request real-time updates
            page: Page number for pagination
            page_size: Items per page

        Returns:
            Dictionary with signals and metadata
        """
        data = {
            "symbol": symbol,
            "timeframe": timeframe,
            "strategy": strategy,
            "lookback_periods": lookback_periods,
            "confidence_threshold": confidence_threshold,
            "real_time": real_time,
        }

        if parameters:
            data["parameters"] = parameters

        params = {"page": page, "page_size": page_size}

        response = self._request("POST", "/signals", json_data=data, params=params)
        return response.get("data", {})

    # Backtest endpoints
    def run_backtest(
        self,
        symbol: str,
        timeframe: str,
        strategy: Union[str, List[str]],
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        initial_capital: float = 10000.0,
        commission: float = 0.0002,
        slippage: float = 0.0001,
        position_size: float = 0.02,
        max_positions: int = 5,
        parameters: Optional[Dict[str, Any]] = None,
        monte_carlo: bool = False,
        walk_forward: bool = False,
        auto_report: bool = True,
    ) -> Dict[str, Any]:
        """Run backtest.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            strategy: Strategy or list of strategies
            start_date: Backtest start date
            end_date: Backtest end date
            initial_capital: Initial capital
            commission: Commission rate
            slippage: Slippage rate
            position_size: Position size as fraction of capital
            max_positions: Maximum concurrent positions
            parameters: Strategy parameters
            monte_carlo: Run Monte Carlo simulation
            walk_forward: Use walk-forward optimization
            auto_report: Generate performance report

        Returns:
            Dictionary with backtest results
        """
        # Convert dates to ISO format if needed
        if isinstance(start_date, datetime):
            start_date = start_date.isoformat()
        if isinstance(end_date, datetime):
            end_date = end_date.isoformat()

        data = {
            "symbol": symbol,
            "timeframe": timeframe,
            "strategy": strategy,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": initial_capital,
            "commission": commission,
            "slippage": slippage,
            "position_size": position_size,
            "max_positions": max_positions,
            "monte_carlo": monte_carlo,
            "walk_forward": walk_forward,
            "auto_report": auto_report,
        }

        if parameters:
            data["parameters"] = parameters

        response = self._request("POST", "/backtest", json_data=data)
        return response.get("data", {})

    def get_backtest_report(
        self, backtest_id: str, format: str = "json"
    ) -> Union[Dict[str, Any], bytes]:
        """Get backtest report.

        Args:
            backtest_id: Backtest ID
            format: Report format ('json', 'html', 'pdf')

        Returns:
            Report data (dict for JSON, bytes for HTML/PDF)
        """
        params = {"format": format}

        if format == "json":
            response = self._request("GET", f"/reports/{backtest_id}", params=params)
            return response.get("data", {})
        else:
            # For HTML/PDF, return raw bytes
            url = self._build_url(f"/reports/{backtest_id}")
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.content

    # Batch operations
    def batch(self, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute batch operations.

        Args:
            operations: List of operations to execute

        Returns:
            Dictionary with batch results
        """
        response = self._request("POST", "/batch", json_data=operations)
        return response.get("data", {})

    # Version management
    def get_version_info(self) -> Dict[str, Any]:
        """Get API version information."""
        response = self._request("GET", "/api/versions")
        return response

    def set_version(self, version: str) -> None:
        """Change API version.

        Args:
            version: New version to use (e.g., 'v1', 'v2')
        """
        self.version = version
        self.session.headers["Accept"] = f"application/vnd.fxml4.{version}+json"

    # Health check
    def health_check(self) -> Dict[str, Any]:
        """Check API health status."""
        response = self._request("GET", "/health")
        return response.get("data", {})

    # Search
    def search(
        self, query: str, type: Optional[str] = None, limit: int = 10
    ) -> Dict[str, Any]:
        """Search across resources.

        Args:
            query: Search query
            type: Resource type to search
            limit: Maximum results

        Returns:
            Dictionary with search results
        """
        params = {"q": query, "limit": limit}

        if type:
            params["type"] = type

        response = self._request("GET", "/search", params=params)
        return response.get("data", {})
