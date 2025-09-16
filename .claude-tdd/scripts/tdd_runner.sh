#!/bin/bash
# FXML4 Claude TDD - Language-Agnostic Test Runner
# Provides unified interface for TDD operations across Python and TypeScript

set -euo pipefail

# Configuration
TDD_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ROOT="$(cd "$TDD_ROOT/.." && pwd)"
CONFIG_FILE="$TDD_ROOT/config.yml"
DISCOVERY_CACHE="$TDD_ROOT/discovery_results.json"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Help function
show_help() {
    cat << EOF
FXML4 Claude TDD Runner - Language-Agnostic Test Operations

USAGE:
    $0 <command> [options]

COMMANDS:
    discover                 Discover all tests across components
    test <component>         Run tests for specific component
    test-all                 Run tests for all components
    red <component>          Execute Red phase (failing tests)
    green <component>        Execute Green phase (implement code)
    refactor <component>     Execute Refactor phase
    cycle <component>        Execute full Red-Green-Refactor cycle
    mutate <component>       Run mutation testing
    contract <component>     Run contract testing
    status                   Show current TDD status
    reset                    Reset TDD state

COMPONENTS:
    core                     Core trading system (Python/FastAPI)
    elliott_wave             Elliott Wave analysis (Python)
    frontend                 UI components (TypeScript/Next.js)
    all                      All components

OPTIONS:
    --category <cat>         Filter by test category (unit, integration, etc.)
    --markers <markers>      Filter by test markers (comma-separated)
    --parallel               Run tests in parallel
    --verbose                Verbose output
    --dry-run                Show what would be executed
    --timeout <seconds>      Test timeout (default: 300)

EXAMPLES:
    $0 discover
    $0 test core --category unit
    $0 cycle frontend --verbose
    $0 test-all --parallel --markers "not slow"
    $0 mutate core --dry-run

For more information, see: .claude-tdd/config.yml
EOF
}

# Load configuration
load_config() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        log_error "TDD configuration not found: $CONFIG_FILE"
        exit 1
    fi
}

# Discover tests
discover_tests() {
    log_info "Discovering tests across all components..."

    cd "$PROJECT_ROOT"
    python "$TDD_ROOT/scripts/discover_tests.py"

    if [[ $? -eq 0 ]]; then
        log_success "Test discovery completed"
        if [[ -f "$DISCOVERY_CACHE" ]]; then
            log_info "Results cached in: $DISCOVERY_CACHE"
        fi
    else
        log_error "Test discovery failed"
        exit 1
    fi
}

# Get component configuration
get_component_config() {
    local component="$1"

    case "$component" in
        "core")
            echo "core/ python pytest"
            ;;
        "elliott_wave")
            echo "elliott_wave/ python pytest"
            ;;
        "frontend")
            echo "frontend/ typescript jest"
            ;;
        *)
            log_error "Unknown component: $component"
            exit 1
            ;;
    esac
}

# Run Python tests
run_python_tests() {
    local component_path="$1"
    local test_args="$2"

    log_info "Running Python tests in $component_path"

    cd "$PROJECT_ROOT/$component_path"

    # Activate virtual environment if it exists
    if [[ -f "venv/bin/activate" ]]; then
        source venv/bin/activate
    elif [[ -f "../venv/bin/activate" ]]; then
        source ../venv/bin/activate
    fi

    # Run pytest with specified arguments
    pytest $test_args
    return $?
}

# Run TypeScript tests
run_typescript_tests() {
    local component_path="$1"
    local test_args="$2"

    log_info "Running TypeScript tests in $component_path"

    cd "$PROJECT_ROOT/$component_path"

    # Ensure node_modules are installed
    if [[ ! -d "node_modules" ]]; then
        log_info "Installing dependencies..."
        npm install
    fi

    # Run Jest with specified arguments
    npm test -- $test_args
    return $?
}

