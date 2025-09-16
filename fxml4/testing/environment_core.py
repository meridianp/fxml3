"""CI/CD environment adaptation utilities."""

import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class CIEnvironmentAdapter:
    """Adapts test configuration based on CI/CD environment."""

    def __init__(self):
        self.ci_providers = {
            "github_actions": ["GITHUB_ACTIONS", "GITHUB_WORKFLOW"],
            "gitlab_ci": ["GITLAB_CI"],
            "jenkins": ["JENKINS_URL", "BUILD_NUMBER"],
            "travis": ["TRAVIS"],
            "circleci": ["CIRCLECI"],
        }

    def is_ci_environment(self) -> bool:
        """Check if running in a CI environment."""
        # Check for generic CI indicators
        if os.getenv("CI", "").lower() in ("1", "true", "yes"):
            return True

        # Check for specific CI providers
        for provider, env_vars in self.ci_providers.items():
            if any(os.getenv(var) for var in env_vars):
                return True

        return False

    def get_ci_provider(self) -> str:
        """Get the CI provider name."""
        for provider, env_vars in self.ci_providers.items():
            if any(os.getenv(var) for var in env_vars):
                return provider
        return "unknown"

    def get_adapted_config(self) -> Dict[str, Any]:
        """Get configuration adapted for current environment."""
        if self.is_ci_environment():
            return self._get_ci_config()
        else:
            return self._get_local_config()

    def _get_ci_config(self) -> Dict[str, Any]:
        """Get CI-optimized configuration."""
        return {
            "timeout_multiplier": 2.0,  # CI can be slower
            "retry_count": 3,
            "log_level": "INFO",
            "enable_debug_logging": False,
            "max_parallel_tests": 2,  # Conservative for CI
            "database_pool_size": 2,
            "memory_limit": 512,  # MB
            "enable_performance_monitoring": True,
        }

    def _get_local_config(self) -> Dict[str, Any]:
        """Get local development configuration."""
        return {
            "timeout_multiplier": 1.0,
            "retry_count": 1,
            "log_level": "DEBUG",
            "enable_debug_logging": True,
            "max_parallel_tests": 4,
            "database_pool_size": 5,
            "memory_limit": 1024,  # MB
            "enable_performance_monitoring": False,
        }


class ResourceScaler:
    """Scales resources based on environment capabilities."""

    def __init__(self):
        self.environment_profiles = {
            "local": {
                "max_parallel_tests": 8,
                "database_pool_size": 10,
                "memory_limit": 2048,
                "timeout_multiplier": 1.0,
                "enable_expensive_tests": True,
            },
            "ci": {
                "max_parallel_tests": 4,
                "database_pool_size": 5,
                "memory_limit": 1024,
                "timeout_multiplier": 2.0,
                "enable_expensive_tests": False,
            },
            "minimal": {
                "max_parallel_tests": 1,
                "database_pool_size": 1,
                "memory_limit": 256,
                "timeout_multiplier": 3.0,
                "enable_expensive_tests": False,
            },
        }

    def get_scaled_config(self, environment: str = "local") -> Dict[str, Any]:
        """Get resource configuration scaled for environment."""
        if environment not in self.environment_profiles:
            environment = "ci"  # Default to conservative CI settings

        return self.environment_profiles[environment].copy()

    def detect_environment_resources(self) -> Dict[str, Any]:
        """Auto-detect available resources."""
        try:
            import psutil

            cpu_count = psutil.cpu_count()
            memory_gb = psutil.virtual_memory().total / (1024**3)

            if memory_gb >= 8 and cpu_count >= 8:
                return self.get_scaled_config("local")
            elif memory_gb >= 4 and cpu_count >= 4:
                return self.get_scaled_config("ci")
            else:
                return self.get_scaled_config("minimal")

        except ImportError:
            # Fallback without psutil
            return self.get_scaled_config("ci")


class TestSelector:
    """Selects appropriate tests based on environment constraints."""

    def __init__(self):
        self.environment_configs = {
            "ci": {
                "excluded_markers": ["requires_ib", "requires_fxcm", "slow", "manual"],
                "included_patterns": ["test_unit_*", "test_integration_*"],
                "max_test_duration": 300,  # 5 minutes
                "enable_parallel": True,
            },
            "local": {
                "excluded_markers": ["manual"],
                "included_patterns": ["test_*"],
                "max_test_duration": 3600,  # 1 hour
                "enable_parallel": True,
            },
            "full": {
                "excluded_markers": [],
                "included_patterns": ["test_*"],
                "max_test_duration": None,
                "enable_parallel": True,
            },
        }

    def select_tests_for_environment(
        self, environment: str = "local"
    ) -> Dict[str, Any]:
        """Select appropriate tests for environment."""
        if environment not in self.environment_configs:
            environment = "ci"  # Default to conservative selection

        config = self.environment_configs[environment].copy()

        # Add computed fields
        if environment == "ci":
            # Add more restrictive patterns for CI
            config["pytest_args"] = [
                "-m",
                "not slow and not requires_ib and not requires_fxcm",
                "--maxfail=5",  # Stop after 5 failures
                "--tb=short",  # Short traceback format
            ]
        else:
            config["pytest_args"] = [
                "--tb=long",  # Full traceback for debugging
                "-v",  # Verbose output
            ]

        return config

    def get_recommended_markers(self, environment: str = "local") -> List[str]:
        """Get recommended pytest markers for environment."""
        if environment == "ci":
            return [
                "unit",  # Fast unit tests
                "integration",  # Basic integration tests
                "api",  # API endpoint tests
                "not slow",  # Exclude slow tests
                "not requires_ib",  # Exclude IB dependency tests
                "not requires_fxcm",  # Exclude FXCM dependency tests
            ]
        elif environment == "local":
            return [
                "unit",
                "integration",
                "api",
                "performance",  # Performance benchmarks
                "security",  # Security tests
            ]
        else:  # full
            return ["all"]
