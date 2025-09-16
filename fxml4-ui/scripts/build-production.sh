#!/bin/bash

# FXML4 UI Production Build Script
set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Build configuration
BUILD_TARGET=${1:-production}
ANALYZE=${2:-false}

log_info "Starting FXML4 UI production build..."
log_info "Target: $BUILD_TARGET"
log_info "Analyze: $ANALYZE"

cd "$PROJECT_DIR"

# Clean previous builds
log_info "Cleaning previous builds..."
rm -rf .next
rm -rf out
rm -rf dist
rm -rf analyze

# Install dependencies
log_info "Installing dependencies..."
npm ci --production=false

# Run quality checks
log_info "Running code quality checks..."

# Linting
log_info "Running ESLint..."
npm run lint

# Type checking
log_info "Running TypeScript type check..."
npm run type-check

# Format checking
log_info "Checking code formatting..."
npm run format:check

# Run tests
log_info "Running test suite..."
npm run test:unit
npm run test:component

# Build the application
log_info "Building application for $BUILD_TARGET..."

if [[ "$ANALYZE" == "true" ]]; then
    log_info "Building with bundle analysis..."
    npm run analyze
else
    npm run build
fi

# Verify build output
log_info "Verifying build output..."

if [[ ! -d ".next" ]]; then
    log_error "Build failed: .next directory not found"
    exit 1
fi

if [[ ! -f ".next/BUILD_ID" ]]; then
    log_error "Build failed: BUILD_ID not found"
    exit 1
fi

BUILD_ID=$(cat .next/BUILD_ID)
log_success "Build completed successfully (ID: $BUILD_ID)"

# Generate build report
log_info "Generating build report..."

# Get build size information
TOTAL_SIZE=$(du -sh .next | cut -f1)
STATIC_SIZE=$(du -sh .next/static 2>/dev/null | cut -f1 || echo "0")

# Get dependency information
DEP_COUNT=$(npm list --production --depth=0 2>/dev/null | grep -c "├──\|└──" || echo "0")
DEV_DEP_COUNT=$(npm list --depth=0 2>/dev/null | grep -c "├──\|└──" || echo "0")

# Create build report
cat > build-report.json << EOF
{
  "timestamp": "$(date -Iseconds)",
  "build_id": "$BUILD_ID",
  "target": "$BUILD_TARGET",
  "node_version": "$(node --version)",
  "npm_version": "$(npm --version)",
  "sizes": {
    "total": "$TOTAL_SIZE",
    "static": "$STATIC_SIZE"
  },
  "dependencies": {
    "production": $DEP_COUNT,
    "development": $DEV_DEP_COUNT
  },
  "environment": {
    "NODE_ENV": "${NODE_ENV:-production}",
    "CI": "${CI:-false}",
    "GITHUB_SHA": "${GITHUB_SHA:-unknown}"
  }
}
EOF

log_success "Build report generated: build-report.json"

# Bundle size check
log_info "Checking bundle size limits..."
if command -v npx >/dev/null && npm run bundle:size >/dev/null 2>&1; then
    log_success "Bundle size within limits"
else
    log_warning "Bundle size check failed or not configured"
fi

# Generate production artifacts
log_info "Generating production artifacts..."

# Create version file
echo "$BUILD_ID" > .next/VERSION
echo "$(date -Iseconds)" > .next/BUILD_DATE

# Create health check endpoint data
mkdir -p .next/health
cat > .next/health/build-info.json << EOF
{
  "build_id": "$BUILD_ID",
  "build_date": "$(date -Iseconds)",
  "node_version": "$(node --version)",
  "git_commit": "${GITHUB_SHA:-$(git rev-parse HEAD 2>/dev/null || echo 'unknown')}",
  "git_branch": "${GITHUB_REF_NAME:-$(git branch --show-current 2>/dev/null || echo 'unknown')}"
}
EOF

# Performance budget check
if [[ -f "scripts/performance-benchmarks.js" ]]; then
    log_info "Running performance benchmarks..."
    node scripts/performance-benchmarks.js || log_warning "Performance benchmarks failed"
fi

# Security scan (if tools available)
if command -v npm audit >/dev/null; then
    log_info "Running security audit..."
    npm audit --audit-level moderate --production || log_warning "Security audit found issues"
fi

# Final verification
log_info "Performing final verification..."

# Check critical files
CRITICAL_FILES=(
    ".next/BUILD_ID"
    ".next/static"
    ".next/server"
)

for file in "${CRITICAL_FILES[@]}"; do
    if [[ ! -e "$file" ]]; then
        log_error "Critical file missing: $file"
        exit 1
    fi
done

# Summary
log_success "Production build completed successfully!"
echo ""
echo "Build Summary:"
echo "- Build ID: $BUILD_ID"
echo "- Total Size: $TOTAL_SIZE"
echo "- Static Size: $STATIC_SIZE"
echo "- Dependencies: $DEP_COUNT production, $DEV_DEP_COUNT development"
echo "- Target: $BUILD_TARGET"
echo "- Timestamp: $(date -Iseconds)"
echo ""

if [[ "$ANALYZE" == "true" && -f "analyze/client.html" ]]; then
    log_info "Bundle analysis report available at: analyze/client.html"
fi

log_success "Build ready for deployment!"

exit 0
