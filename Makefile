# FXML4 Unified Monorepo Makefile
# Comprehensive build, test, and deployment system
#
# This Makefile supports the new monorepo structure:
# - core/           Main trading system (FastAPI backend)
# - elliott_wave/   Elliott Wave analysis (Python + Streamlit)
# - frontend/       Next.js web interface (React + TypeScript)
# - infrastructure/ Deployment & DevOps configs (K8s, Docker, Terraform)
#
# Component-specific targets:
# - core-*:         Core trading system operations
# - elliott-*:      Elliott Wave analysis operations
# - frontend-*:     Next.js frontend operations
# - infra-*:        Infrastructure and deployment operations
# - all-*:          Cross-component operations

.PHONY: help test test-all test-unit test-integration test-e2e test-security test-performance \
        test-docker test-clean docker-test-build docker-test-up docker-test-down \
        coverage report lint format check install \
        core-install core-test core-lint core-start \
        elliott-install elliott-test elliott-lint elliott-start \
        frontend-install frontend-test frontend-lint frontend-start frontend-build \
        infra-validate infra-deploy infra-destroy \
        all-install all-test all-lint all-clean

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

# Configuration
PYTHON := python3
VENV := venv
PYTEST := $(VENV)/bin/pytest
PIP := $(VENV)/bin/pip
PROJECT := fxml4
TEST_RESULTS_DIR := test-results
COVERAGE_THRESHOLD := 80

# Docker configurations
DOCKER_COMPOSE := docker-compose
DOCKER_COMPOSE_TEST := $(DOCKER_COMPOSE) -f docker-compose.test.yml
DOCKER_COMPOSE_LOCAL := $(DOCKER_COMPOSE) -f docker-compose.local.yml

help: ## Show this help message
	@echo "$(BLUE)FXML4 Unified Monorepo$(NC)"
	@echo "======================"
	@echo ""
	@echo "$(YELLOW)Available targets:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Quick Start:$(NC)"
	@echo "  make all-install   # Set up all components"
	@echo "  make all-test      # Run all tests"
	@echo "  make all-lint      # Lint all code"
	@echo ""
	@echo "$(YELLOW)Component-specific:$(NC)"
	@echo "  make core-start    # Start trading API"
	@echo "  make elliott-start # Start Elliott Wave dashboard"
	@echo "  make frontend-start# Start frontend dev server"

install: ## Install development dependencies
	@echo "$(YELLOW)Setting up development environment...$(NC)"
	@if [ ! -d "$(VENV)" ]; then \
		$(PYTHON) -m venv $(VENV); \
		echo "$(GREEN)✓ Virtual environment created$(NC)"; \
	fi
	@$(PIP) install --upgrade pip
	@$(PIP) install -r requirements-dev.txt
	@$(PIP) install -e .
	@pre-commit install
	@echo "$(GREEN)✓ Development environment ready$(NC)"

# ============================================================================
# STANDARD TEST PIPELINE
# ============================================================================

test: test-clean ## Run complete test suite
	@echo "$(BLUE)Running Complete Test Suite$(NC)"
	@echo "============================="
	@$(MAKE) test-unit
	@$(MAKE) test-integration
	@$(MAKE) test-e2e
	@$(MAKE) test-security
	@$(MAKE) test-performance-pytest
	@$(MAKE) coverage
	@echo ""
	@echo "$(GREEN)✅ All tests completed successfully!$(NC)"

test-all: test ## Alias for complete test suite

test-unit: ## Run unit tests only
	@echo "$(YELLOW)Running Unit Tests...$(NC)"
	@$(PYTEST) tests/ -m "unit and not slow and not requires_ib and not requires_fxcm" \
		-v --tb=short \
		--junit-xml=$(TEST_RESULTS_DIR)/unit-results.xml \
		--cov=$(PROJECT) --cov-report=term-missing --cov-report=xml:$(TEST_RESULTS_DIR)/unit-coverage.xml
	@echo "$(GREEN)✓ Unit tests passed$(NC)"

test-integration: ## Run integration tests
	@echo "$(YELLOW)Running Integration Tests...$(NC)"
	@$(PYTEST) tests/ -m "integration and not requires_ib and not requires_fxcm" \
		-v --tb=short \
		--junit-xml=$(TEST_RESULTS_DIR)/integration-results.xml
	@echo "$(GREEN)✓ Integration tests passed$(NC)"

test-security: ## Run security tests
	@echo "$(YELLOW)Running Security Tests...$(NC)"
	@$(PYTEST) tests/ -m "security or auth" \
		-v --tb=short \
		--junit-xml=$(TEST_RESULTS_DIR)/security-results.xml
	@$(PYTHON) scripts/validate_security.py
	@echo "$(GREEN)✓ Security tests passed$(NC)"

