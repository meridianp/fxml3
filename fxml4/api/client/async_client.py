"""Asynchronous client for FXML4 API."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import aiohttp
from aiohttp import ClientTimeout

from .exceptions import (
    AuthenticationError,
    FXML4Error,
    RateLimitError,
    ServerError,
    ValidationError,
    VersionError,
)

logger = logging.getLogger(__name__)


class AsyncFXML4Client:
    """Asynchronous client for interacting with FXML4 API.

    Example:
        ```python
        import asyncio
        from fxml4.api.client import AsyncFXML4Client

        async def main():
            # Initialize client
            async with AsyncFXML4Client(
                base_url="https://api.fxml4.com",
                api_key="your-api-key"
            ) as client:
                # Get market data
                data = await client.get_data(
                    symbol="EURUSD",
                    timeframe="1h",
                    start_date="2023-01-01",
                    end_date="2023-12-31"
                )

                # Generate signals
                signals = await client.generate_signals(
                    symbol="EURUSD",
                    timeframe="1h",
                    strategy="ml_strategy"
                )

        asyncio.run(main())
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
        retry_delay: float = 1.0,
    ):
        """Initialize async FXML4 API client.

        Args:
            base_url: Base URL of the API
            api_key: API key for authentication
            username: Username for authentication
            password: Password for authentication
            version: API version to use
            timeout: Request timeout in seconds
            retry_count: Number of retries for failed requests
            retry_delay: Delay between retries in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.username = username
        self.password = password
        self.version = version
        self.timeout = ClientTimeout(total=timeout)
        self.retry_count = retry_count
        self.retry_delay = retry_delay

        self._session: Optional[aiohttp.ClientSession] = None
        self._token: Optional[str] = None

        # Default headers
        self._headers = {
            "Content-Type": "application/json",
            "Accept": f"application/vnd.fxml4.{version}+json",
            "User-Agent": f"FXML4-Python-AsyncClient/{version}",
        }

        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"

    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession(
            headers=self._headers, timeout=self.timeout
        )

        # Authenticate if credentials provided
        if self.username and self.password and not self.api_key:
            await self._authenticate()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()

    async def _authenticate(self) -> None:
        """Authenticate with username and password."""
        try:
            async with self._session.post(
                f"{self.base_url}/token",
                data={
                    "username": self.username,
                    "password": self.password,
                    "grant_type": "password",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise AuthenticationError(f"Authentication failed: {text}")

                data = await response.json()
                self._token = data["access_token"]
                self._session.headers["Authorization"] = f"Bearer {self._token}"

        except aiohttp.ClientError as e:
            raise AuthenticationError(f"Authentication failed: {str(e)}")

    def _build_url(self, endpoint: str) -> str:
        """Build full URL for endpoint."""
        if endpoint.startswith("/"):
            endpoint = endpoint[1:]

        # Add version prefix if not already present
        if not endpoint.startswith(f"api/{self.version}"):
            endpoint = f"api/{self.version}/{endpoint}"

        return f"{self.base_url}/{endpoint}"

    async def _handle_response(
        self, response: aiohttp.ClientResponse
    ) -> Dict[str, Any]:
        """Handle API response and raise appropriate exceptions."""
        try:
            data = await response.json()
        except (json.JSONDecodeError, aiohttp.ContentTypeError):
            text = await response.text()
            data = {"message": text}

        if response.status == 401:
            raise AuthenticationError(
                "Authentication failed", status_code=401, response=data
            )
        elif response.status == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                "Rate limit exceeded",
                retry_after=int(retry_after) if retry_after else None,
                status_code=429,
                response=data,
            )
        elif response.status == 400:
            raise ValidationError(
                data.get("message", "Validation error"),
                errors=data.get("details", []),
                status_code=400,
                response=data,
            )
        elif response.status >= 500:
            raise ServerError(
                data.get("message", "Server error"),
                status_code=response.status,
                response=data,
            )
        elif response.status >= 400:
            raise FXML4Error(
                data.get("message", "Request failed"),
                status_code=response.status,
                response=data,
            )

        return data

    async def _request_with_retry(
        self, method: str, url: str, **kwargs
    ) -> aiohttp.ClientResponse:
        """Make request with retry logic."""
        last_error = None

        for attempt in range(self.retry_count):
            try:
                async with self._session.request(method, url, **kwargs) as response:
                    if response.status in [429, 500, 502, 503, 504]:
                        if attempt < self.retry_count - 1:
                            await asyncio.sleep(self.retry_delay * (attempt + 1))
                            continue

                    return response

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_error = e
                if attempt < self.retry_count - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue

        raise FXML4Error(
            f"Request failed after {self.retry_count} attempts: {last_error}"
        )

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Make HTTP request to API."""
        if not self._session:
            raise RuntimeError(
                "Client not initialized. Use 'async with' context manager."
            )

        url = self._build_url(endpoint)

        logger.debug(f"{method} {url}")

        async with await self._request_with_retry(
            method=method, url=url, params=params, json=json_data, **kwargs
        ) as response:
            return await self._handle_response(response)

    # Async versions of all client methods
    async def get_data(
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
        """Get market data asynchronously."""
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

        response = await self._request("POST", "/data", json_data=data, params=params)
        return response.get("data", {})

    async def generate_signals(
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
        """Generate trading signals asynchronously."""
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

        response = await self._request(
            "POST", "/signals", json_data=data, params=params
        )
        return response.get("data", {})

    async def run_backtest(
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
        """Run backtest asynchronously."""
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

        response = await self._request("POST", "/backtest", json_data=data)
        return response.get("data", {})

    async def connect_websocket(self, channel: str, symbol: Optional[str] = None):
        """Connect to WebSocket for real-time updates.

        Args:
            channel: Channel to subscribe to ('signals', 'data', etc.)
            symbol: Optional symbol to filter by

        Yields:
            WebSocket messages
        """
        ws_url = self.base_url.replace("http", "ws")
        endpoint = f"/api/{self.version}/ws/{channel}"
        if symbol:
            endpoint += f"/{symbol}"

        ws_url = f"{ws_url}{endpoint}"

        async with self._session.ws_connect(ws_url) as ws:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    yield data
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    raise FXML4Error(f"WebSocket error: {ws.exception()}")

    # Additional async methods
    async def batch(self, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute batch operations asynchronously."""
        response = await self._request("POST", "/batch", json_data=operations)
        return response.get("data", {})

    async def health_check(self) -> Dict[str, Any]:
        """Check API health status asynchronously."""
        response = await self._request("GET", "/health")
        return response.get("data", {})

    async def search(
        self, query: str, type: Optional[str] = None, limit: int = 10
    ) -> Dict[str, Any]:
        """Search across resources asynchronously."""
        params = {"q": query, "limit": limit}

        if type:
            params["type"] = type

        response = await self._request("GET", "/search", params=params)
        return response.get("data", {})
