#!/bin/bash

# FXML4 GitFlow Setup Script
# Initializes GitFlow workflow for the FXML4 project

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

print_banner() {
    echo ""
    echo "🌊 FXML4 GitFlow Setup"
    echo "======================"
    echo ""
}

# Check if we're in a git repository
check_git_repo() {
    if ! git rev-parse --git-dir >/dev/null 2>&1; then
        print_error "This script must be run from within a git repository"
        exit 1
    fi
    print_success "Git repository detected"
}

# Check current branch and status
check_repo_status() {
    local current_branch=$(git rev-parse --abbrev-ref HEAD)
    local status=$(git status --porcelain)

    print_info "Current branch: $current_branch"

    if [ -n "$status" ]; then
        print_warning "Working directory has uncommitted changes"
        echo "Please commit or stash changes before proceeding."
        read -p "Continue anyway? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    print_success "Repository status checked"
}

# Create develop branch if it doesn't exist
create_develop_branch() {
    if git show-ref --verify --quiet refs/heads/develop; then
        print_info "Develop branch already exists"
    else
        print_info "Creating develop branch from main..."
        git checkout -b develop main
        print_success "Develop branch created"
    fi

    # Ensure develop is up to date with main
    git checkout develop
    git merge main --no-ff -m "Initialize develop branch from main"
}

# Set up git configuration
setup_git_config() {
    print_info "Setting up git configuration..."

    # Set commit template
    if [ -f ".gitmessage" ]; then
        git config commit.template .gitmessage
        print_success "Commit message template configured"
    fi

    # Set up useful aliases
    git config alias.co checkout
    git config alias.br branch
    git config alias.ci commit
    git config alias.st status

    # GitFlow specific aliases
    git config alias.feature '!f() { git checkout -b feature/$1 develop; }; f'
    git config alias.bugfix '!f() { git checkout -b bugfix/$1 develop; }; f'
    git config alias.hotfix '!f() { git checkout -b hotfix/$1 main; }; f'
    git config alias.release '!f() { git checkout -b release/$1 develop; }; f'

    # Cleanup alias
    git config alias.cleanup "!git branch --merged | grep -v '\\*\\|main\\|develop' | xargs -n 1 git branch -d"

    # Pretty log alias
    git config alias.lg "log --graph --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --abbrev-commit"

    print_success "Git aliases configured"
}

# Install git hooks
install_git_hooks() {
    print_info "Installing git hooks..."

    if [ -f ".githooks/install-hooks.sh" ]; then
        chmod +x .githooks/install-hooks.sh
        ./.githooks/install-hooks.sh
        print_success "Git hooks installed"
    else
        print_warning "Git hooks installation script not found"
    fi
}

# Create example branches (optional)
create_example_branches() {
    read -p "Create example branches for demonstration? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Creating example branches..."

        # Create example feature branch
        git checkout develop
        git checkout -b feature/example-feature
        echo "# Example Feature" > FEATURE_EXAMPLE.md
        echo "This is an example feature branch. Delete this file when you understand the workflow." >> FEATURE_EXAMPLE.md
        git add FEATURE_EXAMPLE.md
        git commit -m "feat(example): add example feature for GitFlow demonstration"
        print_success "Created feature/example-feature"

        # Create example release branch
        git checkout develop
        git checkout -b release/1.0.1
        echo "# Release 1.0.1" > RELEASE_EXAMPLE.md
        echo "This is an example release branch. Delete this file when you understand the workflow." >> RELEASE_EXAMPLE.md
        git add RELEASE_EXAMPLE.md
        git commit -m "chore(release): prepare release 1.0.1"
        print_success "Created release/1.0.1"

        # Return to develop
        git checkout develop

        print_warning "Example branches created. Remember to delete them after learning:"
        echo "  git branch -D feature/example-feature"
        echo "  git branch -D release/1.0.1"
        echo "  git push origin --delete feature/example-feature (if pushed)"
        echo "  git push origin --delete release/1.0.1 (if pushed)"
    fi
}

# Set up remote tracking
setup_remote_tracking() {
    print_info "Setting up remote branch tracking..."

    # Push develop branch to remote if it doesn't exist there
    if ! git ls-remote --heads origin develop | grep -q develop; then
        git push -u origin develop
        print_success "Pushed develop branch to origin"
    else
        # Set up tracking if not already set
        git branch --set-upstream-to=origin/develop develop
        print_success "Set up tracking for develop branch"
    fi
}

# Display project information
show_project_info() {
    local current_version=$(grep '"version"' package.json 2>/dev/null | sed 's/.*"version": "\([^"]*\)".*/\1/' || echo "unknown")

    print_info "Project Information:"
    echo "  📦 Name: FXML4 Enterprise Trading Platform"
    echo "  🏷️  Version: $current_version"
    echo "  🌳 Git Flow: Initialized"
    echo "  📚 Documentation: GITFLOW.md"
}

# Show next steps
show_next_steps() {
    echo ""
    echo "🎯 Next Steps:"
    echo "=============="
    echo ""
    echo "1. Share this setup with your team:"
    echo "   📤 Each team member should run: ./scripts/setup-gitflow.sh"
    echo ""
    echo "2. Start your first feature:"
    echo "   🚀 git checkout develop"
    echo "   🌟 git checkout -b feature/your-feature-name"
    echo ""
    echo "3. Make changes and commit:"
    echo "   ✏️  git add ."
    echo "   💾 git commit  # (uses template for proper format)"
    echo ""
    echo "4. Push and create PR:"
    echo "   📤 git push -u origin feature/your-feature-name"
    echo "   🔄 gh pr create --base develop"
    echo ""
    echo "5. Review workflow documentation:"
    echo "   📖 Read GITFLOW.md for detailed processes"
    echo ""
    echo "🔧 Utility commands:"
    echo "  • ./scripts/new-feature.sh <name>     - Start new feature"
    echo "  • ./scripts/prepare-release.sh <ver> - Prepare release"
    echo "  • git cleanup                        - Remove merged branches"
    echo "  • git lg                            - Pretty git log"
    echo ""
}

# Main execution
main() {
    print_banner
    check_git_repo
    check_repo_status
    create_develop_branch
    setup_git_config
    install_git_hooks
    setup_remote_tracking
    create_example_branches
    show_project_info
    show_next_steps

    print_success "GitFlow setup completed successfully!"
    echo ""
}

# Run main function
main "$@"
