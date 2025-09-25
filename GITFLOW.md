# FXML4 GitFlow Workflow Guide

**Version:** 1.0
**Last Updated:** September 2025
**Project:** FXML4 Enterprise Trading Platform

---

## 📋 Table of Contents

- [Overview](#overview)
- [Branch Structure](#branch-structure)
- [Workflow Diagrams](#workflow-diagrams)
- [Step-by-Step Processes](#step-by-step-processes)
- [Team Guidelines](#team-guidelines)
- [Quick Reference](#quick-reference)
- [Troubleshooting](#troubleshooting)

---

## 🌟 Overview

FXML4 uses a modified GitFlow workflow optimized for enterprise trading platform development. This workflow ensures code quality, enables parallel development, and maintains production stability.

### Key Principles

- **`main`** branch contains only production-ready code
- **`develop`** branch integrates completed features
- **Feature branches** isolate new development
- **Release branches** prepare versions for production
- **Hotfix branches** address critical production issues

### Branch Lifecycle

```
Production Issue → hotfix/issue-name → main → tag → develop
                                      ↑                ↓
                                   release/1.x.x ← develop
                                      ↑                ↓
New Feature → feature/feature-name → develop    bugfix/bug-name
```

---

## 🌳 Branch Structure

### Main Branches

| Branch | Purpose | Lifetime | Protected |
|--------|---------|----------|-----------|
| `main` | Production releases | Permanent | ✅ Yes |
| `develop` | Integration branch | Permanent | ✅ Yes |

### Supporting Branches

| Branch Type | Naming Convention | Branch From | Merge To | Lifetime |
|-------------|-------------------|-------------|----------|----------|
| Feature | `feature/description` | `develop` | `develop` | Temporary |
| Bugfix | `bugfix/description` | `develop` | `develop` | Temporary |
| Release | `release/X.Y.Z` | `develop` | `main` + `develop` | Temporary |
| Hotfix | `hotfix/description` | `main` | `main` + `develop` | Temporary |

---

## 📊 Workflow Diagrams

### Standard Feature Development

```
develop  ●──●──●──●──●──●──●──●──●
           \           \     /
            \           \   /
feature      ●──●──●──●─●──●
                    ↑
                 PR Review
```

### Release Preparation

```
main     ●──●──────────●──●
           \           /    \
            \         /      \
develop      ●──●──●─●────●───●
                \   /
                 \ /
release/1.2.0     ●──●──●
                     ↑
                Bug fixes only
```

### Hotfix Process

```
main     ●──●──●──────●──●
           \        /    \
            \      /      \
hotfix       ●──●──       \
                           \
develop      ●──●──●──●──●──●
                     ↑
                Cherry-pick fix
```

---

## 🔄 Step-by-Step Processes

### 🚀 Starting a New Feature

```bash
# 1. Ensure you're on develop and up to date
git checkout develop
git pull origin develop

# 2. Create and switch to feature branch
git checkout -b feature/user-authentication

# 3. Work on your feature
git add .
git commit -m "feat(auth): implement JWT token validation"

# 4. Push feature branch
git push -u origin feature/user-authentication

# 5. Create Pull Request to develop
gh pr create --base develop --title "feat(auth): Add user authentication system"
```

### 🔧 Finishing a Feature

```bash
# 1. Ensure feature is complete and tested
npm test  # or pytest for Python components

# 2. Update feature branch with latest develop
git checkout develop
git pull origin develop
git checkout feature/user-authentication
git rebase develop

# 3. Push updated branch
git push --force-with-lease origin feature/user-authentication

# 4. Create/Update Pull Request
# 5. After PR approval and merge, cleanup
git checkout develop
git pull origin develop
git branch -d feature/user-authentication
git push origin --delete feature/user-authentication
```

### 📦 Creating a Release

```bash
# 1. Create release branch from develop
git checkout develop
git pull origin develop
git checkout -b release/1.2.0

# 2. Update version numbers
# - Update package.json version
# - Update CHANGELOG.md
# - Update documentation

# 3. Commit version changes
git add .
git commit -m "chore(release): bump version to 1.2.0"

# 4. Push release branch
git push -u origin release/1.2.0

# 5. Create PR to main
gh pr create --base main --title "release: v1.2.0"

# 6. After PR approval, tag the release
git checkout main
git pull origin main
git tag -a v1.2.0 -m "Release version 1.2.0"
git push origin v1.2.0

# 7. Merge back to develop
git checkout develop
git merge main
git push origin develop

# 8. Delete release branch
git branch -d release/1.2.0
git push origin --delete release/1.2.0
```

### 🚨 Emergency Hotfix

```bash
# 1. Create hotfix branch from main
git checkout main
git pull origin main
git checkout -b hotfix/critical-trading-bug

# 2. Fix the issue
git add .
git commit -m "fix(trading): resolve order execution timeout"

# 3. Push hotfix branch
git push -u origin hotfix/critical-trading-bug

# 4. Create PR to main
gh pr create --base main --title "hotfix: Fix critical trading bug"

# 5. After merge, tag hotfix version
git checkout main
git pull origin main
git tag -a v1.1.1 -m "Hotfix version 1.1.1"
git push origin v1.1.1

# 6. Merge to develop
git checkout develop
git merge main
git push origin develop

# 7. Cleanup
git branch -d hotfix/critical-trading-bug
git push origin --delete hotfix/critical-trading-bug
```

---

## 👥 Team Guidelines

### Code Review Requirements

- **Feature Branches:** Minimum 2 approvals
- **Release Branches:** Minimum 2 approvals + lead developer
- **Hotfix Branches:** Minimum 1 approval (expedited process)
- **All PRs:** Must pass automated checks

### Merge Strategies

| Branch Type | Merge Strategy | Reasoning |
|-------------|----------------|-----------|
| Feature → develop | **Squash merge** | Clean history, single commit per feature |
| Bugfix → develop | **Squash merge** | Clean history, single commit per fix |
| Release → main | **Merge commit** | Preserve release history |
| Hotfix → main | **Merge commit** | Preserve hotfix history |

### Branch Naming Conventions

```bash
# Features
feature/user-dashboard
feature/elliott-wave-detection
feature/api-rate-limiting

# Bug fixes
bugfix/memory-leak-trading-engine
bugfix/websocket-reconnection
bugfix/data-validation-error

# Releases
release/1.2.0
release/2.0.0-beta

# Hotfixes
hotfix/security-patch
hotfix/trading-halt-fix
hotfix/data-corruption
```

### Commit Message Standards

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`

**Examples:**
```
feat(api): add real-time market data endpoint
fix(ui): resolve dashboard rendering issue
docs: update installation instructions
test(trading): add unit tests for order validation
```

---

## ⚡ Quick Reference

### Essential Commands

```bash
# Setup (run once)
./scripts/setup-gitflow.sh

# Start feature
git checkout develop && git pull && git checkout -b feature/my-feature

# Daily workflow
git add . && git commit -m "feat(scope): description"
git push origin feature/my-feature

# Rebase with develop
git fetch origin && git rebase origin/develop

# Create PR (GitHub CLI)
gh pr create --base develop --title "feat: Add new feature"

# Cleanup after merge
git checkout develop && git pull && git branch -d feature/my-feature
```

### Branch Status Check

```bash
# Check current branch and status
git status

# See branch relationships
git log --graph --oneline --all -10

# Check for unpushed commits
git log @{u}..HEAD --oneline

# See branches with tracking info
git branch -vv
```

### Useful Aliases

Add to your `.gitconfig`:

```ini
[alias]
    co = checkout
    br = branch
    ci = commit
    st = status
    unstage = reset HEAD --
    last = log -1 HEAD
    visual = !gitk

    # GitFlow specific
    feature = checkout -b feature/
    bugfix = checkout -b bugfix/
    hotfix = checkout -b hotfix/

    # Branch management
    cleanup = "!git branch --merged | grep -v '\\*\\|main\\|develop' | xargs -n 1 git branch -d"

    # Pretty logs
    lg = log --graph --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --abbrev-commit
```

---

## 🛠️ Troubleshooting

### Common Issues

#### Merge Conflicts

```bash
# During rebase
git status                    # See conflicted files
# Edit files to resolve conflicts
git add <resolved-files>
git rebase --continue

# During merge
git status                    # See conflicted files
# Edit files to resolve conflicts
git add <resolved-files>
git commit
```

#### Accidental Commits to Wrong Branch

```bash
# Move commits to correct branch
git checkout correct-branch
git cherry-pick <commit-hash>
git checkout wrong-branch
git reset --hard HEAD~1       # Remove from wrong branch
```

#### Force Push After Rebase

```bash
# Safe force push (checks remote state)
git push --force-with-lease origin feature/my-feature

# If someone else pushed to your branch
git pull --rebase origin feature/my-feature
git push origin feature/my-feature
```

#### Sync Fork with Upstream

```bash
# Add upstream remote (once)
git remote add upstream https://github.com/original/fxml4.git

# Sync develop branch
git checkout develop
git fetch upstream
git merge upstream/develop
git push origin develop
```

### Emergency Procedures

#### Revert a Bad Merge

```bash
# Revert merge commit (use -m 1 for main branch)
git revert -m 1 <merge-commit-hash>
git push origin main
```

#### Rollback Release

```bash
# Create hotfix to rollback
git checkout main
git checkout -b hotfix/rollback-v1.2.0
git revert <release-merge-commit>
git push origin hotfix/rollback-v1.2.0
# Follow hotfix process
```

---

## 📞 Support

### Team Contacts

- **Lead Developer:** Technical decisions, architectural reviews
- **DevOps Team:** CI/CD issues, deployment problems
- **QA Team:** Testing standards, quality gates

### Resources

- [Git Documentation](https://git-scm.com/doc)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [GitHub Flow](https://docs.github.com/en/get-started/quickstart/github-flow)
- [FXML4 Development Guide](./docs/development-guide.md)

---

**Last Updated:** September 2025
**Document Version:** 1.0
**Next Review:** December 2025
