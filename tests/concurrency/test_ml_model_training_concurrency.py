"""ML model training concurrency tests for FXML4.

Tests concurrent ML model training operations, resource sharing,
model versioning conflicts, and training pipeline coordination.
"""

import asyncio
import random
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest

from tests.utils.concurrency_utils import (
    DeadlockDetector,
    LoadGenerator,
    RaceConditionDetector,
    concurrency_test_environment,
)


@dataclass
class ModelTrainingJob:
    """Model training job specification."""

    job_id: str
    symbol: str
    timeframe: str
    model_type: str
    data_start: datetime
    data_end: datetime
    hyperparameters: Dict[str, Any]
    priority: int = 1
    max_training_time: float = 60.0


class MockMLModelTrainer:
    """Mock ML model trainer for concurrency testing."""

    def __init__(self, max_concurrent_trainings: int = 3):
        self.max_concurrent_trainings = max_concurrent_trainings
        self.active_trainings = {}
        self.completed_trainings = {}
        self.training_semaphore = asyncio.Semaphore(max_concurrent_trainings)
        self.model_registry = {}
        self._lock = asyncio.Lock()
        self.resource_usage = {"cpu_cores": 0, "memory_gb": 0.0, "gpu_utilization": 0.0}
        self.max_resources = {
            "cpu_cores": 8,
            "memory_gb": 32.0,
            "gpu_utilization": 100.0,
        }

    async def start_training(self, job: ModelTrainingJob) -> str:
        """Start model training job."""
        async with self.training_semaphore:
            async with self._lock:
                # Check resource availability
                if not self._check_resource_availability(job):
                    raise ResourceWarning(
                        f"Insufficient resources for job {job.job_id}"
                    )

                # Allocate resources
                self._allocate_resources(job)

                # Track active training
                self.active_trainings[job.job_id] = {
                    "job": job,
                    "start_time": time.perf_counter(),
                    "status": "training",
                    "progress": 0.0,
                    "resource_allocation": self._get_job_resource_allocation(job),
                }

            try:
                # Simulate training process
                await self._simulate_training(job)

                async with self._lock:
                    # Complete training
                    training_info = self.active_trainings.pop(job.job_id)
                    training_info["end_time"] = time.perf_counter()
                    training_info["status"] = "completed"
                    training_info["model_path"] = (
                        f"/models/{job.symbol}_{job.model_type}_{job.job_id}.pkl"
                    )

                    self.completed_trainings[job.job_id] = training_info

                    # Register model
                    model_key = f"{job.symbol}_{job.timeframe}_{job.model_type}"
                    self.model_registry[model_key] = {
                        "job_id": job.job_id,
                        "model_path": training_info["model_path"],
                        "training_time": training_info["end_time"]
                        - training_info["start_time"],
                        "created_at": datetime.now(timezone.utc),
                    }

                    # Release resources
                    self._release_resources(job)

                return job.job_id

            except Exception as e:
                async with self._lock:
                    if job.job_id in self.active_trainings:
                        self.active_trainings[job.job_id]["status"] = "failed"
                        self.active_trainings[job.job_id]["error"] = str(e)
                        del self.active_trainings[job.job_id]
                    self._release_resources(job)
                raise

    def _check_resource_availability(self, job: ModelTrainingJob) -> bool:
        """Check if resources are available for training job."""
        required_resources = self._get_job_resource_allocation(job)

        return (
            self.resource_usage["cpu_cores"] + required_resources["cpu_cores"]
            <= self.max_resources["cpu_cores"]
            and self.resource_usage["memory_gb"] + required_resources["memory_gb"]
            <= self.max_resources["memory_gb"]
            and self.resource_usage["gpu_utilization"]
            + required_resources["gpu_utilization"]
            <= self.max_resources["gpu_utilization"]
        )

    def _get_job_resource_allocation(self, job: ModelTrainingJob) -> Dict[str, float]:
        """Get resource allocation for training job."""
        if job.model_type == "lstm":
            return {"cpu_cores": 2, "memory_gb": 8.0, "gpu_utilization": 50.0}
        elif job.model_type == "transformer":
            return {"cpu_cores": 4, "memory_gb": 16.0, "gpu_utilization": 80.0}
        elif job.model_type == "lightgbm":
            return {"cpu_cores": 3, "memory_gb": 4.0, "gpu_utilization": 0.0}
        else:  # linear
            return {"cpu_cores": 1, "memory_gb": 2.0, "gpu_utilization": 0.0}

    def _allocate_resources(self, job: ModelTrainingJob):
        """Allocate resources for training job."""
        allocation = self._get_job_resource_allocation(job)
        for resource, amount in allocation.items():
            self.resource_usage[resource] += amount

    def _release_resources(self, job: ModelTrainingJob):
        """Release resources from training job."""
        allocation = self._get_job_resource_allocation(job)
        for resource, amount in allocation.items():
            self.resource_usage[resource] = max(
                0, self.resource_usage[resource] - amount
            )

    async def _simulate_training(self, job: ModelTrainingJob):
        """Simulate model training process."""
        training_steps = random.randint(50, 200)
        step_duration = job.max_training_time / training_steps

        for step in range(training_steps):
            # Simulate training step
            await asyncio.sleep(step_duration)

            # Update progress
            async with self._lock:
                if job.job_id in self.active_trainings:
                    self.active_trainings[job.job_id]["progress"] = (
                        step + 1
                    ) / training_steps

            # Simulate occasional training failures
            if random.random() < 0.01:  # 1% chance of failure
                raise RuntimeError(
                    f"Training failed at step {step} for job {job.job_id}"
                )

    async def get_training_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get training job status."""
        async with self._lock:
            if job_id in self.active_trainings:
                return self.active_trainings[job_id].copy()
            elif job_id in self.completed_trainings:
                return self.completed_trainings[job_id].copy()
            else:
                return None

    async def cancel_training(self, job_id: str) -> bool:
        """Cancel active training job."""
        async with self._lock:
            if job_id in self.active_trainings:
                job = self.active_trainings[job_id]["job"]
                self.active_trainings[job_id]["status"] = "cancelled"
                self._release_resources(job)
                del self.active_trainings[job_id]
                return True
            return False

    def get_resource_utilization(self) -> Dict[str, float]:
        """Get current resource utilization."""
        return {
            resource: (usage / self.max_resources[resource]) * 100
            for resource, usage in self.resource_usage.items()
        }

    def get_training_statistics(self) -> Dict[str, Any]:
        """Get training statistics."""
        return {
            "active_trainings": len(self.active_trainings),
            "completed_trainings": len(self.completed_trainings),
            "registered_models": len(self.model_registry),
            "resource_utilization": self.get_resource_utilization(),
        }


class ModelVersioningManager:
    """Manage model versioning and concurrent access."""

    def __init__(self):
        self.model_versions = {}
        self.version_locks = {}
        self._global_lock = asyncio.Lock()

    async def register_model(
        self, model_key: str, model_path: str, metadata: Dict[str, Any]
    ) -> str:
        """Register new model version."""
        async with self._global_lock:
            if model_key not in self.model_versions:
                self.model_versions[model_key] = []
                self.version_locks[model_key] = asyncio.Lock()

            version_id = f"{model_key}_v{len(self.model_versions[model_key]) + 1}"

            version_info = {
                "version_id": version_id,
                "model_path": model_path,
                "metadata": metadata,
                "created_at": datetime.now(timezone.utc),
                "status": "active",
            }

            self.model_versions[model_key].append(version_info)
            return version_id

    async def get_latest_model(self, model_key: str) -> Optional[Dict[str, Any]]:
        """Get latest model version."""
        async with self.version_locks.get(model_key, asyncio.Lock()):
            if model_key in self.model_versions and self.model_versions[model_key]:
                return self.model_versions[model_key][-1].copy()
            return None

    async def update_model_status(
        self, model_key: str, version_id: str, status: str
    ) -> bool:
        """Update model version status."""
        async with self.version_locks.get(model_key, asyncio.Lock()):
            if model_key in self.model_versions:
                for version in self.model_versions[model_key]:
                    if version["version_id"] == version_id:
                        version["status"] = status
                        return True
            return False


@pytest.mark.concurrency
@pytest.mark.ml
class TestMLModelTrainingConcurrency:
    """Test ML model training concurrent operations."""

    @pytest.fixture
    def ml_trainer(self):
        """Create ML model trainer."""
        return MockMLModelTrainer(max_concurrent_trainings=5)

    @pytest.fixture
    def version_manager(self):
        """Create model versioning manager."""
        return ModelVersioningManager()

    @pytest.mark.asyncio
    async def test_concurrent_model_training(self, ml_trainer):
        """Test concurrent model training jobs."""

        async def submit_training_job(job_spec: tuple) -> str:
            """Submit model training job."""
            symbol, model_type, timeframe, priority = job_spec

            job = ModelTrainingJob(
                job_id=f"job_{symbol}_{model_type}_{int(time.time() * 1000)}",
                symbol=symbol,
                timeframe=timeframe,
                model_type=model_type,
                data_start=datetime.now(timezone.utc) - timedelta(days=30),
                data_end=datetime.now(timezone.utc),
                hyperparameters={"learning_rate": 0.001, "epochs": 100},
                priority=priority,
                max_training_time=random.uniform(0.1, 0.5),  # Fast training for testing
            )

            return await ml_trainer.start_training(job)

        # Generate diverse training jobs
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]
        model_types = ["lstm", "transformer", "lightgbm", "linear"]
        timeframes = ["1h", "4h", "1d"]

        training_jobs = []
        for i in range(20):
            symbol = random.choice(symbols)
            model_type = random.choice(model_types)
            timeframe = random.choice(timeframes)
            priority = random.randint(1, 5)
            training_jobs.append((symbol, model_type, timeframe, priority))

        async with concurrency_test_environment(max_concurrent=10) as env:
            result = await env.test_async_operation(
                submit_training_job, training_jobs, max_concurrent=10, timeout=15.0
            )

            # Validate training results
            assert result.operations_completed > 15  # Most should complete
            assert result.operations_failed < 5  # Few failures expected

            # Check resource management
            stats = ml_trainer.get_training_statistics()
            assert stats["active_trainings"] == 0  # All should be completed
            assert stats["completed_trainings"] > 0

            # Verify resource release
            utilization = ml_trainer.get_resource_utilization()
            assert all(util == 0.0 for util in utilization.values())

    @pytest.mark.asyncio
    async def test_resource_contention_management(self, ml_trainer):
        """Test resource contention in concurrent training."""

        async def resource_intensive_training(job_spec: tuple) -> str:
            """Submit resource-intensive training job."""
            job_id, model_type = job_spec

            job = ModelTrainingJob(
                job_id=job_id,
                symbol="EURUSD",
                timeframe="1h",
                model_type=model_type,
                data_start=datetime.now(timezone.utc) - timedelta(days=30),
                data_end=datetime.now(timezone.utc),
                hyperparameters={"learning_rate": 0.001, "epochs": 50},
                max_training_time=0.2,
            )

            return await ml_trainer.start_training(job)

        # Create jobs that will compete for resources
        resource_jobs = [
            (f"transformer_job_{i}", "transformer")  # High resource jobs
            for i in range(8)
        ]

        async with concurrency_test_environment(max_concurrent=8) as env:
            result = await env.test_async_operation(
                resource_intensive_training,
                resource_jobs,
                max_concurrent=8,
                timeout=10.0,
            )

            # Should handle resource contention gracefully
            assert result.operations_completed > 0

            # Some jobs should fail due to resource constraints
            assert result.operations_failed > 0
            assert "Insufficient resources" in str(result.errors)

    @pytest.mark.asyncio
    async def test_model_versioning_concurrency(self, version_manager):
        """Test concurrent model versioning operations."""

        async def concurrent_model_registration(registration_spec: tuple) -> str:
            """Register model concurrently."""
            model_key, iteration = registration_spec

            model_path = f"/models/{model_key}_iter_{iteration}.pkl"
            metadata = {
                "iteration": iteration,
                "accuracy": random.uniform(0.7, 0.95),
                "training_time": random.uniform(60, 300),
            }

            # Simulate concurrent registration attempts
            await asyncio.sleep(random.uniform(0.001, 0.01))

            return await version_manager.register_model(model_key, model_path, metadata)

        # Generate concurrent registrations for same model keys
        model_keys = ["EURUSD_1h_lstm", "GBPUSD_4h_transformer", "USDJPY_1d_lightgbm"]
        registrations = []

        for model_key in model_keys:
            for iteration in range(10):  # 10 versions per model
                registrations.append((model_key, iteration))

        async with concurrency_test_environment(max_concurrent=15) as env:
            result = await env.test_async_operation(
                concurrent_model_registration,
                registrations,
                max_concurrent=15,
                timeout=5.0,
            )

            # All registrations should succeed
            assert result.operations_completed == len(registrations)
            assert result.operations_failed == 0

            # Verify version consistency
            for model_key in model_keys:
                latest_model = await version_manager.get_latest_model(model_key)
                assert latest_model is not None
                assert latest_model["metadata"]["iteration"] == 9  # Last iteration

    @pytest.mark.asyncio
    async def test_training_pipeline_coordination(self, ml_trainer, version_manager):
        """Test coordination between training and versioning."""

        async def coordinated_training_pipeline(pipeline_spec: tuple) -> Dict[str, Any]:
            """Execute coordinated training pipeline."""
            symbol, model_type, timeframe = pipeline_spec

            # Start training
            job = ModelTrainingJob(
                job_id=f"coord_{symbol}_{model_type}_{int(time.time() * 1000)}",
                symbol=symbol,
                timeframe=timeframe,
                model_type=model_type,
                data_start=datetime.now(timezone.utc) - timedelta(days=30),
                data_end=datetime.now(timezone.utc),
                hyperparameters={"learning_rate": 0.001, "epochs": 20},
                max_training_time=0.3,
            )

            job_id = await ml_trainer.start_training(job)

            # Get training status
            status = await ml_trainer.get_training_status(job_id)

            # Register model version
            model_key = f"{symbol}_{timeframe}_{model_type}"
            if status and status["status"] == "completed":
                version_id = await version_manager.register_model(
                    model_key,
                    status["model_path"],
                    {
                        "job_id": job_id,
                        "training_time": status["end_time"] - status["start_time"],
                        "symbol": symbol,
                        "model_type": model_type,
                    },
                )

                return {"job_id": job_id, "version_id": version_id, "status": "success"}
            else:
                return {
                    "job_id": job_id,
                    "status": "failed",
                    "error": status.get("error") if status else "Unknown error",
                }

        # Generate pipeline jobs
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        model_types = ["lstm", "lightgbm"]
        timeframes = ["1h", "4h"]

        pipelines = [
            (symbol, model_type, timeframe)
            for symbol in symbols
            for model_type in model_types
            for timeframe in timeframes
        ]

        async with concurrency_test_environment(max_concurrent=6) as env:
            result = await env.test_async_operation(
                coordinated_training_pipeline, pipelines, max_concurrent=6, timeout=10.0
            )

            # Validate pipeline coordination
            assert result.operations_completed == len(pipelines)
            assert result.operations_failed == 0

            # Verify model registration
            for symbol in symbols:
                for model_type in model_types:
                    for timeframe in timeframes:
                        model_key = f"{symbol}_{timeframe}_{model_type}"
                        latest_model = await version_manager.get_latest_model(model_key)
                        assert latest_model is not None

    @pytest.mark.asyncio
    async def test_training_cancellation_race_conditions(self, ml_trainer):
        """Test race conditions in training job cancellation."""

        async def training_with_cancellation(job_spec: tuple) -> str:
            """Submit training job that might be cancelled."""
            job_id, cancel_delay = job_spec

            job = ModelTrainingJob(
                job_id=job_id,
                symbol="EURUSD",
                timeframe="1h",
                model_type="lstm",
                data_start=datetime.now(timezone.utc) - timedelta(days=30),
                data_end=datetime.now(timezone.utc),
                hyperparameters={"learning_rate": 0.001, "epochs": 100},
                max_training_time=1.0,  # Longer training for cancellation testing
            )

            # Start training
            training_task = asyncio.create_task(ml_trainer.start_training(job))

            # Schedule cancellation
            cancel_task = asyncio.create_task(asyncio.sleep(cancel_delay))

            try:
                # Race between training completion and cancellation
                done, pending = await asyncio.wait(
                    [training_task, cancel_task], return_when=asyncio.FIRST_COMPLETED
                )

                if cancel_task in done:
                    # Cancel training
                    cancelled = await ml_trainer.cancel_training(job_id)
                    training_task.cancel()

                    try:
                        await training_task
                    except asyncio.CancelledError:
                        pass

                    return (
                        f"cancelled_{job_id}"
                        if cancelled
                        else f"cancel_failed_{job_id}"
                    )
                else:
                    # Training completed first
                    cancel_task.cancel()
                    result = await training_task
                    return f"completed_{result}"

            except Exception as e:
                return f"error_{job_id}_{e}"

        # Generate jobs with varying cancellation delays
        cancellation_jobs = [
            (f"cancel_test_{i:03d}", random.uniform(0.05, 0.3)) for i in range(20)
        ]

        async with concurrency_test_environment(max_concurrent=10) as env:
            result = await env.test_async_operation(
                training_with_cancellation,
                cancellation_jobs,
                max_concurrent=10,
                timeout=5.0,
            )

            # Should handle cancellation races gracefully
            assert result.operations_completed == len(cancellation_jobs)
            assert result.operations_failed == 0

            # Verify final state consistency
            stats = ml_trainer.get_training_statistics()
            assert stats["active_trainings"] == 0  # No stuck trainings

            # Check resource cleanup
            utilization = ml_trainer.get_resource_utilization()
            assert all(util == 0.0 for util in utilization.values())


@pytest.mark.concurrency
@pytest.mark.ml
@pytest.mark.performance
class TestMLTrainingPerformance:
    """Performance tests for ML training under concurrent load."""

    @pytest.mark.asyncio
    async def test_training_throughput_benchmark(self):
        """Benchmark training job throughput."""

        trainer = MockMLModelTrainer(max_concurrent_trainings=8)

        async def benchmark_training_job(job_spec: tuple) -> str:
            """Benchmark training job submission."""
            job_id, model_type = job_spec

            job = ModelTrainingJob(
                job_id=job_id,
                symbol="EURUSD",
                timeframe="1h",
                model_type=model_type,
                data_start=datetime.now(timezone.utc) - timedelta(days=7),
                data_end=datetime.now(timezone.utc),
                hyperparameters={"learning_rate": 0.001, "epochs": 10},
                max_training_time=0.1,  # Fast training for throughput test
            )

            return await trainer.start_training(job)

        # Generate benchmark jobs
        model_types = ["linear", "lightgbm"]  # Fast training models
        benchmark_jobs = [
            (f"benchmark_job_{i:04d}", random.choice(model_types)) for i in range(50)
        ]

        start_time = time.perf_counter()

        async with concurrency_test_environment(max_concurrent=8) as env:
            result = await env.test_async_operation(
                benchmark_training_job, benchmark_jobs, max_concurrent=8, timeout=10.0
            )

            end_time = time.perf_counter()

            # Performance requirements
            assert result.operations_completed == 50
            assert result.operations_failed == 0
            assert result.throughput_ops_per_sec > 10  # > 10 trainings/sec
            assert result.avg_response_time < 0.2  # < 200ms average

            # Total time should be reasonable
            total_time = end_time - start_time
            assert total_time < 8.0  # Should complete within 8 seconds

    @pytest.mark.asyncio
    async def test_resource_utilization_efficiency(self):
        """Test efficient resource utilization during training."""

        trainer = MockMLModelTrainer(max_concurrent_trainings=4)

        async def resource_monitoring_training(job_spec: tuple) -> Dict[str, Any]:
            """Training with resource utilization monitoring."""
            job_id, model_type = job_spec

            job = ModelTrainingJob(
                job_id=job_id,
                symbol="GBPUSD",
                timeframe="4h",
                model_type=model_type,
                data_start=datetime.now(timezone.utc) - timedelta(days=14),
                data_end=datetime.now(timezone.utc),
                hyperparameters={"learning_rate": 0.001, "epochs": 20},
                max_training_time=0.3,
            )

            # Monitor resource utilization during training
            start_utilization = trainer.get_resource_utilization()

            result = await trainer.start_training(job)

            end_utilization = trainer.get_resource_utilization()

            return {
                "job_id": result,
                "start_utilization": start_utilization,
                "end_utilization": end_utilization,
            }

        # Mix of resource-intensive jobs
        resource_jobs = [
            (f"resource_job_{i:02d}", model_type)
            for i in range(12)
            for model_type in ["transformer", "lstm"]  # Resource-intensive models
        ]

        async with concurrency_test_environment(max_concurrent=4) as env:
            result = await env.test_async_operation(
                resource_monitoring_training,
                resource_jobs,
                max_concurrent=4,
                timeout=15.0,
            )

            # Should handle resource constraints efficiently
            assert result.operations_completed > 8  # Most should complete
            assert result.throughput_ops_per_sec > 1  # > 1 training/sec

            # Final resource utilization should be zero
            final_utilization = trainer.get_resource_utilization()
            assert all(util == 0.0 for util in final_utilization.values())
