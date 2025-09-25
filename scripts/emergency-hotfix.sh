#!/bin/bash

# FXML4 Emergency Hotfix Script
# Provides fast-track hotfix creation for critical production issues

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
MAGENTA='\033[0;35m'
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

print_urgent() {
    echo -e "${MAGENTA}🚨${NC} $1"
}

print_usage() {
    echo ""
    echo "🚨 FXML4 Emergency Hotfix Creator"
    echo "================================="
    echo ""
    echo "Usage: $0 <hotfix-name> <severity> [description]"
    echo ""
    echo "Parameters:"
    echo "  hotfix-name  - Brief name for the hotfix (kebab-case)"
    echo "  severity     - critical, high, medium"
    echo "  description  - Optional description of the issue"
    echo ""
    echo "Examples:"
    echo "  $0 trading-engine-crash critical"
    echo "  $0 memory-leak-fix high \"Fix memory leak in data processing\""
    echo "  $0 api-timeout-fix medium"
    echo ""
    echo "🔴 CRITICAL: System down, trading halted, data loss"
    echo "🟠 HIGH:     Major functionality broken, significant impact"
    echo "🟡 MEDIUM:   Important fix, moderate impact"
    echo ""
    echo "The script will:"
    echo "  1. Create hotfix branch from main"
    echo "  2. Set up tracking and alerts"
    echo "  3. Prepare for expedited review process"
    echo "  4. Generate hotfix documentation"
    echo ""
}

# Validate severity level
validate_severity() {
    local severity="$1"

    case "$severity" in
        critical|high|medium)
            print_success "Severity level validated: $severity"
            ;;
        *)
            print_error "Invalid severity level: $severity"
            echo "Valid levels: critical, high, medium"
            exit 1
            ;;
    esac
}

