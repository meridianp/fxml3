#!/usr/bin/env python3
"""
Test suite for automated data updates system.
Retrospective tests for existing production data freshness maintenance infrastructure.
"""

import asyncio
import json
import os
import subprocess

# Import the module under test
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, patch

import pytest

sys.path.append(str(Path(__file__).parent.parent.parent / "scripts"))
from automated_data_updates import AutomatedDataUpdater


class TestAutomatedDataUpdaterInitialization:
    """Test updater initialization and configuration."""

    def test_initialization_default_path(self):
        """Test updater initialization with default data path."""
        # Given: No custom path
        # When: Creating updater
        updater = AutomatedDataUpdater()

        # Then: Default configuration is applied
        assert updater.data_path == Path("/polygon")
        assert updater.processed_path == Path("/polygon/processed")
        assert updater.logs_path == Path("/polygon/logs/automated_updates")
        assert updater.major_pairs == [
            "EURUSD",
            "GBPUSD",
            "USDJPY",
            "AUDUSD",
            "USDCHF",
            "USDCAD",
        ]

    def test_initialization_custom_path(self):
        """Test updater initialization with custom data path."""
        # Given: Custom data path
        custom_path = "/custom/polygon/data"

        # When: Creating updater
        updater = AutomatedDataUpdater(data_path=custom_path)

        # Then: Custom path is used
        assert updater.data_path == Path(custom_path)
        assert updater.processed_path == Path(custom_path) / "processed"
        assert updater.logs_path == Path(custom_path) / "logs" / "automated_updates"

    @patch.dict(os.environ, {"POLYGON_API_KEY": "test_api_key"})
    def test_initialization_with_api_key(self):
        """Test updater picks up API key from environment."""
        # Given: API key in environment
        # When: Creating updater
        updater = AutomatedDataUpdater()

        # Then: API key is loaded
        assert updater.polygon_api_key == "test_api_key"

    def test_initialization_creates_log_directory(self, tmp_path):
        """Test updater creates log directory structure."""
        # Given: Temporary path
        data_path = tmp_path / "polygon_data"

        # When: Creating updater
        updater = AutomatedDataUpdater(data_path=str(data_path))

        # Then: Log directory is created
        assert updater.logs_path.exists()
        assert updater.logs_path.is_dir()
        assert updater.logs_path.name == "automated_updates"


