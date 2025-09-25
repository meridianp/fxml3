#!/bin/bash

# FXML4 Release Preparation Script
# Automates release branch preparation following GitFlow

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
    echo "📦 FXML4 Release Preparation"
    echo "============================"
    echo ""
    echo "Usage: $0 <version> [release-type]"
    echo ""
    echo "Parameters:"
    echo "  version      - Semantic version (e.g., 1.2.0, 2.0.0-beta)"
    echo "  release-type - Optional: patch, minor, major, prerelease"
    echo ""
    echo "Examples:"
    echo "  $0 1.2.0          # Create release/1.2.0 branch"
    echo "  $0 1.1.1 patch    # Patch release"
    echo "  $0 2.0.0 major    # Major release"
    echo "  $0 1.2.0-beta     # Pre-release"
    echo ""
    echo "The script will:"
    echo "  1. Validate version format"
    echo "  2. Create release branch from develop"
    echo "  3. Update version numbers in package.json"
    echo "  4. Generate/update CHANGELOG.md"
    echo "  5. Create release preparation commit"
    echo "  6. Set up branch tracking"
    echo ""
}

# Validate semantic version format
validate_version() {
    local version="$1"

    if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.-]+)?$ ]]; then
        print_error "Invalid version format: $version"
        echo "Expected: X.Y.Z or X.Y.Z-prerelease (e.g., 1.2.0, 2.0.0-beta.1)"
        exit 1
    fi

    print_success "Version format is valid: $version"
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
        print_error "You have uncommitted changes. Please commit or stash them first."
        git status --short
        exit 1
    fi
}

# Prepare develop branch
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

# Check if release branch already exists
check_release_branch() {
    local version="$1"
    local branch_name="release/$version"

    if git show-ref --verify --quiet refs/heads/$branch_name; then
        print_error "Release branch $branch_name already exists"
        echo ""
        print_info "Existing release branches:"
        git branch | grep release/ || echo "  (none)"
        exit 1
    fi
}

# Create release branch
create_release_branch() {
    local version="$1"
    local branch_name="release/$version"

    print_info "Creating release branch: $branch_name"
    git checkout -b $branch_name

    print_success "Release branch created and checked out"
}

# Update version in package.json
update_package_version() {
    local version="$1"

    if [ -f "package.json" ]; then
        print_info "Updating version in package.json to $version..."

        # Use sed to update version in package.json
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s/\"version\": \".*\"/\"version\": \"$version\"/" package.json
        else
            # Linux
            sed -i "s/\"version\": \".*\"/\"version\": \"$version\"/" package.json
        fi

        print_success "Updated package.json version"
    else
        print_warning "package.json not found, skipping version update"
    fi
}

# Update version in Python setup
update_python_version() {
    local version="$1"

    if [ -f "setup.py" ]; then
        print_info "Updating version in setup.py..."
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s/version=\".*\"/version=\"$version\"/" setup.py
        else
            sed -i "s/version=\".*\"/version=\"$version\"/" setup.py
        fi
        print_success "Updated setup.py version"
    fi

    if [ -f "pyproject.toml" ]; then
        print_info "Updating version in pyproject.toml..."
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s/version = \".*\"/version = \"$version\"/" pyproject.toml
        else
            sed -i "s/version = \".*\"/version = \"$version\"/" pyproject.toml
        fi
        print_success "Updated pyproject.toml version"
    fi
}

# Generate or update CHANGELOG.md
update_changelog() {
    local version="$1"
    local release_date=$(date +"%Y-%m-%d")

    print_info "Updating CHANGELOG.md..."

    # Create CHANGELOG.md if it doesn't exist
    if [ ! -f "CHANGELOG.md" ]; then
        cat > CHANGELOG.md << EOF
# Changelog

All notable changes to the FXML4 project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [$version] - $release_date

### Added
- Initial release preparation

### Changed

### Deprecated

### Removed

### Fixed

### Security

EOF
        print_success "Created CHANGELOG.md"
    else
        # Update existing changelog
        # Insert new version section after [Unreleased]
        local temp_file=$(mktemp)
        awk -v version="$version" -v date="$release_date" '
            /^## \[Unreleased\]/ {
                print $0
                print ""
                print "## [" version "] - " date
                print ""
                print "### Added"
                print ""
                print "### Changed"
                print ""
                print "### Fixed"
                print ""
                next
            }
            {print}
        ' CHANGELOG.md > "$temp_file"
        mv "$temp_file" CHANGELOG.md
        print_success "Updated CHANGELOG.md"
    fi

    print_warning "Please edit CHANGELOG.md to add the actual changes for this release"
}

