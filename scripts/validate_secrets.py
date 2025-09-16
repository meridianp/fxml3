#!/usr/bin/env python3
"""
Production Secrets Validation Script for FXML4

This script validates that all required environment variables and secrets
are properly configured for production deployment.

Usage:
    python scripts/validate_secrets.py [--env-file .env.production]
"""

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class SecretRequirement:
    """Represents a required secret/environment variable."""

    name: str
    description: str
    required_for_production: bool
    min_length: Optional[int] = None
    pattern: Optional[str] = None
    example: Optional[str] = None


# Define all required secrets for production
REQUIRED_SECRETS = [
    # Database secrets
    SecretRequirement(
        "FXML4_DATABASE_PASSWORD",
        "Database password for PostgreSQL/TimescaleDB",
        True,
        min_length=12,
    ),
    SecretRequirement(
        "DB_PASSWORD",
        "External database password (for docker-compose)",
        True,
        min_length=12,
    ),
    # Security secrets
    SecretRequirement(
        "FXML4_JWT_SECRET_KEY",
        "JWT signing secret key",
        True,
        min_length=32,
        example="Use: openssl rand -base64 32",
    ),
    # Redis/RabbitMQ secrets
    SecretRequirement(
        "REDIS_PASSWORD", "Redis authentication password", True, min_length=16
    ),
    SecretRequirement(
        "RABBITMQ_PASSWORD", "RabbitMQ authentication password", True, min_length=16
    ),
    # API Keys
    SecretRequirement(
        "OPENAI_API_KEY",
        "OpenAI API key for LLM integration",
        True,
        min_length=20,
        pattern="sk-",
    ),
    SecretRequirement(
        "ALPHA_VANTAGE_API_KEY",
        "Alpha Vantage API key for market data",
        True,
        min_length=8,
    ),
    SecretRequirement(
        "POLYGON_API_KEY", "Polygon.io API key for market data", True, min_length=8
    ),
    # Trading account secrets
    SecretRequirement(
        "IB_ACCOUNT_ID",
        "Interactive Brokers account ID",
        True,
        min_length=6,
        example="DU123456 or U123456",
    ),
    # Encryption keys
    SecretRequirement(
        "DATA_ENCRYPTION_KEY",
        "Key for encrypting sensitive data at rest",
        True,
        min_length=32,
        example="Use: openssl rand -base64 32",
    ),
    # Optional but recommended
    SecretRequirement(
        "ANTHROPIC_API_KEY",
        "Anthropic API key for Claude integration",
        False,
        min_length=20,
    ),
    SecretRequirement(
        "PINECONE_API_KEY", "Pinecone API key for vector search", False, min_length=20
    ),
    SecretRequirement(
        "FXCM_API_TOKEN", "FXCM API token (if using FXCM broker)", False, min_length=20
    ),
]


