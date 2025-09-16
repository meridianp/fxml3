"""
Comprehensive API Endpoint Discovery and Contract Testing

This module systematically discovers all API endpoints and validates their contracts
against the expected specifications defined in the FXML4 system.

Test-Driven Development (TDD) approach:
1. Red: Define endpoint discovery and contract validation expectations
2. Green: Implement discovery mechanism and basic validation
3. Refactor: Enhance with comprehensive contract checking
"""

import ast
import inspect
import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pytest
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute


class EndpointCategory(Enum):
    """Categories of API endpoints for systematic testing"""

    CORE = "core"
    AUTH = "authentication"
    TRADING = "trading"
    DATA = "data"
    SIGNALS = "signals"
    ORDERS = "orders"
    RISK = "risk_management"
    USERS = "user_management"
    MONITORING = "monitoring"
    AUDIT = "audit_trail"
    REPORTING = "regulatory_reporting"
    PERFORMANCE = "performance"
    BACKTESTING = "backtesting"
    UNKNOWN = "unknown"


@dataclass
class EndpointContract:
    """Contract specification for an API endpoint"""

    path: str
    method: str
    category: EndpointCategory
    handler_function: str
    requires_auth: bool
    request_model: Optional[str] = None
    response_model: Optional[str] = None
    parameters: List[Dict[str, Any]] = None
    description: str = ""
    tags: List[str] = None
    status_codes: List[int] = None

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = []
        if self.tags is None:
            self.tags = []
        if self.status_codes is None:
            self.status_codes = [200]


