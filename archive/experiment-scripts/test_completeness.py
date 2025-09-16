#!/usr/bin/env python3
"""
FXML4 Completeness Test Script

This script tests the completeness and basic functionality of the FXML4 application
without requiring external dependencies.
"""

import sys
import os
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_file_structure():
    """Test that essential files and directories exist."""
    print("=== Testing File Structure ===")
    
    essential_files = [
        "fxml4/__init__.py",
        "fxml4/main.py", 
        "fxml4/config.py",
        "fxml4/api/main.py",
        "fxml4/backtesting/backtest_engine.py",
        "fxml4/strategy/integrated_strategy.py",
        "fxml4/ml/features.py",
        "fxml4/wave_analysis/elliott_wave.py",
        "fxml4/data_engineering/data_feeds/base_feed.py",
        "fxml4/llm_integration/rag.py",
        "config/default.yaml",
        "requirements.txt",
        "setup.py",
        "Dockerfile",
        "docker-compose.yml",
        "README.md"
    ]
    
    missing_files = []
    for file_path in essential_files:
        if os.path.exists(file_path):
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path}")
            missing_files.append(file_path)
    
    essential_dirs = [
        "fxml4/api",
        "fxml4/backtesting", 
        "fxml4/strategy",
        "fxml4/ml",
        "fxml4/wave_analysis",
        "fxml4/data_engineering",
        "fxml4/llm_integration",
        "config",
        "docs",
        "tests"
    ]
    
    missing_dirs = []
    for dir_path in essential_dirs:
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            print(f"✓ {dir_path}/")
        else:
            print(f"✗ {dir_path}/")
            missing_dirs.append(dir_path)
    
    return missing_files, missing_dirs

def test_module_syntax():
    """Test that Python modules have valid syntax."""
    print("\n=== Testing Module Syntax ===")
    
    python_files = [
        "fxml4/__init__.py",
        "fxml4/main.py",
        "fxml4/config.py", 
        "fxml4/api/main.py",
        "fxml4/backtesting/backtest_engine.py",
        "fxml4/strategy/integrated_strategy.py",
        "fxml4/ml/features.py",
        "fxml4/wave_analysis/elliott_wave.py",
        "fxml4/data_engineering/data_feeds/base_feed.py",
        "fxml4/llm_integration/rag.py"
    ]
    
    syntax_errors = []
    for file_path in python_files:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    compile(f.read(), file_path, 'exec')
                print(f"✓ {file_path} - valid syntax")
            except SyntaxError as e:
                print(f"✗ {file_path} - syntax error: {e}")
                syntax_errors.append((file_path, str(e)))
            except Exception as e:
                print(f"? {file_path} - other error: {e}")
        else:
            print(f"- {file_path} - file not found")
    
    return syntax_errors

def test_configuration():
    """Test configuration loading."""
    print("\n=== Testing Configuration ===")
    
    try:
        import yaml
        with open('config/default.yaml', 'r') as f:
            config = yaml.safe_load(f)
        print("✓ YAML configuration loads successfully")
        
        # Check essential config sections
        essential_sections = [
            'api', 'database', 'data', 'ml', 'backtesting', 
            'wave_analysis', 'llm_integration'
        ]
        
        missing_sections = []
        for section in essential_sections:
            if section in config:
                print(f"✓ Config section '{section}' present")
            else:
                print(f"✗ Config section '{section}' missing")
                missing_sections.append(section)
        
        return missing_sections
        
    except ImportError:
        print("✗ PyYAML not available - cannot test config loading")
        return ["yaml_missing"]
    except Exception as e:
        print(f"✗ Configuration loading failed: {e}")
        return ["config_error"]

def test_docker_setup():
    """Test Docker configuration."""
    print("\n=== Testing Docker Setup ===")
    
    docker_files = [
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.dev.yml",
        "docker-compose.timescaledb.yml"
    ]
    
    missing_docker_files = []
    for file_path in docker_files:
        if os.path.exists(file_path):
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path}")
            missing_docker_files.append(file_path)
    
    return missing_docker_files