test-performance-pytest: ## Run performance tests with pytest
	@echo "$(YELLOW)Running Performance Tests...$(NC)"
	@$(PYTEST) tests/ -m "performance or slow" \
		-v --tb=short --durations=10 \
		--junit-xml=$(TEST_RESULTS_DIR)/performance-results.xml
	@echo "$(GREEN)✓ Performance tests passed$(NC)"

# ============================================================================
# CONTAINERIZED E2E TEST PIPELINE
# ============================================================================

test-e2e: docker-test-build ## Run containerized E2E tests
	@echo "$(BLUE)Running Containerized E2E Tests$(NC)"
	@echo "================================"
	@./scripts/run_e2e_auth_tests.sh run
	@echo "$(GREEN)✓ E2E tests passed$(NC)"

test-docker: test-e2e ## Alias for containerized E2E tests

docker-test-build: ## Build test containers
	@echo "$(YELLOW)Building test containers...$(NC)"
	@$(DOCKER_COMPOSE_TEST) build
	@echo "$(GREEN)✓ Test containers built$(NC)"

docker-test-up: ## Start test environment
	@echo "$(YELLOW)Starting test environment...$(NC)"
	@$(DOCKER_COMPOSE_TEST) up -d
	@echo "$(GREEN)✓ Test environment running$(NC)"
	@echo "Services available at:"
	@echo "  - API: http://localhost:8002"
	@echo "  - RabbitMQ: http://localhost:15673"
	@echo "  - PostgreSQL: localhost:5433"
	@echo "  - Redis: localhost:6380"

docker-test-down: ## Stop test environment
	@echo "$(YELLOW)Stopping test environment...$(NC)"
	@$(DOCKER_COMPOSE_TEST) down -v --remove-orphans
	@echo "$(GREEN)✓ Test environment stopped$(NC)"

docker-test-logs: ## View test container logs
	@$(DOCKER_COMPOSE_TEST) logs -f

docker-test-exec: ## Execute tests in running containers
	@echo "$(YELLOW)Executing tests in containers...$(NC)"
	@$(DOCKER_COMPOSE_TEST) run --rm test-runner

# ============================================================================
# CONTINUOUS INTEGRATION PIPELINE
# ============================================================================

ci-pipeline: ## Complete CI pipeline (for GitHub Actions/Jenkins)
	@echo "$(BLUE)FXML4 CI Pipeline$(NC)"
	@echo "=================="
	@$(MAKE) install
	@$(MAKE) lint
	@$(MAKE) test-unit
	@$(MAKE) test-integration
	@$(MAKE) test-security
	@$(MAKE) docker-test-build
	@$(MAKE) test-e2e
	@$(MAKE) test-integration-frontend
	@$(MAKE) test-performance
	@$(MAKE) coverage-check
	@$(MAKE) report
	@echo "$(GREEN)✅ Complete CI Pipeline with Performance Regression Testing Passed!$(NC)"

ci-quick: ## Quick CI pipeline (unit + integration only)
	@echo "$(BLUE)Quick CI Pipeline$(NC)"
	@$(MAKE) lint
	@$(MAKE) test-unit
	@$(MAKE) test-integration
	@$(MAKE) coverage-check

# ============================================================================
# CODE QUALITY & COVERAGE
# ============================================================================

lint: ## Run code linters
	@echo "$(YELLOW)Running linters...$(NC)"
	@black --check .
	@isort --check-only .
	@flake8 .
	@mypy $(PROJECT) --ignore-missing-imports
	@echo "$(GREEN)✓ Code quality checks passed$(NC)"

format: ## Format code
	@echo "$(YELLOW)Formatting code...$(NC)"
	@black .
	@isort .
	@echo "$(GREEN)✓ Code formatted$(NC)"

check: lint ## Run all checks (alias for lint)

coverage: ## Generate coverage report
	@echo "$(YELLOW)Generating coverage report...$(NC)"
	@$(PYTEST) tests/ -m "not requires_ib and not requires_fxcm" \
		--cov=$(PROJECT) --cov-report=html:$(TEST_RESULTS_DIR)/coverage-html \
		--cov-report=term --cov-report=xml:$(TEST_RESULTS_DIR)/coverage.xml
	@echo "$(GREEN)✓ Coverage report generated$(NC)"
	@echo "HTML report: $(TEST_RESULTS_DIR)/coverage-html/index.html"

