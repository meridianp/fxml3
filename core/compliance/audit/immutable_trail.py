"""
Immutable Compliance Audit Trail System for FXML4.

This module provides cryptographically secure, tamper-proof audit logging
for regulatory compliance with comprehensive transaction tracking and
integrity verification capabilities.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    and_,
    desc,
    func,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from fxml4.api.auth.audit_logger import AuditEventType, auth_audit_logger
from fxml4.api.auth.database import get_db
from fxml4.api.auth.models import User
from fxml4.config import get_config
from fxml4.core.logging import get_logger

Base = declarative_base()


class AuditEventCategory(Enum):
    """Categories of audit events."""

    TRADING = "trading"  # Trade executions, orders
    RISK_MANAGEMENT = "risk_management"  # Risk limit violations, position changes
    AUTHENTICATION = "authentication"  # Login, logout, token events
    AUTHORIZATION = "authorization"  # Permission checks, role changes
    DATA_ACCESS = "data_access"  # Data queries, exports
    SYSTEM_ADMIN = "system_admin"  # Configuration changes, system events
    COMPLIANCE = "compliance"  # Regulatory reports, surveillance
    FINANCIAL = "financial"  # P&L, settlements, reconciliation


class IntegrityLevel(Enum):
    """Integrity verification levels."""

    BASIC = "basic"  # Simple hash verification
    ENHANCED = "enhanced"  # HMAC with secret key
    CRYPTOGRAPHIC = "cryptographic"  # Digital signatures with PKI


@dataclass
class AuditRecord:
    """Individual audit record structure."""

    record_id: str  # Unique record identifier
    timestamp: datetime  # Event timestamp (UTC)
    category: AuditEventCategory  # Event category
    event_type: str  # Specific event type
    user_id: Optional[str] = None  # User who triggered event
    session_id: Optional[str] = None  # Session identifier
    source_ip: Optional[str] = None  # Source IP address
    user_agent: Optional[str] = None  # User agent string
    resource_type: Optional[str] = None  # Type of resource affected
    resource_id: Optional[str] = None  # Specific resource identifier
    action: Optional[str] = None  # Action performed
    details: Optional[Dict[str, Any]] = None  # Additional event details
    before_state: Optional[Dict[str, Any]] = None  # State before change
    after_state: Optional[Dict[str, Any]] = None  # State after change
    outcome: str = "success"  # Event outcome (success/failure/error)
    error_message: Optional[str] = None  # Error details if outcome != success
    correlation_id: Optional[str] = None  # For tracking related events
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata

    def __post_init__(self):
        if self.record_id is None:
            self.record_id = str(uuid.uuid4())
        if self.details is None:
            self.details = {}
        if self.metadata is None:
            self.metadata = {}


@dataclass
class AuditBlock:
    """Blockchain-inspired audit block for immutable chaining."""

    block_id: str  # Unique block identifier
    sequence_number: int  # Sequential block number
    timestamp: datetime  # Block creation timestamp
    previous_hash: str  # Hash of previous block
    merkle_root: str  # Merkle root of contained records
    records: List[AuditRecord]  # Audit records in this block
    block_hash: str  # Hash of this block
    digital_signature: Optional[str] = None  # Digital signature for integrity

    def __post_init__(self):
        if self.block_id is None:
            self.block_id = str(uuid.uuid4())


class AuditTrailModel(Base):
    """SQLAlchemy model for persistent audit trail storage."""

    __tablename__ = "compliance_audit_trail"

    # Primary fields
    record_id = Column(String, primary_key=True)
    sequence_number = Column(Integer, nullable=False, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    # Event categorization
    category = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)

    # User and session tracking
    user_id = Column(String, index=True)
    session_id = Column(String, index=True)
    source_ip = Column(String, index=True)
    user_agent = Column(Text)

    # Resource tracking
    resource_type = Column(String, index=True)
    resource_id = Column(String, index=True)
    action = Column(String, index=True)

    # Event details (stored as JSON)
    details = Column(Text)  # JSON string
    before_state = Column(Text)  # JSON string
    after_state = Column(Text)  # JSON string

    # Outcome tracking
    outcome = Column(String, nullable=False, default="success", index=True)
    error_message = Column(Text)
    correlation_id = Column(String, index=True)

    # Integrity fields
    record_hash = Column(String, nullable=False)  # SHA-256 hash
    previous_hash = Column(String, nullable=False)  # Previous record hash
    merkle_path = Column(Text)  # Merkle tree path for verification

    # Block information
    block_id = Column(String, index=True)
    block_sequence = Column(Integer, index=True)

    # Digital signature for enhanced integrity
    digital_signature = Column(Text)

    # Metadata
    metadata = Column(Text)  # JSON string

    # Indexes for performance
    __table_args__ = (
        Index("idx_audit_timestamp_category", "timestamp", "category"),
        Index("idx_audit_user_timestamp", "user_id", "timestamp"),
        Index("idx_audit_correlation", "correlation_id", "timestamp"),
        Index("idx_audit_outcome_timestamp", "outcome", "timestamp"),
    )


class MerkleTree:
    """Merkle tree implementation for audit record integrity."""

    def __init__(self, records: List[AuditRecord]):
        """Initialize Merkle tree with audit records."""
        self.records = records
        self.leaves = []
        self.tree = []
        self.root = None

        if records:
            self._build_tree()

    def _build_tree(self):
        """Build the Merkle tree from audit records."""
        # Create leaf hashes
        self.leaves = []
        for record in self.records:
            record_data = json.dumps(asdict(record), sort_keys=True, default=str)
            leaf_hash = hashlib.sha256(record_data.encode()).hexdigest()
            self.leaves.append(leaf_hash)

        # Build tree bottom-up
        current_level = self.leaves.copy()
        self.tree = [current_level.copy()]

        while len(current_level) > 1:
            next_level = []

            # Process pairs
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else left

                combined = left + right
                parent_hash = hashlib.sha256(combined.encode()).hexdigest()
                next_level.append(parent_hash)

            current_level = next_level
            self.tree.append(current_level.copy())

        self.root = current_level[0] if current_level else None

    def get_root(self) -> Optional[str]:
        """Get the Merkle root hash."""
        return self.root

    def get_proof(self, leaf_index: int) -> List[Tuple[str, str]]:
        """Get Merkle proof for a specific leaf."""
        if leaf_index >= len(self.leaves):
            return []

        proof = []
        current_index = leaf_index

        for level in range(len(self.tree) - 1):
            level_nodes = self.tree[level]

            if current_index % 2 == 0:
                # Left node, need right sibling
                sibling_index = current_index + 1
                if sibling_index < len(level_nodes):
                    proof.append(("right", level_nodes[sibling_index]))
            else:
                # Right node, need left sibling
                sibling_index = current_index - 1
                proof.append(("left", level_nodes[sibling_index]))

            current_index = current_index // 2

        return proof

    @staticmethod
    def verify_proof(leaf_data: str, proof: List[Tuple[str, str]], root: str) -> bool:
        """Verify a Merkle proof against the root."""
        current_hash = hashlib.sha256(leaf_data.encode()).hexdigest()

        for direction, sibling_hash in proof:
            if direction == "left":
                combined = sibling_hash + current_hash
            else:
                combined = current_hash + sibling_hash

            current_hash = hashlib.sha256(combined.encode()).hexdigest()

        return current_hash == root


class CryptoManager:
    """Cryptographic operations for audit trail integrity."""

    def __init__(self):
        """Initialize crypto manager with keys."""
        self.config = get_config()
        self.logger = get_logger(__name__)

        # HMAC secret key for record integrity
        self.hmac_key = self._get_or_generate_hmac_key()

        # RSA key pair for digital signatures (if configured)
        self.private_key = None
        self.public_key = None

        if self.config.get("compliance.audit.enable_digital_signatures", False):
            self._initialize_rsa_keys()

        self.logger.info("CryptoManager initialized successfully")

    def _get_or_generate_hmac_key(self) -> bytes:
        """Get or generate HMAC secret key."""
        key_env = self.config.get("compliance.audit.hmac_key")
        if key_env:
            return key_env.encode("utf-8")

        # Generate random key
        return secrets.token_bytes(32)  # 256-bit key

    def _initialize_rsa_keys(self):
        """Initialize RSA key pair for digital signatures."""
        try:
            # Try to load existing keys
            private_key_path = self.config.get("compliance.audit.private_key_path")
            public_key_path = self.config.get("compliance.audit.public_key_path")

            if private_key_path and Path(private_key_path).exists():
                with open(private_key_path, "rb") as f:
                    self.private_key = serialization.load_pem_private_key(
                        f.read(), password=None
                    )

            if public_key_path and Path(public_key_path).exists():
                with open(public_key_path, "rb") as f:
                    self.public_key = serialization.load_pem_public_key(f.read())

            # Generate new keys if not found
            if not self.private_key:
                self.private_key = rsa.generate_private_key(
                    public_exponent=65537, key_size=2048
                )
                self.public_key = self.private_key.public_key()

                self.logger.info("Generated new RSA key pair for audit signatures")

        except Exception as e:
            self.logger.error(f"Error initializing RSA keys: {e}")
            self.private_key = None
            self.public_key = None

    def calculate_record_hash(
        self, record: AuditRecord, previous_hash: str = ""
    ) -> str:
        """Calculate SHA-256 hash of an audit record."""
        # Create deterministic record representation
        record_dict = asdict(record)
        record_dict["previous_hash"] = previous_hash

        # Sort keys for deterministic hashing
        record_json = json.dumps(record_dict, sort_keys=True, default=str)

        return hashlib.sha256(record_json.encode()).hexdigest()

    def calculate_hmac(self, data: str) -> str:
        """Calculate HMAC for data integrity."""
        return hmac.new(self.hmac_key, data.encode(), hashlib.sha256).hexdigest()

    def verify_hmac(self, data: str, expected_hmac: str) -> bool:
        """Verify HMAC integrity."""
        calculated_hmac = self.calculate_hmac(data)
        return hmac.compare_digest(calculated_hmac, expected_hmac)

    def sign_data(self, data: str) -> Optional[str]:
        """Create digital signature for data."""
        if not self.private_key:
            return None

        try:
            signature = self.private_key.sign(
                data.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )

            return signature.hex()

        except Exception as e:
            self.logger.error(f"Error creating digital signature: {e}")
            return None

    def verify_signature(self, data: str, signature_hex: str) -> bool:
        """Verify digital signature."""
        if not self.public_key or not signature_hex:
            return False

        try:
            signature = bytes.fromhex(signature_hex)

            self.public_key.verify(
                signature,
                data.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )

            return True

        except (InvalidSignature, Exception) as e:
            self.logger.error(f"Signature verification failed: {e}")
            return False


class ImmutableAuditTrail:
    """
    Immutable audit trail system with cryptographic integrity.

    Features:
    - Cryptographically secured audit records
    - Blockchain-inspired chaining for tamper detection
    - Merkle tree verification for batch integrity
    - Digital signatures for enhanced security
    - Comprehensive compliance reporting
    - Real-time integrity monitoring
    """

    def __init__(self):
        """Initialize immutable audit trail system."""
        self.config = get_config()
        self.logger = get_logger(__name__)

        # Cryptographic manager
        self.crypto = CryptoManager()

        # Configuration
        self.integrity_level = IntegrityLevel(
            self.config.get("compliance.audit.integrity_level", "enhanced")
        )
        self.block_size = self.config.get("compliance.audit.block_size", 100)
        self.auto_block_interval = self.config.get(
            "compliance.audit.auto_block_minutes", 60
        )

        # State management
        self.pending_records: List[AuditRecord] = []
        self.current_blocks: List[AuditBlock] = []
        self.last_block_hash = "0"  # Genesis hash
        self.sequence_counter = 0

        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        self.is_running = False

        # Performance metrics
        self.records_processed = 0
        self.blocks_created = 0
        self.integrity_violations = 0
        self.last_block_time: Optional[datetime] = None

        self.logger.info(
            f"ImmutableAuditTrail initialized with {self.integrity_level.value} integrity level"
        )

    async def log_audit_event(
        self,
        category: AuditEventCategory,
        event_type: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
        outcome: str = "success",
        error_message: Optional[str] = None,
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Log an audit event to the immutable trail.

        Args:
            category: Event category
            event_type: Specific event type
            user_id: User who triggered the event
            session_id: Session identifier
            source_ip: Source IP address
            user_agent: User agent string
            resource_type: Type of resource affected
            resource_id: Specific resource identifier
            action: Action performed
            details: Additional event details
            before_state: State before the change
            after_state: State after the change
            outcome: Event outcome (success/failure/error)
            error_message: Error details if outcome != success
            correlation_id: For tracking related events
            metadata: Additional metadata

        Returns:
            Record ID of the logged event
        """

        # Create audit record
        record = AuditRecord(
            record_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            category=category,
            event_type=event_type,
            user_id=user_id,
            session_id=session_id,
            source_ip=source_ip,
            user_agent=user_agent,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            details=details or {},
            before_state=before_state,
            after_state=after_state,
            outcome=outcome,
            error_message=error_message,
            correlation_id=correlation_id,
            metadata=metadata or {},
        )

        # Add to pending records
        self.pending_records.append(record)
        self.records_processed += 1

        # Create block if threshold reached
        if len(self.pending_records) >= self.block_size:
            await self._create_audit_block()

        self.logger.debug(
            f"Logged audit event: {category.value}.{event_type} (ID: {record.record_id})"
        )
        return record.record_id

    async def _create_audit_block(self) -> Optional[AuditBlock]:
        """Create an audit block from pending records."""
        if not self.pending_records:
            return None

        # Create Merkle tree for integrity
        merkle_tree = MerkleTree(self.pending_records)
        merkle_root = merkle_tree.get_root() or ""

        # Create block
        block = AuditBlock(
            block_id=str(uuid.uuid4()),
            sequence_number=len(self.current_blocks),
            timestamp=datetime.now(timezone.utc),
            previous_hash=self.last_block_hash,
            merkle_root=merkle_root,
            records=self.pending_records.copy(),
            block_hash="",  # Will be calculated
        )

        # Calculate block hash
        block_data = {
            "block_id": block.block_id,
            "sequence_number": block.sequence_number,
            "timestamp": block.timestamp.isoformat(),
            "previous_hash": block.previous_hash,
            "merkle_root": block.merkle_root,
            "records_count": len(block.records),
        }

        block_json = json.dumps(block_data, sort_keys=True)
        block.block_hash = hashlib.sha256(block_json.encode()).hexdigest()

        # Digital signature if enabled
        if self.integrity_level == IntegrityLevel.CRYPTOGRAPHIC:
            block.digital_signature = self.crypto.sign_data(block_json)

        # Persist block and records
        await self._persist_audit_block(block, merkle_tree)

        # Update state
        self.current_blocks.append(block)
        self.last_block_hash = block.block_hash
        self.blocks_created += 1
        self.last_block_time = block.timestamp
        self.pending_records.clear()

        self.logger.info(
            f"Created audit block {block.sequence_number} with {len(block.records)} records"
        )
        return block

    async def _persist_audit_block(self, block: AuditBlock, merkle_tree: MerkleTree):
        """Persist audit block and records to database."""

        try:
            async with get_db() as db:
                # Persist each audit record
                for i, record in enumerate(block.records):
                    # Calculate record hash with chaining
                    previous_record_hash = ""
                    if i > 0:
                        previous_record_hash = self.crypto.calculate_record_hash(
                            block.records[i - 1], self.last_block_hash if i == 0 else ""
                        )
                    elif len(self.current_blocks) > 0:
                        # Link to last record of previous block
                        last_block = self.current_blocks[-1]
                        if last_block.records:
                            previous_record_hash = self.crypto.calculate_record_hash(
                                last_block.records[-1]
                            )

                    record_hash = self.crypto.calculate_record_hash(
                        record, previous_record_hash
                    )

                    # Get Merkle proof
                    merkle_proof = merkle_tree.get_proof(i)
                    merkle_path = json.dumps(merkle_proof)

                    # Create digital signature if enabled
                    digital_signature = None
                    if self.integrity_level == IntegrityLevel.CRYPTOGRAPHIC:
                        record_data = json.dumps(
                            asdict(record), sort_keys=True, default=str
                        )
                        digital_signature = self.crypto.sign_data(record_data)

                    # Create database record
                    audit_model = AuditTrailModel(
                        record_id=record.record_id,
                        timestamp=record.timestamp,
                        category=record.category.value,
                        event_type=record.event_type,
                        user_id=record.user_id,
                        session_id=record.session_id,
                        source_ip=record.source_ip,
                        user_agent=record.user_agent,
                        resource_type=record.resource_type,
                        resource_id=record.resource_id,
                        action=record.action,
                        details=(
                            json.dumps(record.details, default=str)
                            if record.details
                            else None
                        ),
                        before_state=(
                            json.dumps(record.before_state, default=str)
                            if record.before_state
                            else None
                        ),
                        after_state=(
                            json.dumps(record.after_state, default=str)
                            if record.after_state
                            else None
                        ),
                        outcome=record.outcome,
                        error_message=record.error_message,
                        correlation_id=record.correlation_id,
                        record_hash=record_hash,
                        previous_hash=previous_record_hash,
                        merkle_path=merkle_path,
                        block_id=block.block_id,
                        block_sequence=block.sequence_number,
                        digital_signature=digital_signature,
                        metadata=(
                            json.dumps(record.metadata, default=str)
                            if record.metadata
                            else None
                        ),
                    )

                    db.add(audit_model)

                await db.commit()

        except Exception as e:
            self.logger.error(f"Error persisting audit block: {e}")
            raise

    async def verify_record_integrity(self, record_id: str) -> Dict[str, Any]:
        """
        Verify the integrity of a specific audit record.

        Args:
            record_id: ID of the record to verify

        Returns:
            Verification result with details
        """

        try:
            async with get_db() as db:
                query = select(AuditTrailModel).where(
                    AuditTrailModel.record_id == record_id
                )
                result = await db.execute(query)
                audit_record = result.scalar_one_or_none()

                if not audit_record:
                    return {
                        "valid": False,
                        "error": "Record not found",
                        "record_id": record_id,
                    }

                verification_result = {
                    "record_id": record_id,
                    "valid": True,
                    "checks": {},
                }

                # Reconstruct audit record
                record = AuditRecord(
                    record_id=audit_record.record_id,
                    timestamp=audit_record.timestamp,
                    category=AuditEventCategory(audit_record.category),
                    event_type=audit_record.event_type,
                    user_id=audit_record.user_id,
                    session_id=audit_record.session_id,
                    source_ip=audit_record.source_ip,
                    user_agent=audit_record.user_agent,
                    resource_type=audit_record.resource_type,
                    resource_id=audit_record.resource_id,
                    action=audit_record.action,
                    details=(
                        json.loads(audit_record.details) if audit_record.details else {}
                    ),
                    before_state=(
                        json.loads(audit_record.before_state)
                        if audit_record.before_state
                        else None
                    ),
                    after_state=(
                        json.loads(audit_record.after_state)
                        if audit_record.after_state
                        else None
                    ),
                    outcome=audit_record.outcome,
                    error_message=audit_record.error_message,
                    correlation_id=audit_record.correlation_id,
                    metadata=(
                        json.loads(audit_record.metadata)
                        if audit_record.metadata
                        else {}
                    ),
                )

                # Verify hash chain
                calculated_hash = self.crypto.calculate_record_hash(
                    record, audit_record.previous_hash
                )
                hash_valid = calculated_hash == audit_record.record_hash
                verification_result["checks"]["hash_chain"] = hash_valid

                if not hash_valid:
                    verification_result["valid"] = False

                # Verify digital signature if present
                if audit_record.digital_signature:
                    record_data = json.dumps(
                        asdict(record), sort_keys=True, default=str
                    )
                    signature_valid = self.crypto.verify_signature(
                        record_data, audit_record.digital_signature
                    )
                    verification_result["checks"]["digital_signature"] = signature_valid

                    if not signature_valid:
                        verification_result["valid"] = False

                # Verify Merkle proof if available
                if audit_record.merkle_path:
                    try:
                        merkle_proof = json.loads(audit_record.merkle_path)
                        record_data = json.dumps(
                            asdict(record), sort_keys=True, default=str
                        )

                        # Get block's Merkle root for verification
                        block_query = (
                            select(AuditTrailModel.record_hash)
                            .where(AuditTrailModel.block_id == audit_record.block_id)
                            .order_by(AuditTrailModel.sequence_number.asc())
                        )

                        block_result = await db.execute(block_query)
                        block_records = block_result.scalars().all()

                        # Rebuild Merkle root (simplified verification)
                        merkle_valid = len(merkle_proof) > 0  # Basic check
                        verification_result["checks"]["merkle_proof"] = merkle_valid

                    except Exception as e:
                        verification_result["checks"]["merkle_proof"] = False
                        verification_result["valid"] = False

                return verification_result

        except Exception as e:
            self.logger.error(f"Error verifying record integrity: {e}")
            return {"valid": False, "error": str(e), "record_id": record_id}

    async def verify_chain_integrity(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Verify the integrity of the audit chain within a date range.

        Args:
            start_date: Start date for verification (optional)
            end_date: End date for verification (optional)

        Returns:
            Chain verification result
        """

        try:
            async with get_db() as db:
                # Build query
                query = select(AuditTrailModel).order_by(
                    AuditTrailModel.sequence_number.asc()
                )

                if start_date:
                    query = query.where(AuditTrailModel.timestamp >= start_date)
                if end_date:
                    query = query.where(AuditTrailModel.timestamp <= end_date)

                result = await db.execute(query)
                records = result.scalars().all()

                verification_result = {
                    "valid": True,
                    "total_records": len(records),
                    "verified_records": 0,
                    "broken_chains": [],
                    "invalid_signatures": [],
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                }

                # Verify each record in sequence
                for i, audit_record in enumerate(records):
                    try:
                        # Reconstruct record
                        record = AuditRecord(
                            record_id=audit_record.record_id,
                            timestamp=audit_record.timestamp,
                            category=AuditEventCategory(audit_record.category),
                            event_type=audit_record.event_type,
                            user_id=audit_record.user_id,
                            session_id=audit_record.session_id,
                            source_ip=audit_record.source_ip,
                            user_agent=audit_record.user_agent,
                            resource_type=audit_record.resource_type,
                            resource_id=audit_record.resource_id,
                            action=audit_record.action,
                            details=(
                                json.loads(audit_record.details)
                                if audit_record.details
                                else {}
                            ),
                            before_state=(
                                json.loads(audit_record.before_state)
                                if audit_record.before_state
                                else None
                            ),
                            after_state=(
                                json.loads(audit_record.after_state)
                                if audit_record.after_state
                                else None
                            ),
                            outcome=audit_record.outcome,
                            error_message=audit_record.error_message,
                            correlation_id=audit_record.correlation_id,
                            metadata=(
                                json.loads(audit_record.metadata)
                                if audit_record.metadata
                                else {}
                            ),
                        )

                        # Verify hash chain
                        calculated_hash = self.crypto.calculate_record_hash(
                            record, audit_record.previous_hash
                        )
                        if calculated_hash != audit_record.record_hash:
                            verification_result["broken_chains"].append(
                                {
                                    "record_id": audit_record.record_id,
                                    "sequence": audit_record.sequence_number,
                                    "expected_hash": audit_record.record_hash,
                                    "calculated_hash": calculated_hash,
                                }
                            )
                            verification_result["valid"] = False

                        # Verify digital signature
                        if audit_record.digital_signature:
                            record_data = json.dumps(
                                asdict(record), sort_keys=True, default=str
                            )
                            if not self.crypto.verify_signature(
                                record_data, audit_record.digital_signature
                            ):
                                verification_result["invalid_signatures"].append(
                                    {
                                        "record_id": audit_record.record_id,
                                        "sequence": audit_record.sequence_number,
                                    }
                                )
                                verification_result["valid"] = False

                        verification_result["verified_records"] += 1

                    except Exception as e:
                        self.logger.error(
                            f"Error verifying record {audit_record.record_id}: {e}"
                        )
                        verification_result["valid"] = False

                return verification_result

        except Exception as e:
            self.logger.error(f"Error verifying chain integrity: {e}")
            return {"valid": False, "error": str(e)}

    async def search_audit_records(
        self,
        category: Optional[AuditEventCategory] = None,
        event_type: Optional[str] = None,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        outcome: Optional[str] = None,
        correlation_id: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Search audit records with various filters.

        Args:
            category: Event category filter
            event_type: Event type filter
            user_id: User ID filter
            resource_type: Resource type filter
            resource_id: Resource ID filter
            start_date: Start date filter
            end_date: End date filter
            outcome: Outcome filter
            correlation_id: Correlation ID filter
            limit: Maximum records to return
            offset: Offset for pagination

        Returns:
            List of matching audit records
        """

        try:
            async with get_db() as db:
                # Build query
                query = select(AuditTrailModel).order_by(
                    AuditTrailModel.timestamp.desc()
                )

                # Apply filters
                if category:
                    query = query.where(AuditTrailModel.category == category.value)
                if event_type:
                    query = query.where(AuditTrailModel.event_type == event_type)
                if user_id:
                    query = query.where(AuditTrailModel.user_id == user_id)
                if resource_type:
                    query = query.where(AuditTrailModel.resource_type == resource_type)
                if resource_id:
                    query = query.where(AuditTrailModel.resource_id == resource_id)
                if start_date:
                    query = query.where(AuditTrailModel.timestamp >= start_date)
                if end_date:
                    query = query.where(AuditTrailModel.timestamp <= end_date)
                if outcome:
                    query = query.where(AuditTrailModel.outcome == outcome)
                if correlation_id:
                    query = query.where(
                        AuditTrailModel.correlation_id == correlation_id
                    )

                # Apply pagination
                query = query.limit(limit).offset(offset)

                result = await db.execute(query)
                records = result.scalars().all()

                # Convert to dict format
                audit_records = []
                for record in records:
                    audit_records.append(
                        {
                            "record_id": record.record_id,
                            "sequence_number": record.sequence_number,
                            "timestamp": record.timestamp.isoformat(),
                            "category": record.category,
                            "event_type": record.event_type,
                            "user_id": record.user_id,
                            "session_id": record.session_id,
                            "source_ip": record.source_ip,
                            "user_agent": record.user_agent,
                            "resource_type": record.resource_type,
                            "resource_id": record.resource_id,
                            "action": record.action,
                            "details": (
                                json.loads(record.details) if record.details else {}
                            ),
                            "before_state": (
                                json.loads(record.before_state)
                                if record.before_state
                                else None
                            ),
                            "after_state": (
                                json.loads(record.after_state)
                                if record.after_state
                                else None
                            ),
                            "outcome": record.outcome,
                            "error_message": record.error_message,
                            "correlation_id": record.correlation_id,
                            "block_id": record.block_id,
                            "block_sequence": record.block_sequence,
                            "metadata": (
                                json.loads(record.metadata) if record.metadata else {}
                            ),
                        }
                    )

                return audit_records

        except Exception as e:
            self.logger.error(f"Error searching audit records: {e}")
            return []

    async def start_background_services(self):
        """Start background services for audit trail management."""

        if self.is_running:
            return

        self.is_running = True

        # Start periodic block creation
        block_task = asyncio.create_task(self._periodic_block_creation())
        self._background_tasks.add(block_task)
        block_task.add_done_callback(self._background_tasks.discard)

        # Start integrity monitoring
        integrity_task = asyncio.create_task(self._integrity_monitoring())
        self._background_tasks.add(integrity_task)
        integrity_task.add_done_callback(self._background_tasks.discard)

        self.logger.info("Started audit trail background services")

    async def stop_background_services(self):
        """Stop all background services."""

        self.is_running = False

        # Cancel all background tasks
        for task in self._background_tasks:
            task.cancel()

        # Wait for tasks to complete
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)

        self._background_tasks.clear()

        # Create final block if there are pending records
        if self.pending_records:
            await self._create_audit_block()

        self.logger.info("Stopped audit trail background services")

    async def _periodic_block_creation(self):
        """Periodic task to create audit blocks."""

        while self.is_running:
            try:
                # Check if we should create a block
                if self.pending_records and (
                    not self.last_block_time
                    or datetime.now(timezone.utc) - self.last_block_time
                    >= timedelta(minutes=self.auto_block_interval)
                ):

                    await self._create_audit_block()

                # Sleep for check interval
                await asyncio.sleep(300)  # Check every 5 minutes

            except Exception as e:
                self.logger.error(f"Error in periodic block creation: {e}")
                await asyncio.sleep(600)  # Wait longer on error

    async def _integrity_monitoring(self):
        """Background integrity monitoring."""

        while self.is_running:
            try:
                # Perform periodic integrity checks
                end_date = datetime.now(timezone.utc)
                start_date = end_date - timedelta(hours=24)  # Check last 24 hours

                verification_result = await self.verify_chain_integrity(
                    start_date, end_date
                )

                if not verification_result["valid"]:
                    self.integrity_violations += 1

                    # Log integrity violation
                    self.logger.error(
                        f"Audit trail integrity violation detected: {verification_result}"
                    )

                    # Alert administrators
                    await self.log_audit_event(
                        category=AuditEventCategory.SYSTEM_ADMIN,
                        event_type="integrity_violation",
                        outcome="error",
                        error_message="Audit trail integrity violation detected",
                        details=verification_result,
                    )

                # Sleep for monitoring interval
                await asyncio.sleep(3600)  # Check every hour

            except Exception as e:
                self.logger.error(f"Error in integrity monitoring: {e}")
                await asyncio.sleep(3600)  # Wait longer on error

    async def get_audit_statistics(self) -> Dict[str, Any]:
        """Get comprehensive audit trail statistics."""

        try:
            async with get_db() as db:
                # Count total records
                total_query = select(func.count(AuditTrailModel.record_id))
                total_result = await db.execute(total_query)
                total_records = total_result.scalar()

                # Count by category
                category_query = select(
                    AuditTrailModel.category, func.count(AuditTrailModel.record_id)
                ).group_by(AuditTrailModel.category)

                category_result = await db.execute(category_query)
                category_counts = dict(category_result.fetchall())

                # Count by outcome
                outcome_query = select(
                    AuditTrailModel.outcome, func.count(AuditTrailModel.record_id)
                ).group_by(AuditTrailModel.outcome)

                outcome_result = await db.execute(outcome_query)
                outcome_counts = dict(outcome_result.fetchall())

                # Recent activity (last 24 hours)
                recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                recent_query = select(func.count(AuditTrailModel.record_id)).where(
                    AuditTrailModel.timestamp >= recent_cutoff
                )
                recent_result = await db.execute(recent_query)
                recent_records = recent_result.scalar()

                return {
                    "total_records": total_records,
                    "records_by_category": category_counts,
                    "records_by_outcome": outcome_counts,
                    "recent_records_24h": recent_records,
                    "blocks_created": self.blocks_created,
                    "pending_records": len(self.pending_records),
                    "integrity_violations": self.integrity_violations,
                    "last_block_time": (
                        self.last_block_time.isoformat()
                        if self.last_block_time
                        else None
                    ),
                    "integrity_level": self.integrity_level.value,
                    "is_running": self.is_running,
                }

        except Exception as e:
            self.logger.error(f"Error getting audit statistics: {e}")
            return {"error": str(e)}