class TestDataStalenessDetection:
    """Test data staleness detection functionality."""

    def test_detect_staleness_no_data_paths(self, tmp_path):
        """Test staleness detection when no data paths exist."""
        # Given: Empty data directory
        updater = AutomatedDataUpdater(data_path=str(tmp_path))

        # When: Detecting staleness
        staleness_report = updater.detect_staleness()

        # Then: Report shows no pairs analyzed
        assert staleness_report["pairs_analyzed"] == 0
        assert staleness_report["stale_pairs"] == []
        assert staleness_report["fresh_pairs"] == []
        assert staleness_report["update_needed"] is False
        assert "timestamp" in staleness_report
        assert "current_date" in staleness_report

    def test_detect_staleness_with_fresh_data(self, tmp_path):
        """Test staleness detection with fresh data."""
        # Given: Data directory with recent data
        processed_path = tmp_path / "processed"
        symbol_path = processed_path / "C_EURUSD"
        symbol_path.mkdir(parents=True)

        # Create data for today
        today = date.today()
        day_path = (
            symbol_path
            / f"year={today.year}"
            / f"month={today.month}"
            / f"day={today.day}"
        )
        day_path.mkdir(parents=True, exist_ok=True)
        (day_path / "data.parquet.gz").touch()

        updater = AutomatedDataUpdater(data_path=str(tmp_path))

        # When: Detecting staleness
        staleness_report = updater.detect_staleness()

        # Then: EURUSD is reported as fresh
        assert staleness_report["pairs_analyzed"] == 1
        assert len(staleness_report["fresh_pairs"]) == 1
        assert staleness_report["fresh_pairs"][0]["symbol"] == "EURUSD"
        assert staleness_report["fresh_pairs"][0]["days_stale"] == 0
        assert staleness_report["update_needed"] is False

    def test_detect_staleness_with_stale_data(self, tmp_path):
        """Test staleness detection with stale data."""
        # Given: Data directory with old data
        processed_path = tmp_path / "processed"
        symbol_path = processed_path / "C_GBPUSD"
        symbol_path.mkdir(parents=True)

        # Create data for 3 days ago (stale)
        stale_date = date.today() - timedelta(days=3)
        day_path = (
            symbol_path
            / f"year={stale_date.year}"
            / f"month={stale_date.month}"
            / f"day={stale_date.day}"
        )
        day_path.mkdir(parents=True, exist_ok=True)
        (day_path / "data.parquet.gz").touch()

        updater = AutomatedDataUpdater(data_path=str(tmp_path))

        # When: Detecting staleness
        staleness_report = updater.detect_staleness()

        # Then: GBPUSD is reported as stale
        assert staleness_report["pairs_analyzed"] == 1
        assert len(staleness_report["stale_pairs"]) == 1
        assert staleness_report["stale_pairs"][0]["symbol"] == "GBPUSD"
        assert staleness_report["stale_pairs"][0]["days_stale"] == 3
        assert staleness_report["update_needed"] is True

    def test_detect_staleness_mixed_freshness(self, tmp_path):
        """Test staleness detection with mixed data freshness."""
        # Given: Data directory with mixed fresh/stale data
        processed_path = tmp_path / "processed"

        # Fresh data for EURUSD (today)
        eurusd_path = processed_path / "C_EURUSD"
        eurusd_path.mkdir(parents=True)
        today = date.today()
        day_path = (
            eurusd_path
            / f"year={today.year}"
            / f"month={today.month}"
            / f"day={today.day}"
        )
        day_path.mkdir(parents=True, exist_ok=True)
        (day_path / "data.parquet.gz").touch()

        # Stale data for GBPUSD (5 days ago)
        gbpusd_path = processed_path / "C_GBPUSD"
        gbpusd_path.mkdir(parents=True)
        stale_date = date.today() - timedelta(days=5)
        day_path = (
            gbpusd_path
            / f"year={stale_date.year}"
            / f"month={stale_date.month}"
            / f"day={stale_date.day}"
        )
        day_path.mkdir(parents=True, exist_ok=True)
        (day_path / "data.parquet.gz").touch()

        updater = AutomatedDataUpdater(data_path=str(tmp_path))

        # When: Detecting staleness
        staleness_report = updater.detect_staleness()

        # Then: Mixed results are reported correctly
        assert staleness_report["pairs_analyzed"] == 2
        assert len(staleness_report["fresh_pairs"]) == 1
        assert len(staleness_report["stale_pairs"]) == 1
        assert staleness_report["fresh_pairs"][0]["symbol"] == "EURUSD"
        assert staleness_report["stale_pairs"][0]["symbol"] == "GBPUSD"
        assert staleness_report["update_needed"] is True

    def test_detect_staleness_finds_latest_date(self, tmp_path):
        """Test staleness detection finds the latest available date."""
        # Given: Data directory with multiple dates
        processed_path = tmp_path / "processed"
        symbol_path = processed_path / "C_USDJPY"
        symbol_path.mkdir(parents=True)

        # Create data for multiple dates
        dates = [
            date.today() - timedelta(days=10),  # Oldest
            date.today() - timedelta(days=5),  # Middle
            date.today() - timedelta(days=2),  # Latest (should be detected)
        ]

        for test_date in dates:
            day_path = (
                symbol_path
                / f"year={test_date.year}"
                / f"month={test_date.month}"
                / f"day={test_date.day}"
            )
            day_path.mkdir(parents=True, exist_ok=True)
            (day_path / "data.parquet.gz").touch()

        updater = AutomatedDataUpdater(data_path=str(tmp_path))

        # When: Detecting staleness
        staleness_report = updater.detect_staleness()

        # Then: Latest date is correctly identified
        assert staleness_report["pairs_analyzed"] == 1
        assert len(staleness_report["stale_pairs"]) == 1
        stale_pair = staleness_report["stale_pairs"][0]
        assert stale_pair["symbol"] == "USDJPY"
        assert stale_pair["days_stale"] == 2  # Based on latest date
        assert (
            stale_pair["latest_date"] == (date.today() - timedelta(days=2)).isoformat()
        )