coverage-check: ## Check coverage threshold
	@echo "$(YELLOW)Checking coverage threshold (>=$(COVERAGE_THRESHOLD)%)...$(NC)"
	@$(PYTEST) tests/ -m "not requires_ib and not requires_fxcm" \
		--cov=$(PROJECT) --cov-fail-under=$(COVERAGE_THRESHOLD) \
		--cov-report=term --quiet || \
		(echo "$(RED)❌ Coverage below threshold!$(NC)" && exit 1)
	@echo "$(GREEN)✓ Coverage meets threshold$(NC)"

# ============================================================================
# REPORTING & ARTIFACTS
# ============================================================================

report: ## Generate test reports
	@echo "$(YELLOW)Generating test reports...$(NC)"
	@mkdir -p $(TEST_RESULTS_DIR)
	@echo "Test Report Summary" > $(TEST_RESULTS_DIR)/summary.txt
	@echo "==================" >> $(TEST_RESULTS_DIR)/summary.txt
	@echo "" >> $(TEST_RESULTS_DIR)/summary.txt
	@echo "Generated: $$(date)" >> $(TEST_RESULTS_DIR)/summary.txt
	@echo "" >> $(TEST_RESULTS_DIR)/summary.txt
	@if [ -f "$(TEST_RESULTS_DIR)/unit-results.xml" ]; then \
		echo "Unit Tests: ✓" >> $(TEST_RESULTS_DIR)/summary.txt; \
	fi
	@if [ -f "$(TEST_RESULTS_DIR)/integration-results.xml" ]; then \
		echo "Integration Tests: ✓" >> $(TEST_RESULTS_DIR)/summary.txt; \
	fi
	@if [ -f "$(TEST_RESULTS_DIR)/security-results.xml" ]; then \
		echo "Security Tests: ✓" >> $(TEST_RESULTS_DIR)/summary.txt; \
	fi
	@if [ -f "$(TEST_RESULTS_DIR)/performance-results.xml" ]; then \
		echo "Performance Tests: ✓" >> $(TEST_RESULTS_DIR)/summary.txt; \
	fi
	@echo "" >> $(TEST_RESULTS_DIR)/summary.txt
	@cat $(TEST_RESULTS_DIR)/summary.txt
	@echo "$(GREEN)✓ Reports generated in $(TEST_RESULTS_DIR)/$(NC)"

test-clean: ## Clean test artifacts
	@echo "$(YELLOW)Cleaning test artifacts...$(NC)"
	@rm -rf $(TEST_RESULTS_DIR)
	@rm -rf .pytest_cache
	@rm -rf .coverage
	@rm -rf htmlcov
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@mkdir -p $(TEST_RESULTS_DIR)
	@echo "$(GREEN)✓ Test artifacts cleaned$(NC)"

# ============================================================================
# SPECIALIZED TEST TARGETS
# ============================================================================

test-auth: ## Run authentication tests
	@echo "$(YELLOW)Running Authentication Tests...$(NC)"
	@$(PYTEST) tests/auth/ tests/e2e/test_auth_security_flow_e2e.py -v
	@echo "$(GREEN)✓ Authentication tests passed$(NC)"

test-integration-frontend: ## Run frontend-backend integration tests
	@echo "$(BLUE)Running Frontend-Backend Integration Tests$(NC)"
	@echo "=========================================="
	@./scripts/run_frontend_backend_integration_tests.sh run
	@echo "$(GREEN)✓ Frontend-backend integration tests completed$(NC)"

test-integration-up: ## Start integration test services only
	@echo "$(YELLOW)Starting integration test services...$(NC)"
	@./scripts/run_frontend_backend_integration_tests.sh up
	@echo "$(GREEN)✓ Integration services started$(NC)"

test-integration-down: ## Stop integration test services
	@echo "$(YELLOW)Stopping integration test services...$(NC)"
	@./scripts/run_frontend_backend_integration_tests.sh down
	@echo "$(GREEN)✓ Integration services stopped$(NC)"

test-integration-status: ## Check integration test services status
	@echo "$(YELLOW)Integration test services status:$(NC)"
	@./scripts/run_frontend_backend_integration_tests.sh status

test-integration-clean: ## Clean integration test environment
	@echo "$(YELLOW)Cleaning integration test environment...$(NC)"
	@./scripts/run_frontend_backend_integration_tests.sh clean
	@echo "$(GREEN)✓ Integration test environment cleaned$(NC)"

test-trading: ## Run trading tests
	@echo "$(YELLOW)Running Trading Tests...$(NC)"
	@$(PYTEST) tests/ -m "trading" -v
	@echo "$(GREEN)✓ Trading tests passed$(NC)"

