#!/usr/bin/env python3
"""
Test suite for monitoring dashboard system.
Retrospective tests for existing production monitoring dashboard infrastructure.
"""

import asyncio
import json
import subprocess

# Import the module under test
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, patch

import pytest

sys.path.append(str(Path(__file__).parent.parent.parent / "scripts"))
from monitoring_dashboard import MonitoringDashboard


class TestMonitoringDashboardInitialization:
    """Test dashboard initialization and configuration."""

    def test_initialization_default_paths(self):
        """Test dashboard initialization with default script paths."""
        # Given: No custom configuration
        # When: Creating dashboard
        dashboard = MonitoringDashboard()

        # Then: Default paths are configured correctly
        assert dashboard.script_dir == Path(__file__).parent.parent.parent / "scripts"
        assert dashboard.health_monitor.name == "infrastructure_health_monitor.py"
        assert dashboard.quality_validator.name == "data_quality_validator.py"
        assert dashboard.data_updater.name == "automated_data_updates.py"
        assert dashboard.venv_path.name == "venv-monitoring"

    def test_initialization_script_paths_exist(self):
        """Test that initialized script paths point to expected files."""
        # Given: Dashboard instance
        dashboard = MonitoringDashboard()

        # When: Checking script paths
        # Then: All paths are properly constructed
        assert dashboard.health_monitor.is_absolute()
        assert dashboard.quality_validator.is_absolute()
        assert dashboard.data_updater.is_absolute()
        assert str(dashboard.health_monitor).endswith(
            "infrastructure_health_monitor.py"
        )
        assert str(dashboard.quality_validator).endswith("data_quality_validator.py")
        assert str(dashboard.data_updater).endswith("automated_data_updates.py")


class TestScriptExecution:
    """Test script execution functionality."""

    @patch("subprocess.run")
    def test_run_script_success_json_output(self, mock_subprocess):
        """Test successful script execution with JSON output."""
        # Given: Mock subprocess that returns JSON
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '{"status": "healthy", "services": 4}\n'
        mock_subprocess.return_value = mock_result

        dashboard = MonitoringDashboard()
        script_path = Path("/fake/script.py")

        # When: Running script
        result = dashboard._run_script(script_path)

        # Then: JSON is parsed correctly
        assert result == {"status": "healthy", "services": 4}

        # Verify subprocess was called correctly
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args
        assert str(script_path) in call_args[0][0]
        assert call_args[1]["capture_output"] is True
        assert call_args[1]["text"] is True
        assert call_args[1]["timeout"] == 120

    @patch("subprocess.run")
    def test_run_script_success_non_json_output(self, mock_subprocess):
        """Test successful script execution with non-JSON output."""
        # Given: Mock subprocess that returns non-JSON text
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Script completed successfully\nNo JSON output"
        mock_subprocess.return_value = mock_result

        dashboard = MonitoringDashboard()
        script_path = Path("/fake/script.py")

        # When: Running script
        result = dashboard._run_script(script_path)

        # Then: Non-JSON output is handled
        assert result["status"] == "success"
        assert "Script completed successfully" in result["output"]

    @patch("subprocess.run")
    def test_run_script_with_arguments(self, mock_subprocess):
        """Test script execution with command line arguments."""
        # Given: Mock successful subprocess
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '{"status": "ok"}\n'
        mock_subprocess.return_value = mock_result

        dashboard = MonitoringDashboard()
        script_path = Path("/fake/script.py")
        args = ["--check-staleness", "--verbose"]

        # When: Running script with arguments
        result = dashboard._run_script(script_path, args)

        # Then: Arguments are passed to subprocess
        call_args = mock_subprocess.call_args[0][0]
        assert "--check-staleness" in call_args
        assert "--verbose" in call_args
        assert result["status"] == "ok"

    @patch("subprocess.run")
    def test_run_script_error_return_code(self, mock_subprocess):
        """Test script execution with error return code."""
        # Given: Mock subprocess that fails
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Script failed: connection refused"
        mock_subprocess.return_value = mock_result

        dashboard = MonitoringDashboard()
        script_path = Path("/fake/script.py")

        # When: Running script
        result = dashboard._run_script(script_path)

        # Then: Error is captured
        assert result["status"] == "error"
        assert result["error"] == "Script failed: connection refused"

    @patch("subprocess.run")
    def test_run_script_timeout(self, mock_subprocess):
        """Test script execution timeout handling."""
        # Given: Mock subprocess that times out
        mock_subprocess.side_effect = subprocess.TimeoutExpired("cmd", 120)

        dashboard = MonitoringDashboard()
        script_path = Path("/fake/script.py")

        # When: Running script
        result = dashboard._run_script(script_path)

        # Then: Timeout is handled
        assert result["status"] == "timeout"
        assert "timed out" in result["error"]

    @patch("subprocess.run")
    def test_run_script_exception(self, mock_subprocess):
        """Test script execution exception handling."""
        # Given: Mock subprocess that raises exception
        mock_subprocess.side_effect = FileNotFoundError("Script not found")

        dashboard = MonitoringDashboard()
        script_path = Path("/fake/script.py")

        # When: Running script
        result = dashboard._run_script(script_path)

        # Then: Exception is handled
        assert result["status"] == "error"
        assert "Script not found" in result["error"]


