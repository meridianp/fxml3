#!/usr/bin/env python3
"""
FXML4 API Test Runner

Master script for running comprehensive API tests for the FXML4 trading platform.
This script provides a command-line interface to execute different types of API tests
including endpoint discovery, contract validation, security testing, and comprehensive
orchestrated test suites.

Usage:
    python tests/run_api_tests.py --help
    python tests/run_api_tests.py discovery
    python tests/run_api_tests.py contracts
    python tests/run_api_tests.py security
    python tests/run_api_tests.py comprehensive
    python tests/run_api_tests.py all

Features:
- Test-driven development (TDD) approach
- Comprehensive endpoint discovery (145+ endpoints)
- Contract validation testing
- Security vulnerability assessment
- Authentication and authorization testing
- Performance and load testing
- HTML and JSON report generation
- CI/CD integration ready
"""

import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.api.test_authentication_security import SecurityTestSuite
from tests.api.test_contract_validation import APIContractValidator

# Import our test frameworks
from tests.api.test_endpoint_discovery import APIEndpointDiscovery
from tests.api.test_orchestration import APITestOrchestrator


def setup_logging(level: str = "INFO"):
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def run_endpoint_discovery(
    api_root: Path, verbose: bool = False
) -> Dict[str, Any]:
    """Run endpoint discovery tests"""
    print("🔍 Running API Endpoint Discovery...")
    start_time = time.time()

    discovery = APIEndpointDiscovery(api_root)
    endpoints = discovery.discover_all_endpoints()
    summary = discovery.generate_endpoint_summary()

    duration = time.time() - start_time

    print(f"✅ Discovery completed in {duration:.2f}s")
    print(
        f"   📊 Found {len(endpoints)} endpoints across {summary['router_files_processed']} router files"
    )
    print(
        f"   🔐 {summary['authentication_required']} endpoints require authentication"
    )

    if verbose:
        print("\n📋 Endpoints by category:")
        for category, count in summary["by_category"].items():
            print(f"   • {category}: {count}")

        print("\n📋 Endpoints by HTTP method:")
        for method, count in summary["by_method"].items():
            print(f"   • {method}: {count}")

        print("\n📋 Sample endpoints:")
        for endpoint in endpoints[:10]:
            auth_icon = "🔒" if endpoint.requires_auth else "🌐"
            print(
                f"   {auth_icon} {endpoint.method:6} {endpoint.path:30} [{endpoint.category.value}]"
            )

        if len(endpoints) > 10:
            print(f"   ... and {len(endpoints) - 10} more endpoints")

    return {"endpoints_count": len(endpoints), "summary": summary, "duration": duration}


async def run_contract_validation(
    api_base_url: str, max_endpoints: int = 20, verbose: bool = False
) -> Dict[str, Any]:
    """Run contract validation tests"""
    print("📋 Running API Contract Validation...")
    start_time = time.time()

    # First discover endpoints
    api_root = Path(__file__).parent.parent / "fxml4" / "api"
    discovery = APIEndpointDiscovery(api_root)
    all_endpoints = discovery.discover_all_endpoints()

    # Filter to safe endpoints for testing
    safe_endpoints = [
        ep
        for ep in all_endpoints
        if ep.method in ["GET", "POST"]
        and not any(
            dangerous in ep.path.lower()
            for dangerous in ["delete", "remove", "destroy", "stop", "cancel"]
        )
    ][:max_endpoints]

    print(f"   🎯 Testing {len(safe_endpoints)} safe endpoints (limited for demo)")

    # Run contract validation
    validator = APIContractValidator(api_base_url)

    try:
        results = await validator.validate_all_endpoints(safe_endpoints)
        report = validator.generate_contract_report(results)

        duration = time.time() - start_time

        print(f"✅ Contract validation completed in {duration:.2f}s")
        print(
            f"   📊 {report['summary']['passed']}/{report['summary']['total_endpoints']} endpoints passed"
        )
        print(f"   🎯 Success rate: {report['summary']['success_rate']:.1f}%")
        print(
            f"   ⚡ Average response time: {report['performance']['average_response_time_ms']:.2f}ms"
        )

        if report["summary"]["failed"] > 0:
            print(f"   ⚠️  {report['summary']['failed']} endpoints failed validation")

            if verbose:
                print("\n❌ Failed endpoints:")
                for failed in report["failed_endpoints"][:5]:
                    print(
                        f"   • {failed['method']} {failed['endpoint']} - {failed['violations']} violations"
                    )

        return {"results": results, "report": report, "duration": duration}

    finally:
        await validator.close()