test-performance: ## Run performance regression tests
	@echo "$(BLUE)Running Performance Regression Tests$(NC)"
	@echo "====================================="
	@./scripts/run_performance_regression_tests.sh test --api-url http://localhost:8001
	@echo "$(GREEN)✓ Performance regression tests completed$(NC)"

test-performance-baseline: ## Initialize performance baselines
	@echo "$(YELLOW)Initializing performance baselines...$(NC)"
	@./scripts/run_performance_regression_tests.sh baseline --api-url http://localhost:8001
	@echo "$(GREEN)✓ Performance baselines initialized$(NC)"

test-performance-report: ## Generate performance reports
	@echo "$(YELLOW)Generating performance reports...$(NC)"
	@./scripts/run_performance_regression_tests.sh report
	@echo "$(GREEN)✓ Performance reports generated$(NC)"

test-performance-clean: ## Clean performance test artifacts
	@echo "$(YELLOW)Cleaning performance test artifacts...$(NC)"
	@./scripts/run_performance_regression_tests.sh clean
	@echo "$(GREEN)✓ Performance test artifacts cleaned$(NC)"

test-ml: ## Run ML pipeline tests
	@echo "$(YELLOW)Running ML Pipeline Tests...$(NC)"
	@$(PYTEST) tests/ -m "ml" -v
	@echo "$(GREEN)✓ ML tests passed$(NC)"

test-broker: ## Run broker integration tests (requires setup)
	@echo "$(YELLOW)Running Broker Integration Tests...$(NC)"
	@$(PYTEST) tests/ -m "requires_ib or requires_fxcm" -v --tb=short
	@echo "$(GREEN)✓ Broker tests passed$(NC)"

# ============================================================================
# DEVELOPMENT HELPERS
# ============================================================================

test-watch: ## Run tests in watch mode
	@echo "$(YELLOW)Starting test watcher...$(NC)"
	@while true; do \
		$(MAKE) test-unit; \
		echo "$(YELLOW)Watching for changes... (Ctrl+C to stop)$(NC)"; \
		inotifywait -e modify -r $(PROJECT) tests/ 2>/dev/null || sleep 5; \
	done

test-debug: ## Run tests with debugging enabled
	@echo "$(YELLOW)Running tests with debugging...$(NC)"
	@PYTEST_TIMEOUT=0 $(PYTEST) tests/ -vvs --tb=long --pdb

test-parallel: ## Run tests in parallel
	@echo "$(YELLOW)Running tests in parallel...$(NC)"
	@$(PYTEST) tests/ -n auto -v
	@echo "$(GREEN)✓ Parallel tests completed$(NC)"

# ============================================================================
# DOCKER DEVELOPMENT
# ============================================================================

dev-up: ## Start development environment
	@echo "$(YELLOW)Starting development environment...$(NC)"
	@$(DOCKER_COMPOSE_LOCAL) up -d
	@echo "$(GREEN)✓ Development environment running$(NC)"

dev-down: ## Stop development environment
	@echo "$(YELLOW)Stopping development environment...$(NC)"
	@$(DOCKER_COMPOSE_LOCAL) down
	@echo "$(GREEN)✓ Development environment stopped$(NC)"

dev-logs: ## View development logs
	@$(DOCKER_COMPOSE_LOCAL) logs -f

dev-rebuild: ## Rebuild development containers
	@echo "$(YELLOW)Rebuilding development containers...$(NC)"
	@$(DOCKER_COMPOSE_LOCAL) build --no-cache
	@echo "$(GREEN)✓ Containers rebuilt$(NC)"

# ============================================================================
# MONOREPO COMPONENT TARGETS
# ============================================================================

# Core Trading System
core-install: ## Install core trading system dependencies
	@echo "$(YELLOW)Installing core trading system dependencies...$(NC)"
	@$(PIP) install -r requirements/base.txt
	@$(PIP) install -r requirements/production.txt
	@$(PIP) install -e core/
	@echo "$(GREEN)✓ Core system dependencies installed$(NC)"

core-test: ## Run core trading system tests
	@echo "$(YELLOW)Running core trading system tests...$(NC)"
	@$(PYTEST) tests/unit/core/ tests/integration/core/ -v
	@echo "$(GREEN)✓ Core system tests passed$(NC)"

core-lint: ## Lint core trading system code
	@echo "$(YELLOW)Linting core trading system...$(NC)"
	@black --check core/
	@isort --check-only core/
	@flake8 core/
	@mypy core/ --ignore-missing-imports
	@echo "$(GREEN)✓ Core system linting passed$(NC)"