class SecretsValidator:
    """Validates production secrets configuration."""

    def __init__(self, env_file: Optional[str] = None):
        """Initialize validator with optional env file."""
        self.env_file = env_file
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.passed: List[str] = []

        # Load environment file if specified
        if env_file and os.path.exists(env_file):
            self._load_env_file(env_file)

    def _load_env_file(self, env_file: str) -> None:
        """Load environment variables from file."""
        try:
            with open(env_file, "r") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Skip comments and empty lines
                    if not line or line.startswith("#"):
                        continue

                    # Parse KEY=VALUE format
                    if "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()

                        # Handle variable substitution ${VAR} patterns
                        if value.startswith("${") and value.endswith("}"):
                            # This is a variable reference, check if the referenced var exists
                            ref_var = value[2:-1].split(":-")[
                                0
                            ]  # Handle ${VAR:-default}
                            if ref_var in os.environ:
                                os.environ[key] = os.environ[ref_var]
                        elif not value.startswith("${"):
                            # Direct value assignment
                            os.environ[key] = value

        except Exception as e:
            self.errors.append(f"Failed to load env file {env_file}: {e}")

    def validate_secret(self, requirement: SecretRequirement) -> bool:
        """Validate a single secret requirement."""
        value = os.environ.get(requirement.name)

        if not value:
            if requirement.required_for_production:
                self.errors.append(
                    f"❌ REQUIRED: {requirement.name} is not set\n"
                    f"   Description: {requirement.description}\n"
                    f"   {requirement.example or 'Set this environment variable'}"
                )
                return False
            else:
                self.warnings.append(
                    f"⚠️  OPTIONAL: {requirement.name} is not set\n"
                    f"   Description: {requirement.description}"
                )
                return True

        # Check minimum length
        if requirement.min_length and len(value) < requirement.min_length:
            self.errors.append(
                f"❌ INVALID: {requirement.name} is too short\n"
                f"   Current length: {len(value)}, minimum: {requirement.min_length}\n"
                f"   {requirement.example or 'Use a longer value'}"
            )
            return False

        # Check pattern if specified
        if requirement.pattern and not value.startswith(requirement.pattern):
            self.errors.append(
                f"❌ INVALID: {requirement.name} doesn't match expected pattern\n"
                f"   Expected to start with: {requirement.pattern}\n"
                f"   {requirement.example or 'Check the format'}"
            )
            return False

        # Check for common insecure values
        insecure_values = {
            "password",
            "secret",
            "key",
            "token",
            "changeme",
            "default",
            "admin",
            "123456",
            "test",
            "demo",
        }

        if value.lower() in insecure_values:
            self.errors.append(
                f"❌ INSECURE: {requirement.name} uses a common/default value\n"
                f"   Current value: {value}\n"
                f"   Use a unique, randomly generated value"
            )
            return False

        self.passed.append(f"✅ {requirement.name}: OK")
        return True

    def validate_all(self) -> bool:
        """Validate all secret requirements."""
        print("🔒 FXML4 Production Secrets Validation")
        print("=" * 50)

        if self.env_file:
            print(f"📁 Loading environment from: {self.env_file}")
        else:
            print("📁 Using system environment variables")

        print()

        all_valid = True

        # Validate each requirement
        for requirement in REQUIRED_SECRETS:
            if not self.validate_secret(requirement):
                all_valid = False

        # Print results
        print("\n📊 VALIDATION RESULTS")
        print("-" * 30)

        if self.passed:
            print("✅ PASSED:")
            for msg in self.passed:
                print(f"   {msg}")
            print()

        if self.warnings:
            print("⚠️  WARNINGS:")
            for msg in self.warnings:
                print(f"   {msg}")
            print()

        if self.errors:
            print("❌ ERRORS:")
            for msg in self.errors:
                print(f"   {msg}")
            print()

        # Summary
        total_required = len([r for r in REQUIRED_SECRETS if r.required_for_production])
        passed_required = len(
            [
                p
                for p in self.passed
                if any(
                    req.name in p and req.required_for_production
                    for req in REQUIRED_SECRETS
                )
            ]
        )

        print(f"📈 SUMMARY: {passed_required}/{total_required} required secrets valid")

        if all_valid:
            print("🎉 ALL VALIDATIONS PASSED - Ready for production!")
            return True
        else:
            print("🚫 VALIDATION FAILED - Fix errors before production deployment")
            return False

    def generate_env_template(self) -> str:
        """Generate a template .env file with all required secrets."""
        template = "# FXML4 Production Secrets Template\n"
        template += "# Generated by validate_secrets.py\n"
        template += "# Fill in all values before production deployment\n\n"

        for requirement in REQUIRED_SECRETS:
            if requirement.required_for_production:
                template += f"# REQUIRED: {requirement.description}\n"
            else:
                template += f"# OPTIONAL: {requirement.description}\n"

            if requirement.example:
                template += f"# {requirement.example}\n"

            template += f"{requirement.name}=\n\n"

        return template


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Validate FXML4 production secrets")
    parser.add_argument(
        "--env-file",
        default=".env.production",
        help="Environment file to validate (default: .env.production)",
    )
    parser.add_argument(
        "--generate-template",
        action="store_true",
        help="Generate a secrets template file",
    )

    args = parser.parse_args()

    validator = SecretsValidator(args.env_file)

    if args.generate_template:
        template = validator.generate_env_template()
        template_file = "secrets_template.env"
        with open(template_file, "w") as f:
            f.write(template)
        print(f"📝 Generated secrets template: {template_file}")
        return

    # Run validation
    success = validator.validate_all()

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