class TestStaleDataUpdating:
    """Test stale data updating functionality."""

    @pytest.mark.asyncio
    async def test_update_stale_data_no_updates_needed(self, tmp_path):
        """Test update when no data is stale."""
        # Given: Updater with fresh data
        updater = AutomatedDataUpdater(data_path=str(tmp_path))

        # Mock detect_staleness to return no stale data
        with patch.object(updater, "detect_staleness") as mock_detect:
            mock_detect.return_value = {"update_needed": False, "stale_pairs": []}

            # When: Running update
            result = await updater.update_stale_data()

            # Then: No updates are performed
            assert result["status"] == "success"
            assert result["message"] == "No updates needed"
            assert result["pairs_updated"] == 0

    @pytest.mark.asyncio
    async def test_update_stale_data_no_api_key(self, tmp_path):
        """Test update fails gracefully without API key."""
        # Given: Updater without API key
        updater = AutomatedDataUpdater(data_path=str(tmp_path))
        updater.polygon_api_key = None

        # Mock detect_staleness to return stale data
        with patch.object(updater, "detect_staleness") as mock_detect:
            mock_detect.return_value = {
                "update_needed": True,
                "stale_pairs": [{"symbol": "EURUSD", "latest_date": "2023-01-01"}],
            }

            # When: Running update
            result = await updater.update_stale_data()

            # Then: Error is returned
            assert result["status"] == "error"
            assert "No Polygon API key" in result["message"]
            assert result["pairs_updated"] == 0

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"POLYGON_API_KEY": "test_key"})
    @patch("subprocess.run")
    async def test_update_stale_data_successful_backfill(
        self, mock_subprocess, tmp_path
    ):
        """Test successful stale data update."""
        # Given: Updater with API key and stale data
        updater = AutomatedDataUpdater(data_path=str(tmp_path))

        # Mock successful subprocess result
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = (
            json.dumps({"files_created": 3, "records_processed": 1440}) + "\n"
        )
        mock_subprocess.return_value = mock_result

        # Mock detect_staleness
        stale_date = date.today() - timedelta(days=3)
        with patch.object(updater, "detect_staleness") as mock_detect:
            mock_detect.return_value = {
                "update_needed": True,
                "stale_pairs": [
                    {
                        "symbol": "EURUSD",
                        "latest_date": stale_date.isoformat(),
                        "days_stale": 3,
                    }
                ],
            }

            # When: Running update
            result = await updater.update_stale_data()

            # Then: Update is successful
            assert result["status"] == "success"
            assert result["pairs_updated"] == 1
            assert result["total_records_added"] == 1440
            assert len(result["pair_results"]) == 1

            pair_result = result["pair_results"][0]
            assert pair_result["symbol"] == "EURUSD"
            assert pair_result["status"] == "success"
            assert pair_result["records_processed"] == 1440

            # Verify subprocess was called with correct parameters
            mock_subprocess.assert_called_once()
            call_args = mock_subprocess.call_args
            assert "scripts/polygon_backfill_system.py" in call_args[0][0]
            assert "--backfill" in call_args[0][0]
            assert "EURUSD" in call_args[0][0]

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"POLYGON_API_KEY": "test_key"})
    @patch("subprocess.run")
    async def test_update_stale_data_backfill_error(self, mock_subprocess, tmp_path):
        """Test handling of backfill subprocess errors."""
        # Given: Updater with failing subprocess
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "API rate limit exceeded"
        mock_subprocess.return_value = mock_result

        updater = AutomatedDataUpdater(data_path=str(tmp_path))

        stale_date = date.today() - timedelta(days=2)
        with patch.object(updater, "detect_staleness") as mock_detect:
            mock_detect.return_value = {
                "update_needed": True,
                "stale_pairs": [
                    {
                        "symbol": "GBPUSD",
                        "latest_date": stale_date.isoformat(),
                        "days_stale": 2,
                    }
                ],
            }

            # When: Running update
            result = await updater.update_stale_data()

            # Then: Error is handled gracefully
            assert result["status"] == "success"  # Overall status still success
            assert result["pairs_updated"] == 0  # But no pairs were updated
            assert len(result["pair_results"]) == 1

            pair_result = result["pair_results"][0]
            assert pair_result["symbol"] == "GBPUSD"
            assert pair_result["status"] == "error"
            assert "API rate limit exceeded" in pair_result["error"]

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"POLYGON_API_KEY": "test_key"})
    @patch("subprocess.run")
    async def test_update_stale_data_timeout(self, mock_subprocess, tmp_path):
        """Test handling of subprocess timeout."""
        # Given: Subprocess that times out
        mock_subprocess.side_effect = subprocess.TimeoutExpired("cmd", 300)

        updater = AutomatedDataUpdater(data_path=str(tmp_path))

        stale_date = date.today() - timedelta(days=1)
        with patch.object(updater, "detect_staleness") as mock_detect:
            mock_detect.return_value = {
                "update_needed": True,
                "stale_pairs": [
                    {
                        "symbol": "USDJPY",
                        "latest_date": stale_date.isoformat(),
                        "days_stale": 1,
                    }
                ],
            }

            # When: Running update
            result = await updater.update_stale_data()

            # Then: Timeout is handled
            assert result["pairs_updated"] == 0
            pair_result = result["pair_results"][0]
            assert pair_result["symbol"] == "USDJPY"
            assert pair_result["status"] == "timeout"
            assert "timed out" in pair_result["error"]

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"POLYGON_API_KEY": "test_key"})
    @patch("subprocess.run")
    async def test_update_stale_data_saves_log(self, mock_subprocess, tmp_path):
        """Test that update results are saved to log file."""
        # Given: Successful update
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = (
            json.dumps({"files_created": 1, "records_processed": 500}) + "\n"
        )
        mock_subprocess.return_value = mock_result

        updater = AutomatedDataUpdater(data_path=str(tmp_path))

        stale_date = date.today() - timedelta(days=1)
        with patch.object(updater, "detect_staleness") as mock_detect:
            mock_detect.return_value = {
                "update_needed": True,
                "stale_pairs": [
                    {
                        "symbol": "AUDUSD",
                        "latest_date": stale_date.isoformat(),
                        "days_stale": 1,
                    }
                ],
            }

            # When: Running update
            await updater.update_stale_data()

            # Then: Log file is created
            log_files = list(updater.logs_path.glob("update_*.json"))
            assert len(log_files) == 1

            # Verify log content
            with open(log_files[0]) as f:
                log_data = json.load(f)
            assert log_data["pairs_updated"] == 1
            assert log_data["total_records_added"] == 500

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"POLYGON_API_KEY": "test_key"})
    @patch("subprocess.run")
    async def test_update_stale_data_date_range_calculation(
        self, mock_subprocess, tmp_path
    ):
        """Test correct date range calculation for backfill."""
        # Given: Stale data scenario
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"records_processed": 100}) + "\n"
        mock_subprocess.return_value = mock_result

        updater = AutomatedDataUpdater(data_path=str(tmp_path))

        # Data is 5 days stale
        latest_data_date = date.today() - timedelta(days=5)
        with patch.object(updater, "detect_staleness") as mock_detect:
            mock_detect.return_value = {
                "update_needed": True,
                "stale_pairs": [
                    {
                        "symbol": "USDCAD",
                        "latest_date": latest_data_date.isoformat(),
                        "days_stale": 5,
                    }
                ],
            }

            # When: Running update
            await updater.update_stale_data()

            # Then: Correct date range is calculated
            call_args = mock_subprocess.call_args[0][0]

            # Should start from day after latest data
            expected_start = latest_data_date + timedelta(days=1)
            # Should end yesterday (not today, as today may be incomplete)
            expected_end = date.today() - timedelta(days=1)

            assert expected_start.isoformat() in call_args
            assert expected_end.isoformat() in call_args