# Generate release notes from git commits
generate_release_notes() {
    local version="$1"

    print_info "Generating release notes from recent commits..."

    # Get commits since last tag or start of develop
    local last_tag=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
    local commit_range

    if [ -n "$last_tag" ]; then
        commit_range="$last_tag..develop"
    else
        commit_range="develop"
    fi

    # Generate release notes file
    cat > "RELEASE_NOTES_$version.md" << EOF
# Release Notes - FXML4 v$version

**Release Date:** $(date +"%Y-%m-%d")
**Version:** $version

## Summary

<!-- Add a brief summary of this release -->

## Changes

### Features
$(git log $commit_range --pretty=format:"- %s" --grep="^feat" | head -20)

### Bug Fixes
$(git log $commit_range --pretty=format:"- %s" --grep="^fix" | head -20)

### Other Changes
$(git log $commit_range --pretty=format:"- %s" --grep="^docs\|^chore\|^refactor" | head -10)

## Technical Details

- **Commits:** $(git rev-list --count $commit_range)
- **Contributors:** $(git shortlog -sn $commit_range | wc -l)

## Migration Guide

<!-- Add any breaking changes or migration steps -->

## Testing

Please test the following areas:
- [ ] Core trading functionality
- [ ] Elliott Wave analysis
- [ ] ML signal generation
- [ ] Risk management
- [ ] API endpoints
- [ ] WebSocket real-time feeds

EOF

    print_success "Generated RELEASE_NOTES_$version.md"
    print_info "Please review and edit the release notes file"
}

# Create release preparation commit
create_release_commit() {
    local version="$1"

    # Add changed files
    git add .

    # Check if there are changes to commit
    if git diff --staged --quiet; then
        print_warning "No changes to commit for release preparation"
        return 0
    fi

    local commit_message="chore(release): prepare release $version

- Update version to $version in package.json
- Update CHANGELOG.md with release notes
- Generate release documentation

Ready for final testing and merge to main."

    git commit -m "$commit_message"
    print_success "Created release preparation commit"
}

# Set up branch tracking
setup_branch_tracking() {
    local version="$1"
    local branch_name="release/$version"

    print_info "Setting up remote tracking..."
    if git push -u origin $branch_name; then
        print_success "Release branch pushed and tracking set up"
    else
        print_warning "Failed to push branch. You can push later with:"
        echo "  git push -u origin $branch_name"
    fi
}

# Show next steps
show_next_steps() {
    local version="$1"
    local branch_name="release/$version"

    echo ""
    echo "🚀 Release branch '$branch_name' prepared!"
    echo "========================================"
    echo ""
    echo "📋 Release Checklist:"
    echo ""
    echo "1. Review and finalize release content:"
    echo "   📝 Edit CHANGELOG.md with actual changes"
    echo "   📄 Review RELEASE_NOTES_$version.md"
    echo "   🔍 Verify version numbers are correct"
    echo ""
    echo "2. Perform release testing:"
    echo "   🧪 npm test                    - Run all tests"
    echo "   🐍 pytest tests/              - Run Python tests"
    echo "   🏗️  npm run build              - Build production assets"
    echo "   📊 Check performance metrics"
    echo ""
    echo "3. Final release commits (bug fixes only):"
    echo "   🐛 git add . && git commit -m 'fix: release bug'"
    echo "   📤 git push origin $branch_name"
    echo ""
    echo "4. Create Pull Request to main:"
    echo "   🔄 gh pr create --base main --title 'release: v$version'"
    echo "   👥 Request reviews from team leads"
    echo "   ✅ Ensure all CI checks pass"
    echo ""
    echo "5. After PR approval and merge:"
    echo "   🏷️  Tag the release: git tag -a v$version -m 'Release $version'"
    echo "   📤 Push tag: git push origin v$version"
    echo "   🔄 Merge back to develop"
    echo ""
    echo "6. Post-release cleanup:"
    echo "   🗑️  Delete release branch after merge"
    echo "   📢 Announce release to team"
    echo "   🚀 Deploy to production if applicable"
    echo ""
    echo "⚠️  Release branch rules:"
    echo "  • Only bug fixes and release preparation commits allowed"
    echo "  • No new features should be added"
    echo "  • Focus on stabilization and documentation"
    echo ""
    echo "📚 Documentation:"
    echo "  • GITFLOW.md - Complete workflow guide"
    echo "  • RELEASE_NOTES_$version.md - This release notes"
    echo ""
}

# Main execution
main() {
    local version="$1"
    local release_type="$2"

    if [ "$version" = "-h" ] || [ "$version" = "--help" ] || [ -z "$version" ]; then
        print_usage
        exit 0
    fi

    validate_version "$version"
    check_git_repo
    check_develop_branch
    check_working_directory
    check_release_branch "$version"
    prepare_develop
    create_release_branch "$version"
    update_package_version "$version"
    update_python_version "$version"
    update_changelog "$version"
    generate_release_notes "$version"
    create_release_commit "$version"
    setup_branch_tracking "$version"
    show_next_steps "$version"

    print_success "Release $version preparation completed!"
}

# Run main function
main "$@"