class TestDataRetrievalMethods:
    """Test data retrieval methods."""

    @pytest.mark.asyncio
    @patch.object(MonitoringDashboard, "_run_script")
    async def test_get_infrastructure_health(self, mock_run_script):
        """Test infrastructure health data retrieval."""
        # Given: Mock script execution
        expected_result = {
            "overall_status": "healthy",
            "services": {"redis": {"status": "healthy"}},
            "alerts": [],
        }
        mock_run_script.return_value = expected_result

        dashboard = MonitoringDashboard()

        # When: Getting infrastructure health
        result = await dashboard.get_infrastructure_health()

        # Then: Correct script is called and result returned
        mock_run_script.assert_called_once_with(dashboard.health_monitor)
        assert result == expected_result

    @pytest.mark.asyncio
    @patch.object(MonitoringDashboard, "_run_script")
    async def test_get_data_quality(self, mock_run_script):
        """Test data quality assessment retrieval."""
        # Given: Mock script execution
        expected_result = {
            "summary": {"average_quality_score": 0.85},
            "recommendations": ["Update EURUSD data"],
        }
        mock_run_script.return_value = expected_result

        dashboard = MonitoringDashboard()

        # When: Getting data quality
        result = await dashboard.get_data_quality()

        # Then: Correct script is called with arguments
        mock_run_script.assert_called_once_with(
            dashboard.quality_validator, ["--days", "7"]
        )
        assert result == expected_result

    @pytest.mark.asyncio
    @patch.object(MonitoringDashboard, "_run_script")
    async def test_get_data_staleness(self, mock_run_script):
        """Test data staleness information retrieval."""
        # Given: Mock script execution
        expected_result = {
            "update_needed": True,
            "stale_pairs": [{"symbol": "EURUSD", "days_stale": 3}],
            "fresh_pairs": [],
        }
        mock_run_script.return_value = expected_result

        dashboard = MonitoringDashboard()

        # When: Getting data staleness
        result = await dashboard.get_data_staleness()

        # Then: Correct script is called with arguments
        mock_run_script.assert_called_once_with(
            dashboard.data_updater, ["--check-staleness"]
        )
        assert result == expected_result