class TestDailyUpdateJob:
    """Test daily update job functionality."""

    @patch("asyncio.run")
    def test_run_daily_update_success(self, mock_asyncio_run):
        """Test successful daily update job."""
        # Given: Updater and successful async result
        updater = AutomatedDataUpdater()
        mock_asyncio_run.return_value = {"status": "success", "pairs_updated": 3}

        # When: Running daily update
        # Then: Should not raise exception
        updater.run_daily_update()
        mock_asyncio_run.assert_called_once_with(updater.update_stale_data())

    @patch("asyncio.run")
    def test_run_daily_update_failure(self, mock_asyncio_run):
        """Test daily update job handles failures gracefully."""
        # Given: Updater and failed async result
        updater = AutomatedDataUpdater()
        mock_asyncio_run.return_value = {
            "status": "error",
            "message": "API key missing",
        }

        # When: Running daily update
        # Then: Should not raise exception
        updater.run_daily_update()
        mock_asyncio_run.assert_called_once()

    @patch("asyncio.run")
    def test_run_daily_update_exception(self, mock_asyncio_run):
        """Test daily update job handles exceptions gracefully."""
        # Given: Updater and exception in async call
        updater = AutomatedDataUpdater()
        mock_asyncio_run.side_effect = Exception("Network error")

        # When: Running daily update
        # Then: Should not raise exception (should be caught and logged)
        updater.run_daily_update()
        mock_asyncio_run.assert_called_once()


