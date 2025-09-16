"""Database isolation and testing utilities."""

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List
from unittest.mock import Mock

logger = logging.getLogger(__name__)


class TransactionalTestCase:
    """Provides transaction-based test isolation."""

    def __init__(self):
        self.in_transaction = False
        self.mock_connection = Mock()
        self.test_data = {}

    def setup(self):
        """Start a test transaction."""
        self.in_transaction = True
        logger.info("Started test transaction")

    def execute_sql(self, sql: str, params: List = None):
        """Execute SQL within the test transaction."""
        if not self.in_transaction:
            raise RuntimeError("Not in transaction")

        # Mock SQL execution with in-memory storage
        if sql.upper().startswith("INSERT"):
            # Simple INSERT simulation
            table_name = "test_table"  # Simplified
            if table_name not in self.test_data:
                self.test_data[table_name] = []
            self.test_data[table_name].append({"name": "test"})

    def query_sql(self, sql: str, params: List = None):
        """Query SQL within the test transaction."""
        if not self.in_transaction:
            raise RuntimeError("Not in transaction")

        # Mock SELECT operations
        if sql.upper().startswith("SELECT COUNT"):
            table_name = "test_table"
            count = len(self.test_data.get(table_name, []))
            return [(count,)]
        return []

    def teardown(self):
        """Rollback the test transaction."""
        self.in_transaction = False
        self.test_data.clear()  # Simulate rollback
        logger.info("Rolled back test transaction")


class SchemaIsolationManager:
    """Manages per-test schema isolation."""

    def __init__(self):
        self.schemas = {}
        self._schema_counter = 0

    def create_test_schema(self):
        """Create an isolated schema for a test."""
        self._schema_counter += 1
        schema_name = f"test_schema_{uuid.uuid4().hex[:8]}"

        schema = TestSchema(schema_name)
        self.schemas[schema_name] = schema

        return schema

    def cleanup_schemas(self):
        """Clean up all test schemas."""
        for schema_name in list(self.schemas.keys()):
            logger.info(f"Dropping schema: {schema_name}")
            del self.schemas[schema_name]


class TestSchema:
    """Represents an isolated test schema."""

    def __init__(self, name: str):
        self.name = name
        self.tables = {}

    def create_table(self, table_name: str, columns: List[str]):
        """Create a table in this schema."""
        self.tables[table_name] = {"columns": columns, "data": []}
        logger.info(f"Created table {table_name} in schema {self.name}")

    def get_table_columns(self, table_name: str) -> List[str]:
        """Get columns for a table."""
        if table_name not in self.tables:
            raise ValueError(f"Table {table_name} does not exist")
        return self.tables[table_name]["columns"]


class ParallelSafeDatabase:
    """Database implementation safe for parallel test execution."""

    def __init__(self):
        self.connections = {}
        self.data_store = {}
        self._lock = threading.Lock()

    def get_connection(self, worker_id: int = None):
        """Get a connection for a specific worker."""
        if worker_id is None:
            worker_id = threading.get_ident()

        if worker_id not in self.connections:
            self.connections[worker_id] = DatabaseConnection(worker_id, self)

        return self.connections[worker_id]


class DatabaseConnection:
    """Mock database connection with thread safety."""

    def __init__(self, worker_id: int, database: ParallelSafeDatabase):
        self.worker_id = worker_id
        self.database = database

    def execute(self, sql: str):
        """Execute SQL with thread safety."""
        with self.database._lock:
            # Simulate INSERT operation
            if "INSERT INTO test_data" in sql:
                if "test_data" not in self.database.data_store:
                    self.database.data_store["test_data"] = []

                # Extract worker_id from SQL (simplified)
                worker_id = self.worker_id
                self.database.data_store["test_data"].append(
                    {"worker_id": worker_id, "data": f"data_from_worker_{worker_id}"}
                )

    def query(self, sql: str, params: List = None):
        """Query with thread safety."""
        with self.database._lock:
            if "SELECT COUNT" in sql and "WHERE worker_id" in sql:
                # Count records for this worker
                worker_records = [
                    record
                    for record in self.database.data_store.get("test_data", [])
                    if record["worker_id"] == self.worker_id
                ]
                return [(len(worker_records),)]
        return [(0,)]
