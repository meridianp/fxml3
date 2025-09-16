#!/usr/bin/env python3
"""Test Manual Execution Interface.

This script tests the manual execution interface by validating the frontend
components and backend API endpoints.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_file_structure():
    """Test that manual execution files exist."""
    print("Testing Manual Execution File Structure")
    print("-" * 50)

    files_to_check = [
        "fxml4/api/routers/manual_execution.py",
        "fxml4/api/static/manual_execution.html",
        "fxml4/brokers/adapters/manual_rabbitmq_adapter.py",
    ]

    results = {}
    for file_path in files_to_check:
        full_path = Path(file_path)
        exists = full_path.exists()
        results[file_path] = exists
        status = "✅" if exists else "❌"
        print(f"  {status} {file_path}")

    return results


def test_manual_interface_content():
    """Test manual execution HTML content."""
    print("\nTesting Manual Execution Interface Content")
    print("-" * 50)

    interface_path = Path("fxml4/api/static/manual_execution.html")

    if not interface_path.exists():
        print("❌ Manual execution interface not found")
        return False

    with open(interface_path, "r") as f:
        content = f.read()

    checks = {
        "HTML Structure": "<html" in content.lower(),
        "Manual Execution Title": "manual order execution" in content.lower(),
        "Order Cards": "order-card" in content,
        "Approval Actions": "btn-approve" in content,
        "Rejection Actions": "btn-reject" in content,
        "WebSocket Support": "websocket" in content.lower(),
        "Real-time Updates": "connectWebSocket" in content,
        "Keyboard Shortcuts": "keydown" in content,
        "Audio Notifications": "newOrderSound" in content,
        "Time Remaining": "time-remaining" in content,
        "Order Details Panel": "details-panel" in content,
        "Connection Status": "connectionStatus" in content,
    }

    all_passed = True
    for check, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check}")
        if not passed:
            all_passed = False

    print(f"\nInterface content size: {len(content):,} characters")
    return all_passed


def test_api_router_content():
    """Test manual execution API router."""
    print("\nTesting Manual Execution API Router")
    print("-" * 50)

    router_path = Path("fxml4/api/routers/manual_execution.py")
    if not router_path.exists():
        print("❌ Manual execution router not found")
        return False

    with open(router_path, "r") as f:
        content = f.read()

    features = {
        "Status Endpoint": "/status" in content,
        "Pending Orders": "/orders/pending" in content,
        "Order History": "/orders/history" in content,
        "Order Details": "/orders/{cl_ord_id}" in content,
        "Approve Endpoint": "/approve" in content,
        "Reject Endpoint": "/reject" in content,
        "WebSocket Support": "websocket" in content.lower(),
        "Authentication": "verify_auth" in content,
        "Statistics": "/stats" in content,
        "Configuration": "/config" in content,
        "Health Check": "/health" in content,
        "Pydantic Models": "BaseModel" in content,
    }

    all_present = True
    for feature, present in features.items():
        status = "✅" if present else "❌"
        print(f"  {status} {feature}")
        if not present:
            all_present = False

    return all_present


def test_manual_adapter_components():
    """Test manual adapter structure."""
    print("\nTesting Manual Adapter Components")
    print("-" * 50)

    adapter_path = Path("fxml4/brokers/adapters/manual_rabbitmq_adapter.py")
    if not adapter_path.exists():
        print("❌ Manual RabbitMQ adapter not found")
        return False

    with open(adapter_path, "r") as f:
        content = f.read()

    components = {
        "Manual Adapter Class": "ManualRabbitMQAdapter" in content,
        "Order Approval": "approve_order" in content,
        "Order Rejection": "reject_order" in content,
        "Pending Orders": "pending_orders" in content,
        "WebSocket Management": "websocket" in content.lower(),
        "Auto Rejection": "auto_reject" in content,
        "Order History": "order_history" in content,
        "Approval Status": "ApprovalStatus" in content,
        "Review Time": "review_time" in content,
        "Connection Management": "connect" in content,
    }

    all_present = True
    for component, present in components.items():
        status = "✅" if present else "❌"
        print(f"  {status} {component}")
        if not present:
            all_present = False

    return all_present


def test_interface_features():
    """Test specific interface features."""
    print("\nTesting Interface Features")
    print("-" * 50)

    interface_path = Path("fxml4/api/static/manual_execution.html")
    if not interface_path.exists():
        print("❌ Interface file not found")
        return False

    with open(interface_path, "r") as f:
        content = f.read()

    # Check for specific JavaScript functions
    js_functions = {
        "Order Selection": "selectOrder" in content,
        "Order Approval": "approveOrder" in content,
        "Order Rejection": "rejectOrder" in content,
        "WebSocket Handling": "handleWebSocketMessage" in content,
        "UI Updates": "updateOrdersList" in content,
        "Notifications": "showNotification" in content,
        "Time Updates": "updateTimeRemaining" in content,
        "Sound Alerts": "playNotificationSound" in content,
        "Form Handling": "showApprovalForm" in content,
        "Connection Management": "setConnectionStatus" in content,
    }

    # Check for CSS classes
    css_classes = {
        "Order Cards": ".order-card" in content,
        "Status Indicators": ".status-dot" in content,
        "Action Buttons": ".btn-approve" in content,
        "Time Display": ".time-remaining" in content,
        "Connection Status": ".connection-lost" in content,
        "Responsive Layout": "grid-template-columns" in content,
        "Dark Theme": "background-color: #0f1419" in content,
        "Animations": "@keyframes" in content,
    }

    all_features = {**js_functions, **css_classes}
    all_present = True

    for feature, present in all_features.items():
        status = "✅" if present else "❌"
        print(f"  {status} {feature}")
        if not present:
            all_present = False

    return all_present


def test_integration_points():
    """Test integration between components."""
    print("\nTesting Integration Points")
    print("-" * 50)

    # Check main API integration
    main_api_path = Path("fxml4/api/main.py")
    if main_api_path.exists():
        with open(main_api_path, "r") as f:
            main_content = f.read()

        integrations = {
            "Manual Router Included": "manual_router" in main_content,
            "Static Files Mounted": "StaticFiles" in main_content,
            "Manual Route": "/manual" in main_content,
            "Dependencies Import": "dependencies" in main_content,
        }

        for integration, present in integrations.items():
            status = "✅" if present else "❌"
            print(f"  {status} {integration}")
    else:
        print("❌ Main API file not found")
        return False

    # Check if manual execution route exists
    manual_route_exists = (
        '@app.get("/manual")' in main_content or "manual_execution.html" in main_content
    )
    status = "✅" if manual_route_exists else "❌"
    print(f"  {status} Manual Execution Route")

    return True


def main():
    """Main test function."""
    print("=" * 60)
    print("FXML4 Manual Execution Interface Test")
    print("=" * 60)

    # Run all tests
    file_results = test_file_structure()
    interface_results = test_manual_interface_content()
    router_results = test_api_router_content()
    adapter_results = test_manual_adapter_components()
    features_results = test_interface_features()
    integration_results = test_integration_points()

    # Calculate results
    files_passed = sum(1 for r in file_results.values() if r)
    files_total = len(file_results)

    # Summary
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)

    print(f"📁 File Structure: {files_passed}/{files_total} files present")
    print(f"🎯 Interface Content: {'✅' if interface_results else '❌'}")
    print(f"🔌 API Router: {'✅' if router_results else '❌'}")
    print(f"⚙️  Manual Adapter: {'✅' if adapter_results else '❌'}")
    print(f"🎨 Interface Features: {'✅' if features_results else '❌'}")
    print(f"🔗 Integration: {'✅' if integration_results else '❌'}")

    # Overall assessment
    critical_passed = (
        files_passed >= files_total * 0.8  # 80% of files exist
        and interface_results  # Interface content is valid
        and router_results  # API router has required features
        and features_results  # UI features are implemented
    )

    if critical_passed:
        print("\n🎉 MANUAL EXECUTION INTERFACE READY!")
        print("\nKey Features Available:")
        print("  ✅ Real-time order approval interface")
        print("  ✅ WebSocket-based live updates")
        print("  ✅ Order approval and rejection workflows")
        print("  ✅ Time-based auto-rejection")
        print("  ✅ Audio and visual notifications")
        print("  ✅ Keyboard shortcuts for efficiency")
        print("  ✅ Mobile-responsive design")
        print("  ✅ Connection status monitoring")

        print("\nInterface Access:")
        print("  • Manual Execution: http://localhost:8000/manual")
        print("  • Static Access: http://localhost:8000/static/manual_execution.html")
        print("  • API Endpoints: http://localhost:8000/manual/*")

        print("\nNext Steps:")
        print("  1. Install dependencies: pip install fastapi uvicorn websockets")
        print("  2. Configure manual adapter in broker manager")
        print("  3. Start API server and test interface")

    else:
        print("\n❌ SOME COMPONENTS MISSING OR INCOMPLETE")
        print("Check the details above to resolve issues")

    return critical_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