class TestScheduler:
    """Test scheduler functionality."""

    @patch("schedule.every")
    @patch("time.sleep")
    def test_start_scheduler_configuration(self, mock_sleep, mock_schedule):
        """Test scheduler is configured correctly."""
        # Given: Mock scheduler objects
        mock_day_job = Mock()
        mock_hour_job = Mock()
        mock_schedule.return_value.day.at.return_value.do.return_value = mock_day_job
        mock_schedule.return_value.hours.do.return_value = mock_hour_job

        # Mock schedule.run_pending to exit loop quickly
        with patch("schedule.run_pending") as mock_run_pending:
            mock_sleep.side_effect = KeyboardInterrupt()  # Exit loop

            updater = AutomatedDataUpdater()

            # When: Starting scheduler
            with pytest.raises(KeyboardInterrupt):
                updater.start_scheduler()

            # Then: Jobs are scheduled correctly
            mock_schedule.assert_has_calls(
                [
                    call().day.at("06:00").do(updater.run_daily_update),
                    call(4).hours.do(updater.detect_staleness),
                ]
            )


class TestProductionBehaviorValidation:
    """Test against known production behavior patterns."""

    @pytest.mark.integration
    def test_updater_handles_major_currency_pairs(self):
        """Test updater works with all major currency pairs."""
        # Given: Updater instance
        updater = AutomatedDataUpdater()

        # When: Checking configuration
        # Then: All expected major pairs are configured
        expected_pairs = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD"]
        assert updater.major_pairs == expected_pairs

    def test_updater_uses_production_paths(self):
        """Test updater uses realistic production paths."""
        # Given: Default updater
        updater = AutomatedDataUpdater()

        # When: Checking paths
        # Then: Paths match production structure
        assert str(updater.data_path) == "/polygon"
        assert str(updater.processed_path) == "/polygon/processed"
        assert "automated_updates" in str(updater.logs_path)

    def test_updater_timeout_realistic(self):
        """Test subprocess timeout is realistic for production."""
        # Given: Updater instance
        updater = AutomatedDataUpdater()

        # When: Looking at timeout in update method (hardcoded in implementation)
        # Then: 300 seconds (5 minutes) is reasonable for backfill operations
        # This is tested indirectly through the timeout test above
        # Validate timeout configuration
        assert (
            updater.timeout == 300
        ), "Timeout should be 300 seconds for backfill operations"
        assert updater.max_retries == 3, "Should have appropriate retry limit"
        assert updater.retry_delay == 5, "Should have reasonable retry delay"

    @pytest.mark.asyncio
    async def test_staleness_threshold_production_appropriate(self):
        """Test staleness threshold (> 1 day) is appropriate for production."""
        # Given: Updater and test data
        updater = AutomatedDataUpdater()

        # Mock data that is exactly 1 day stale
        with patch.object(updater, "detect_staleness") as mock_detect:
            mock_detect.return_value = {
                "update_needed": False,  # 1 day is not considered stale
                "stale_pairs": [],
                "fresh_pairs": [{"symbol": "EURUSD", "days_stale": 1}],
            }

            result = await updater.update_stale_data()

            # Then: 1 day staleness doesn't trigger updates (appropriate for forex)
            assert result["message"] == "No updates needed"