# Validate hotfix name
validate_hotfix_name() {
    local name="$1"

    if [ -z "$name" ]; then
        print_error "Hotfix name is required"
        print_usage
        exit 1
    fi

    if [[ ! "$name" =~ ^[a-z0-9-]+$ ]]; then
        print_error "Hotfix name should only contain lowercase letters, numbers, and hyphens"
        exit 1
    fi

    if [ ${#name} -gt 50 ]; then
        print_error "Hotfix name should be 50 characters or less"
        exit 1
    fi
}

# Check git repository and main branch
check_git_repo() {
    if ! git rev-parse --git-dir >/dev/null 2>&1; then
        print_error "This script must be run from within a git repository"
        exit 1
    fi

    # Check if main branch exists
    if ! git show-ref --verify --quiet refs/heads/main; then
        print_error "Main branch doesn't exist. Hotfixes must be created from main."
        exit 1
    fi
}

# Emergency confirmation for critical issues
confirm_emergency() {
    local severity="$1"
    local hotfix_name="$2"

    if [ "$severity" = "critical" ]; then
        print_urgent "CRITICAL HOTFIX CREATION"
        echo ""
        echo "⚠️  This will create an emergency hotfix for: $hotfix_name"
        echo "⚠️  Critical hotfixes bypass normal review processes"
        echo "⚠️  Ensure you have approval from technical leadership"
        echo ""
        read -p "Are you authorized to create a critical hotfix? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_error "Critical hotfix creation cancelled"
            exit 1
        fi

        print_warning "Emergency hotfix authorized. Proceeding..."
    fi
}

# Check for uncommitted changes
check_working_directory() {
    local status=$(git status --porcelain)
    if [ -n "$status" ]; then
        print_warning "You have uncommitted changes:"
        git status --short
        echo ""
        read -p "Stash changes and continue with hotfix? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git stash push -m "Auto-stash before hotfix: $(date)"
            print_success "Changes stashed"
        else
            print_error "Please commit or stash your changes before creating a hotfix"
            exit 1
        fi
    fi
}

# Prepare main branch
prepare_main() {
    print_info "Switching to main branch..."
    git checkout main

    print_info "Pulling latest changes from origin..."
    if git pull origin main; then
        print_success "Main branch updated"
    else
        print_error "Failed to pull from origin. This is critical for hotfixes."
        exit 1
    fi
}

# Check if hotfix branch already exists
check_hotfix_branch() {
    local hotfix_name="$1"
    local branch_name="hotfix/$hotfix_name"

    if git show-ref --verify --quiet refs/heads/$branch_name; then
        print_error "Hotfix branch $branch_name already exists"
        echo ""
        print_info "Existing hotfix branches:"
        git branch | grep hotfix/ || echo "  (none)"
        exit 1
    fi
}

# Create hotfix branch
create_hotfix_branch() {
    local hotfix_name="$1"
    local branch_name="hotfix/$hotfix_name"

    print_info "Creating hotfix branch: $branch_name"
    git checkout -b $branch_name

    print_success "Hotfix branch created and checked out"
}

# Generate hotfix documentation
create_hotfix_documentation() {
    local hotfix_name="$1"
    local severity="$2"
    local description="$3"

    # Create hotfix documentation directory
    mkdir -p "docs/hotfixes"

    local doc_file="docs/hotfixes/$hotfix_name.md"
    local current_time=$(date +"%Y-%m-%d %H:%M:%S %Z")

    cat > "$doc_file" << EOF
# Hotfix: $hotfix_name

## Overview
**Severity:** $severity
**Created:** $current_time
**Branch:** hotfix/$hotfix_name
**Status:** 🔧 In Progress

## Problem Description
$description

## Root Cause Analysis
<!-- Document the root cause once identified -->

## Solution Implementation
<!-- Document the fix being implemented -->

## Testing Plan
### Pre-deployment Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed
- [ ] Performance impact assessed

### Post-deployment Verification
- [ ] Production monitoring shows fix is effective
- [ ] No new issues introduced
- [ ] System performance restored

## Rollback Plan
<!-- Document how to rollback if issues occur -->

## Communication Plan
### Stakeholders Notified
- [ ] Technical leadership
- [ ] Operations team
- [ ] Customer support (if customer-facing)
- [ ] Product team

### Communication Channels
- Slack: #incidents
- Email: engineering-alerts@company.com
- Status page: Updated if customer-facing

## Timeline
- **Issue Identified:**
- **Hotfix Started:** $current_time
- **Target Completion:**
- **Deployed to Production:**
- **Issue Resolved:**

## Post-mortem
<!-- Complete after resolution -->
- [ ] Post-mortem scheduled
- [ ] Root cause documented
- [ ] Prevention measures identified
- [ ] Process improvements noted

## Related Issues
<!-- Link any related GitHub issues, incident reports, etc. -->

---
**Emergency Contact:** On-call engineer
**Escalation Path:** Technical Lead → Engineering Manager → VP Engineering
EOF

    git add "$doc_file"
    print_success "Created hotfix documentation: $doc_file"
}

# Set up hotfix tracking and alerts
setup_hotfix_tracking() {
    local hotfix_name="$1"
    local severity="$2"
    local branch_name="hotfix/$hotfix_name"

    # Create initial commit
    git commit -m "hotfix($hotfix_name): initialize $severity hotfix

Severity: $severity
Status: In Progress
Created: $(date +"%Y-%m-%d %H:%M:%S")

This is an emergency hotfix branch for production issue.
Follow expedited review process for $severity issues."

    # Push to set up tracking
    print_info "Setting up remote tracking..."
    if git push -u origin $branch_name; then
        print_success "Hotfix branch pushed and tracking set up"
    else
        print_error "Failed to push branch. This is critical for hotfixes."
        exit 1
    fi
}

# Show severity-specific workflow
show_workflow_guidance() {
    local hotfix_name="$1"
    local severity="$2"
    local branch_name="hotfix/$hotfix_name"

    echo ""
    case "$severity" in
        critical)
            print_urgent "🚨 CRITICAL HOTFIX WORKFLOW 🚨"
            echo "================================"
            echo ""
            echo "⏰ Target Timeline: Fix within 2 hours"
            echo "👥 Review Process: 1 senior engineer approval (expedited)"
            echo "🚀 Deployment: Direct to production after minimal testing"
            echo ""
            ;;
        high)
            print_warning "🟠 HIGH PRIORITY HOTFIX WORKFLOW"
            echo "================================="
            echo ""
            echo "⏰ Target Timeline: Fix within 24 hours"
            echo "👥 Review Process: 2 approvals required"
            echo "🚀 Deployment: After thorough testing"
            echo ""
            ;;
        medium)
            print_info "🟡 MEDIUM PRIORITY HOTFIX WORKFLOW"
            echo "=================================="
            echo ""
            echo "⏰ Target Timeline: Fix within 72 hours"
            echo "👥 Review Process: Standard review process"
            echo "🚀 Deployment: Follow normal deployment schedule"
            echo ""
            ;;
    esac
}

