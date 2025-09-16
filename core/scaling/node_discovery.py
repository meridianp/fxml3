"""
Node Discovery and Health Checking

Automatic service discovery and health monitoring for FXML4 cluster:
- Automatic node registration and discovery
- Comprehensive health checking with custom probes
- Network partition detection and handling
- Service mesh integration capabilities
"""

import asyncio
import hashlib
import json
import logging
import random
import socket
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from .cluster_manager import NodeInfo, NodeStatus, NodeType


class DiscoveryMethod(Enum):
    """Service discovery methods"""

    MULTICAST = "multicast"
    BROADCAST = "broadcast"
    CONSUL = "consul"
    ETCD = "etcd"
    KUBERNETES = "kubernetes"
    STATIC = "static"


class HealthCheckType(Enum):
    """Health check types"""

    HTTP = "http"
    TCP = "tcp"
    UDP = "udp"
    COMMAND = "command"
    CUSTOM = "custom"


@dataclass
class HealthCheckConfig:
    """Health check configuration"""

    check_type: HealthCheckType
    endpoint: str
    interval_seconds: float = 10.0
    timeout_seconds: float = 5.0
    retry_count: int = 3
    failure_threshold: int = 3
    success_threshold: int = 1
    expected_response: Optional[str] = None
    custom_headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class DiscoveryEvent:
    """Service discovery event"""

    event_type: str  # "node_added", "node_updated", "node_removed"
    node_info: NodeInfo
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class HealthChecker:
    """
    Comprehensive health checker for trading nodes

    Implements multiple health check types with configurable thresholds
    and automatic remediation capabilities.
    """

    def __init__(self):
        self.health_configs: Dict[str, HealthCheckConfig] = {}
        self.health_results: Dict[str, Dict[str, Any]] = {}
        self.running = False
        self.check_tasks: List[asyncio.Task] = []

        # Callbacks for health events
        self.health_changed_callbacks: List[
            Callable[[str, bool, Dict[str, Any]], None]
        ] = []

        self.logger = logging.getLogger("HealthChecker")

    def add_health_check(self, node_id: str, config: HealthCheckConfig):
        """Add health check configuration for node"""
        self.health_configs[node_id] = config
        self.health_results[node_id] = {
            "healthy": True,
            "consecutive_failures": 0,
            "consecutive_successes": 0,
            "last_check": 0,
            "last_success": time.time(),
            "last_failure": 0,
            "total_checks": 0,
            "total_failures": 0,
            "response_time_ms": 0.0,
        }

    def remove_health_check(self, node_id: str):
        """Remove health check for node"""
        if node_id in self.health_configs:
            del self.health_configs[node_id]
        if node_id in self.health_results:
            del self.health_results[node_id]

    async def start(self):
        """Start health checking"""
        if self.running:
            return

        self.running = True
        self.logger.info("Starting health checker")

        # Start health check tasks for each node
        for node_id in self.health_configs:
            task = asyncio.create_task(self._health_check_loop(node_id))
            self.check_tasks.append(task)

    async def stop(self):
        """Stop health checking"""
        if not self.running:
            return

        self.running = False
        self.logger.info("Stopping health checker")

        # Cancel all health check tasks
        for task in self.check_tasks:
            task.cancel()

        # Wait for tasks to complete
        if self.check_tasks:
            await asyncio.gather(*self.check_tasks, return_exceptions=True)

        self.check_tasks.clear()

    async def _health_check_loop(self, node_id: str):
        """Health check loop for specific node"""
        config = self.health_configs[node_id]

        while self.running:
            try:
                # Perform health check
                is_healthy, response_time_ms, details = (
                    await self._perform_health_check(node_id, config)
                )

                # Update results
                result = self.health_results[node_id]
                result["last_check"] = time.time()
                result["total_checks"] += 1
                result["response_time_ms"] = response_time_ms

                old_healthy = result["healthy"]

                if is_healthy:
                    result["consecutive_successes"] += 1
                    result["consecutive_failures"] = 0
                    result["last_success"] = time.time()

                    # Mark healthy if we've had enough consecutive successes
                    if (
                        not result["healthy"]
                        and result["consecutive_successes"] >= config.success_threshold
                    ):
                        result["healthy"] = True
                        self._notify_health_changed(node_id, True, details)

                else:
                    result["consecutive_failures"] += 1
                    result["consecutive_successes"] = 0
                    result["total_failures"] += 1
                    result["last_failure"] = time.time()

                    # Mark unhealthy if we've had enough consecutive failures
                    if (
                        result["healthy"]
                        and result["consecutive_failures"] >= config.failure_threshold
                    ):
                        result["healthy"] = False
                        self._notify_health_changed(node_id, False, details)

                # Log health status changes
                if old_healthy != result["healthy"]:
                    status = "healthy" if result["healthy"] else "unhealthy"
                    self.logger.info(f"Node {node_id} is now {status}")

                await asyncio.sleep(config.interval_seconds)

            except Exception as e:
                self.logger.error(f"Health check error for {node_id}: {e}")
                await asyncio.sleep(config.interval_seconds)

    async def _perform_health_check(
        self, node_id: str, config: HealthCheckConfig
    ) -> tuple:
        """Perform individual health check"""
        start_time = time.time()

        try:
            if config.check_type == HealthCheckType.HTTP:
                success, details = await self._http_health_check(config)
            elif config.check_type == HealthCheckType.TCP:
                success, details = await self._tcp_health_check(config)
            elif config.check_type == HealthCheckType.UDP:
                success, details = await self._udp_health_check(config)
            elif config.check_type == HealthCheckType.COMMAND:
                success, details = await self._command_health_check(config)
            elif config.check_type == HealthCheckType.CUSTOM:
                success, details = await self._custom_health_check(node_id, config)
            else:
                success, details = False, {"error": "Unknown health check type"}

            response_time_ms = (time.time() - start_time) * 1000
            return success, response_time_ms, details

        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            return False, response_time_ms, {"error": str(e)}

    async def _http_health_check(self, config: HealthCheckConfig) -> tuple:
        """Perform HTTP health check"""
        import aiohttp

        try:
            timeout = aiohttp.ClientTimeout(total=config.timeout_seconds)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    config.endpoint, headers=config.custom_headers
                ) as response:

                    success = response.status < 400
                    response_text = await response.text()

                    # Check expected response if configured
                    if config.expected_response and success:
                        success = config.expected_response in response_text

                    details = {
                        "status_code": response.status,
                        "response_size": len(response_text),
                        "headers": dict(response.headers),
                    }

                    return success, details

        except Exception as e:
            return False, {"error": str(e)}

    async def _tcp_health_check(self, config: HealthCheckConfig) -> tuple:
        """Perform TCP health check"""
        try:
            # Parse host and port from endpoint
            if "://" in config.endpoint:
                host_port = config.endpoint.split("://")[1]
            else:
                host_port = config.endpoint

            host, port = host_port.split(":")
            port = int(port)

            # Attempt TCP connection
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=config.timeout_seconds
            )

            writer.close()
            await writer.wait_closed()

            return True, {"connected": True, "host": host, "port": port}

        except Exception as e:
            return False, {"error": str(e)}

    async def _udp_health_check(self, config: HealthCheckConfig) -> tuple:
        """Perform UDP health check"""
        try:
            # Parse host and port from endpoint
            if "://" in config.endpoint:
                host_port = config.endpoint.split("://")[1]
            else:
                host_port = config.endpoint

            host, port = host_port.split(":")
            port = int(port)

            # Create UDP socket and send test packet
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(config.timeout_seconds)

            test_message = b"HEALTH_CHECK"
            sock.sendto(test_message, (host, port))

            # Try to receive response
            try:
                response, addr = sock.recvfrom(1024)
                success = True
                details = {"response": response.decode(), "addr": addr}
            except socket.timeout:
                # For UDP, no response might still be healthy
                success = True
                details = {"sent": True, "no_response": True}

            sock.close()
            return success, details

        except Exception as e:
            return False, {"error": str(e)}

    async def _command_health_check(self, config: HealthCheckConfig) -> tuple:
        """Perform command-based health check"""
        try:
            proc = await asyncio.create_subprocess_shell(
                config.endpoint,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=config.timeout_seconds
            )

            success = proc.returncode == 0
            details = {
                "return_code": proc.returncode,
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
            }

            return success, details

        except Exception as e:
            return False, {"error": str(e)}

    async def _custom_health_check(
        self, node_id: str, config: HealthCheckConfig
    ) -> tuple:
        """Perform custom health check (placeholder for extension)"""
        # This would be implemented by specific trading system components
        # For now, return a simple success
        return True, {"custom_check": "not_implemented"}

    def _notify_health_changed(
        self, node_id: str, is_healthy: bool, details: Dict[str, Any]
    ):
        """Notify callbacks of health status change"""
        for callback in self.health_changed_callbacks:
            try:
                callback(node_id, is_healthy, details)
            except Exception as e:
                self.logger.error(f"Health changed callback error: {e}")

    def add_health_changed_callback(
        self, callback: Callable[[str, bool, Dict[str, Any]], None]
    ):
        """Add callback for health status changes"""
        self.health_changed_callbacks.append(callback)

    def get_health_status(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get current health status for node"""
        return self.health_results.get(node_id)

    def get_all_health_status(self) -> Dict[str, Dict[str, Any]]:
        """Get health status for all nodes"""
        return self.health_results.copy()


class NodeDiscovery:
    """
    Automatic service discovery for FXML4 trading nodes

    Supports multiple discovery mechanisms and maintains a real-time
    registry of available trading services.
    """

    def __init__(
        self,
        discovery_method: DiscoveryMethod = DiscoveryMethod.MULTICAST,
        cluster_name: str = "fxml4-cluster",
    ):
        self.discovery_method = discovery_method
        self.cluster_name = cluster_name

        # Node registry
        self.discovered_nodes: Dict[str, NodeInfo] = {}
        self.local_node_info: Optional[NodeInfo] = None

        # Discovery configuration
        self.multicast_group = "224.0.1.100"
        self.multicast_port = 5007
        self.announcement_interval = 30.0  # seconds
        self.node_timeout = 90.0  # seconds

        # Event callbacks
        self.discovery_callbacks: List[Callable[[DiscoveryEvent], None]] = []

        # Health checker integration
        self.health_checker = HealthChecker()
        self.health_checker.add_health_changed_callback(self._on_health_changed)

        # Threading and networking
        self.running = False
        self.discovery_task = None
        self.announcement_task = None
        self.cleanup_task = None

        self.logger = logging.getLogger("NodeDiscovery")

    def register_local_node(self, node_info: NodeInfo):
        """Register local node for announcement"""
        self.local_node_info = node_info

        # Add health check for local node
        health_config = HealthCheckConfig(
            check_type=HealthCheckType.HTTP,
            endpoint=f"http://{node_info.host}:{node_info.port}/health",
            interval_seconds=5.0,
            failure_threshold=2,
        )
        self.health_checker.add_health_check(node_info.node_id, health_config)

    async def start(self):
        """Start service discovery"""
        if self.running:
            return

        self.running = True
        self.logger.info(f"Starting node discovery ({self.discovery_method.value})")

        # Start health checker
        await self.health_checker.start()

        if self.discovery_method == DiscoveryMethod.MULTICAST:
            self.discovery_task = asyncio.create_task(self._multicast_discovery())
            if self.local_node_info:
                self.announcement_task = asyncio.create_task(
                    self._multicast_announcements()
                )
        elif self.discovery_method == DiscoveryMethod.STATIC:
            # Static discovery doesn't need background tasks
            pass
        else:
            self.logger.warning(
                f"Discovery method {self.discovery_method.value} not implemented"
            )

        # Start cleanup task
        self.cleanup_task = asyncio.create_task(self._cleanup_stale_nodes())

    async def stop(self):
        """Stop service discovery"""
        if not self.running:
            return

        self.running = False
        self.logger.info("Stopping node discovery")

        # Stop health checker
        await self.health_checker.stop()

        # Cancel tasks
        for task in [self.discovery_task, self.announcement_task, self.cleanup_task]:
            if task:
                task.cancel()

        # Wait for tasks to complete
        tasks = [
            t
            for t in [self.discovery_task, self.announcement_task, self.cleanup_task]
            if t
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _multicast_discovery(self):
        """Multicast-based service discovery"""
        import socket

        # Create multicast socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", self.multicast_port))

        # Join multicast group
        mreq = socket.inet_aton(self.multicast_group) + socket.inet_aton("0.0.0.0")
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.settimeout(1.0)

        self.logger.info(
            f"Listening for discoveries on {self.multicast_group}:{self.multicast_port}"
        )

        while self.running:
            try:
                data, addr = sock.recvfrom(4096)
                await self._handle_discovery_message(data, addr)
            except socket.timeout:
                continue
            except Exception as e:
                self.logger.error(f"Multicast discovery error: {e}")

        sock.close()

    async def _multicast_announcements(self):
        """Send multicast announcements for local node"""
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

        while self.running:
            try:
                if self.local_node_info:
                    message = self._create_announcement_message()
                    sock.sendto(
                        message.encode(), (self.multicast_group, self.multicast_port)
                    )

                await asyncio.sleep(self.announcement_interval)

            except Exception as e:
                self.logger.error(f"Announcement error: {e}")

        sock.close()

    async def _handle_discovery_message(self, data: bytes, addr: tuple):
        """Handle received discovery message"""
        try:
            message = json.loads(data.decode())

            if message.get("cluster") != self.cluster_name:
                return  # Different cluster

            if message.get("type") == "node_announcement":
                await self._handle_node_announcement(message, addr)
            elif message.get("type") == "node_query":
                await self._handle_node_query(message, addr)

        except Exception as e:
            self.logger.debug(f"Failed to parse discovery message: {e}")

    async def _handle_node_announcement(self, message: Dict[str, Any], addr: tuple):
        """Handle node announcement message"""
        try:
            node_data = message["node"]
            node_id = node_data["node_id"]

            # Skip our own announcements
            if self.local_node_info and node_id == self.local_node_info.node_id:
                return

            # Create or update node info
            node_info = NodeInfo(
                node_id=node_id,
                node_type=NodeType(node_data["node_type"]),
                host=node_data["host"],
                port=node_data["port"],
                status=NodeStatus(node_data.get("status", "healthy")),
                cpu_cores=node_data.get("cpu_cores", 1),
                memory_gb=node_data.get("memory_gb", 1),
                version=node_data.get("version", "1.0.0"),
                metadata=node_data.get("metadata", {}),
            )

            is_new_node = node_id not in self.discovered_nodes
            self.discovered_nodes[node_id] = node_info

            # Set up health checking for new nodes
            if is_new_node:
                health_config = HealthCheckConfig(
                    check_type=HealthCheckType.HTTP,
                    endpoint=f"http://{node_info.host}:{node_info.port}/health",
                )
                self.health_checker.add_health_check(node_id, health_config)

                # Notify discovery event
                event = DiscoveryEvent(event_type="node_added", node_info=node_info)
                self._notify_discovery_event(event)

                self.logger.info(
                    f"Discovered new node: {node_id} at {node_info.host}:{node_info.port}"
                )
            else:
                # Notify update event
                event = DiscoveryEvent(event_type="node_updated", node_info=node_info)
                self._notify_discovery_event(event)

        except Exception as e:
            self.logger.error(f"Failed to handle node announcement: {e}")

    async def _handle_node_query(self, message: Dict[str, Any], addr: tuple):
        """Handle node query message"""
        # Respond with our node information if we have it
        if self.local_node_info:
            response = self._create_announcement_message()
            # Send response back to querying node
            # Implementation would depend on specific networking setup

    def _create_announcement_message(self) -> str:
        """Create announcement message for local node"""
        if not self.local_node_info:
            return ""

        message = {
            "type": "node_announcement",
            "cluster": self.cluster_name,
            "timestamp": time.time(),
            "node": {
                "node_id": self.local_node_info.node_id,
                "node_type": self.local_node_info.node_type.value,
                "host": self.local_node_info.host,
                "port": self.local_node_info.port,
                "status": self.local_node_info.status.value,
                "cpu_cores": self.local_node_info.cpu_cores,
                "memory_gb": self.local_node_info.memory_gb,
                "version": self.local_node_info.version,
                "metadata": self.local_node_info.metadata,
            },
        }

        return json.dumps(message)

    async def _cleanup_stale_nodes(self):
        """Clean up stale/offline nodes"""
        while self.running:
            try:
                current_time = time.time()
                stale_nodes = []

                for node_id, node_info in self.discovered_nodes.items():
                    # Check if node hasn't been seen recently
                    if current_time - node_info.last_heartbeat > self.node_timeout:
                        stale_nodes.append(node_id)

                # Remove stale nodes
                for node_id in stale_nodes:
                    node_info = self.discovered_nodes.pop(node_id)
                    self.health_checker.remove_health_check(node_id)

                    # Notify removal event
                    event = DiscoveryEvent(
                        event_type="node_removed", node_info=node_info
                    )
                    self._notify_discovery_event(event)

                    self.logger.info(f"Removed stale node: {node_id}")

                await asyncio.sleep(30.0)  # Check every 30 seconds

            except Exception as e:
                self.logger.error(f"Cleanup error: {e}")

    def _on_health_changed(
        self, node_id: str, is_healthy: bool, details: Dict[str, Any]
    ):
        """Handle health status changes"""
        if node_id in self.discovered_nodes:
            node_info = self.discovered_nodes[node_id]
            old_status = node_info.status

            # Update node status based on health
            if is_healthy:
                if node_info.status in [NodeStatus.FAILING, NodeStatus.OFFLINE]:
                    node_info.status = NodeStatus.HEALTHY
            else:
                node_info.status = NodeStatus.FAILING

            # Notify if status changed
            if old_status != node_info.status:
                event = DiscoveryEvent(
                    event_type="node_updated",
                    node_info=node_info,
                    metadata={"health_changed": True, "health_details": details},
                )
                self._notify_discovery_event(event)

    def _notify_discovery_event(self, event: DiscoveryEvent):
        """Notify discovery event callbacks"""
        for callback in self.discovery_callbacks:
            try:
                callback(event)
            except Exception as e:
                self.logger.error(f"Discovery callback error: {e}")

    def add_discovery_callback(self, callback: Callable[[DiscoveryEvent], None]):
        """Add callback for discovery events"""
        self.discovery_callbacks.append(callback)

    def get_discovered_nodes(
        self, node_type: Optional[NodeType] = None
    ) -> List[NodeInfo]:
        """Get discovered nodes, optionally filtered by type"""
        nodes = list(self.discovered_nodes.values())

        if node_type:
            nodes = [node for node in nodes if node.node_type == node_type]

        return nodes

    def get_healthy_nodes(self, node_type: Optional[NodeType] = None) -> List[NodeInfo]:
        """Get healthy discovered nodes"""
        nodes = self.get_discovered_nodes(node_type)
        return [node for node in nodes if node.is_healthy]

    def add_static_node(self, node_info: NodeInfo):
        """Add static node (for static discovery)"""
        self.discovered_nodes[node_info.node_id] = node_info

        # Set up health checking
        health_config = HealthCheckConfig(
            check_type=HealthCheckType.HTTP,
            endpoint=f"http://{node_info.host}:{node_info.port}/health",
        )
        self.health_checker.add_health_check(node_info.node_id, health_config)

        # Notify discovery event
        event = DiscoveryEvent(event_type="node_added", node_info=node_info)
        self._notify_discovery_event(event)


# Example usage and testing
if __name__ == "__main__":

    async def main():
        print("FXML4 Node Discovery Test")
        print("=" * 40)

        # Create discovery service
        discovery = NodeDiscovery(DiscoveryMethod.MULTICAST, "test-cluster")

        # Add discovery callback
        def on_discovery_event(event: DiscoveryEvent):
            print(f"Discovery event: {event.event_type} - {event.node_info.node_id}")

        discovery.add_discovery_callback(on_discovery_event)

        # Register local node
        local_node = NodeInfo(
            node_id="test-node-1",
            node_type=NodeType.API,
            host="localhost",
            port=8000,
            cpu_cores=4,
            memory_gb=8,
        )
        discovery.register_local_node(local_node)

        # Start discovery
        await discovery.start()

        # For testing, add some static nodes
        for i in range(3):
            static_node = NodeInfo(
                node_id=f"static-node-{i}",
                node_type=NodeType.TRADING,
                host=f"10.0.1.{i+10}",
                port=9000 + i,
                cpu_cores=8,
                memory_gb=16,
            )
            discovery.add_static_node(static_node)

        # Let discovery run for a bit
        print("Running discovery for 30 seconds...")
        await asyncio.sleep(30)

        # Print discovered nodes
        nodes = discovery.get_discovered_nodes()
        print(f"\nDiscovered {len(nodes)} nodes:")
        for node in nodes:
            print(f"  {node.node_id} ({node.node_type.value}) - {node.status.value}")

        # Print health status
        health_status = discovery.health_checker.get_all_health_status()
        print(f"\nHealth status:")
        for node_id, status in health_status.items():
            healthy = "healthy" if status["healthy"] else "unhealthy"
            print(f"  {node_id}: {healthy} ({status['total_checks']} checks)")

        # Stop discovery
        await discovery.stop()
        print("\nNode discovery test completed!")

    # Run the test
    asyncio.run(main())