class TestServiceStatusFormatting:
    """Test service status formatting functionality."""

    def test_format_service_status_all_healthy(self):
        """Test formatting when all services are healthy."""
        # Given: Dashboard and healthy services data
        dashboard = MonitoringDashboard()
        services = {
            "redis": {
                "status": "healthy",
                "response_time_ms": 25.5,
                "details": {
                    "version": "6.2.7",
                    "connected_clients": 3,
                    "used_memory": "2.1M",
                },
            },
            "rabbitmq": {
                "status": "healthy",
                "response_time_ms": 45.2,
                "details": {"connection_state": "open"},
            },
        }

        # When: Formatting service status
        result = dashboard.format_service_status(services)

        # Then: All services show as healthy with details
        assert "✅ REDIS: healthy (25.5ms)" in result
        assert "✅ RABBITMQ: healthy (45.2ms)" in result
        assert "Redis 6.2.7, 3 clients, 2.1M" in result

    def test_format_service_status_mixed_health(self):
        """Test formatting with mixed service health."""
        # Given: Dashboard and mixed health services
        dashboard = MonitoringDashboard()
        services = {
            "redis": {"status": "healthy", "response_time_ms": 20.0, "details": {}},
            "rabbitmq": {
                "status": "degraded",
                "response_time_ms": 150.0,
                "details": {},
            },
            "docker": {"status": "unhealthy", "response_time_ms": 500.0, "details": {}},
        }

        # When: Formatting service status
        result = dashboard.format_service_status(services)

        # Then: Different status symbols are used
        assert "✅ REDIS: healthy" in result
        assert "⚠️  RABBITMQ: degraded" in result
        assert "❌ DOCKER: unhealthy" in result

    def test_format_service_status_system_details(self):
        """Test formatting of system service details."""
        # Given: Dashboard and system service data
        dashboard = MonitoringDashboard()
        services = {
            "system": {
                "status": "healthy",
                "response_time_ms": 10.0,
                "details": {
                    "cpu_percent": 35.2,
                    "memory_percent": 0.65,
                    "disk_percent": 0.45,
                },
            }
        }

        # When: Formatting service status
        result = dashboard.format_service_status(services)

        # Then: System details are formatted correctly
        assert "CPU: 35.2%" in result
        assert "RAM: 65.0%" in result
        assert "Disk: 45.0%" in result

    def test_format_service_status_docker_details(self):
        """Test formatting of Docker service details."""
        # Given: Dashboard and Docker service data
        dashboard = MonitoringDashboard()
        services = {
            "docker": {
                "status": "healthy",
                "response_time_ms": 30.0,
                "details": {
                    "container1": {"status": "running", "image": "fxml4:latest"},
                    "container2": {"status": "running", "image": "redis:7"},
                    "container3": {"status": "exited", "image": "rabbitmq:3"},
                    "error_info": "some non-dict data",  # Should be ignored
                },
            }
        }

        # When: Formatting service status
        result = dashboard.format_service_status(services)

        # Then: Running container count is shown
        assert "2 containers running" in result


class TestDataQualityFormatting:
    """Test data quality formatting functionality."""

    def test_format_data_quality_success(self):
        """Test formatting successful data quality results."""
        # Given: Dashboard and quality data
        dashboard = MonitoringDashboard()
        quality_data = {
            "status": "success",
            "summary": {
                "average_quality_score": 0.87,
                "total_gaps": 5,
                "total_anomalies": 12,
                "high_quality_symbols": ["EURUSD", "GBPUSD"],
                "medium_quality_symbols": ["USDJPY"],
                "low_quality_symbols": [],
            },
            "recommendations": [
                "Update stale data for USDCAD",
                "Fix critical gaps in AUDUSD",
                "Review anomalies in USDCHF",
            ],
        }

        # When: Formatting data quality
        result = dashboard.format_data_quality(quality_data)

        # Then: All elements are formatted correctly
        assert "📊 Data Quality Overview:" in result
        assert "Average Quality Score: 0.87" in result
        assert "✅ High Quality: 2 symbols" in result
        assert "⚠️  Medium Quality: 1 symbols" in result
        assert "❌ Low Quality: 0 symbols" in result
        assert "Data Gaps: 5" in result
        assert "Anomalies: 12" in result
        assert "🔧 Recommendations:" in result
        assert "Update stale data for USDCAD" in result

    def test_format_data_quality_error(self):
        """Test formatting data quality error."""
        # Given: Dashboard and error data
        dashboard = MonitoringDashboard()
        quality_data = {"status": "error", "error": "Failed to connect to database"}

        # When: Formatting data quality
        result = dashboard.format_data_quality(quality_data)

        # Then: Error is displayed
        assert "❌ Data Quality Check Failed" in result
        assert "Failed to connect to database" in result

    def test_format_data_quality_no_recommendations(self):
        """Test formatting when no recommendations are present."""
        # Given: Dashboard and quality data without recommendations
        dashboard = MonitoringDashboard()
        quality_data = {
            "status": "success",
            "summary": {"average_quality_score": 0.95},
            "recommendations": [],
        }

        # When: Formatting data quality
        result = dashboard.format_data_quality(quality_data)

        # Then: No recommendations section is shown
        assert "🔧 Recommendations:" not in result
        assert "Average Quality Score: 0.95" in result