async def run_security_tests(
    api_base_url: str, include_penetration: bool = False, verbose: bool = False
) -> Dict[str, Any]:
    """Run security tests"""
    print("🔒 Running Security Tests...")
    start_time = time.time()

    security_suite = SecurityTestSuite(api_base_url)

    try:
        all_results = []

        # Authentication tests
        print("   🔐 Testing authentication mechanisms...")
        auth_results = await security_suite.test_authentication_mechanisms()
        all_results.extend(auth_results)

        # Authorization tests
        print("   🛡️  Testing authorization controls...")
        authz_results = await security_suite.test_authorization_controls()
        all_results.extend(authz_results)

        # Injection vulnerability tests (limited for safety)
        if include_penetration:
            print("   💉 Testing injection vulnerabilities...")
            injection_results = await security_suite.test_injection_vulnerabilities()
            all_results.extend(injection_results)

        # Rate limiting tests
        print("   🚦 Testing rate limiting...")
        rate_results = await security_suite.test_rate_limiting()
        all_results.extend(rate_results)

        # Security headers tests
        print("   📄 Testing security headers...")
        headers_results = await security_suite.test_security_headers()
        all_results.extend(headers_results)

        # Generate security report
        report = await security_suite.generate_security_report(all_results)

        duration = time.time() - start_time

        print(f"✅ Security testing completed in {duration:.2f}s")
        print(
            f"   📊 {report['summary']['passed']}/{report['summary']['total_tests']} tests passed"
        )
        print(f"   🎯 Success rate: {report['summary']['success_rate']:.1f}%")
        print(f"   🔢 Security score: {report['summary']['security_score']:.1f}/100")
        print(f"   ⚠️  Risk level: {report['risk_assessment']['overall_risk']}")

        if report["risk_assessment"]["critical_findings_count"] > 0:
            print(
                f"   🚨 {report['risk_assessment']['critical_findings_count']} critical security findings"
            )

            if verbose:
                print("\n🚨 Critical findings:")
                for finding in report["critical_findings"][:3]:
                    print(f"   • {finding['test_type']}: {finding['details']}")

        if verbose and report["recommendations"]:
            print("\n💡 Security recommendations:")
            for rec in report["recommendations"][:3]:
                print(f"   • {rec}")

        return {"results": all_results, "report": report, "duration": duration}

    finally:
        await security_suite.close()


async def run_comprehensive_tests(
    api_base_url: str, api_root: Path, verbose: bool = False
) -> Dict[str, Any]:
    """Run comprehensive orchestrated test suite"""
    print("🎯 Running Comprehensive Test Suite...")
    print("   This includes discovery, contracts, security, and performance testing")

    orchestrator = APITestOrchestrator(api_base_url, api_root)

    # Configure for demonstration
    orchestrator.test_config.update(
        {
            "discovery": {"enabled": True, "timeout_seconds": 30},
            "contract_validation": {
                "enabled": True,
                "timeout_seconds": 180,
                "max_endpoints": 15,
                "safe_endpoints_only": True,
            },
            "security_testing": {
                "enabled": True,
                "timeout_seconds": 240,
                "include_penetration_tests": False,
            },
            "performance_testing": {"enabled": True, "timeout_seconds": 60},
        }
    )

    start_time = time.time()

    try:
        report = await orchestrator.execute_comprehensive_test_suite()

        duration = time.time() - start_time

        print(f"✅ Comprehensive testing completed in {duration:.2f}s")
        print(f"   📊 Overall success rate: {report.overall_success_rate:.1f}%")
        print(f"   🔍 Endpoints discovered: {report.endpoints_discovered}")
        print(f"   📋 Contracts validated: {report.contracts_validated}")
        print(f"   🔒 Security tests run: {report.security_tests_run}")
        print(f"   🚨 Critical issues: {len(report.critical_issues)}")

        print(f"\n📋 Phase Results:")
        for phase in report.phase_results:
            status_icon = "✅" if phase.status.value == "completed" else "❌"
            print(
                f"   {status_icon} {phase.phase.value}: {phase.tests_passed}/{phase.tests_run} passed ({phase.duration_seconds:.1f}s)"
            )
            if phase.error_message:
                print(f"      ⚠️  {phase.error_message}")

        if verbose and report.critical_issues:
            print(f"\n🚨 Critical Issues:")
            for issue in report.critical_issues[:3]:
                print(
                    f"   • {issue.get('type', 'Unknown')}: {issue.get('details', 'No details')}"
                )

        if verbose and report.recommendations:
            print(f"\n💡 Recommendations:")
            for rec in report.recommendations[:3]:
                print(f"   • {rec}")

        # Save reports
        try:
            json_path, html_path = orchestrator.save_report(report)
            print(f"\n📄 Reports saved:")
            print(f"   📊 JSON: {json_path}")
            print(f"   🌐 HTML: {html_path}")
        except Exception as e:
            print(f"   ⚠️  Could not save reports: {e}")

        return {"report": report, "duration": duration}

    except Exception as e:
        print(f"❌ Comprehensive testing failed: {e}")
        raise


