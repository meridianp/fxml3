#!/usr/bin/env python3
"""
Security Validation Script for FXML4

This script validates that security configurations are properly set
and no hardcoded secrets remain in the codebase.
"""

import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


# Color codes for output
class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


def print_status(message: str, status: str, color: str = Colors.WHITE):
    """Print a status message with color coding."""
    print(f"{color}{status:<10}{Colors.END} {message}")


def print_header(header: str):
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{header:^60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}\n")


def check_environment_variables() -> List[Tuple[str, bool, str]]:
    """Check critical environment variables."""
    print_header("Environment Variables Validation")

    required_vars = [
        ("FXML4_JWT_SECRET_KEY", "JWT signing secret"),
        ("FXML4_DB_PASSWORD", "Database password"),
        ("POSTGRES_PASSWORD", "Docker PostgreSQL password"),
    ]

    recommended_vars = [
        ("FXML4_DEMO_ADMIN_PASSWORD", "Demo admin password"),
        ("FXML4_DEMO_USER_PASSWORD", "Demo user password"),
        ("POLYGON_API_KEY", "Polygon.io API key"),
        ("ALPHA_VANTAGE_API_KEY", "Alpha Vantage API key"),
        ("OPENAI_API_KEY", "OpenAI API key"),
        ("ANTHROPIC_API_KEY", "Anthropic API key"),
        ("PINECONE_API_KEY", "Pinecone API key"),
    ]

    results = []

    print(f"{Colors.BOLD}Required Variables:{Colors.END}")
    for var, description in required_vars:
        value = os.environ.get(var)
        if value:
            # Check if it's a placeholder value
            if any(
                placeholder in value.lower()
                for placeholder in [
                    "change-",
                    "your-",
                    "placeholder",
                    "insecure-default",
                ]
            ):
                print_status(f"{var}: {description}", "PLACEHOLDER", Colors.YELLOW)
                results.append((var, False, "Uses placeholder value"))
            else:
                print_status(f"{var}: {description}", "SET", Colors.GREEN)
                results.append((var, True, "Properly configured"))
        else:
            print_status(f"{var}: {description}", "MISSING", Colors.RED)
            results.append((var, False, "Not set"))

    print(f"\n{Colors.BOLD}Recommended Variables:{Colors.END}")
    for var, description in recommended_vars:
        value = os.environ.get(var)
        if value:
            if any(
                placeholder in value.lower()
                for placeholder in ["change-", "your-", "placeholder"]
            ):
                print_status(f"{var}: {description}", "PLACEHOLDER", Colors.YELLOW)
                results.append((var, False, "Uses placeholder value"))
            else:
                print_status(f"{var}: {description}", "SET", Colors.GREEN)
                results.append((var, True, "Properly configured"))
        else:
            print_status(f"{var}: {description}", "NOT SET", Colors.YELLOW)
            results.append((var, False, "Not set (optional)"))

    return results