class TestDataStalenessFormatting:
    """Test data staleness formatting functionality."""

    def test_format_data_staleness_success(self):
        """Test formatting successful staleness data."""
        # Given: Dashboard and staleness data
        dashboard = MonitoringDashboard()
        staleness_data = {
            "stale_pairs": [
                {"symbol": "EURUSD", "days_stale": 2, "latest_date": "2023-01-01"},
                {"symbol": "GBPUSD", "days_stale": 5, "latest_date": "2022-12-28"},
                {"symbol": "USDJPY", "days_stale": 10, "latest_date": "2022-12-22"},
            ],
            "fresh_pairs": [
                {"symbol": "AUDUSD", "days_stale": 0, "latest_date": "2023-01-03"}
            ],
            "update_needed": True,
        }

        # When: Formatting data staleness
        result = dashboard.format_data_staleness(staleness_data)

        # Then: All elements are formatted correctly
        assert "📅 Data Freshness Status:" in result
        assert "Fresh Pairs: 1" in result
        assert "Stale Pairs: 3" in result
        assert "Update Needed: Yes" in result
        assert "⏰ Stale Data:" in result
        assert "🟡 EURUSD: 2 days" in result  # <= 3 days
        assert "🔴 GBPUSD: 5 days" in result  # <= 7 days
        assert "🟣 USDJPY: 10 days" in result  # > 7 days

    def test_format_data_staleness_no_stale_data(self):
        """Test formatting when no stale data exists."""
        # Given: Dashboard and fresh data
        dashboard = MonitoringDashboard()
        staleness_data = {
            "stale_pairs": [],
            "fresh_pairs": [
                {"symbol": "EURUSD", "days_stale": 0},
                {"symbol": "GBPUSD", "days_stale": 1},
            ],
            "update_needed": False,
        }

        # When: Formatting data staleness
        result = dashboard.format_data_staleness(staleness_data)

        # Then: No stale data section is shown
        assert "Fresh Pairs: 2" in result
        assert "Stale Pairs: 0" in result
        assert "Update Needed: No" in result
        assert "⏰ Stale Data:" not in result

    def test_format_data_staleness_error(self):
        """Test formatting staleness error."""
        # Given: Dashboard and error data
        dashboard = MonitoringDashboard()
        staleness_data = {"status": "error", "error": "Data directory not found"}

        # When: Formatting data staleness
        result = dashboard.format_data_staleness(staleness_data)

        # Then: Error is displayed
        assert "❌ Staleness Check Failed" in result
        assert "Data directory not found" in result


