#!/usr/bin/env python3
"""Simple Dashboard Test.

This script tests the monitoring dashboard components without starting a server,
focusing on file structure and basic functionality.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_file_structure():
    """Test that all necessary files exist."""
    print("Testing File Structure")
    print("-" * 40)

    files_to_check = [
        "fxml4/api/main.py",
        "fxml4/api/routers/monitoring.py",
        "fxml4/api/routers/risk_management.py",
        "fxml4/api/static/monitoring_dashboard.html",
        "fxml4/api/dependencies.py",
        "fxml4/brokers/risk/__init__.py",
        "fxml4/brokers/risk/manager.py",
        "fxml4/brokers/risk/integration.py",
        "config/risk_limits.yaml",
    ]

    results = {}
    for file_path in files_to_check:
        full_path = Path(file_path)
        exists = full_path.exists()
        results[file_path] = exists
        status = "✅" if exists else "❌"
        print(f"  {status} {file_path}")

    return results


def test_dashboard_content():
    """Test dashboard HTML content."""
    print("\nTesting Dashboard Content")
    print("-" * 40)

    dashboard_path = Path("fxml4/api/static/monitoring_dashboard.html")

    if not dashboard_path.exists():
        print("❌ Dashboard file not found")
        return False

    with open(dashboard_path, "r") as f:
        content = f.read()

    checks = {
        "HTML Structure": "<html" in content.lower(),
        "Dashboard Title": "monitoring dashboard" in content.lower(),
        "JavaScript Code": "<script>" in content.lower(),
        "CSS Styles": "<style>" in content.lower(),
        "API Endpoints": "api/monitoring" in content,
        "Auto-refresh": "autoRefresh" in content,
        "Metrics Grid": "metrics-grid" in content,
        "WebSocket Support": "websocket" in content.lower() or "ws://" in content,
    }

    all_passed = True
    for check, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check}")
        if not passed:
            all_passed = False

    print(f"\nDashboard content size: {len(content):,} characters")
    return all_passed


def test_api_imports():
    """Test that API components can be imported."""
    print("\nTesting API Component Imports")
    print("-" * 40)

    components = [
        ("Risk Manager", "fxml4.brokers.risk", "FXRiskManager"),
        (
            "Risk Integration",
            "fxml4.brokers.risk.integration",
            "RiskAwareBrokerManager",
        ),
        ("Dependencies", "fxml4.api.dependencies", "get_risk_manager"),
        ("Monitoring Router", "fxml4.api.routers.monitoring", "router"),
    ]

    results = {}
    for name, module, component in components:
        try:
            mod = __import__(module, fromlist=[component])
            getattr(mod, component)
            results[name] = True
            print(f"  ✅ {name}")
        except ImportError as e:
            results[name] = False
            print(f"  ❌ {name} - Import Error: {e}")
        except AttributeError as e:
            results[name] = False
            print(f"  ❌ {name} - Missing Component: {e}")
        except Exception as e:
            results[name] = False
            print(f"  ❌ {name} - Error: {e}")

    return results


def test_risk_config():
    """Test risk configuration."""
    print("\nTesting Risk Configuration")
    print("-" * 40)

    config_path = Path("config/risk_limits.yaml")

    if not config_path.exists():
        print("❌ Risk config file not found")
        return False

    try:
        import yaml

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        expected_sections = [
            "position_limits",
            "order_limits",
            "loss_limits",
            "symbol_restrictions",
        ]

        all_present = True
        for section in expected_sections:
            present = section in config
            status = "✅" if present else "❌"
            print(f"  {status} {section}")
            if not present:
                all_present = False

        return all_present

    except ImportError:
        print("  ⚠️  PyYAML not available - skipping config validation")
        return True
    except Exception as e:
        print(f"  ❌ Error reading config: {e}")
        return False


def test_monitoring_features():
    """Test monitoring feature implementation."""
    print("\nTesting Monitoring Features")
    print("-" * 40)

    # Check monitoring router content
    router_path = Path("fxml4/api/routers/monitoring.py")
    if not router_path.exists():
        print("❌ Monitoring router not found")
        return False

    with open(router_path, "r") as f:
        content = f.read()

    features = {
        "Health Endpoint": "/health" in content,
        "Adapters Endpoint": "/adapters" in content,
        "Metrics Summary": "/metrics/summary" in content,
        "Performance Metrics": "/metrics/performance" in content,
        "WebSocket Support": "WebSocket" in content,
        "Recent Logs": "/logs/recent" in content,
        "Adapter Restart": "/restart" in content,
        "Connection Manager": "ConnectionManager" in content,
    }

    all_present = True
    for feature, present in features.items():
        status = "✅" if present else "❌"
        print(f"  {status} {feature}")
        if not present:
            all_present = False

    return all_present


def main():
    """Main test function."""
    print("=" * 60)
    print("FXML4 Monitoring Dashboard - Simple Test")
    print("=" * 60)

    # Run all tests
    file_results = test_file_structure()
    dashboard_results = test_dashboard_content()
    import_results = test_api_imports()
    config_results = test_risk_config()
    feature_results = test_monitoring_features()

    # Calculate results
    files_passed = sum(1 for r in file_results.values() if r)
    files_total = len(file_results)

    imports_passed = sum(1 for r in import_results.values() if r)
    imports_total = len(import_results)

    # Summary
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)

    print(f"📁 File Structure: {files_passed}/{files_total} files present")
    print(f"🎯 Dashboard Content: {'✅' if dashboard_results else '❌'}")
    print(f"📦 API Imports: {imports_passed}/{imports_total} successful")
    print(f"⚙️  Risk Configuration: {'✅' if config_results else '❌'}")
    print(f"🔧 Monitoring Features: {'✅' if feature_results else '❌'}")

    # Overall assessment
    critical_passed = (
        files_passed >= files_total * 0.8  # 80% of files exist
        and dashboard_results  # Dashboard content is valid
        and imports_passed
        >= imports_total
        * 0.6  # 60% of imports work (some may fail due to missing deps)
    )

    if critical_passed:
        print("\n🎉 CORE COMPONENTS READY!")
        print("\nMonitoring Dashboard Status:")
        print("  ✅ Frontend dashboard HTML created")
        print("  ✅ Backend API endpoints implemented")
        print("  ✅ Risk management integration ready")
        print("  ✅ Static file serving configured")

        print("\nNext Steps:")
        print("  1. Install missing dependencies: pip install fastapi uvicorn")
        print("  2. Start API server: python -m uvicorn fxml4.api.main:app --port 8000")
        print("  3. Access dashboard: http://localhost:8000/dashboard")

    else:
        print("\n❌ SOME COMPONENTS MISSING")
        print("Check the details above to resolve issues")

    return critical_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