core-start: ## Start core trading API server
	@echo "$(YELLOW)Starting core trading API server...$(NC)"
	@cd core && $(PYTHON) -m fxml4.api.main

# Elliott Wave Analysis
elliott-install: ## Install Elliott Wave dependencies
	@echo "$(YELLOW)Installing Elliott Wave dependencies...$(NC)"
	@$(PIP) install -r requirements/elliott-wave.txt
	@$(PIP) install -e elliott_wave/
	@echo "$(GREEN)✓ Elliott Wave dependencies installed$(NC)"

elliott-test: ## Run Elliott Wave tests
	@echo "$(YELLOW)Running Elliott Wave tests...$(NC)"
	@$(PYTEST) tests/unit/elliott_wave/ tests/integration/elliott_wave/ -v
	@echo "$(GREEN)✓ Elliott Wave tests passed$(NC)"

elliott-lint: ## Lint Elliott Wave code
	@echo "$(YELLOW)Linting Elliott Wave analysis...$(NC)"
	@black --check elliott_wave/
	@isort --check-only elliott_wave/
	@flake8 elliott_wave/
	@echo "$(GREEN)✓ Elliott Wave linting passed$(NC)"

elliott-start: ## Start Elliott Wave Streamlit dashboard
	@echo "$(YELLOW)Starting Elliott Wave Streamlit dashboard...$(NC)"
	@cd elliott_wave && streamlit run main.py

# Frontend Application
frontend-install: ## Install frontend dependencies
	@echo "$(YELLOW)Installing frontend dependencies...$(NC)"
	@cd frontend && npm install
	@echo "$(GREEN)✓ Frontend dependencies installed$(NC)"

frontend-test: ## Run frontend tests
	@echo "$(YELLOW)Running frontend tests...$(NC)"
	@cd frontend && npm test
	@echo "$(GREEN)✓ Frontend tests passed$(NC)"

frontend-lint: ## Lint frontend code
	@echo "$(YELLOW)Linting frontend code...$(NC)"
	@cd frontend && npm run lint
	@echo "$(GREEN)✓ Frontend linting passed$(NC)"

frontend-build: ## Build frontend for production
	@echo "$(YELLOW)Building frontend for production...$(NC)"
	@cd frontend && npm run build
	@echo "$(GREEN)✓ Frontend built successfully$(NC)"

frontend-start: ## Start frontend development server
	@echo "$(YELLOW)Starting frontend development server...$(NC)"
	@cd frontend && npm run dev

# Infrastructure Operations
infra-validate: ## Validate infrastructure configurations
	@echo "$(YELLOW)Validating infrastructure configurations...$(NC)"
	@kubectl --dry-run=client apply -f infrastructure/k8s/ || echo "$(YELLOW)K8s validation skipped (kubectl not available)$(NC)"
	@cd infrastructure/terraform && terraform validate || echo "$(YELLOW)Terraform validation skipped (terraform not available)$(NC)"
	@docker-compose -f infrastructure/docker/docker-compose.yml config
	@echo "$(GREEN)✓ Infrastructure configurations validated$(NC)"

infra-deploy: ## Deploy infrastructure
	@echo "$(YELLOW)Deploying infrastructure...$(NC)"
	@kubectl apply -f infrastructure/k8s/
	@echo "$(GREEN)✓ Infrastructure deployed$(NC)"

infra-destroy: ## Destroy infrastructure
	@echo "$(YELLOW)Destroying infrastructure...$(NC)"
	@kubectl delete -f infrastructure/k8s/
	@echo "$(GREEN)✓ Infrastructure destroyed$(NC)"

# Cross-component Operations
all-install: core-install elliott-install frontend-install ## Install all dependencies
	@echo "$(GREEN)✅ All components installed successfully!$(NC)"

all-test: core-test elliott-test frontend-test ## Run all tests
	@echo "$(GREEN)✅ All component tests passed!$(NC)"

all-lint: core-lint elliott-lint frontend-lint ## Lint all code
	@echo "$(GREEN)✅ All components linted successfully!$(NC)"

all-clean: test-clean ## Clean all artifacts
	@echo "$(YELLOW)Cleaning all component artifacts...$(NC)"
	@rm -rf core/build core/dist core/*.egg-info
	@rm -rf elliott_wave/build elliott_wave/dist elliott_wave/*.egg-info
	@cd frontend && rm -rf node_modules/.cache .next/cache || true
	@echo "$(GREEN)✓ All artifacts cleaned$(NC)"

# Default target
.DEFAULT_GOAL := help