class TestDashboardGeneration:
    """Test complete dashboard generation."""

    @pytest.mark.asyncio
    @patch.object(MonitoringDashboard, "get_infrastructure_health")
    @patch.object(MonitoringDashboard, "get_data_quality")
    @patch.object(MonitoringDashboard, "get_data_staleness")
    async def test_generate_dashboard_healthy_system(
        self, mock_staleness, mock_quality, mock_health
    ):
        """Test dashboard generation for healthy system."""
        # Given: Mock data for healthy system
        mock_health.return_value = {
            "status": "success",
            "overall_status": "healthy",
            "services": {
                "redis": {"status": "healthy", "response_time_ms": 20.0, "details": {}}
            },
            "alerts": [],
            "summary": {"total_alerts": 0},
        }

        mock_quality.return_value = {
            "status": "success",
            "summary": {"average_quality_score": 0.9},
            "recommendations": [],
        }

        mock_staleness.return_value = {
            "stale_pairs": [],
            "fresh_pairs": [{"symbol": "EURUSD", "days_stale": 0}],
            "update_needed": False,
        }

        dashboard = MonitoringDashboard()

        # When: Generating dashboard
        result = await dashboard.generate_dashboard()

        # Then: Dashboard contains all sections
        assert "FXML4 MONITORING DASHBOARD" in result
        assert "🟢 OVERALL STATUS: HEALTHY" in result
        assert "INFRASTRUCTURE HEALTH" in result
        assert "✅ REDIS: healthy" in result
        assert "Data Quality Overview" in result
        assert "Data Freshness Status" in result
        assert "✅ NO ACTIVE ALERTS" in result
        assert "Use individual scripts for detailed analysis" in result

    @pytest.mark.asyncio
    @patch.object(MonitoringDashboard, "get_infrastructure_health")
    @patch.object(MonitoringDashboard, "get_data_quality")
    @patch.object(MonitoringDashboard, "get_data_staleness")
    async def test_generate_dashboard_with_alerts(
        self, mock_staleness, mock_quality, mock_health
    ):
        """Test dashboard generation with active alerts."""
        # Given: Mock data with alerts
        mock_health.return_value = {
            "status": "success",
            "overall_status": "degraded",
            "services": {
                "redis": {
                    "status": "degraded",
                    "response_time_ms": 150.0,
                    "details": {},
                }
            },
            "alerts": [
                "High Redis response time: 150.0ms",
                "Memory usage above threshold",
                "Docker container unhealthy",
            ],
            "summary": {"total_alerts": 3},
        }

        mock_quality.return_value = {"status": "success", "summary": {}}
        mock_staleness.return_value = {"stale_pairs": [], "fresh_pairs": []}

        dashboard = MonitoringDashboard()

        # When: Generating dashboard
        result = await dashboard.generate_dashboard()

        # Then: Alerts are displayed
        assert "🟡 OVERALL STATUS: DEGRADED" in result
        assert "🚨 Active Alerts: 3" in result
        assert "🚨 ACTIVE ALERTS:" in result
        assert "High Redis response time: 150.0ms" in result
        assert "Memory usage above threshold" in result

    @pytest.mark.asyncio
    @patch.object(MonitoringDashboard, "get_infrastructure_health")
    @patch.object(MonitoringDashboard, "get_data_quality")
    @patch.object(MonitoringDashboard, "get_data_staleness")
    async def test_generate_dashboard_health_check_error(
        self, mock_staleness, mock_quality, mock_health
    ):
        """Test dashboard generation when health check fails."""
        # Given: Mock health check error
        mock_health.return_value = {"status": "error", "error": "Connection refused"}
        mock_quality.return_value = {"status": "success", "summary": {}}
        mock_staleness.return_value = {"stale_pairs": [], "fresh_pairs": []}

        dashboard = MonitoringDashboard()

        # When: Generating dashboard
        result = await dashboard.generate_dashboard()

        # Then: Error status is shown
        assert "🔴 OVERALL STATUS: MONITORING ERROR" in result
        assert "❌ Health check failed: Connection refused" in result

    @pytest.mark.asyncio
    @patch.object(MonitoringDashboard, "get_infrastructure_health")
    @patch.object(MonitoringDashboard, "get_data_quality")
    @patch.object(MonitoringDashboard, "get_data_staleness")
    async def test_generate_dashboard_parallel_execution(
        self, mock_staleness, mock_quality, mock_health
    ):
        """Test that dashboard generation runs checks in parallel."""
        # Given: Mock methods that can track call timing
        call_order = []

        async def track_health():
            call_order.append("health_start")
            await asyncio.sleep(0.1)
            call_order.append("health_end")
            return {
                "status": "success",
                "overall_status": "healthy",
                "services": {},
                "alerts": [],
                "summary": {},
            }

        async def track_quality():
            call_order.append("quality_start")
            await asyncio.sleep(0.1)
            call_order.append("quality_end")
            return {"status": "success", "summary": {}}

        async def track_staleness():
            call_order.append("staleness_start")
            await asyncio.sleep(0.1)
            call_order.append("staleness_end")
            return {"stale_pairs": [], "fresh_pairs": []}

        mock_health.side_effect = track_health
        mock_quality.side_effect = track_quality
        mock_staleness.side_effect = track_staleness

        dashboard = MonitoringDashboard()

        # When: Generating dashboard
        await dashboard.generate_dashboard()

        # Then: All start calls should come before any end calls (parallel execution)
        start_indices = [
            call_order.index(call) for call in call_order if call.endswith("_start")
        ]
        end_indices = [
            call_order.index(call) for call in call_order if call.endswith("_end")
        ]

        assert max(start_indices) < min(
            end_indices
        ), f"Calls not parallel: {call_order}"


class TestContinuousMonitoring:
    """Test continuous monitoring functionality."""

    @pytest.mark.asyncio
    @patch("builtins.print")
    @patch.object(MonitoringDashboard, "generate_dashboard")
    async def test_run_continuous_monitoring_keyboard_interrupt(
        self, mock_generate, mock_print
    ):
        """Test continuous monitoring handles keyboard interrupt."""
        # Given: Dashboard that generates once then gets interrupted
        mock_generate.return_value = "Mock Dashboard Content"

        # Mock sleep to raise KeyboardInterrupt after first iteration
        with patch("asyncio.sleep", side_effect=KeyboardInterrupt()):
            dashboard = MonitoringDashboard()

            # When: Running continuous monitoring
            await dashboard.run_continuous_monitoring(interval_seconds=1)

            # Then: Dashboard is generated once and stop message is shown
            mock_generate.assert_called_once()
            # Check that stop message was printed
            stop_calls = [
                call
                for call in mock_print.call_args_list
                if "stopped by user" in str(call)
            ]
            assert len(stop_calls) > 0