class APIEndpointDiscovery:
    """Systematic discovery and analysis of FXML4 API endpoints"""

    def __init__(self, api_root_path: Path):
        self.api_root_path = api_root_path
        self.discovered_endpoints: List[EndpointContract] = []
        self.router_files: List[Path] = []
        self.endpoint_patterns = {
            # Authentication patterns (check first - most specific)
            r"/auth/": EndpointCategory.AUTH,
            r"/token": EndpointCategory.AUTH,
            r"/login": EndpointCategory.AUTH,
            r"/logout": EndpointCategory.AUTH,
            r"/2fa": EndpointCategory.AUTH,
            # Trading patterns
            r"/trading/": EndpointCategory.TRADING,
            r"/positions": EndpointCategory.TRADING,
            r"/account": EndpointCategory.TRADING,
            # Data patterns
            r"/data": EndpointCategory.DATA,
            r"/symbols": EndpointCategory.DATA,
            r"/tick": EndpointCategory.DATA,
            r"/ohlcv": EndpointCategory.DATA,
            r"/store": EndpointCategory.DATA,
            # Signal patterns
            r"/signals": EndpointCategory.SIGNALS,
            # Order patterns
            r"/orders": EndpointCategory.ORDERS,
            # Risk patterns
            r"/risk": EndpointCategory.RISK,
            r"/limits": EndpointCategory.RISK,
            r"/exposure": EndpointCategory.RISK,
            r"/violations": EndpointCategory.RISK,
            r"/monitoring": EndpointCategory.RISK,  # Risk monitoring
            # User patterns
            r"/users": EndpointCategory.USERS,
            r"/roles": EndpointCategory.USERS,
            r"/permissions": EndpointCategory.USERS,
            # Monitoring patterns
            r"/health": EndpointCategory.MONITORING,
            r"/metrics": EndpointCategory.MONITORING,
            r"/status": EndpointCategory.MONITORING,
            r"/adapters": EndpointCategory.MONITORING,
            r"/logs": EndpointCategory.MONITORING,
            # Audit patterns
            r"/audit": EndpointCategory.AUDIT,
            r"/events": EndpointCategory.AUDIT,
            # Reporting patterns
            r"/reporting": EndpointCategory.REPORTING,
            r"/reports": EndpointCategory.REPORTING,
            r"/regulatory": EndpointCategory.REPORTING,
            # Performance patterns
            r"/performance": EndpointCategory.PERFORMANCE,
            r"/backtests": EndpointCategory.BACKTESTING,
            # Core patterns (check last - catch root and basic endpoints)
            r"^/$": EndpointCategory.CORE,
            r"/dashboard": EndpointCategory.CORE,
            r"/manual": EndpointCategory.CORE,
        }

    def discover_router_files(self) -> List[Path]:
        """Discover all router files in the API structure"""
        router_path = self.api_root_path / "routers"

        if not router_path.exists():
            return []

        router_files = []
        for file_path in router_path.rglob("*.py"):
            if file_path.name != "__init__.py" and not file_path.name.startswith(
                "test_"
            ):
                router_files.append(file_path)

        self.router_files = router_files
        return router_files

    def parse_router_file(self, file_path: Path) -> List[EndpointContract]:
        """Parse a router file to extract endpoint definitions"""
        endpoints = []

        try:
            with open(file_path, "r") as f:
                content = f.read()

            # Parse AST to get more accurate information
            tree = ast.parse(content)

            # Extract endpoint definitions using regex patterns
            endpoint_matches = re.finditer(
                r'@router\.(get|post|put|delete|patch)\(["\']([^"\']+)["\'].*?\)\s*'
                r"(?:async\s+)?def\s+(\w+)\s*\(",
                content,
                re.MULTILINE | re.DOTALL,
            )

            for match in endpoint_matches:
                method = match.group(1).upper()
                path = match.group(2)
                function_name = match.group(3)

                # Determine category
                category = self._categorize_endpoint(path)

                # Check if authentication is required
                requires_auth = self._check_auth_requirement(content, function_name)

                # Extract additional metadata
                description = self._extract_docstring(content, function_name)
                tags = self._extract_tags(content, match.start())

                endpoint = EndpointContract(
                    path=path,
                    method=method,
                    category=category,
                    handler_function=function_name,
                    requires_auth=requires_auth,
                    description=description,
                    tags=tags,
                )

                endpoints.append(endpoint)

        except Exception as e:
            pytest.fail(f"Failed to parse router file {file_path}: {e}")

        return endpoints

    def _categorize_endpoint(self, path: str) -> EndpointCategory:
        """Categorize endpoint based on path patterns"""
        for pattern, category in self.endpoint_patterns.items():
            if re.search(pattern, path, re.IGNORECASE):
                return category
        return EndpointCategory.UNKNOWN

    def _check_auth_requirement(self, content: str, function_name: str) -> bool:
        """Check if endpoint requires authentication"""
        function_pattern = rf"def\s+{function_name}\s*\([^)]*"
        match = re.search(function_pattern, content)

        if match:
            # Look for Depends(get_current_active_user) or similar patterns
            function_def = content[
                match.start() : match.start() + 500
            ]  # Check next 500 chars
            auth_patterns = [
                r"Depends\(get_current_active_user",
                r"current_user.*=.*Depends",
                r"UATUser.*=.*Depends",
            ]

            for pattern in auth_patterns:
                if re.search(pattern, function_def):
                    return True

        return False

    def _extract_docstring(self, content: str, function_name: str) -> str:
        """Extract function docstring"""
        function_pattern = rf'def\s+{function_name}\s*\([^)]*\):[^"]*"""([^"]+)"""'
        match = re.search(function_pattern, content, re.DOTALL)

        if match:
            return match.group(1).strip()
        return ""

    def _extract_tags(self, content: str, position: int) -> List[str]:
        """Extract FastAPI tags from decorator"""
        # Look backwards from position to find tags parameter
        search_area = content[max(0, position - 200) : position + 200]
        tags_match = re.search(r"tags=\[([^\]]+)\]", search_area)

        if tags_match:
            tags_str = tags_match.group(1)
            tags = [tag.strip(" \"'") for tag in tags_str.split(",")]
            return tags
        return []

    def discover_all_endpoints(self) -> List[EndpointContract]:
        """Discover all API endpoints from router files"""
        self.discover_router_files()

        all_endpoints = []
        for router_file in self.router_files:
            endpoints = self.parse_router_file(router_file)
            all_endpoints.extend(endpoints)

        self.discovered_endpoints = all_endpoints
        return all_endpoints

    def get_endpoints_by_category(
        self, category: EndpointCategory
    ) -> List[EndpointContract]:
        """Get endpoints filtered by category"""
        return [ep for ep in self.discovered_endpoints if ep.category == category]

    def generate_endpoint_summary(self) -> Dict[str, Any]:
        """Generate summary statistics of discovered endpoints"""
        if not self.discovered_endpoints:
            self.discover_all_endpoints()

        summary = {
            "total_endpoints": len(self.discovered_endpoints),
            "by_category": {},
            "by_method": {},
            "authentication_required": 0,
            "router_files_processed": len(self.router_files),
        }

        for endpoint in self.discovered_endpoints:
            # Category breakdown
            category_name = endpoint.category.value
            summary["by_category"][category_name] = (
                summary["by_category"].get(category_name, 0) + 1
            )

            # Method breakdown
            summary["by_method"][endpoint.method] = (
                summary["by_method"].get(endpoint.method, 0) + 1
            )

            # Authentication
            if endpoint.requires_auth:
                summary["authentication_required"] += 1

        return summary