# Test specific component
test_component() {
    local component="$1"
    local category="${2:-}"
    local markers="${3:-}"
    local parallel="${4:-false}"
    local verbose="${5:-false}"

    read -r component_path language framework <<< "$(get_component_config "$component")"

    log_info "Testing component: $component ($language/$framework)"

    # Build test arguments
    local test_args=""

    if [[ -n "$category" ]]; then
        if [[ "$language" == "python" ]]; then
            test_args="$test_args -m $category"
        fi
    fi

    if [[ -n "$markers" ]]; then
        if [[ "$language" == "python" ]]; then
            test_args="$test_args -m \"$markers\""
        fi
    fi

    if [[ "$parallel" == "true" ]]; then
        if [[ "$language" == "python" ]]; then
            test_args="$test_args -n auto"
        fi
    fi

    if [[ "$verbose" == "true" ]]; then
        if [[ "$language" == "python" ]]; then
            test_args="$test_args -v"
        else
            test_args="$test_args --verbose"
        fi
    fi

    # Execute tests
    if [[ "$language" == "python" ]]; then
        run_python_tests "$component_path" "$test_args"
    elif [[ "$language" == "typescript" ]]; then
        run_typescript_tests "$component_path" "$test_args"
    fi

    return $?
}

# Test all components
test_all_components() {
    local category="${1:-}"
    local markers="${2:-}"
    local parallel="${3:-false}"
    local verbose="${4:-false}"

    local components=("core" "elliott_wave" "frontend")
    local overall_result=0

    log_info "Running tests for all components"

    for component in "${components[@]}"; do
        log_info "Testing component: $component"

        if test_component "$component" "$category" "$markers" "$parallel" "$verbose"; then
            log_success "✓ $component tests passed"
        else
            log_error "✗ $component tests failed"
            overall_result=1
        fi

        echo "---"
    done

    if [[ $overall_result -eq 0 ]]; then
        log_success "All component tests passed!"
    else
        log_error "Some component tests failed"
    fi

    return $overall_result
}

# Execute Red phase (failing tests)
execute_red_phase() {
    local component="$1"

    log_info "Executing RED phase for $component"
    log_info "Looking for failing tests that define expected behavior..."

    # Run tests and expect failures
    if test_component "$component" "" "" "false" "true"; then
        log_warning "No failing tests found - this may indicate missing test coverage"
        return 1
    else
        log_success "Found failing tests - RED phase complete"
        return 0
    fi
}

# Execute Green phase (implement code)
execute_green_phase() {
    local component="$1"

    log_info "Executing GREEN phase for $component"
    log_info "Implementing minimal code to make tests pass..."

    # This would typically involve Claude Code orchestration
    log_warning "GREEN phase requires Claude Code orchestration (not implemented in this script)"
    log_info "Use Claude Code with TDD orchestrator agent to implement code"

    return 0
}

# Execute Refactor phase
execute_refactor_phase() {
    local component="$1"

    log_info "Executing REFACTOR phase for $component"
    log_info "Improving code quality while keeping tests green..."

    # Run tests to ensure they still pass
    if test_component "$component" "" "" "false" "true"; then
        log_success "REFACTOR phase complete - all tests still pass"
        return 0
    else
        log_error "REFACTOR phase failed - tests are now failing"
        return 1
    fi
}

# Execute full TDD cycle
execute_tdd_cycle() {
    local component="$1"

    log_info "Executing full TDD cycle for $component"

    if execute_red_phase "$component"; then
        if execute_green_phase "$component"; then
            if execute_refactor_phase "$component"; then
                log_success "TDD cycle completed successfully for $component"
                return 0
            fi
        fi
    fi

    log_error "TDD cycle failed for $component"
    return 1
}

# Run mutation testing
run_mutation_testing() {
    local component="$1"
    local dry_run="${2:-false}"

    read -r component_path language framework <<< "$(get_component_config "$component")"

    log_info "Running mutation testing for $component ($language)"

    cd "$PROJECT_ROOT/$component_path"

    if [[ "$language" == "python" ]]; then
        if [[ "$dry_run" == "true" ]]; then
            log_info "Would run: mutmut run"
        else
            # Install mutmut if not available
            if ! command -v mutmut &> /dev/null; then
                pip install mutmut
            fi
            mutmut run
        fi
    elif [[ "$language" == "typescript" ]]; then
        if [[ "$dry_run" == "true" ]]; then
            log_info "Would run: npx stryker run"
        else
            npx stryker run
        fi
    fi
}