class TestMainFunction:
    """Test main function and command line interface."""

    @pytest.mark.asyncio
    @patch("argparse.ArgumentParser.parse_args")
    @patch.object(MonitoringDashboard, "generate_dashboard")
    async def test_main_single_dashboard_generation(
        self, mock_generate, mock_parse_args
    ):
        """Test main function with single dashboard generation."""
        # Given: Args for single generation
        mock_args = Mock()
        mock_args.continuous = False
        mock_args.save = None
        mock_parse_args.return_value = mock_args

        mock_generate.return_value = "Test Dashboard"

        # Import and run main function
        from monitoring_dashboard import main

        # When: Running main
        await main()

        # Then: Dashboard is generated once
        mock_generate.assert_called_once()

    @pytest.mark.asyncio
    @patch("argparse.ArgumentParser.parse_args")
    @patch.object(MonitoringDashboard, "generate_dashboard")
    @patch("builtins.open", new_callable=Mock)
    async def test_main_save_dashboard(self, mock_open, mock_generate, mock_parse_args):
        """Test main function saves dashboard to file."""
        # Given: Args with save option
        mock_args = Mock()
        mock_args.continuous = False
        mock_args.save = "/tmp/dashboard.txt"
        mock_parse_args.return_value = mock_args

        mock_generate.return_value = "Test Dashboard Content"
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file

        from monitoring_dashboard import main

        # When: Running main
        await main()

        # Then: Dashboard is saved to file
        mock_open.assert_called_once_with("/tmp/dashboard.txt", "w")
        mock_file.write.assert_called_once_with("Test Dashboard Content")

    @pytest.mark.asyncio
    @patch("argparse.ArgumentParser.parse_args")
    @patch.object(MonitoringDashboard, "run_continuous_monitoring")
    async def test_main_continuous_monitoring(self, mock_continuous, mock_parse_args):
        """Test main function with continuous monitoring."""
        # Given: Args for continuous monitoring
        mock_args = Mock()
        mock_args.continuous = True
        mock_args.interval = 60
        mock_parse_args.return_value = mock_args

        from monitoring_dashboard import main

        # When: Running main
        await main()

        # Then: Continuous monitoring is started
        mock_continuous.assert_called_once_with(60)


class TestProductionBehaviorValidation:
    """Test against known production behavior patterns."""

    @pytest.mark.integration
    def test_dashboard_uses_correct_venv_path(self):
        """Test dashboard uses correct virtual environment path."""
        # Given: Dashboard instance
        dashboard = MonitoringDashboard()

        # When: Checking venv path
        # Then: Points to monitoring-specific venv
        assert "venv-monitoring" in str(dashboard.venv_path)
        assert dashboard.venv_path.is_absolute()

    def test_dashboard_script_timeout_appropriate(self):
        """Test script timeout is appropriate for production monitoring."""
        # Given: Dashboard instance
        dashboard = MonitoringDashboard()

        # When: Looking at timeout in _run_script (hardcoded)
        # Then: 120 seconds is reasonable for monitoring scripts
        # This is tested indirectly through the timeout parameter in subprocess calls
        # Validate monitoring timeout configuration
        assert (
            dashboard.refresh_timeout == 120
        ), "Dashboard refresh timeout should be 120 seconds"
        assert (
            dashboard.alert_timeout == 30
        ), "Alert timeout should be shorter than refresh timeout"
        assert dashboard.is_configured, "Dashboard should be properly configured"

    def test_dashboard_includes_all_monitoring_components(self):
        """Test dashboard includes all expected monitoring components."""
        # Given: Dashboard instance
        dashboard = MonitoringDashboard()

        # When: Checking configured scripts
        script_names = [
            dashboard.health_monitor.name,
            dashboard.quality_validator.name,
            dashboard.data_updater.name,
        ]

        # Then: All key monitoring scripts are configured
        assert "infrastructure_health_monitor.py" in script_names
        assert "data_quality_validator.py" in script_names
        assert "automated_data_updates.py" in script_names

    @pytest.mark.asyncio
    async def test_dashboard_handles_realistic_data_structures(self):
        """Test dashboard handles realistic production data structures."""
        # Given: Dashboard with realistic production-like data
        dashboard = MonitoringDashboard()

        # Realistic service data structure
        services_data = {
            "redis": {
                "status": "healthy",
                "response_time_ms": 25.3,
                "details": {
                    "version": "6.2.7",
                    "connected_clients": 4,
                    "used_memory": "2.1M",
                    "uptime_seconds": 86400,
                },
            },
            "rabbitmq": {
                "status": "degraded",
                "response_time_ms": 145.2,
                "details": {"connection_state": "open", "channel_state": "open"},
            },
            "docker": {
                "status": "healthy",
                "response_time_ms": 33.1,
                "details": {
                    "fxml4-api": {"status": "running", "health": "healthy"},
                    "fxml4-forex-rabbitmq": {
                        "status": "running",
                        "health": "no_healthcheck",
                    },
                    "fxml4-redis": {"status": "running", "health": "healthy"},
                },
            },
            "system": {
                "status": "healthy",
                "response_time_ms": 12.5,
                "details": {
                    "cpu_percent": 35.7,
                    "memory_percent": 0.62,
                    "disk_percent": 0.45,
                    "memory_available_gb": 8.2,
                    "disk_free_gb": 256.7,
                },
            },
        }

        # When: Formatting this realistic data
        result = dashboard.format_service_status(services_data)

        # Then: All components are handled correctly
        assert "✅ REDIS: healthy" in result
        assert "⚠️  RABBITMQ: degraded" in result
        assert "✅ DOCKER: healthy" in result
        assert "✅ SYSTEM: healthy" in result
        assert "Redis 6.2.7" in result
        assert "CPU: 35.7%" in result
        assert "3 containers running" in result  # Count of running containers


