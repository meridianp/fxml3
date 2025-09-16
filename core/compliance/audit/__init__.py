"""
Compliance Audit Module for FXML4.

Provides immutable audit trail capabilities with cryptographic integrity:
- Tamper-proof audit logging
- Blockchain-inspired record chaining
- Merkle tree verification
- Digital signatures for enhanced security
- Comprehensive compliance reporting
"""

from .immutable_trail import (
    AuditBlock,
    AuditEventCategory,
    AuditRecord,
    CryptoManager,
    ImmutableAuditTrail,
    IntegrityLevel,
    MerkleTree,
    immutable_audit_trail,
    log_compliance_event,
    log_system_event,
    log_trading_event,
)

__all__ = [
    "ImmutableAuditTrail",
    "AuditRecord",
    "AuditBlock",
    "AuditEventCategory",
    "IntegrityLevel",
    "MerkleTree",
    "CryptoManager",
    "immutable_audit_trail",
    "log_trading_event",
    "log_compliance_event",
    "log_system_event",
]