# Show TDD status
show_status() {
    log_info "TDD Status for FXML4"
    echo

    if [[ -f "$DISCOVERY_CACHE" ]]; then
        log_info "Last test discovery: $(stat -c %y "$DISCOVERY_CACHE")"

        # Extract summary from discovery cache
        if command -v jq &> /dev/null; then
            local total_files=$(jq -r '.test_suites | to_entries | map(.value.total_files) | add' "$DISCOVERY_CACHE")
            local total_tests=$(jq -r '.test_suites | to_entries | map(.value.total_tests) | add' "$DISCOVERY_CACHE")

            echo "Total Test Files: $total_files"
            echo "Total Test Cases: $total_tests"
        fi
    else
        log_warning "No test discovery cache found. Run 'discover' first."
    fi

    echo
    log_info "Component Status:"

    for component in "core" "elliott_wave" "frontend"; do
        read -r component_path language framework <<< "$(get_component_config "$component")"

        if [[ -d "$PROJECT_ROOT/$component_path" ]]; then
            echo "  ✓ $component ($language/$framework)"
        else
            echo "  ✗ $component (missing)"
        fi
    done
}

# Reset TDD state
reset_tdd_state() {
    log_info "Resetting TDD state..."

    # Remove cache files
    rm -f "$DISCOVERY_CACHE"
    rm -rf "$TDD_ROOT/progress/"*.json

    log_success "TDD state reset"
}

# Parse command line arguments
parse_arguments() {
    local command="${1:-}"

    case "$command" in
        "discover")
            discover_tests
            ;;
        "test")
            local component="${2:-}"
            if [[ -z "$component" ]]; then
                log_error "Component required for test command"
                show_help
                exit 1
            fi

            # Parse additional options
            local category=""
            local markers=""
            local parallel="false"
            local verbose="false"

            shift 2
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --category)
                        category="$2"
                        shift 2
                        ;;
                    --markers)
                        markers="$2"
                        shift 2
                        ;;
                    --parallel)
                        parallel="true"
                        shift
                        ;;
                    --verbose)
                        verbose="true"
                        shift
                        ;;
                    *)
                        log_error "Unknown option: $1"
                        exit 1
                        ;;
                esac
            done

            test_component "$component" "$category" "$markers" "$parallel" "$verbose"
            ;;
        "test-all")
            # Parse options similar to test command
            local category=""
            local markers=""
            local parallel="false"
            local verbose="false"

            shift
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --category)
                        category="$2"
                        shift 2
                        ;;
                    --markers)
                        markers="$2"
                        shift 2
                        ;;
                    --parallel)
                        parallel="true"
                        shift
                        ;;
                    --verbose)
                        verbose="true"
                        shift
                        ;;
                    *)
                        log_error "Unknown option: $1"
                        exit 1
                        ;;
                esac
            done

            test_all_components "$category" "$markers" "$parallel" "$verbose"
            ;;
        "red")
            local component="${2:-}"
            if [[ -z "$component" ]]; then
                log_error "Component required for red command"
                exit 1
            fi
            execute_red_phase "$component"
            ;;
        "green")
            local component="${2:-}"
            if [[ -z "$component" ]]; then
                log_error "Component required for green command"
                exit 1
            fi
            execute_green_phase "$component"
            ;;
        "refactor")
            local component="${2:-}"
            if [[ -z "$component" ]]; then
                log_error "Component required for refactor command"
                exit 1
            fi
            execute_refactor_phase "$component"
            ;;
        "cycle")
            local component="${2:-}"
            if [[ -z "$component" ]]; then
                log_error "Component required for cycle command"
                exit 1
            fi
            execute_tdd_cycle "$component"
            ;;
        "mutate")
            local component="${2:-}"
            if [[ -z "$component" ]]; then
                log_error "Component required for mutate command"
                exit 1
            fi

            local dry_run="false"
            if [[ "${3:-}" == "--dry-run" ]]; then
                dry_run="true"
            fi

            run_mutation_testing "$component" "$dry_run"
            ;;
        "status")
            show_status
            ;;
        "reset")
            reset_tdd_state
            ;;
        "help"|"-h"|"--help"|"")
            show_help
            ;;
        *)
            log_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

# Main execution
main() {
    load_config
    parse_arguments "$@"
}

main "$@"
