"""
API Compatibility Checker
=========================

Validates backward and forward compatibility of API contracts to ensure
stable API evolution and prevent breaking changes.
"""

import difflib
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from .contract_models import (
    APIContract,
    EndpointContract,
    FieldSchema,
    SchemaContract,
    ValidationResult,
)

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Types of API changes."""

    BREAKING = "breaking"
    NON_BREAKING = "non_breaking"
    COMPATIBLE = "compatible"
    DEPRECATED = "deprecated"


@dataclass
class APIChange:
    """Represents a change in API contract."""

    change_type: ChangeType
    location: str
    description: str
    old_value: Any = None
    new_value: Any = None
    severity: str = "medium"  # low, medium, high, critical

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "change_type": self.change_type.value,
            "location": self.location,
            "description": self.description,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "severity": self.severity,
        }


@dataclass
class CompatibilityReport:
    """Compatibility analysis report."""

    is_compatible: bool
    changes: List[APIChange] = field(default_factory=list)
    breaking_changes: List[APIChange] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def has_breaking_changes(self) -> bool:
        """Whether report contains breaking changes."""
        return len(self.breaking_changes) > 0

    @property
    def change_summary(self) -> Dict[str, int]:
        """Summary of changes by type."""
        summary = {}
        for change in self.changes:
            change_type = change.change_type.value
            summary[change_type] = summary.get(change_type, 0) + 1
        return summary

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_compatible": self.is_compatible,
            "has_breaking_changes": self.has_breaking_changes,
            "change_summary": self.change_summary,
            "changes": [change.to_dict() for change in self.changes],
            "breaking_changes": [change.to_dict() for change in self.breaking_changes],
            "warnings": self.warnings,
        }


class CompatibilityChecker:
    """
    API compatibility validation engine.

    Compares API contracts to identify breaking and non-breaking changes,
    ensuring stable API evolution and backward compatibility.
    """

    def __init__(self):
        """Initialize compatibility checker."""
        self.versioning_rules = self._build_versioning_rules()
        self.breaking_change_rules = self._build_breaking_change_rules()

    def check_compatibility(
        self, old_contract: APIContract, new_contract: APIContract
    ) -> CompatibilityReport:
        """
        Check compatibility between two API contracts.

        Args:
            old_contract: Previous API contract version
            new_contract: New API contract version

        Returns:
            CompatibilityReport with compatibility analysis
        """
        logger.info(
            f"Checking compatibility: {old_contract.version} -> {new_contract.version}"
        )

        report = CompatibilityReport(is_compatible=True)

        # Check global contract changes
        global_changes = self._check_global_changes(old_contract, new_contract)
        report.changes.extend(global_changes)

        # Check endpoint changes
        endpoint_changes = self._check_endpoint_changes(old_contract, new_contract)
        report.changes.extend(endpoint_changes)

        # Check schema changes
        schema_changes = self._check_schema_changes(old_contract, new_contract)
        report.changes.extend(schema_changes)

        # Identify breaking changes
        report.breaking_changes = [
            change
            for change in report.changes
            if change.change_type == ChangeType.BREAKING
        ]

        # Determine overall compatibility
        report.is_compatible = len(report.breaking_changes) == 0

        # Add warnings for potential issues
        report.warnings.extend(self._generate_compatibility_warnings(report.changes))

        logger.info(
            f"Compatibility check complete: {len(report.changes)} changes, "
            f"{len(report.breaking_changes)} breaking"
        )

        return report

    def _check_global_changes(
        self, old_contract: APIContract, new_contract: APIContract
    ) -> List[APIChange]:
        """Check for global contract changes."""
        changes = []

        # Version changes
        if old_contract.version != new_contract.version:
            version_change = self._analyze_version_change(
                old_contract.version, new_contract.version
            )
            changes.append(version_change)

        # Base URL changes
        if old_contract.base_url != new_contract.base_url:
            changes.append(
                APIChange(
                    change_type=ChangeType.BREAKING,
                    location="global.base_url",
                    description=f"Base URL changed from {old_contract.base_url} to {new_contract.base_url}",
                    old_value=old_contract.base_url,
                    new_value=new_contract.base_url,
                    severity="high",
                )
            )

        # Title changes
        if old_contract.title != new_contract.title:
            changes.append(
                APIChange(
                    change_type=ChangeType.NON_BREAKING,
                    location="global.title",
                    description=f"API title changed from '{old_contract.title}' to '{new_contract.title}'",
                    old_value=old_contract.title,
                    new_value=new_contract.title,
                    severity="low",
                )
            )

        return changes

    def _check_endpoint_changes(
        self, old_contract: APIContract, new_contract: APIContract
    ) -> List[APIChange]:
        """Check for endpoint changes."""
        changes = []

        # Build endpoint maps
        old_endpoints = {(ep.path, ep.method): ep for ep in old_contract.endpoints}
        new_endpoints = {(ep.path, ep.method): ep for ep in new_contract.endpoints}

        # Check for removed endpoints
        removed_endpoints = set(old_endpoints.keys()) - set(new_endpoints.keys())
        for endpoint_key in removed_endpoints:
            endpoint = old_endpoints[endpoint_key]
            changes.append(
                APIChange(
                    change_type=ChangeType.BREAKING,
                    location=f"endpoint.{endpoint.path}",
                    description=f"Endpoint removed: {endpoint.method.value} {endpoint.path}",
                    severity="critical",
                )
            )

        # Check for added endpoints
        added_endpoints = set(new_endpoints.keys()) - set(old_endpoints.keys())
        for endpoint_key in added_endpoints:
            endpoint = new_endpoints[endpoint_key]
            changes.append(
                APIChange(
                    change_type=ChangeType.COMPATIBLE,
                    location=f"endpoint.{endpoint.path}",
                    description=f"Endpoint added: {endpoint.method.value} {endpoint.path}",
                    severity="low",
                )
            )

        # Check for modified endpoints
        common_endpoints = set(old_endpoints.keys()) & set(new_endpoints.keys())
        for endpoint_key in common_endpoints:
            old_endpoint = old_endpoints[endpoint_key]
            new_endpoint = new_endpoints[endpoint_key]

            endpoint_changes = self._check_endpoint_modifications(
                old_endpoint, new_endpoint
            )
            changes.extend(endpoint_changes)

        return changes

    def _check_endpoint_modifications(
        self, old_endpoint: EndpointContract, new_endpoint: EndpointContract
    ) -> List[APIChange]:
        """Check for modifications to an existing endpoint."""
        changes = []
        location_prefix = f"endpoint.{old_endpoint.path}"

        # Check deprecation status
        if not old_endpoint.deprecated and new_endpoint.deprecated:
            changes.append(
                APIChange(
                    change_type=ChangeType.DEPRECATED,
                    location=f"{location_prefix}.deprecated",
                    description=f"Endpoint deprecated: {old_endpoint.method.value} {old_endpoint.path}",
                    severity="medium",
                )
            )

        # Check response status codes
        old_success_codes = set(old_endpoint.success_status_codes)
        new_success_codes = set(new_endpoint.success_status_codes)

        removed_success_codes = old_success_codes - new_success_codes
        for code in removed_success_codes:
            changes.append(
                APIChange(
                    change_type=ChangeType.BREAKING,
                    location=f"{location_prefix}.success_status_codes",
                    description=f"Success status code {code} removed",
                    severity="high",
                )
            )

        added_success_codes = new_success_codes - old_success_codes
        for code in added_success_codes:
            changes.append(
                APIChange(
                    change_type=ChangeType.COMPATIBLE,
                    location=f"{location_prefix}.success_status_codes",
                    description=f"Success status code {code} added",
                    severity="low",
                )
            )

        # Check content types
        if old_endpoint.request_content_type != new_endpoint.request_content_type:
            changes.append(
                APIChange(
                    change_type=ChangeType.BREAKING,
                    location=f"{location_prefix}.request_content_type",
                    description=f"Request content type changed from {old_endpoint.request_content_type} to {new_endpoint.request_content_type}",
                    old_value=old_endpoint.request_content_type,
                    new_value=new_endpoint.request_content_type,
                    severity="high",
                )
            )

        if old_endpoint.response_content_type != new_endpoint.response_content_type:
            changes.append(
                APIChange(
                    change_type=ChangeType.BREAKING,
                    location=f"{location_prefix}.response_content_type",
                    description=f"Response content type changed from {old_endpoint.response_content_type} to {new_endpoint.response_content_type}",
                    old_value=old_endpoint.response_content_type,
                    new_value=new_endpoint.response_content_type,
                    severity="high",
                )
            )

        # Check query parameters
        param_changes = self._check_parameter_changes(
            old_endpoint.query_parameters,
            new_endpoint.query_parameters,
            f"{location_prefix}.query_parameters",
        )
        changes.extend(param_changes)

        # Check path parameters
        path_param_changes = self._check_parameter_changes(
            old_endpoint.path_parameters,
            new_endpoint.path_parameters,
            f"{location_prefix}.path_parameters",
        )
        changes.extend(path_param_changes)

        return changes

    def _check_parameter_changes(
        self,
        old_params: List[FieldSchema],
        new_params: List[FieldSchema],
        location: str,
    ) -> List[APIChange]:
        """Check for parameter changes."""
        changes = []

        # Build parameter maps
        old_param_map = {param.name: param for param in old_params}
        new_param_map = {param.name: param for param in new_params}

        # Check for removed parameters
        removed_params = set(old_param_map.keys()) - set(new_param_map.keys())
        for param_name in removed_params:
            param = old_param_map[param_name]
            change_type = (
                ChangeType.BREAKING if param.required else ChangeType.COMPATIBLE
            )
            severity = "high" if param.required else "medium"

            changes.append(
                APIChange(
                    change_type=change_type,
                    location=f"{location}.{param_name}",
                    description=f"Parameter '{param_name}' removed",
                    severity=severity,
                )
            )

        # Check for added parameters
        added_params = set(new_param_map.keys()) - set(old_param_map.keys())
        for param_name in added_params:
            param = new_param_map[param_name]
            change_type = (
                ChangeType.BREAKING if param.required else ChangeType.COMPATIBLE
            )
            severity = "high" if param.required else "low"

            changes.append(
                APIChange(
                    change_type=change_type,
                    location=f"{location}.{param_name}",
                    description=f"Parameter '{param_name}' added",
                    severity=severity,
                )
            )

        # Check for modified parameters
        common_params = set(old_param_map.keys()) & set(new_param_map.keys())
        for param_name in common_params:
            old_param = old_param_map[param_name]
            new_param = new_param_map[param_name]

            param_changes = self._check_field_changes(
                old_param, new_param, f"{location}.{param_name}"
            )
            changes.extend(param_changes)

        return changes

    def _check_schema_changes(
        self, old_contract: APIContract, new_contract: APIContract
    ) -> List[APIChange]:
        """Check for schema changes across all endpoints."""
        changes = []

        # Collect all schemas from both contracts
        old_schemas = {}
        new_schemas = {}

        for endpoint in old_contract.endpoints:
            if endpoint.request_schema:
                old_schemas[f"{endpoint.path}.request"] = endpoint.request_schema

            for status_code, schema in endpoint.response_schemas.items():
                old_schemas[f"{endpoint.path}.response.{status_code}"] = schema

        for endpoint in new_contract.endpoints:
            if endpoint.request_schema:
                new_schemas[f"{endpoint.path}.request"] = endpoint.request_schema

            for status_code, schema in endpoint.response_schemas.items():
                new_schemas[f"{endpoint.path}.response.{status_code}"] = schema

        # Compare schemas
        all_schema_keys = set(old_schemas.keys()) | set(new_schemas.keys())

        for schema_key in all_schema_keys:
            old_schema = old_schemas.get(schema_key)
            new_schema = new_schemas.get(schema_key)

            if old_schema and not new_schema:
                changes.append(
                    APIChange(
                        change_type=ChangeType.BREAKING,
                        location=f"schema.{schema_key}",
                        description=f"Schema removed: {schema_key}",
                        severity="high",
                    )
                )
            elif not old_schema and new_schema:
                changes.append(
                    APIChange(
                        change_type=ChangeType.COMPATIBLE,
                        location=f"schema.{schema_key}",
                        description=f"Schema added: {schema_key}",
                        severity="low",
                    )
                )
            elif old_schema and new_schema:
                schema_changes = self._check_schema_modifications(
                    old_schema, new_schema, schema_key
                )
                changes.extend(schema_changes)

        return changes

    def _check_schema_modifications(
        self, old_schema: SchemaContract, new_schema: SchemaContract, schema_key: str
    ) -> List[APIChange]:
        """Check for modifications to a schema."""
        changes = []

        # Build field maps
        old_field_map = {field.name: field for field in old_schema.fields}
        new_field_map = {field.name: field for field in new_schema.fields}

        # Check for removed fields
        removed_fields = set(old_field_map.keys()) - set(new_field_map.keys())
        for field_name in removed_fields:
            field = old_field_map[field_name]
            change_type = (
                ChangeType.BREAKING if field.required else ChangeType.COMPATIBLE
            )
            severity = "high" if field.required else "medium"

            changes.append(
                APIChange(
                    change_type=change_type,
                    location=f"schema.{schema_key}.{field_name}",
                    description=f"Field '{field_name}' removed from schema",
                    severity=severity,
                )
            )

        # Check for added fields
        added_fields = set(new_field_map.keys()) - set(old_field_map.keys())
        for field_name in added_fields:
            field = new_field_map[field_name]

            # Adding required fields is breaking for request schemas
            if "request" in schema_key and field.required:
                change_type = ChangeType.BREAKING
                severity = "high"
            else:
                change_type = ChangeType.COMPATIBLE
                severity = "low"

            changes.append(
                APIChange(
                    change_type=change_type,
                    location=f"schema.{schema_key}.{field_name}",
                    description=f"Field '{field_name}' added to schema",
                    severity=severity,
                )
            )

        # Check for modified fields
        common_fields = set(old_field_map.keys()) & set(new_field_map.keys())
        for field_name in common_fields:
            old_field = old_field_map[field_name]
            new_field = new_field_map[field_name]

            field_changes = self._check_field_changes(
                old_field, new_field, f"schema.{schema_key}.{field_name}"
            )
            changes.extend(field_changes)

        # Check additional properties setting
        if old_schema.additional_properties != new_schema.additional_properties:
            if (
                old_schema.additional_properties
                and not new_schema.additional_properties
            ):
                changes.append(
                    APIChange(
                        change_type=ChangeType.BREAKING,
                        location=f"schema.{schema_key}.additional_properties",
                        description="Schema no longer allows additional properties",
                        severity="medium",
                    )
                )
            else:
                changes.append(
                    APIChange(
                        change_type=ChangeType.COMPATIBLE,
                        location=f"schema.{schema_key}.additional_properties",
                        description="Schema now allows additional properties",
                        severity="low",
                    )
                )

        return changes

    def _check_field_changes(
        self, old_field: FieldSchema, new_field: FieldSchema, location: str
    ) -> List[APIChange]:
        """Check for changes to a field."""
        changes = []

        # Type changes
        if old_field.type != new_field.type:
            changes.append(
                APIChange(
                    change_type=ChangeType.BREAKING,
                    location=f"{location}.type",
                    description=f"Field type changed from {old_field.type} to {new_field.type}",
                    old_value=old_field.type,
                    new_value=new_field.type,
                    severity="high",
                )
            )

        # Required changes
        if old_field.required != new_field.required:
            if not old_field.required and new_field.required:
                changes.append(
                    APIChange(
                        change_type=ChangeType.BREAKING,
                        location=f"{location}.required",
                        description=f"Field '{old_field.name}' is now required",
                        severity="high",
                    )
                )
            else:
                changes.append(
                    APIChange(
                        change_type=ChangeType.COMPATIBLE,
                        location=f"{location}.required",
                        description=f"Field '{old_field.name}' is no longer required",
                        severity="low",
                    )
                )

        # Constraint changes
        constraint_changes = self._check_constraint_changes(
            old_field, new_field, location
        )
        changes.extend(constraint_changes)

        return changes

    def _check_constraint_changes(
        self, old_field: FieldSchema, new_field: FieldSchema, location: str
    ) -> List[APIChange]:
        """Check for constraint changes on a field."""
        changes = []

        # Minimum value changes
        if old_field.minimum != new_field.minimum:
            if new_field.minimum is not None and (
                old_field.minimum is None or new_field.minimum > old_field.minimum
            ):
                changes.append(
                    APIChange(
                        change_type=ChangeType.BREAKING,
                        location=f"{location}.minimum",
                        description=f"Minimum value constraint tightened from {old_field.minimum} to {new_field.minimum}",
                        old_value=old_field.minimum,
                        new_value=new_field.minimum,
                        severity="medium",
                    )
                )
            else:
                changes.append(
                    APIChange(
                        change_type=ChangeType.COMPATIBLE,
                        location=f"{location}.minimum",
                        description=f"Minimum value constraint relaxed from {old_field.minimum} to {new_field.minimum}",
                        old_value=old_field.minimum,
                        new_value=new_field.minimum,
                        severity="low",
                    )
                )

        # Maximum value changes
        if old_field.maximum != new_field.maximum:
            if new_field.maximum is not None and (
                old_field.maximum is None or new_field.maximum < old_field.maximum
            ):
                changes.append(
                    APIChange(
                        change_type=ChangeType.BREAKING,
                        location=f"{location}.maximum",
                        description=f"Maximum value constraint tightened from {old_field.maximum} to {new_field.maximum}",
                        old_value=old_field.maximum,
                        new_value=new_field.maximum,
                        severity="medium",
                    )
                )
            else:
                changes.append(
                    APIChange(
                        change_type=ChangeType.COMPATIBLE,
                        location=f"{location}.maximum",
                        description=f"Maximum value constraint relaxed from {old_field.maximum} to {new_field.maximum}",
                        old_value=old_field.maximum,
                        new_value=new_field.maximum,
                        severity="low",
                    )
                )

        # Enum changes
        if old_field.enum != new_field.enum:
            if old_field.enum and new_field.enum:
                old_enum_set = set(old_field.enum)
                new_enum_set = set(new_field.enum)

                removed_values = old_enum_set - new_enum_set
                if removed_values:
                    changes.append(
                        APIChange(
                            change_type=ChangeType.BREAKING,
                            location=f"{location}.enum",
                            description=f"Enum values removed: {list(removed_values)}",
                            severity="medium",
                        )
                    )

                added_values = new_enum_set - old_enum_set
                if added_values:
                    changes.append(
                        APIChange(
                            change_type=ChangeType.COMPATIBLE,
                            location=f"{location}.enum",
                            description=f"Enum values added: {list(added_values)}",
                            severity="low",
                        )
                    )

        return changes

    def _analyze_version_change(self, old_version: str, new_version: str) -> APIChange:
        """Analyze version change for semantic versioning compliance."""
        try:
            old_parts = [int(x) for x in old_version.split(".")]
            new_parts = [int(x) for x in new_version.split(".")]

            # Pad shorter version with zeros
            max_len = max(len(old_parts), len(new_parts))
            old_parts.extend([0] * (max_len - len(old_parts)))
            new_parts.extend([0] * (max_len - len(new_parts)))

            # Determine change type based on semantic versioning
            if new_parts[0] > old_parts[0]:  # Major version bump
                change_type = ChangeType.BREAKING
                severity = "critical"
                description = f"Major version change: {old_version} -> {new_version}"
            elif new_parts[1] > old_parts[1]:  # Minor version bump
                change_type = ChangeType.COMPATIBLE
                severity = "medium"
                description = f"Minor version change: {old_version} -> {new_version}"
            elif new_parts[2] > old_parts[2]:  # Patch version bump
                change_type = ChangeType.NON_BREAKING
                severity = "low"
                description = f"Patch version change: {old_version} -> {new_version}"
            else:
                change_type = ChangeType.NON_BREAKING
                severity = "low"
                description = f"Version change: {old_version} -> {new_version}"

        except ValueError:
            # Non-semantic versioning
            change_type = ChangeType.NON_BREAKING
            severity = "medium"
            description = f"Version change: {old_version} -> {new_version}"

        return APIChange(
            change_type=change_type,
            location="global.version",
            description=description,
            old_value=old_version,
            new_value=new_version,
            severity=severity,
        )

    def _generate_compatibility_warnings(self, changes: List[APIChange]) -> List[str]:
        """Generate warnings based on change patterns."""
        warnings = []

        # Check for multiple breaking changes
        breaking_count = sum(
            1 for change in changes if change.change_type == ChangeType.BREAKING
        )
        if breaking_count > 5:
            warnings.append(
                f"High number of breaking changes detected: {breaking_count}"
            )

        # Check for deprecated endpoints
        deprecated_count = sum(
            1 for change in changes if change.change_type == ChangeType.DEPRECATED
        )
        if deprecated_count > 0:
            warnings.append(
                f"{deprecated_count} endpoint(s) deprecated - consider migration plan"
            )

        # Check for removed endpoints
        removed_endpoints = [
            change for change in changes if "Endpoint removed" in change.description
        ]
        if removed_endpoints:
            warnings.append(
                f"{len(removed_endpoints)} endpoint(s) removed - ensure client compatibility"
            )

        return warnings

    def _build_versioning_rules(self) -> Dict[str, Any]:
        """Build versioning compatibility rules."""
        return {
            "semantic_versioning": {
                "major_bump_breaking": True,
                "minor_bump_compatible": True,
                "patch_bump_non_breaking": True,
            },
            "api_versioning": {
                "url_versioning": True,
                "header_versioning": True,
                "parameter_versioning": False,
            },
        }

    def _build_breaking_change_rules(self) -> Dict[str, List[str]]:
        """Build rules for identifying breaking changes."""
        return {
            "endpoint_changes": [
                "removed_endpoint",
                "changed_method",
                "changed_path",
                "changed_content_type",
            ],
            "schema_changes": [
                "removed_required_field",
                "changed_field_type",
                "tightened_constraints",
                "removed_enum_values",
            ],
            "parameter_changes": [
                "added_required_parameter",
                "removed_parameter",
                "changed_parameter_type",
            ],
        }


class APIEvolutionTracker:
    """
    Track API evolution over multiple versions.
    """

    def __init__(self):
        """Initialize evolution tracker."""
        self.version_history = {}
        self.compatibility_reports = {}

    def add_version(self, contract: APIContract) -> None:
        """Add API contract version to history."""
        self.version_history[contract.version] = contract
        logger.info(f"Added API version {contract.version} to evolution history")

    def track_evolution(
        self, versions: List[str] = None
    ) -> Dict[str, CompatibilityReport]:
        """Track evolution across multiple versions."""
        if versions is None:
            versions = sorted(self.version_history.keys())

        evolution_reports = {}
        checker = CompatibilityChecker()

        for i in range(len(versions) - 1):
            old_version = versions[i]
            new_version = versions[i + 1]

            if (
                old_version in self.version_history
                and new_version in self.version_history
            ):
                old_contract = self.version_history[old_version]
                new_contract = self.version_history[new_version]

                report = checker.check_compatibility(old_contract, new_contract)
                evolution_reports[f"{old_version}->{new_version}"] = report

                logger.info(
                    f"Evolution tracking: {old_version} -> {new_version} - "
                    f"{'Compatible' if report.is_compatible else 'Breaking changes detected'}"
                )

        return evolution_reports

    def generate_evolution_summary(self) -> Dict[str, Any]:
        """Generate summary of API evolution."""
        versions = sorted(self.version_history.keys())
        evolution_reports = self.track_evolution(versions)

        total_changes = 0
        total_breaking_changes = 0

        for report in evolution_reports.values():
            total_changes += len(report.changes)
            total_breaking_changes += len(report.breaking_changes)

        return {
            "versions_tracked": len(versions),
            "evolution_steps": len(evolution_reports),
            "total_changes": total_changes,
            "total_breaking_changes": total_breaking_changes,
            "compatibility_rate": (
                (
                    len(evolution_reports)
                    - sum(1 for r in evolution_reports.values() if not r.is_compatible)
                )
                / len(evolution_reports)
                * 100
                if evolution_reports
                else 100
            ),
            "version_history": versions,
            "evolution_reports": {k: v.to_dict() for k, v in evolution_reports.items()},
        }
