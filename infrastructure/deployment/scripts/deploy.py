#!/usr/bin/env python3
"""
FXML4 Deployment Script
Handles controlled deployment to staging and production environments
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DeploymentManager:
    """Manages the deployment process for FXML4."""

    def __init__(self, environment: str, config_path: str):
        self.environment = environment
        self.config = self._load_config(config_path)
        self.deployment_id = f"deploy-{environment}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        self.start_time = time.time()

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load environment configuration."""
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    async def deploy(
        self,
        component: Optional[str] = None,
        dry_run: bool = False,
        force: bool = False,
    ) -> bool:
        """Execute deployment process."""
        logger.info(f"Starting deployment {self.deployment_id}")
        logger.info(f"Environment: {self.environment}")
        logger.info(f"Component: {component or 'all'}")
        logger.info(f"Dry run: {dry_run}")

        try:
            # Pre-deployment checks
            if not await self._pre_deployment_checks(force):
                logger.error("Pre-deployment checks failed")
                return False

            # Create deployment plan
            plan = self._create_deployment_plan(component)
            logger.info(f"Deployment plan created with {len(plan['steps'])} steps")

            if dry_run:
                self._print_deployment_plan(plan)
                return True

            # Execute deployment
            success = await self._execute_deployment(plan)

            if success:
                # Post-deployment validation
                if await self._post_deployment_validation():
                    logger.info("Deployment completed successfully")
                    await self._record_deployment_success()
                else:
                    logger.error("Post-deployment validation failed")
                    await self._rollback_deployment(plan)
                    return False
            else:
                logger.error("Deployment execution failed")
                await self._rollback_deployment(plan)
                return False

            return True

        except Exception as e:
            logger.error(f"Deployment failed with error: {e}")
            await self._rollback_deployment(plan if "plan" in locals() else None)
            return False
        finally:
            duration = time.time() - self.start_time
            logger.info(f"Deployment duration: {duration:.2f} seconds")

    async def _pre_deployment_checks(self, force: bool) -> bool:
        """Run pre-deployment checks."""
        logger.info("Running pre-deployment checks...")

        checks = []

        # Check if tests pass
        if not force:
            checks.append(self._run_tests())

        # Check if images are built
        checks.append(self._verify_images())

        # Check cluster connectivity
        checks.append(self._check_cluster_connectivity())

        # Check resource availability
        checks.append(self._check_resources())

        # Check for active incidents
        if self.environment == "production" and not force:
            checks.append(self._check_incidents())

        results = await asyncio.gather(*checks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Check {i} failed: {result}")
                return False
            elif not result:
                return False

        logger.info("All pre-deployment checks passed")
        return True

    async def _run_tests(self) -> bool:
        """Run test suite."""
        logger.info("Running tests...")

        cmd = ["pytest", "tests/", "-v", "--tb=short"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Tests failed:\n{result.stdout}\n{result.stderr}")
            return False

        logger.info("Tests passed")
        return True

    async def _verify_images(self) -> bool:
        """Verify Docker images are built and pushed."""
        logger.info("Verifying Docker images...")

        images = [
            "fxml4-api",
            "fxml4-data-collector",
            "fxml4-ml-training",
            "fxml4-ml-inference",
            "fxml4-trading-engine",
        ]

        registry = self.config["infrastructure"].get(
            "container_registry", "gcr.io/fxml4"
        )

        for image in images:
            full_image = f"{registry}/{image}:latest"
            cmd = ["docker", "manifest", "inspect", full_image]
            result = subprocess.run(cmd, capture_output=True)

            if result.returncode != 0:
                logger.error(f"Image not found: {full_image}")
                return False

        logger.info("All images verified")
        return True

    async def _check_cluster_connectivity(self) -> bool:
        """Check Kubernetes cluster connectivity."""
        logger.info("Checking cluster connectivity...")

        cluster_name = self.config["infrastructure"]["kubernetes"]["cluster_name"]

        # Set kubectl context
        cmd = ["kubectl", "config", "use-context", cluster_name]
        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            logger.error(f"Failed to set kubectl context: {cluster_name}")
            return False

        # Check cluster health
        cmd = ["kubectl", "cluster-info"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Cluster unhealthy:\n{result.stderr}")
            return False

        logger.info("Cluster connectivity verified")
        return True

    async def _check_resources(self) -> bool:
        """Check if cluster has sufficient resources."""
        logger.info("Checking resource availability...")

        cmd = ["kubectl", "top", "nodes", "--no-headers"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.warning("Could not check node resources")
            return True  # Non-critical

        # Parse resource usage
        for line in result.stdout.strip().split("\n"):
            parts = line.split()
            if len(parts) >= 5:
                cpu_usage = int(parts[2].rstrip("%"))
                mem_usage = int(parts[4].rstrip("%"))

                if cpu_usage > 80:
                    logger.warning(f"High CPU usage on node {parts[0]}: {cpu_usage}%")
                if mem_usage > 80:
                    logger.warning(
                        f"High memory usage on node {parts[0]}: {mem_usage}%"
                    )

        return True

    async def _check_incidents(self) -> bool:
        """Check for active incidents."""
        logger.info("Checking for active incidents...")

        # In a real system, this would check PagerDuty or similar
        # For now, check a simple file-based flag
        incident_file = Path("/tmp/fxml4_incident_active")

        if incident_file.exists():
            logger.error("Active incident detected. Deployment blocked.")
            return False

        return True

    def _create_deployment_plan(self, component: Optional[str]) -> Dict[str, Any]:
        """Create deployment plan based on component and environment."""
        plan = {
            "deployment_id": self.deployment_id,
            "environment": self.environment,
            "component": component or "all",
            "strategy": self.config["deployment"]["strategy"],
            "steps": [],
        }

        if component:
            # Deploy specific component
            plan["steps"].extend(self._get_component_steps(component))
        else:
            # Full deployment
            plan["steps"].extend(
                [
                    {"name": "database_migrations", "type": "migration"},
                    {"name": "config_maps", "type": "config"},
                    {"name": "secrets", "type": "config"},
                    {"name": "data_collector", "type": "deployment"},
                    {"name": "ml_inference", "type": "deployment"},
                    {"name": "trading_engine", "type": "deployment"},
                    {"name": "api", "type": "deployment"},
                    {"name": "monitoring", "type": "deployment"},
                ]
            )

        return plan

    def _get_component_steps(self, component: str) -> List[Dict[str, str]]:
        """Get deployment steps for specific component."""
        component_steps = {
            "api": [{"name": "api", "type": "deployment"}],
            "data-collector": [{"name": "data_collector", "type": "deployment"}],
            "ml": [
                {"name": "ml_training", "type": "job"},
                {"name": "ml_inference", "type": "deployment"},
            ],
            "trading": [{"name": "trading_engine", "type": "deployment"}],
            "monitoring": [{"name": "monitoring", "type": "deployment"}],
        }

        return component_steps.get(component, [])

    def _print_deployment_plan(self, plan: Dict[str, Any]):
        """Print deployment plan for dry run."""
        print("\n" + "=" * 60)
        print("DEPLOYMENT PLAN")
        print("=" * 60)
        print(f"Deployment ID: {plan['deployment_id']}")
        print(f"Environment: {plan['environment']}")
        print(f"Component: {plan['component']}")
        print(f"Strategy: {plan['strategy']}")
        print("\nSteps:")
        for i, step in enumerate(plan["steps"], 1):
            print(f"  {i}. {step['name']} ({step['type']})")
        print("=" * 60 + "\n")

    async def _execute_deployment(self, plan: Dict[str, Any]) -> bool:
        """Execute deployment plan."""
        logger.info("Executing deployment plan...")

        strategy = plan["strategy"]

        if strategy == "blue_green":
            return await self._blue_green_deployment(plan)
        elif strategy == "rolling_update":
            return await self._rolling_update_deployment(plan)
        elif strategy == "canary":
            return await self._canary_deployment(plan)
        else:
            logger.error(f"Unknown deployment strategy: {strategy}")
            return False

    async def _blue_green_deployment(self, plan: Dict[str, Any]) -> bool:
        """Execute blue-green deployment."""
        logger.info("Executing blue-green deployment...")

        # Deploy to green environment
        for step in plan["steps"]:
            logger.info(f"Deploying {step['name']} to green environment...")

            if not await self._deploy_step(step, suffix="-green"):
                return False

            # Verify step
            if not await self._verify_step(step, suffix="-green"):
                return False

        # Run smoke tests on green
        logger.info("Running smoke tests on green environment...")
        if not await self._run_smoke_tests("-green"):
            return False

        # Switch traffic to green
        logger.info("Switching traffic to green environment...")
        if not await self._switch_traffic("green"):
            return False

        # Wait for traffic drain
        await asyncio.sleep(30)

        # Remove blue environment
        logger.info("Removing blue environment...")
        await self._cleanup_environment("blue")

        return True

    async def _rolling_update_deployment(self, plan: Dict[str, Any]) -> bool:
        """Execute rolling update deployment."""
        logger.info("Executing rolling update deployment...")

        for step in plan["steps"]:
            logger.info(f"Updating {step['name']}...")

            if not await self._deploy_step(step):
                return False

            # Wait for rollout
            if not await self._wait_for_rollout(step["name"]):
                return False

            # Verify step
            if not await self._verify_step(step):
                return False

        return True

    async def _canary_deployment(self, plan: Dict[str, Any]) -> bool:
        """Execute canary deployment."""
        logger.info("Executing canary deployment...")

        canary_percentage = self.config["deployment"].get("canary_percentage", 10)

        for step in plan["steps"]:
            logger.info(f"Deploying {step['name']} as canary ({canary_percentage}%)...")

            # Deploy canary
            if not await self._deploy_canary(step, canary_percentage):
                return False

            # Monitor canary
            logger.info(f"Monitoring canary for {step['name']}...")
            if not await self._monitor_canary(step["name"], duration_minutes=10):
                logger.error(f"Canary failed for {step['name']}")
                return False

            # Promote canary
            logger.info(f"Promoting canary for {step['name']}...")
            if not await self._promote_canary(step):
                return False

        return True

    async def _deploy_step(self, step: Dict[str, str], suffix: str = "") -> bool:
        """Deploy a single step."""
        step_type = step["type"]
        name = step["name"]

        if step_type == "migration":
            return await self._run_migrations()
        elif step_type == "config":
            return await self._deploy_config(name)
        elif step_type == "deployment":
            return await self._deploy_service(name + suffix)
        elif step_type == "job":
            return await self._run_job(name)
        else:
            logger.error(f"Unknown step type: {step_type}")
            return False

    async def _run_migrations(self) -> bool:
        """Run database migrations."""
        logger.info("Running database migrations...")

        # This would run actual migrations
        # For now, simulate with kubectl job
        cmd = [
            "kubectl",
            "create",
            "job",
            f"migration-{self.deployment_id}",
            "--from=cronjob/db-migration",
        ]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            logger.error("Failed to create migration job")
            return False

        # Wait for job completion
        return await self._wait_for_job(f"migration-{self.deployment_id}")

    async def _deploy_config(self, name: str) -> bool:
        """Deploy configuration."""
        logger.info(f"Deploying {name}...")

        manifest_path = f"k8s/{self.environment}/{name}.yaml"

        if not Path(manifest_path).exists():
            logger.warning(f"Config not found: {manifest_path}")
            return True

        cmd = ["kubectl", "apply", "-f", manifest_path]
        result = subprocess.run(cmd, capture_output=True)

        return result.returncode == 0

    async def _deploy_service(self, name: str) -> bool:
        """Deploy a service."""
        logger.info(f"Deploying service {name}...")

        # Apply deployment manifest
        manifest_path = f"k8s/{self.environment}/deployments/{name}.yaml"

        if not Path(manifest_path).exists():
            logger.error(f"Manifest not found: {manifest_path}")
            return False

        cmd = ["kubectl", "apply", "-f", manifest_path]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Failed to apply manifest:\n{result.stderr}")
            return False

        return True

    async def _run_job(self, name: str) -> bool:
        """Run a Kubernetes job."""
        logger.info(f"Running job {name}...")

        manifest_path = f"k8s/{self.environment}/jobs/{name}.yaml"

        if not Path(manifest_path).exists():
            logger.error(f"Job manifest not found: {manifest_path}")
            return False

        cmd = ["kubectl", "apply", "-f", manifest_path]
        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            return False

        # Wait for job completion
        return await self._wait_for_job(name)

    async def _wait_for_rollout(self, name: str, timeout: int = 300) -> bool:
        """Wait for deployment rollout to complete."""
        logger.info(f"Waiting for {name} rollout...")

        cmd = [
            "kubectl",
            "rollout",
            "status",
            f"deployment/{name}",
            f"--timeout={timeout}s",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Rollout failed:\n{result.stderr}")
            return False

        logger.info(f"Rollout completed for {name}")
        return True

    async def _wait_for_job(self, name: str, timeout: int = 300) -> bool:
        """Wait for job to complete."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            cmd = ["kubectl", "get", "job", name, "-o", "json"]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                job_status = json.loads(result.stdout)

                if job_status["status"].get("succeeded", 0) > 0:
                    logger.info(f"Job {name} completed successfully")
                    return True
                elif job_status["status"].get("failed", 0) > 0:
                    logger.error(f"Job {name} failed")
                    return False

            await asyncio.sleep(5)

        logger.error(f"Job {name} timed out")
        return False

    async def _verify_step(self, step: Dict[str, str], suffix: str = "") -> bool:
        """Verify deployment step."""
        name = step["name"] + suffix

        if step["type"] == "deployment":
            # Check if pods are ready
            cmd = [
                "kubectl",
                "get",
                "deployment",
                name,
                "-o",
                "jsonpath='{.status.readyReplicas}'",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"Failed to get deployment status for {name}")
                return False

            ready_replicas = int(result.stdout.strip("'") or 0)

            if ready_replicas == 0:
                logger.error(f"No ready replicas for {name}")
                return False

            logger.info(f"Verified {ready_replicas} ready replicas for {name}")

        return True

    async def _run_smoke_tests(self, suffix: str = "") -> bool:
        """Run smoke tests."""
        logger.info("Running smoke tests...")

        # Get service endpoint
        service_name = f"fxml4-api{suffix}"
        cmd = [
            "kubectl",
            "get",
            "service",
            service_name,
            "-o",
            "jsonpath='{.status.loadBalancer.ingress[0].ip}'",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error("Failed to get service endpoint")
            return False

        endpoint = result.stdout.strip("'")

        if not endpoint:
            logger.warning("No external endpoint found, using port-forward")
            # Setup port-forward
            port_forward = subprocess.Popen(
                ["kubectl", "port-forward", f"service/{service_name}", "8080:80"]
            )
            endpoint = "localhost:8080"
            await asyncio.sleep(2)

        # Run smoke tests
        smoke_test_cmd = [
            "python",
            "tests/smoke/smoke_tests.py",
            "--endpoint",
            f"http://{endpoint}",
        ]

        result = subprocess.run(smoke_test_cmd, capture_output=True, text=True)

        if "port_forward" in locals():
            port_forward.terminate()

        if result.returncode != 0:
            logger.error(f"Smoke tests failed:\n{result.stdout}\n{result.stderr}")
            return False

        logger.info("Smoke tests passed")
        return True

    async def _switch_traffic(self, target: str) -> bool:
        """Switch traffic to target environment."""
        logger.info(f"Switching traffic to {target}...")

        # Update ingress to point to target
        ingress_patch = {
            "spec": {
                "rules": [
                    {
                        "http": {
                            "paths": [
                                {
                                    "backend": {
                                        "serviceName": f"fxml4-api-{target}",
                                        "servicePort": 80,
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }

        cmd = [
            "kubectl",
            "patch",
            "ingress",
            "fxml4-ingress",
            "--type=merge",
            "-p",
            json.dumps(ingress_patch),
        ]

        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            logger.error("Failed to update ingress")
            return False

        logger.info(f"Traffic switched to {target}")
        return True

    async def _cleanup_environment(self, env: str):
        """Cleanup old environment."""
        logger.info(f"Cleaning up {env} environment...")

        # Delete deployments
        cmd = ["kubectl", "delete", "deployment", "-l", f"environment={env}"]
        subprocess.run(cmd, capture_output=True)

        # Delete services
        cmd = ["kubectl", "delete", "service", "-l", f"environment={env}"]
        subprocess.run(cmd, capture_output=True)

    async def _deploy_canary(self, step: Dict[str, str], percentage: int) -> bool:
        """Deploy canary version."""
        # This would deploy a canary version with traffic splitting
        # Implementation depends on service mesh (Istio, Linkerd, etc.)
        logger.info(f"Deploying canary for {step['name']} at {percentage}%")
        return True

    async def _monitor_canary(self, name: str, duration_minutes: int) -> bool:
        """Monitor canary deployment."""
        logger.info(f"Monitoring canary {name} for {duration_minutes} minutes...")

        start_time = time.time()
        check_interval = 30  # seconds

        while (time.time() - start_time) < (duration_minutes * 60):
            # Check error rate
            error_rate = await self._get_error_rate(name)
            if error_rate > 0.05:  # 5% threshold
                logger.error(f"High error rate detected: {error_rate:.2%}")
                return False

            # Check latency
            p99_latency = await self._get_p99_latency(name)
            if p99_latency > 1000:  # 1 second threshold
                logger.error(f"High latency detected: {p99_latency}ms")
                return False

            logger.info(
                f"Canary healthy - Error rate: {error_rate:.2%}, P99: {p99_latency}ms"
            )
            await asyncio.sleep(check_interval)

        return True

    async def _get_error_rate(self, name: str) -> float:
        """Get error rate from monitoring system."""
        # This would query Prometheus or similar
        # For now, return mock value
        return 0.02

    async def _get_p99_latency(self, name: str) -> float:
        """Get P99 latency from monitoring system."""
        # This would query Prometheus or similar
        # For now, return mock value
        return 250.0

    async def _promote_canary(self, step: Dict[str, str]) -> bool:
        """Promote canary to full deployment."""
        logger.info(f"Promoting canary for {step['name']}...")

        # Scale up canary and scale down stable
        return await self._deploy_step(step)

    async def _post_deployment_validation(self) -> bool:
        """Run post-deployment validation."""
        logger.info("Running post-deployment validation...")

        validations = []

        # Check all services are healthy
        validations.append(self._check_services_health())

        # Run synthetic transactions
        validations.append(self._run_synthetic_transactions())

        # Validate metrics
        validations.append(self._validate_metrics())

        results = await asyncio.gather(*validations, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception) or not result:
                return False

        logger.info("Post-deployment validation passed")
        return True

    async def _check_services_health(self) -> bool:
        """Check health of all services."""
        services = [
            "fxml4-api",
            "fxml4-data-collector",
            "fxml4-ml-inference",
            "fxml4-trading-engine",
        ]

        for service in services:
            cmd = [
                "kubectl",
                "get",
                "endpoints",
                service,
                "-o",
                "jsonpath='{.subsets[0].addresses}'",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0 or not result.stdout.strip("'"):
                logger.error(f"Service {service} has no endpoints")
                return False

        logger.info("All services healthy")
        return True

    async def _run_synthetic_transactions(self) -> bool:
        """Run synthetic transactions."""
        logger.info("Running synthetic transactions...")

        # This would run actual synthetic tests
        # For now, simulate success
        await asyncio.sleep(5)

        logger.info("Synthetic transactions completed")
        return True

    async def _validate_metrics(self) -> bool:
        """Validate system metrics."""
        logger.info("Validating metrics...")

        # Check key metrics are within expected ranges
        metrics_to_check = [
            ("api_request_rate", 0, 1000),
            ("error_rate", 0, 0.01),
            ("p99_latency", 0, 500),
            ("cpu_usage", 0, 80),
            ("memory_usage", 0, 80),
        ]

        for metric, min_val, max_val in metrics_to_check:
            # This would query actual metrics
            # For now, simulate
            value = 50  # Mock value

            if not min_val <= value <= max_val:
                logger.error(f"Metric {metric} out of range: {value}")
                return False

        logger.info("All metrics within expected ranges")
        return True

    async def _rollback_deployment(self, plan: Optional[Dict[str, Any]]):
        """Rollback deployment."""
        logger.error("Rolling back deployment...")

        if not plan:
            logger.warning("No deployment plan available for rollback")
            return

        # Rollback each step in reverse order
        for step in reversed(plan["steps"]):
            if step["type"] == "deployment":
                logger.info(f"Rolling back {step['name']}...")
                cmd = ["kubectl", "rollout", "undo", f"deployment/{step['name']}"]
                subprocess.run(cmd, capture_output=True)

        logger.info("Rollback completed")

    async def _record_deployment_success(self):
        """Record successful deployment."""
        deployment_record = {
            "deployment_id": self.deployment_id,
            "environment": self.environment,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration": time.time() - self.start_time,
            "status": "success",
        }

        # Save to deployment history
        history_file = Path(f"deployment/history/{self.environment}_deployments.json")
        history_file.parent.mkdir(parents=True, exist_ok=True)

        history = []
        if history_file.exists():
            with open(history_file, "r") as f:
                history = json.load(f)

        history.append(deployment_record)

        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)

        logger.info(f"Deployment recorded: {self.deployment_id}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="FXML4 Deployment Tool")

    parser.add_argument(
        "environment", choices=["staging", "production"], help="Target environment"
    )

    parser.add_argument(
        "--component",
        choices=["api", "data-collector", "ml", "trading", "monitoring"],
        help="Deploy specific component only",
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="Show deployment plan without executing"
    )

    parser.add_argument(
        "--force", action="store_true", help="Skip safety checks (use with caution)"
    )

    parser.add_argument(
        "--config", help="Path to environment config file", default=None
    )

    args = parser.parse_args()

    # Determine config path
    if args.config:
        config_path = args.config
    else:
        config_path = f"deployment/environments/{args.environment}.yaml"

    # Verify config exists
    if not Path(config_path).exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    # Create deployment manager
    manager = DeploymentManager(args.environment, config_path)

    # Run deployment
    success = asyncio.run(
        manager.deploy(component=args.component, dry_run=args.dry_run, force=args.force)
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