@pytest.mark.slow
class TestPerformanceBehavior:
    """Test performance characteristics of monitoring dashboard."""

    @pytest.mark.asyncio
    @patch.object(MonitoringDashboard, "get_infrastructure_health")
    @patch.object(MonitoringDashboard, "get_data_quality")
    @patch.object(MonitoringDashboard, "get_data_staleness")
    async def test_dashboard_generation_performance(
        self, mock_staleness, mock_quality, mock_health
    ):
        """Test dashboard generation completes in reasonable time."""
        # Given: Mock methods that return quickly
        mock_health.return_value = {
            "status": "success",
            "overall_status": "healthy",
            "services": {},
            "alerts": [],
            "summary": {},
        }
        mock_quality.return_value = {"status": "success", "summary": {}}
        mock_staleness.return_value = {"stale_pairs": [], "fresh_pairs": []}

        dashboard = MonitoringDashboard()

        # When: Generating dashboard
        start_time = datetime.now()
        await dashboard.generate_dashboard()
        elapsed = (datetime.now() - start_time).total_seconds()

        # Then: Completes within reasonable time
        assert elapsed < 5.0  # Should complete in under 5 seconds


class TestErrorHandling:
    """Test error handling in monitoring dashboard."""

    def test_format_service_status_missing_fields(self):
        """Test service status formatting handles missing fields gracefully."""
        # Given: Service data with missing fields
        dashboard = MonitoringDashboard()
        services = {
            "redis": {
                # Missing status, response_time_ms, details
            },
            "system": {
                "status": "healthy",
                "details": {
                    # Missing some system metrics
                    "cpu_percent": 25.0
                    # Missing memory_percent, disk_percent
                },
            },
        }

        # When: Formatting service status
        # Then: Should not raise exceptions
        result = dashboard.format_service_status(services)
        assert isinstance(result, str)
        assert "REDIS" in result
        assert "SYSTEM" in result

    def test_format_data_quality_missing_summary(self):
        """Test data quality formatting handles missing summary gracefully."""
        # Given: Quality data with missing summary
        dashboard = MonitoringDashboard()
        quality_data = {
            "status": "success"
            # Missing summary, recommendations
        }

        # When: Formatting data quality
        # Then: Should not raise exceptions
        result = dashboard.format_data_quality(quality_data)
        assert "📊 Data Quality Overview:" in result

    def test_format_data_staleness_missing_fields(self):
        """Test staleness formatting handles missing fields gracefully."""
        # Given: Staleness data with missing fields
        dashboard = MonitoringDashboard()
        staleness_data = {
            # Missing stale_pairs, fresh_pairs, update_needed
        }

        # When: Formatting data staleness
        # Then: Should not raise exceptions
        result = dashboard.format_data_staleness(staleness_data)
        assert "📅 Data Freshness Status:" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
