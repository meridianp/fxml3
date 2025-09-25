#!/bin/bash

# FXML4 New Feature Script
# Streamlines feature branch creation following GitFlow

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_usage() {
    echo ""
    echo "🌟 FXML4 New Feature Creator"
    echo "============================"
    echo ""
    echo "Usage: $0 <feature-name> [description]"
    echo ""
    echo "Examples:"
    echo "  $0 user-authentication"
    echo "  $0 elliott-wave-detection \"Add ML-based Elliott Wave pattern recognition\""
    echo "  $0 api-rate-limiting"
    echo ""
    echo "The script will:"
    echo "  1. Ensure you're on the develop branch"
    echo "  2. Pull latest changes from origin"
    echo "  3. Create feature/your-feature-name branch"
    echo "  4. Set up branch tracking with origin"
    echo "  5. Provide helpful next steps"
    echo ""
}

# Validate input
validate_input() {
    if [ -z "$1" ]; then
        print_error "Feature name is required"
        print_usage
        exit 1
    fi

    # Check if feature name follows conventions
    if [[ ! "$1" =~ ^[a-z0-9-]+$ ]]; then
        print_error "Feature name should only contain lowercase letters, numbers, and hyphens"
        echo "Examples: user-auth, elliott-wave-detection, api-endpoints"
        exit 1
    fi

    # Check if feature name is not too long
    if [ ${#1} -gt 50 ]; then
        print_error "Feature name should be 50 characters or less"
        exit 1
    fi
}

# Check git repository
check_git_repo() {
    if ! git rev-parse --git-dir >/dev/null 2>&1; then
        print_error "This script must be run from within a git repository"
        exit 1
    fi

    # Check if we're in the FXML4 project
    if [ ! -f "package.json" ] || ! grep -q "fxml4" package.json; then
        print_warning "This doesn't appear to be the FXML4 project"
        read -p "Continue anyway? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Check if develop branch exists
check_develop_branch() {
    if ! git show-ref --verify --quiet refs/heads/develop; then
        print_error "Develop branch doesn't exist. Run ./scripts/setup-gitflow.sh first"
        exit 1
    fi
}

# Check for uncommitted changes
check_working_directory() {
    local status=$(git status --porcelain)
    if [ -n "$status" ]; then
        print_warning "You have uncommitted changes:"
        git status --short
        echo ""
        read -p "Stash changes and continue? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git stash push -m "Auto-stash before creating feature branch"
            print_success "Changes stashed"
        else
            print_error "Please commit or stash your changes before creating a feature branch"
            exit 1
        fi
    fi
}

# Switch to develop and update
prepare_develop() {
    print_info "Switching to develop branch..."
    git checkout develop

    print_info "Pulling latest changes from origin..."
    if git pull origin develop; then
        print_success "Develop branch updated"
    else
        print_warning "Failed to pull from origin. Continuing with local develop."
    fi
}

# Create feature branch
create_feature_branch() {
    local feature_name="$1"
    local branch_name="feature/$feature_name"

    # Check if branch already exists
    if git show-ref --verify --quiet refs/heads/$branch_name; then
        print_error "Branch $branch_name already exists"
        echo ""
        print_info "Existing branches:"
        git branch | grep feature/
        exit 1
    fi

    print_info "Creating feature branch: $branch_name"
    git checkout -b $branch_name

    print_success "Feature branch created and checked out"
    return 0
}

# Set up branch tracking
setup_branch_tracking() {
    local feature_name="$1"
    local branch_name="feature/$feature_name"

    # Push to set up tracking
    print_info "Setting up remote tracking..."
    if git push -u origin $branch_name; then
        print_success "Branch pushed and tracking set up"
    else
        print_warning "Failed to push branch. You can push later with:"
        echo "  git push -u origin $branch_name"
    fi
}

# Create initial commit if description provided
create_initial_commit() {
    local feature_name="$1"
    local description="$2"

    if [ -n "$description" ]; then
        # Create a simple feature file
        local feature_file="docs/features/$feature_name.md"
        mkdir -p "docs/features"

        cat > "$feature_file" << EOF
# Feature: $feature_name

## Description
$description

## Status
🚧 **In Development**

## Implementation Checklist
- [ ] Design and planning
- [ ] Core implementation
- [ ] Unit tests
- [ ] Integration tests
- [ ] Documentation
- [ ] Code review
- [ ] QA testing

## Technical Notes
<!-- Add technical details, architecture decisions, etc. -->

## Related Issues
<!-- Link any related GitHub issues -->

---
Created: $(date +"%Y-%m-%d")
Branch: feature/$feature_name
EOF

        git add "$feature_file"
        git commit -m "feat($feature_name): initialize feature with documentation

$description"

        print_success "Initial commit created with feature documentation"
    else
        print_info "No description provided. Create your first commit manually."
    fi
}

# Show next steps
show_next_steps() {
    local feature_name="$1"
    local branch_name="feature/$feature_name"

    echo ""
    echo "🎉 Feature branch '$branch_name' ready!"
    echo "======================================"
    echo ""
    echo "📝 Next steps:"
    echo ""
    echo "1. Start development:"
    echo "   ✏️  Make your changes"
    echo "   📁 Edit files in core/, frontend/, tests/, etc."
    echo ""
    echo "2. Follow TDD workflow:"
    echo "   🔴 Write failing tests first"
    echo "   🟢 Make tests pass with minimal code"
    echo "   🔵 Refactor for quality"
    echo ""
    echo "3. Commit your progress:"
    echo "   📝 git add ."
    echo "   💾 git commit  # Use the template for proper format"
    echo ""
    echo "4. Keep feature up to date:"
    echo "   🔄 git rebase develop  # Regularly sync with develop"
    echo ""
    echo "5. When feature is complete:"
    echo "   📤 git push origin $branch_name"
    echo "   🔄 gh pr create --base develop --title \"feat($feature_name): your title\""
    echo ""
    echo "🔧 Useful commands for this feature:"
    echo "  • git rebase develop                  - Sync with latest develop"
    echo "  • git push --force-with-lease origin $branch_name  - Safe force push after rebase"
    echo "  • npm test                           - Run JavaScript tests"
    echo "  • pytest tests/                     - Run Python tests"
    echo "  • make tdd-cycle                     - Run full TDD cycle"
    echo ""
    echo "📚 Documentation:"
    echo "  • GITFLOW.md - Complete workflow guide"
    echo "  • CLAUDE.md  - Development guidelines"
    echo ""
    echo "💡 Tips:"
    echo "  • Keep commits small and focused"
    echo "  • Use conventional commit format"
    echo "  • Update tests alongside code changes"
    echo "  • Regularly push to backup your work"
    echo ""
}

# Main execution
main() {
    local feature_name="$1"
    local description="$2"

    if [ "$feature_name" = "-h" ] || [ "$feature_name" = "--help" ]; then
        print_usage
        exit 0
    fi

    validate_input "$feature_name"
    check_git_repo
    check_develop_branch
    check_working_directory
    prepare_develop
    create_feature_branch "$feature_name"
    setup_branch_tracking "$feature_name"
    create_initial_commit "$feature_name" "$description"
    show_next_steps "$feature_name"

    print_success "Ready to start development on feature/$feature_name!"
}

# Run main function
main "$@"
