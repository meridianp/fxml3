#!/usr/bin/env python3
"""
Provider test for api_core_contract
Generated automatically by FXML4 Claude TDD framework
"""

import pytest
from pact.verifier import Verifier
import subprocess
import time
import requests
from pathlib import Path


class TestApiCoreContractProvider:
    """Provider tests for core service"""

    @classmethod
    def setup_class(cls):
        """Start the provider service before tests"""
        cls.provider_process = cls._start_provider_service()
        cls._wait_for_service_ready()

    @classmethod
    def teardown_class(cls):
        """Stop the provider service after tests"""
        if hasattr(cls, "provider_process"):
            cls.provider_process.terminate()
            cls.provider_process.wait()

    def test_provider_contract_verification(self):
        """Verify that the provider satisfies the contract"""
        pact_file = Path(".claude-tdd/pact/contracts/frontend-core.json")

        if not pact_file.exists():
            pytest.skip(f"Pact file not found: {pact_file}")

        verifier = Verifier(provider="core", provider_base_url="http://localhost:8001")

        success, logs = verifier.verify_pacts(
            str(pact_file),
            verbose=True,
            provider_states_setup_url="http://localhost:8001/_pact/provider_states",
            provider_states_teardown_url="http://localhost:8001/_pact/provider_states/teardown",
        )

        assert success, f"Provider contract verification failed:\n{logs}"

    @classmethod
    def _start_provider_service(cls):
        """Start the provider service"""
        # Start the FXML4 API service
        cmd = ["python", "scripts/start_fxml4_api.py"]
        return subprocess.Popen(cmd, cwd=Path.cwd())

    @classmethod
    def _wait_for_service_ready(cls, timeout=30):
        """Wait for the service to be ready"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = requests.get("http://localhost:8001/health", timeout=5)
                if response.status_code == 200:
                    print("Provider service is ready")
                    return
            except requests.RequestException:
                pass

            time.sleep(1)

        raise RuntimeError("Provider service failed to start within timeout")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