async def run_all_tests(
    api_base_url: str, api_root: Path, verbose: bool = False
) -> Dict[str, Any]:
    """Run all individual test suites"""
    print("🚀 Running All API Tests...")
    print("   This runs each test suite individually for maximum coverage")

    overall_start = time.time()
    results = {}

    try:
        # 1. Endpoint Discovery
        discovery_results = await run_endpoint_discovery(api_root, verbose)
        results["discovery"] = discovery_results

        print()  # Add spacing between test suites

        # 2. Contract Validation
        contract_results = await run_contract_validation(
            api_base_url, max_endpoints=25, verbose=verbose
        )
        results["contracts"] = contract_results

        print()

        # 3. Security Testing
        security_results = await run_security_tests(
            api_base_url, include_penetration=False, verbose=verbose
        )
        results["security"] = security_results

        overall_duration = time.time() - overall_start

        print(f"\n🎉 All tests completed in {overall_duration:.2f}s")
        print("📊 Summary:")
        print(f"   🔍 Endpoints discovered: {discovery_results['endpoints_count']}")
        print(
            f"   📋 Contract success rate: {contract_results['report']['summary']['success_rate']:.1f}%"
        )
        print(
            f"   🔒 Security score: {security_results['report']['summary']['security_score']:.1f}/100"
        )

        return results

    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        raise


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="FXML4 API Test Runner - Comprehensive API Testing Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tests/run_api_tests.py discovery                    # Discover API endpoints
  python tests/run_api_tests.py contracts --verbose         # Test API contracts with details
  python tests/run_api_tests.py security                     # Run security tests
  python tests/run_api_tests.py comprehensive               # Full orchestrated test suite
  python tests/run_api_tests.py all --verbose               # All tests with full output

  python tests/run_api_tests.py contracts --api-url http://localhost:8000  # Custom API URL
        """,
    )

    parser.add_argument(
        "test_type",
        choices=["discovery", "contracts", "security", "comprehensive", "all"],
        help="Type of tests to run",
    )

    parser.add_argument(
        "--api-url",
        default="http://localhost:8001",
        help="Base URL for API testing (default: http://localhost:8001)",
    )

    parser.add_argument(
        "--api-root",
        type=Path,
        help="Path to API root directory (auto-detected if not provided)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output with detailed results",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)",
    )

    parser.add_argument(
        "--max-endpoints",
        type=int,
        default=20,
        help="Maximum endpoints to test for contract validation (default: 20)",
    )

    parser.add_argument(
        "--include-penetration",
        action="store_true",
        help="Include penetration testing (injection attacks) - use with caution",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)

    # Determine API root path
    api_root = args.api_root or Path(__file__).parent.parent / "fxml4" / "api"
    if not api_root.exists():
        print(f"❌ API root directory not found: {api_root}")
        print(
            "   Please ensure you're running from the project root or specify --api-root"
        )
        return 1

    print("=" * 70)
    print("🚀 FXML4 API TEST RUNNER")
    print("=" * 70)
    print(f"📍 API URL: {args.api_url}")
    print(f"📁 API Root: {api_root}")
    print(f"🧪 Test Type: {args.test_type}")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Run the selected test type
    try:
        if args.test_type == "discovery":
            asyncio.run(run_endpoint_discovery(api_root, args.verbose))

        elif args.test_type == "contracts":
            asyncio.run(
                run_contract_validation(args.api_url, args.max_endpoints, args.verbose)
            )

        elif args.test_type == "security":
            asyncio.run(
                run_security_tests(args.api_url, args.include_penetration, args.verbose)
            )

        elif args.test_type == "comprehensive":
            asyncio.run(run_comprehensive_tests(args.api_url, api_root, args.verbose))

        elif args.test_type == "all":
            asyncio.run(run_all_tests(args.api_url, api_root, args.verbose))

        print()
        print("=" * 70)
        print("✅ Testing completed successfully!")
        print("💡 Tip: Use --verbose for detailed output and recommendations")
        print("=" * 70)

        return 0

    except KeyboardInterrupt:
        print("\n⚠️  Testing interrupted by user")
        return 1

    except Exception as e:
        print(f"\n❌ Testing failed with error: {e}")
        if args.log_level == "DEBUG":
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