class TestErrorHandling:
    """Test error handling in automated updates."""

    def test_detect_staleness_handles_missing_directories(self, tmp_path):
        """Test staleness detection handles missing symbol directories gracefully."""
        # Given: Data path exists but no symbol directories
        processed_path = tmp_path / "processed"
        processed_path.mkdir(parents=True)

        updater = AutomatedDataUpdater(data_path=str(tmp_path))

        # When: Detecting staleness
        staleness_report = updater.detect_staleness()

        # Then: No errors occur, empty results returned
        assert staleness_report["pairs_analyzed"] == 0
        assert staleness_report["stale_pairs"] == []
        assert staleness_report["update_needed"] is False

    def test_detect_staleness_handles_corrupted_directory_structure(self, tmp_path):
        """Test staleness detection handles corrupted directory structures."""
        # Given: Symbol directory with invalid structure
        processed_path = tmp_path / "processed"
        symbol_path = processed_path / "C_EURUSD"
        symbol_path.mkdir(parents=True)

        # Create invalid directory names (not year=, month=, day= format)
        (symbol_path / "invalid_dir").mkdir()
        (symbol_path / "year=2023" / "invalid_month").mkdir(parents=True)

        updater = AutomatedDataUpdater(data_path=str(tmp_path))

        # When: Detecting staleness
        # Then: Should not raise exceptions
        staleness_report = updater.detect_staleness()
        assert isinstance(staleness_report, dict)

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"POLYGON_API_KEY": "test_key"})
    @patch("subprocess.run")
    async def test_update_handles_invalid_json_output(self, mock_subprocess, tmp_path):
        """Test update handles invalid JSON from subprocess."""
        # Given: Subprocess returns invalid JSON
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Invalid JSON output\nSome other output"
        mock_subprocess.return_value = mock_result

        updater = AutomatedDataUpdater(data_path=str(tmp_path))

        with patch.object(updater, "detect_staleness") as mock_detect:
            mock_detect.return_value = {
                "update_needed": True,
                "stale_pairs": [{"symbol": "EURUSD", "latest_date": "2023-01-01"}],
            }

            # When: Running update
            result = await updater.update_stale_data()

            # Then: Handles invalid JSON gracefully
            assert result["pairs_updated"] == 1
            pair_result = result["pair_results"][0]
            assert pair_result["status"] == "success_no_details"
            assert "couldn't parse details" in pair_result["message"]


@pytest.mark.slow
class TestPerformanceBehavior:
    """Test performance characteristics of automated update system."""

    @pytest.mark.asyncio
    async def test_staleness_detection_performance(self, tmp_path):
        """Test staleness detection completes in reasonable time."""
        # Given: Multiple symbol directories with data
        processed_path = tmp_path / "processed"

        for symbol in ["EURUSD", "GBPUSD", "USDJPY"]:
            symbol_path = processed_path / f"C_{symbol}"
            symbol_path.mkdir(parents=True)

            # Create multiple dates for each symbol
            for days_back in range(30):
                test_date = date.today() - timedelta(days=days_back)
                day_path = (
                    symbol_path
                    / f"year={test_date.year}"
                    / f"month={test_date.month}"
                    / f"day={test_date.day}"
                )
                day_path.mkdir(parents=True, exist_ok=True)
                (day_path / "data.parquet.gz").touch()

        updater = AutomatedDataUpdater(data_path=str(tmp_path))

        # When: Detecting staleness
        start_time = datetime.now()
        staleness_report = updater.detect_staleness()
        elapsed = (datetime.now() - start_time).total_seconds()

        # Then: Completes within reasonable time
        assert elapsed < 5.0  # Should complete in under 5 seconds
        assert staleness_report["pairs_analyzed"] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