@pytest.fixture
def api_discovery():
    """Fixture providing API endpoint discovery service"""
    api_root = Path(__file__).parent.parent.parent / "fxml4" / "api"
    return APIEndpointDiscovery(api_root)


class TestEndpointDiscovery:
    """Test suite for API endpoint discovery and contract validation"""

    def test_discover_router_files(self, api_discovery):
        """Test that router files are correctly discovered"""
        router_files = api_discovery.discover_router_files()

        # Red: Define expectations for router discovery
        assert len(router_files) > 0, "Should discover at least one router file"

        # Check that expected router files exist
        expected_routers = ["core.py", "trading.py", "data.py", "signals.py"]
        discovered_names = [f.name for f in router_files]

        for expected in expected_routers:
            assert expected in discovered_names, f"Should discover {expected} router"

    def test_parse_router_endpoints(self, api_discovery):
        """Test parsing of individual router files"""
        # Red: Define expectations for endpoint parsing
        router_files = api_discovery.discover_router_files()
        assert len(router_files) > 0, "Need router files to test parsing"

        # Test parsing of first router file
        first_router = router_files[0]
        endpoints = api_discovery.parse_router_file(first_router)

        # Green: Validate basic parsing works
        assert isinstance(endpoints, list), "Should return list of endpoints"

        if endpoints:  # If endpoints found, validate structure
            endpoint = endpoints[0]
            assert isinstance(
                endpoint, EndpointContract
            ), "Should return EndpointContract objects"
            assert endpoint.path.startswith("/"), "Endpoint paths should start with /"
            assert endpoint.method in [
                "GET",
                "POST",
                "PUT",
                "DELETE",
                "PATCH",
            ], "Should have valid HTTP method"
            assert isinstance(
                endpoint.category, EndpointCategory
            ), "Should have valid category"

    def test_endpoint_categorization(self, api_discovery):
        """Test that endpoints are correctly categorized"""
        # Red: Define categorization expectations
        test_cases = [
            ("/auth/token", EndpointCategory.AUTH),
            ("/trading/status", EndpointCategory.TRADING),
            ("/data", EndpointCategory.DATA),
            ("/signals", EndpointCategory.SIGNALS),
            ("/health", EndpointCategory.MONITORING),
            ("/orders", EndpointCategory.ORDERS),
            ("/risk/limits", EndpointCategory.RISK),
            ("/users", EndpointCategory.USERS),
            ("/unknown-endpoint", EndpointCategory.UNKNOWN),
        ]

        for path, expected_category in test_cases:
            actual_category = api_discovery._categorize_endpoint(path)
            assert (
                actual_category == expected_category
            ), f"Path {path} should be categorized as {expected_category.value}"

    def test_authentication_detection(self, api_discovery):
        """Test detection of authentication requirements"""
        # Red: Define auth detection expectations

        # Mock content with authentication
        auth_content = '''
        async def protected_endpoint(
            current_user: User = Depends(get_current_active_user)
        ):
            """Protected endpoint requiring authentication"""
            return {"user": current_user}
        '''

        # Mock content without authentication
        public_content = '''
        async def public_endpoint():
            """Public endpoint"""
            return {"status": "ok"}
        '''

        # Green: Test authentication detection
        assert (
            api_discovery._check_auth_requirement(auth_content, "protected_endpoint")
            == True
        )
        assert (
            api_discovery._check_auth_requirement(public_content, "public_endpoint")
            == False
        )

    def test_comprehensive_endpoint_discovery(self, api_discovery):
        """Test comprehensive discovery of all API endpoints"""
        # Red: Define comprehensive discovery expectations
        all_endpoints = api_discovery.discover_all_endpoints()

        # Green: Validate discovery results
        assert (
            len(all_endpoints) >= 20
        ), "Should discover significant number of endpoints (expected 100+)"

        # Validate endpoint diversity
        categories_found = set(ep.category for ep in all_endpoints)
        assert (
            len(categories_found) >= 3
        ), "Should find endpoints in multiple categories"

        # Validate HTTP methods
        methods_found = set(ep.method for ep in all_endpoints)
        assert "GET" in methods_found, "Should find GET endpoints"
        assert "POST" in methods_found, "Should find POST endpoints"

        # Check for authentication distribution
        auth_required = sum(1 for ep in all_endpoints if ep.requires_auth)
        public_endpoints = len(all_endpoints) - auth_required

        assert auth_required > 0, "Should find some authenticated endpoints"
        assert public_endpoints > 0, "Should find some public endpoints"

    def test_endpoint_summary_generation(self, api_discovery):
        """Test generation of endpoint discovery summary"""
        # Red: Define summary generation expectations
        summary = api_discovery.generate_endpoint_summary()

        # Green: Validate summary structure and content
        required_keys = [
            "total_endpoints",
            "by_category",
            "by_method",
            "authentication_required",
            "router_files_processed",
        ]
        for key in required_keys:
            assert key in summary, f"Summary should include {key}"

        assert summary["total_endpoints"] > 0, "Should report non-zero endpoint count"
        assert (
            summary["router_files_processed"] > 0
        ), "Should report processed router files"
        assert isinstance(
            summary["by_category"], dict
        ), "Category breakdown should be dict"
        assert isinstance(summary["by_method"], dict), "Method breakdown should be dict"

    def test_core_endpoints_discovered(self, api_discovery):
        """Test that core system endpoints are discovered"""
        # Red: Define core endpoint expectations
        all_endpoints = api_discovery.discover_all_endpoints()

        core_endpoints = api_discovery.get_endpoints_by_category(EndpointCategory.CORE)
        monitoring_endpoints = api_discovery.get_endpoints_by_category(
            EndpointCategory.MONITORING
        )

        # Check that we have core or monitoring endpoints
        assert (
            len(core_endpoints) > 0 or len(monitoring_endpoints) > 0
        ), "Should discover some core or monitoring endpoints"

        # Look for health endpoint specifically in monitoring category
        all_paths = [ep.path for ep in all_endpoints]
        health_found = any("/health" in path or path == "/health" for path in all_paths)
        assert health_found, "Should find health endpoint somewhere in the API"

    def test_trading_endpoints_discovered(self, api_discovery):
        """Test that trading engine endpoints are discovered"""
        # Red: Define trading endpoint expectations
        all_endpoints = api_discovery.discover_all_endpoints()
        trading_endpoints = api_discovery.get_endpoints_by_category(
            EndpointCategory.TRADING
        )

        # Expected trading endpoints
        expected_trading_paths = [
            "/trading/status",
            "/trading/positions",
            "/trading/account",
            "/trading/start",
            "/trading/stop",
        ]

        discovered_paths = [ep.path for ep in trading_endpoints]

        for expected_path in expected_trading_paths:
            found = any(expected_path in path for path in discovered_paths)
            assert found, f"Should discover trading endpoint: {expected_path}"

    def test_data_endpoints_discovered(self, api_discovery):
        """Test that market data endpoints are discovered"""
        # Red: Define data endpoint expectations
        all_endpoints = api_discovery.discover_all_endpoints()
        data_endpoints = api_discovery.get_endpoints_by_category(EndpointCategory.DATA)

        # Should find at least some data endpoints
        assert (
            len(data_endpoints) > 0
        ), f"Should discover at least one data endpoint, found {len(data_endpoints)}"

        # Check specific data endpoints
        data_paths = [ep.path for ep in data_endpoints]

        # Check that we have key data endpoints
        expected_data_paths = ["/data", "/symbols", "/store"]
        expected_patterns = [r"/tick/", r"/ohlcv/"]

        found_paths = 0
        for expected_path in expected_data_paths:
            if expected_path in data_paths:
                found_paths += 1

        found_patterns = 0
        for pattern in expected_patterns:
            if any(re.search(pattern, path) for path in data_paths):
                found_patterns += 1

        assert (
            found_paths >= 2
        ), f"Should find at least 2 specific data paths, found {found_paths}"
        assert (
            found_patterns >= 1
        ), f"Should find at least 1 data pattern, found {found_patterns}"


if __name__ == "__main__":
    # Direct execution for development testing
    api_root = Path(__file__).parent.parent.parent / "fxml4" / "api"
    discovery = APIEndpointDiscovery(api_root)

    print("Discovering FXML4 API endpoints...")
    endpoints = discovery.discover_all_endpoints()

    summary = discovery.generate_endpoint_summary()
    print(f"\nDiscovery Summary:")
    print(f"Total endpoints: {summary['total_endpoints']}")
    print(f"Router files processed: {summary['router_files_processed']}")
    print(f"Authentication required: {summary['authentication_required']}")

    print(f"\nBy category:")
    for category, count in summary["by_category"].items():
        print(f"  {category}: {count}")

    print(f"\nBy HTTP method:")
    for method, count in summary["by_method"].items():
        print(f"  {method}: {count}")

    # Print detailed endpoint list
    print(f"\nDetailed endpoint list:")
    for endpoint in endpoints[:10]:  # Show first 10
        auth_status = "🔒" if endpoint.requires_auth else "🌐"
        print(
            f"  {auth_status} {endpoint.method:6} {endpoint.path:30} [{endpoint.category.value}]"
        )

    if len(endpoints) > 10:
        print(f"  ... and {len(endpoints) - 10} more endpoints")