def scan_for_hardcoded_secrets() -> List[Tuple[str, int, str]]:
    """Scan for potential hardcoded secrets in the codebase."""
    print_header("Hardcoded Secrets Scan")

    # Patterns that might indicate hardcoded secrets
    secret_patterns = [
        (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password"),
        (r'secret\s*=\s*["\'][^"\']+["\']', "Hardcoded secret"),
        (r'api[_-]?key\s*=\s*["\'][^"\']+["\']', "Hardcoded API key"),
        (r'token\s*=\s*["\'][^"\']+["\']', "Hardcoded token"),
        (r"sk-[a-zA-Z0-9]{32,}", "OpenAI API key pattern"),
        (r"sk-ant-[a-zA-Z0-9\-_]{30,}", "Anthropic API key pattern"),
        (r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+", "JWT token pattern"),
    ]

    # Files to scan
    extensions = [".py", ".yaml", ".yml", ".json", ".env.example"]
    exclude_patterns = [
        "venv/",
        "__pycache__/",
        ".git/",
        "node_modules/",
        "logs/",
        "models/",
        "output/",
        "data/",
        "input/",
        ".env",
        ".env.local",
        ".env.production",
        "validate_security.py",  # Exclude this script
    ]

    root_path = Path(__file__).parent.parent
    issues = []

    for ext in extensions:
        for file_path in root_path.rglob(f"*{ext}"):
            # Skip excluded paths
            if any(exclude in str(file_path) for exclude in exclude_patterns):
                continue

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                for line_num, line in enumerate(content.split("\n"), 1):
                    for pattern, description in secret_patterns:
                        matches = re.findall(pattern, line, re.IGNORECASE)
                        if matches:
                            # Skip obvious examples or placeholders
                            if any(
                                placeholder in line.lower()
                                for placeholder in [
                                    "your_",
                                    "your-",
                                    "example",
                                    "placeholder",
                                    "change-",
                                    "insecure-default",
                                    "todo:",
                                    "fixme:",
                                    "fake-",
                                    "dummy-",
                                    "test-",
                                ]
                            ):
                                continue

                            relative_path = file_path.relative_to(root_path)
                            issues.append((str(relative_path), line_num, description))
                            print_status(
                                f"{relative_path}:{line_num} - {description}",
                                "FOUND",
                                Colors.RED,
                            )
            except Exception as e:
                print_status(f"Error scanning {file_path}: {e}", "ERROR", Colors.RED)

    if not issues:
        print_status("No hardcoded secrets detected", "CLEAN", Colors.GREEN)

    return issues


def validate_config_files() -> List[Tuple[str, str]]:
    """Validate configuration files for security issues."""
    print_header("Configuration Files Validation")

    config_files = [
        "config/default.yaml",
        "docker-compose.yml",
        "k8s/secrets/app-secrets.yaml",
        "k8s/secrets/app-secrets-local.yaml",
    ]

    root_path = Path(__file__).parent.parent
    issues = []

    for config_file in config_files:
        file_path = root_path / config_file
        if not file_path.exists():
            print_status(f"{config_file} - File not found", "SKIP", Colors.YELLOW)
            continue

        try:
            with open(file_path, "r") as f:
                content = f.read()

            # Check for insecure default values
            insecure_patterns = [
                "super-secret-key-change-in-production",
                "postgres:postgres@",
                "guest:guest@",
                "admin:admin",
                "password:password",
            ]

            found_issues = False
            for pattern in insecure_patterns:
                if pattern in content:
                    print_status(
                        f"{config_file} - Contains '{pattern}'", "INSECURE", Colors.RED
                    )
                    issues.append(
                        (config_file, f"Contains insecure pattern: {pattern}")
                    )
                    found_issues = True

            if not found_issues:
                print_status(
                    f"{config_file} - No insecure patterns", "SECURE", Colors.GREEN
                )

        except Exception as e:
            print_status(f"{config_file} - Error: {e}", "ERROR", Colors.RED)
            issues.append((config_file, f"Read error: {e}"))

    return issues


def check_file_permissions() -> List[Tuple[str, str]]:
    """Check file permissions for sensitive files."""
    print_header("File Permissions Check")

    sensitive_files = [".env", ".env.local", ".env.production"]
    root_path = Path(__file__).parent.parent
    issues = []

    for filename in sensitive_files:
        file_path = root_path / filename
        if file_path.exists():
            try:
                # Check if file is readable by others
                stat = file_path.stat()
                mode = stat.st_mode

                # Check if others can read (octal 004)
                if mode & 0o004:
                    print_status(
                        f"{filename} - Readable by others (mode: {oct(mode)[-3:]})",
                        "INSECURE",
                        Colors.RED,
                    )
                    issues.append((filename, "Readable by others"))
                else:
                    print_status(
                        f"{filename} - Proper permissions (mode: {oct(mode)[-3:]})",
                        "SECURE",
                        Colors.GREEN,
                    )
            except Exception as e:
                print_status(
                    f"{filename} - Error checking permissions: {e}", "ERROR", Colors.RED
                )
                issues.append((filename, f"Permission check error: {e}"))
        else:
            print_status(f"{filename} - File not found", "N/A", Colors.YELLOW)

    return issues


def test_configuration_loading():
    """Test that configuration loads properly with environment variables."""
    print_header("Configuration Loading Test")

    try:
        # Import and test configuration
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from fxml4.config import get_config

        config = get_config()

        # Test JWT secret
        jwt_secret = config.get("api.auth.secret_key")
        if jwt_secret == "INSECURE-DEFAULT-CHANGE-IN-PRODUCTION":
            print_status("JWT secret using insecure default", "WARNING", Colors.YELLOW)
        elif jwt_secret and len(jwt_secret) >= 32:
            print_status("JWT secret properly configured", "PASS", Colors.GREEN)
        else:
            print_status("JWT secret too short or missing", "FAIL", Colors.RED)

        # Test database password
        db_password = config.get("database.password")
        if db_password == "postgres":
            print_status("Database using default password", "WARNING", Colors.YELLOW)
        else:
            print_status("Database password configured", "PASS", Colors.GREEN)

        # Test API keys
        polygon_key = config.get("polygon.api_key")
        if polygon_key and polygon_key != "":
            print_status("Polygon API key configured", "PASS", Colors.GREEN)
        else:
            print_status("Polygon API key not set", "INFO", Colors.YELLOW)

    except Exception as e:
        print_status(f"Configuration loading failed: {e}", "ERROR", Colors.RED)


def generate_security_report(
    env_results: List[Tuple[str, bool, str]],
    secret_issues: List[Tuple[str, int, str]],
    config_issues: List[Tuple[str, str]],
    permission_issues: List[Tuple[str, str]],
):
    """Generate a comprehensive security report."""
    print_header("Security Validation Report")

    # Count issues
    env_errors = sum(1 for _, success, _ in env_results if not success)
    total_issues = (
        len(secret_issues) + len(config_issues) + len(permission_issues) + env_errors
    )

    if total_issues == 0:
        print_status("All security checks passed!", "SUCCESS", Colors.GREEN)
        print(
            f"\n{Colors.GREEN}✅ Your FXML4 installation is properly secured!{Colors.END}"
        )
        return True
    else:
        print_status(f"Found {total_issues} security issues", "ISSUES", Colors.RED)

        if env_errors > 0:
            print(f"\n{Colors.YELLOW}Environment Variable Issues:{Colors.END}")
            for var, success, message in env_results:
                if not success:
                    print(f"  • {var}: {message}")

        if secret_issues:
            print(f"\n{Colors.RED}Hardcoded Secrets:{Colors.END}")
            for file_path, line_num, description in secret_issues:
                print(f"  • {file_path}:{line_num} - {description}")

        if config_issues:
            print(f"\n{Colors.RED}Configuration Issues:{Colors.END}")
            for file_path, issue in config_issues:
                print(f"  • {file_path}: {issue}")

        if permission_issues:
            print(f"\n{Colors.RED}Permission Issues:{Colors.END}")
            for file_path, issue in permission_issues:
                print(f"  • {file_path}: {issue}")

        print(f"\n{Colors.YELLOW}📋 Next Steps:{Colors.END}")
        print("1. Set required environment variables")
        print("2. Replace any placeholder values with actual secrets")
        print("3. Fix file permissions (chmod 600 .env files)")
        print("4. Remove or replace hardcoded secrets")
        print("5. Run this script again to verify fixes")

        return False


def main():
    """Main validation function."""
    print(f"{Colors.BOLD}{Colors.MAGENTA}")
    print("🔒 FXML4 Security Validation Script")
    print("===================================")
    print(f"{Colors.END}")

    # Run all security checks
    env_results = check_environment_variables()
    secret_issues = scan_for_hardcoded_secrets()
    config_issues = validate_config_files()
    permission_issues = check_file_permissions()

    # Test configuration loading
    test_configuration_loading()

    # Generate final report
    success = generate_security_report(
        env_results, secret_issues, config_issues, permission_issues
    )

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