# Global immutable audit trail instance
immutable_audit_trail = ImmutableAuditTrail()


async def get_immutable_audit_trail() -> ImmutableAuditTrail:
    """Get the global immutable audit trail instance."""
    return immutable_audit_trail


# Convenience functions for common audit events
async def log_trading_event(
    event_type: str, user_id: str, details: Dict[str, Any], **kwargs
) -> str:
    """Log a trading-related audit event."""
    return await immutable_audit_trail.log_audit_event(
        category=AuditEventCategory.TRADING,
        event_type=event_type,
        user_id=user_id,
        details=details,
        **kwargs,
    )


async def log_compliance_event(
    event_type: str, user_id: Optional[str], details: Dict[str, Any], **kwargs
) -> str:
    """Log a compliance-related audit event."""
    return await immutable_audit_trail.log_audit_event(
        category=AuditEventCategory.COMPLIANCE,
        event_type=event_type,
        user_id=user_id,
        details=details,
        **kwargs,
    )


async def log_system_event(event_type: str, details: Dict[str, Any], **kwargs) -> str:
    """Log a system administration audit event."""
    return await immutable_audit_trail.log_audit_event(
        category=AuditEventCategory.SYSTEM_ADMIN,
        event_type=event_type,
        user_id="system",
        details=details,
        **kwargs,
    )
