"""Compliance and Audit Framework for Broker Abstraction.

This package provides comprehensive compliance and audit capabilities
for the FIX-based broker abstraction system.
"""

from .audit_logger import AuditEvent, AuditLogger, AuditSeverity
from .compliance_engine import ComplianceEngine, ComplianceRule, ComplianceViolation
from .regulatory_checks import (
    FISCACompliance,
    MiFIDIICompliance,
    RegulatoryChecker,
    SECCompliance,
)
from .reporting import AuditReporter, ComplianceReporter
from .transaction_monitor import SuspiciousActivity, TransactionMonitor

__all__ = [
    # Audit system
    "AuditLogger",
    "AuditEvent",
    "AuditSeverity",
    # Compliance engine
    "ComplianceEngine",
    "ComplianceRule",
    "ComplianceViolation",
    # Regulatory compliance
    "RegulatoryChecker",
    "FISCACompliance",
    "MiFIDIICompliance",
    "SECCompliance",
    # Transaction monitoring
    "TransactionMonitor",
    "SuspiciousActivity",
    # Reporting
    "ComplianceReporter",
    "AuditReporter",
]