# Show next steps
show_next_steps() {
    local hotfix_name="$1"
    local severity="$2"
    local branch_name="hotfix/$hotfix_name"

    echo "📋 Next Steps:"
    echo ""
    echo "1. 🔍 Investigate and reproduce the issue:"
    echo "   📊 Check logs, metrics, and monitoring"
    echo "   🧪 Create failing test that demonstrates the issue"
    echo "   📝 Update docs/hotfixes/$hotfix_name.md with findings"
    echo ""
    echo "2. 🛠️ Implement the fix:"
    echo "   ✏️  Make minimal changes to resolve the issue"
    echo "   🧪 Ensure failing test now passes"
    echo "   📝 git commit -m 'fix($hotfix_name): resolve production issue'"
    echo ""
    echo "3. 🧪 Test thoroughly:"
    echo "   ⚡ npm test && pytest tests/"
    echo "   🏗️  Build and verify no regressions"
    echo "   📊 Performance testing if applicable"
    echo ""
    echo "4. 📤 Push and create PR:"
    echo "   📤 git push origin $branch_name"

    if [ "$severity" = "critical" ]; then
        echo "   🚨 gh pr create --base main --title 'CRITICAL HOTFIX: $hotfix_name' --label 'critical,hotfix'"
    else
        echo "   🔄 gh pr create --base main --title 'hotfix: $hotfix_name' --label 'hotfix,$severity'"
    fi

    echo ""
    echo "5. 🚀 Deploy after approval:"
    echo "   🏷️  git tag -a v1.x.x -m 'Hotfix $hotfix_name'"
    echo "   📤 git push origin v1.x.x"
    echo "   🔄 Merge back to develop: git checkout develop && git merge main"
    echo ""
    echo "6. 📊 Post-deployment:"
    echo "   👀 Monitor production metrics"
    echo "   ✅ Verify issue is resolved"
    echo "   📝 Complete hotfix documentation"
    echo "   📧 Notify stakeholders"
    echo ""
    echo "🔧 Emergency Commands:"
    echo "  • git revert HEAD           - Quick rollback if needed"
    echo "  • git push --force-with-lease - Force push after rebase"
    echo "  • git cherry-pick <commit>  - Port specific fixes"
    echo ""
    echo "📞 Emergency Contacts:"
    echo "  • On-call engineer: Check incident response doc"
    echo "  • Technical lead: Escalate for guidance"
    echo "  • Operations: Deploy and monitoring support"
    echo ""
    echo "📚 Documentation:"
    echo "  • docs/hotfixes/$hotfix_name.md - This hotfix details"
    echo "  • GITFLOW.md - Complete workflow guide"
    echo ""
}

# Main execution
main() {
    local hotfix_name="$1"
    local severity="$2"
    local description="$3"

    if [ "$hotfix_name" = "-h" ] || [ "$hotfix_name" = "--help" ] || [ -z "$hotfix_name" ]; then
        print_usage
        exit 0
    fi

    if [ -z "$severity" ]; then
        print_error "Severity level is required"
        print_usage
        exit 1
    fi

    validate_hotfix_name "$hotfix_name"
    validate_severity "$severity"
    confirm_emergency "$severity" "$hotfix_name"
    check_git_repo
    check_working_directory
    check_hotfix_branch "$hotfix_name"
    prepare_main
    create_hotfix_branch "$hotfix_name"
    create_hotfix_documentation "$hotfix_name" "$severity" "$description"
    setup_hotfix_tracking "$hotfix_name" "$severity"
    show_workflow_guidance "$hotfix_name" "$severity"
    show_next_steps "$hotfix_name" "$severity"

    if [ "$severity" = "critical" ]; then
        print_urgent "CRITICAL hotfix $hotfix_name initialized!"
        print_urgent "Time is critical - focus on minimal fix to restore service"
    else
        print_success "Hotfix $hotfix_name ($severity priority) ready for development!"
    fi
}

# Run main function
main "$@"
