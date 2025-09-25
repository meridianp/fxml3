#!/bin/bash

# FXML4 Git Hooks Installation Script
# Installs custom git hooks for the project

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

echo ""
echo "🪝 Installing FXML4 Git Hooks..."
echo "================================"

# Check if we're in a git repository
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    print_error "This script must be run from within a git repository"
    exit 1
fi

# Get git hooks directory
GIT_HOOKS_DIR="$(git rev-parse --git-dir)/hooks"
PROJECT_HOOKS_DIR="$(git rev-parse --show-toplevel)/.githooks"

# Check if our hooks directory exists
if [ ! -d "$PROJECT_HOOKS_DIR" ]; then
    print_error "Project hooks directory not found: $PROJECT_HOOKS_DIR"
    exit 1
fi

# Backup existing hooks
if [ -d "$GIT_HOOKS_DIR" ]; then
    echo "📦 Backing up existing hooks..."
    if ls "$GIT_HOOKS_DIR"/* >/dev/null 2>&1; then
        BACKUP_DIR="$GIT_HOOKS_DIR/backup-$(date +%Y%m%d-%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        cp "$GIT_HOOKS_DIR"/* "$BACKUP_DIR/" 2>/dev/null || true
        print_success "Existing hooks backed up to: $BACKUP_DIR"
    fi
fi

# Install hooks
echo "🔗 Installing hooks..."
HOOKS_INSTALLED=0

for hook in "$PROJECT_HOOKS_DIR"/*; do
    if [ -f "$hook" ] && [ -x "$hook" ]; then
        HOOK_NAME=$(basename "$hook")

        # Skip the install script itself and any README files
        if [ "$HOOK_NAME" = "install-hooks.sh" ] || [ "$HOOK_NAME" = "README.md" ]; then
            continue
        fi

        # Create symlink to our hook
        ln -sf "$hook" "$GIT_HOOKS_DIR/$HOOK_NAME"
        print_success "Installed $HOOK_NAME hook"
        HOOKS_INSTALLED=$((HOOKS_INSTALLED + 1))
    fi
done

# Set up git configuration for commit message template
if [ -f "$(git rev-parse --show-toplevel)/.gitmessage" ]; then
    git config commit.template .gitmessage
    print_success "Configured git commit message template"
fi

# Set up core.hooksPath to use our hooks directory (alternative approach)
# git config core.hooksPath .githooks
# print_success "Configured git hooks path"

echo ""
if [ $HOOKS_INSTALLED -gt 0 ]; then
    print_success "Successfully installed $HOOKS_INSTALLED git hooks!"
    echo ""
    echo "📋 Installed hooks:"
    echo "  • pre-commit: Validates commit messages and code quality"
    echo "  • prepare-commit-msg: Adds branch context to commits"
    echo "  • post-checkout: Provides branch-specific guidance"
    echo ""
    echo "🎯 Next steps:"
    echo "  1. Test the hooks by making a commit"
    echo "  2. Share this setup with your team"
    echo "  3. Consider adding more project-specific checks"
    echo ""
    print_warning "Note: Hooks are not automatically shared via git."
    print_warning "Each team member needs to run this script to install hooks locally."
else
    print_warning "No hooks were installed. Check that .githooks directory contains executable files."
fi

echo ""
echo "🔍 To test the hooks, try:"
echo "  git add . && git commit -m 'test: verify hooks are working'"
echo ""