def test_api_endpoints():
    """Test API endpoint definitions."""
    print("\n=== Testing API Endpoints ===")
    
    try:
        # Read the API main file to check for endpoint definitions
        with open('fxml4/api/main.py', 'r') as f:
            api_content = f.read()
        
        expected_endpoints = [
            '@app.get("/")',
            '@app.get("/health")',
            '@app.post("/data")',
            '@app.post("/signals")', 
            '@app.post("/backtest")'
        ]
        
        missing_endpoints = []
        for endpoint in expected_endpoints:
            if endpoint in api_content:
                print(f"✓ API endpoint: {endpoint}")
            else:
                print(f"✗ API endpoint missing: {endpoint}")
                missing_endpoints.append(endpoint)
        
        return missing_endpoints
        
    except Exception as e:
        print(f"✗ API endpoint test failed: {e}")
        return ["api_test_error"]

def test_missing_components():
    """Test for components referenced in docker-compose but missing."""
    print("\n=== Testing Missing Components ===")
    
    # Components referenced in docker-compose.yml but not implemented
    missing_components = []
    
    # Check for UI module
    if not os.path.exists('fxml4/ui'):
        print("✗ fxml4/ui module missing (referenced in docker-compose)")
        missing_components.append("fxml4/ui")
    else:
        print("✓ fxml4/ui module present")
    
    # Check for worker module  
    if not os.path.exists('fxml4/worker'):
        print("✗ fxml4/worker module missing (referenced in docker-compose)")
        missing_components.append("fxml4/worker")
    else:
        print("✓ fxml4/worker module present")
    
    # Check for database migrations
    if not os.path.exists('db/migrations'):
        print("✗ db/migrations directory missing")
        missing_components.append("db/migrations")
    else:
        print("✓ db/migrations directory present")
    
    # Check for monitoring config
    if not os.path.exists('monitoring'):
        print("✗ monitoring directory missing (referenced in docker-compose)")
        missing_components.append("monitoring")
    else:
        print("✓ monitoring directory present")
    
    return missing_components

def main():
    """Run all tests and generate completeness report."""
    print("FXML4 Completeness Test")
    print("=" * 50)
    
    # Run all tests
    missing_files, missing_dirs = test_file_structure()
    syntax_errors = test_module_syntax()
    missing_config_sections = test_configuration()
    missing_docker_files = test_docker_setup()
    missing_endpoints = test_api_endpoints()
    missing_components = test_missing_components()
    
    # Generate summary report
    print("\n" + "=" * 50)
    print("COMPLETENESS SUMMARY")
    print("=" * 50)
    
    total_issues = (len(missing_files) + len(missing_dirs) + len(syntax_errors) +
                   len(missing_config_sections) + len(missing_docker_files) +
                   len(missing_endpoints) + len(missing_components))
    
    if total_issues == 0:
        print("🎉 FXML4 appears to be complete and ready for testing!")
    else:
        print(f"⚠️  Found {total_issues} completeness issues:")
        
        if missing_files:
            print(f"\n📄 Missing Files ({len(missing_files)}):")
            for f in missing_files:
                print(f"   - {f}")
        
        if missing_dirs:
            print(f"\n📁 Missing Directories ({len(missing_dirs)}):")
            for d in missing_dirs:
                print(f"   - {d}")
        
        if syntax_errors:
            print(f"\n🐛 Syntax Errors ({len(syntax_errors)}):")
            for f, e in syntax_errors:
                print(f"   - {f}: {e}")
        
        if missing_config_sections:
            print(f"\n⚙️  Missing Config Sections ({len(missing_config_sections)}):")
            for s in missing_config_sections:
                print(f"   - {s}")
        
        if missing_docker_files:
            print(f"\n🐳 Missing Docker Files ({len(missing_docker_files)}):")
            for f in missing_docker_files:
                print(f"   - {f}")
        
        if missing_endpoints:
            print(f"\n🌐 Missing API Endpoints ({len(missing_endpoints)}):")
            for e in missing_endpoints:
                print(f"   - {e}")
        
        if missing_components:
            print(f"\n🧩 Missing Components ({len(missing_components)}):")
            for c in missing_components:
                print(f"   - {c}")
    
    print(f"\nOverall Status: {'COMPLETE' if total_issues == 0 else 'INCOMPLETE'}")
    return total_issues == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)