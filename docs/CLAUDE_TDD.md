# Claude Code TDD Automation Framework

## Overview

A language-agnostic, monorepo-capable TDD automation framework that leverages Anthropic Claude Code as the primary code synthesizer, with first-class support for mutation and contract testing.

## Architecture

```mermaid
flowchart TB
    subgraph "GitHub Actions Controller"
        A[TDD Workflow Trigger] --> B[Test Discovery & Analysis]
        B --> C[Claude Code Orchestrator]
        C --> D[Progress State Manager]
    end
    
    subgraph "Claude Code Agents"
        C --> E[Trace Analyzer]
        E --> F[Code Synthesizer]
        F --> G[Refactor Guardian]
        G --> H[Test Augmenter]
    end
    
    subgraph "Test Infrastructure"
        F --> I[Language-Agnostic Test Runner]
        I --> J[Mutation Testing Engine]
        I --> K[Contract Testing (Pact)]
        I --> L[Coverage Analysis]
    end
    
    subgraph "Monorepo Support"
        B --> M[Package Dependency Graph]
        M --> N[Affected Package Detection]
        N --> I
    end
    
    D --> O[Incremental Progress Cache]
    O --> P[Partial Success Commits]
```

## Core Components

### 1. GitHub Actions Reusable Workflows

#### Main TDD Workflow (`/.github/workflows/claude-tdd.yml`)

```yaml
name: Claude TDD Automation
on:
  workflow_call:
    inputs:
      max_attempts:
        type: number
        default: 5
      patch_budget:
        type: number
        default: 300
      mutation_threshold:
        type: number
        default: 70
      coverage_threshold:
        type: number
        default: 85
      preserve_progress:
        type: boolean
        default: true
      monorepo_mode:
        type: string
        default: 'auto'  # auto|npm|lerna|nx|rush|pnpm
    secrets:
      ANTHROPIC_API_KEY:
        required: true

jobs:
  discover-tests:
    runs-on: ubuntu-latest
    outputs:
      test_matrix: ${{ steps.discover.outputs.matrix }}
      affected_packages: ${{ steps.discover.outputs.packages }}
      test_framework: ${{ steps.discover.outputs.framework }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for monorepo analysis
      
      - name: Discover Test Framework & Language
        id: discover
        run: |
          # Language-agnostic test discovery
          ./.claude-tdd/scripts/discover-tests.sh
      
      - name: Analyze Monorepo Structure
        if: inputs.monorepo_mode != 'false'
        run: |
          ./.claude-tdd/scripts/analyze-monorepo.sh \
            --mode=${{ inputs.monorepo_mode }} \
            --base=${{ github.event.pull_request.base.sha }}

  run-red-tests:
    needs: discover-tests
    strategy:
      matrix: ${{ fromJson(needs.discover-tests.outputs.test_matrix) }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Test Environment
        uses: ./.github/actions/setup-test-env
        with:
          language: ${{ matrix.language }}
          package: ${{ matrix.package }}
      
      - name: Run Tests (Expecting Failures)
        id: red-tests
        continue-on-error: true
        run: |
          ./.claude-tdd/scripts/run-tests.sh \
            --package=${{ matrix.package }} \
            --type=unit,contract \
            --format=json \
            --output=./test-results/red-${{ matrix.package }}.json
      
      - name: Generate Mutation Baseline
        if: steps.red-tests.outcome == 'failure'
        run: |
          ./.claude-tdd/scripts/mutation-baseline.sh \
            --package=${{ matrix.package }} \
            --config=./.claude-tdd/mutation/${{ matrix.language }}.config.json
      
      - uses: actions/upload-artifact@v4
        with:
          name: red-results-${{ matrix.package }}
          path: ./test-results/

  synthesize-green:
    needs: [discover-tests, run-red-tests]
    runs-on: ubuntu-latest
    strategy:
      matrix: ${{ fromJson(needs.discover-tests.outputs.test_matrix) }}
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.head_ref }}
          token: ${{ secrets.GITHUB_TOKEN }}
      
      - uses: actions/download-artifact@v4
        with:
          name: red-results-${{ matrix.package }}
          path: ./test-results/
      
      - name: Restore Progress Cache
        if: inputs.preserve_progress
        uses: actions/cache@v4
        with:
          path: ./.claude-tdd/progress/
          key: tdd-progress-${{ github.run_id }}-${{ matrix.package }}
          restore-keys: |
            tdd-progress-${{ github.run_id }}-
      
      - name: Claude Code Synthesis Loop
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          python3 ./.claude-tdd/orchestrator/main.py \
            --mode=synthesize \
            --package=${{ matrix.package }} \
            --max-attempts=${{ inputs.max_attempts }} \
            --patch-budget=${{ inputs.patch_budget }} \
            --test-results=./test-results/red-${{ matrix.package }}.json \
            --progress-dir=./.claude-tdd/progress/ \
            --preserve-partial=${{ inputs.preserve_progress }}
      
      - name: Validate Contracts
        run: |
          ./.claude-tdd/scripts/validate-contracts.sh \
            --package=${{ matrix.package }} \
            --pact-broker=${{ vars.PACT_BROKER_URL }}
      
      - name: Commit Green Changes
        if: success()
        run: |
          git config user.name "claude-tdd[bot]"
          git config user.email "claude-tdd[bot]@users.noreply.github.com"
          git add -A
          git diff --staged --quiet || git commit -m "feat(green): synthesize passing code for ${{ matrix.package }} [claude-bot]"
          git push

  mutation-testing:
    needs: synthesize-green
    runs-on: ubuntu-latest
    strategy:
      matrix: ${{ fromJson(needs.discover-tests.outputs.test_matrix) }}
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.head_ref }}
      
      - name: Setup Test Environment
        uses: ./.github/actions/setup-test-env
        with:
          language: ${{ matrix.language }}
          package: ${{ matrix.package }}
      
      - name: Run Mutation Tests
        id: mutation
        run: |
          ./.claude-tdd/scripts/run-mutation.sh \
            --package=${{ matrix.package }} \
            --threshold=${{ inputs.mutation_threshold }} \
            --incremental \
            --output=./mutation-results/
      
      - name: Augment Tests if Below Threshold
        if: steps.mutation.outputs.score < inputs.mutation_threshold
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          python3 ./.claude-tdd/orchestrator/main.py \
            --mode=augment \
            --package=${{ matrix.package }} \
            --mutation-report=./mutation-results/${{ matrix.package }}.json \
            --target-score=${{ inputs.mutation_threshold }}

  contract-verification:
    needs: synthesize-green
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.head_ref }}
      
      - name: Verify All Contracts
        run: |
          ./.claude-tdd/scripts/pact-verify-all.sh \
            --broker=${{ vars.PACT_BROKER_URL }} \
            --publish-results
      
      - name: Generate Contract Documentation
        run: |
          ./.claude-tdd/scripts/generate-contract-docs.sh \
            --output=./docs/contracts/
```

### 2. Claude Code Orchestrator (`/.claude-tdd/orchestrator/main.py`)

```python
#!/usr/bin/env python3
"""
Claude Code TDD Orchestrator
Language-agnostic orchestration for TDD automation
"""

import json
import subprocess
import argparse
from pathlib import Path
from typing import Dict, List, Optional
import asyncio
import tempfile
from dataclasses import dataclass

@dataclass
class TestFailure:
    file: str
    test_name: str
    error: str
    stack_trace: str
    package: str
    language: str

@dataclass
class SynthesisAttempt:
    attempt_number: int
    failures_addressed: List[TestFailure]
    patch: str
    success: bool
    tests_passed: List[str]
    tests_failed: List[str]

class ClaudeCodeOrchestrator:
    def __init__(self, api_key: str, progress_dir: Path):
        self.api_key = api_key
        self.progress_dir = progress_dir
        self.progress_dir.mkdir(parents=True, exist_ok=True)
        
    async def synthesize_loop(
        self,
        package: str,
        test_results: Dict,
        max_attempts: int,
        patch_budget: int,
        preserve_partial: bool
    ) -> bool:
        """Main synthesis loop using Claude Code"""
        
        failures = self._parse_test_failures(test_results)
        progress = self._load_progress(package)
        
        for attempt in range(max_attempts):
            if not failures:
                return True
                
            # Group failures by root cause
            failure_groups = self._group_failures(failures)
            
            for group in failure_groups:
                success = await self._synthesize_for_group(
                    package, group, patch_budget, attempt, preserve_partial
                )
                
                if success:
                    # Remove addressed failures
                    failures = [f for f in failures if f not in group]
                    self._save_progress(package, failures, attempt)
                    
                    if preserve_partial:
                        self._commit_partial_progress(package, attempt)
        
        return len(failures) == 0
    
    async def _synthesize_for_group(
        self,
        package: str,
        failures: List[TestFailure],
        patch_budget: int,
        attempt: int,
        preserve_partial: bool
    ) -> bool:
        """Synthesize code for a group of related failures using Claude Code"""
        
        # Prepare context for Claude Code
        context = self._prepare_context(package, failures)
        
        # Create Claude Code session
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(self._create_claude_prompt(failures, context, patch_budget))
            prompt_file = f.name
        
        try:
            # Invoke Claude Code
            result = subprocess.run([
                'claude-code',
                '--api-key', self.api_key,
                '--task', prompt_file,
                '--working-dir', self._get_package_root(package),
                '--max-file-changes', str(patch_budget // 50),  # Rough estimate
                '--no-interactive',
                '--output-format', 'json'
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                # Parse Claude Code output
                output = json.loads(result.stdout)
                
                # Apply the patch
                if self._apply_patch(output['patch']):
                    # Run tests to verify
                    if self._run_tests(package, [f.test_name for f in failures]):
                        return True
                    elif preserve_partial:
                        # Check if some tests now pass
                        passing = self._get_passing_tests(package, failures)
                        if passing:
                            self._save_partial_success(package, passing)
                            return True
            
        finally:
            Path(prompt_file).unlink(missing_ok=True)
        
        return False
    
    def _create_claude_prompt(
        self,
        failures: List[TestFailure],
        context: Dict,
        patch_budget: int
    ) -> str:
        """Create a detailed prompt for Claude Code"""
        
        return f"""
# TDD Code Synthesis Task

## Objective
Make the following failing tests pass with minimal, safe code changes.

## Failing Tests
{self._format_failures(failures)}

## Context
- Language: {failures[0].language}
- Package: {failures[0].package}
- Test Framework: {context['test_framework']}
- Related Files: {json.dumps(context['related_files'], indent=2)}

## Constraints
1. Maximum {patch_budget} lines of code changes
2. Do NOT modify test files
3. Preserve all existing public APIs
4. Maintain backward compatibility
5. Follow existing code style and patterns
6. Add only minimal code necessary to pass tests

## Contract Specifications
{json.dumps(context.get('contracts', {}), indent=2)}

## Existing Code Context
{context['code_context']}

## Instructions
1. Analyze the test failures to understand requirements
2. Identify the minimal code changes needed
3. Implement ONLY what's necessary to make tests pass
4. Ensure changes are idempotent and safe
5. Validate against contract specifications if applicable

## Expected Output
Provide code changes that will make all specified tests pass.
"""

    async def augment_tests(
        self,
        package: str,
        mutation_report: Dict,
        target_score: float
    ) -> bool:
        """Augment tests based on mutation testing results"""
        
        survived_mutants = self._parse_mutation_report(mutation_report)
        current_score = mutation_report['score']
        
        while current_score < target_score:
            # Identify weakest areas
            weak_areas = self._identify_weak_coverage(survived_mutants)
            
            # Generate additional tests using Claude Code
            new_tests = await self._generate_tests_for_mutants(
                package, weak_areas, survived_mutants
            )
            
            if not new_tests:
                break
                
            # Apply new tests
            self._apply_test_changes(new_tests)
            
            # Re-run mutation testing
            new_report = self._run_mutation_tests(package)
            current_score = new_report['score']
            survived_mutants = self._parse_mutation_report(new_report)
        
        return current_score >= target_score
    
    # Additional helper methods...
    def _parse_test_failures(self, test_results: Dict) -> List[TestFailure]:
        """Parse language-agnostic test results"""
        # Implementation varies by test framework format
        pass
    
    def _group_failures(self, failures: List[TestFailure]) -> List[List[TestFailure]]:
        """Group failures by root cause for efficient synthesis"""
        # Group by file, function, or error type
        pass

# CLI entry point
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Claude Code TDD Orchestrator")
    parser.add_argument("--mode", choices=["synthesize", "augment"], required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--patch-budget", type=int, default=300)
    parser.add_argument("--test-results", type=str)
    parser.add_argument("--mutation-report", type=str)
    parser.add_argument("--target-score", type=float, default=70)
    parser.add_argument("--progress-dir", type=str, default=".claude-tdd/progress")
    parser.add_argument("--preserve-partial", type=bool, default=True)
    
    args = parser.parse_args()
    
    orchestrator = ClaudeCodeOrchestrator(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        progress_dir=Path(args.progress_dir)
    )
    
    if args.mode == "synthesize":
        with open(args.test_results) as f:
            test_results = json.load(f)
        
        success = asyncio.run(orchestrator.synthesize_loop(
            args.package,
            test_results,
            args.max_attempts,
            args.patch_budget,
            args.preserve_partial
        ))
        
        sys.exit(0 if success else 1)
    
    elif args.mode == "augment":
        with open(args.mutation_report) as f:
            mutation_report = json.load(f)
        
        success = asyncio.run(orchestrator.augment_tests(
            args.package,
            mutation_report,
            args.target_score
        ))
        
        sys.exit(0 if success else 1)
```

### 3. Language-Agnostic Test Discovery (`/.claude-tdd/scripts/discover-tests.sh`)

```bash
#!/bin/bash
# Language-agnostic test discovery and framework detection

set -euo pipefail

detect_language() {
    local path="${1:-.}"
    
    # Priority order for language detection
    if [[ -f "$path/package.json" ]]; then
        echo "javascript"
    elif [[ -f "$path/pyproject.toml" ]] || [[ -f "$path/setup.py" ]]; then
        echo "python"
    elif [[ -f "$path/Cargo.toml" ]]; then
        echo "rust"
    elif [[ -f "$path/go.mod" ]]; then
        echo "go"
    elif [[ -f "$path/pom.xml" ]] || [[ -f "$path/build.gradle" ]]; then
        echo "java"
    elif [[ -f "$path/composer.json" ]]; then
        echo "php"
    elif [[ -f "$path/Gemfile" ]]; then
        echo "ruby"
    elif [[ -f "$path/*.csproj" ]] || [[ -f "$path/*.sln" ]]; then
        echo "csharp"
    else
        echo "unknown"
    fi
}

detect_test_framework() {
    local lang="$1"
    local path="${2:-.}"
    
    case "$lang" in
        javascript)
            if grep -q "jest" "$path/package.json" 2>/dev/null; then
                echo "jest"
            elif grep -q "mocha" "$path/package.json" 2>/dev/null; then
                echo "mocha"
            elif grep -q "vitest" "$path/package.json" 2>/dev/null; then
                echo "vitest"
            else
                echo "npm-test"
            fi
            ;;
        python)
            if grep -q "pytest" "$path/pyproject.toml" "$path/setup.cfg" "$path/requirements*.txt" 2>/dev/null; then
                echo "pytest"
            elif grep -q "unittest" "$path/setup.py" 2>/dev/null; then
                echo "unittest"
            else
                echo "pytest"  # Default
            fi
            ;;
        rust)
            echo "cargo-test"
            ;;
        go)
            echo "go-test"
            ;;
        java)
            if [[ -f "$path/pom.xml" ]]; then
                echo "maven-test"
            else
                echo "gradle-test"
            fi
            ;;
        *)
            echo "generic"
            ;;
    esac
}

detect_monorepo_structure() {
    if [[ -f "lerna.json" ]]; then
        echo "lerna"
    elif [[ -f "nx.json" ]]; then
        echo "nx"
    elif [[ -f "rush.json" ]]; then
        echo "rush"
    elif [[ -f "pnpm-workspace.yaml" ]]; then
        echo "pnpm"
    elif [[ -f "package.json" ]] && grep -q "workspaces" package.json; then
        echo "npm-workspaces"
    elif [[ -d "packages" ]] || [[ -d "apps" ]]; then
        echo "convention-based"
    else
        echo "single"
    fi
}

discover_packages() {
    local monorepo_type="$1"
    
    case "$monorepo_type" in
        lerna|npm-workspaces|pnpm)
            # Parse workspace configuration
            node -e "
                const config = require('./package.json');
                const workspaces = config.workspaces || [];
                const glob = require('glob');
                const packages = workspaces.flatMap(w => glob.sync(w));
                console.log(JSON.stringify(packages));
            "
            ;;
        nx)
            npx nx show projects --json
            ;;
        convention-based)
            find . -type f -name "package.json" -o -name "pyproject.toml" \
                -o -name "Cargo.toml" -o -name "go.mod" \
                | xargs -I {} dirname {} \
                | grep -v node_modules \
                | jq -R -s 'split("\n")[:-1]'
            ;;
        *)
            echo '["."]'
            ;;
    esac
}

# Main discovery
monorepo_type=$(detect_monorepo_structure)
packages=$(discover_packages "$monorepo_type")

# Build test matrix
matrix=[]
for pkg in $(echo "$packages" | jq -r '.[]'); do
    lang=$(detect_language "$pkg")
    fraework=$(detect_test_framework "$lang" "$pkg")
    
    matrix=$(echo "$matrix" | jq ". + [{
        \"package\": \"$pkg\",
        \"language\": \"$lang\",
        \"framework\": \"$framework\"
    }]")
done

# Output for GitHub Actions
echo "matrix=$matrix" >> "$GITHUB_OUTPUT"
echo "packages=$packages" >> "$GITHUB_OUTPUT"
echo "monorepo_type=$monorepo_type" >> "$GITHUB_OUTPUT"
```

### 4. Mutation Testing Configuration

#### Language-Specific Mutation Configs

**JavaScript/TypeScript (`/.claude-tdd/mutation/javascript.config.json`)**
```json
{
  "mutator": "stryker",
  "config": {
    "testRunner": "jest",
    "reporters": ["json", "html", "clear-text"],
    "coverageAnalysis": "perTest",
    "mutate": [
      "src/**/*.{js,ts}",
      "!src/**/*.test.{js,ts}",
      "!src/**/*.spec.{js,ts}"
    ],
    "incremental": true,
    "incrementalFile": ".claude-tdd/mutation/stryker-incremental.json"
  }
}
```

**Python (`/.claude-tdd/mutation/python.config.json`)**
```json
{
  "mutator": "mutmut",
  "config": {
    "paths_to_mutate": "src/",
    "tests_dir": "tests/",
    "runner": "pytest -x",
    "use_coverage": true,
    "coverage_file": ".coverage",
    "dict_synonyms": "FancyStrategy"
  }
}
```

**Generic Mutation Runner (`/.claude-tdd/scripts/run-mutation.sh`)**
```bash
#!/bin/bash
# Language-agnostic mutation testing runner

set -euo pipefail

package="$1"
threshold="${2:-70}"
incremental="${3:-false}"
output_dir="${4:-./mutation-results}"

# Detect language and load config
lang=$(detect_language "$package")
config=".claude-tdd/mutation/${lang}.config.json"

if [[ ! -f "$config" ]]; then
    echo "No mutation config for language: $lang"
    exit 1
fi

mutator=$(jq -r '.mutator' "$config")

case "$mutator" in
    stryker)
        cd "$package"
        npx stryker run --config "$config"
        score=$(jq -r '.mutationScore' .stryker-tmp/reports/mutation.json)
        ;;
    mutmut)
        cd "$package"
        mutmut run --use-coverage
        mutmut results --format json > "$output_dir/${package##*/}.json"
        score=$(mutmut results | grep "Mutation score" | awk '{print $3}' | tr -d '%')
        ;;
    *)
        echo "Unknown mutator: $mutator"
        exit 1
        ;;
esac

echo "score=$score" >> "$GITHUB_OUTPUT"

if (( $(echo "$score < $threshold" | bc -l) )); then
    echo "Mutation score $score% is below threshold $threshold%"
    exit 1
fi
```

### 5. Contract Testing Integration

**Pact Configuration (`/.claude-tdd/pact/config.json`)**
```json
{
  "broker": {
    "url": "${PACT_BROKER_URL}",
    "auth": {
      "type": "bearer",
      "token": "${PACT_BROKER_TOKEN}"
    }
  },
  "consumer": {
    "name": "${PACKAGE_NAME}-consumer"
  },
  "provider": {
    "name": "${PACKAGE_NAME}-provider"
  },
  "publishVerificationResult": true,
  "providerVersion": "${GIT_COMMIT}"
}
```

**Contract Validation Script (`/.claude-tdd/scripts/validate-contracts.sh`)**
```bash
#!/bin/bash
# Validate contracts across all supported languages

set -euo pipefail

package="$1"
broker_url="${2:-}"

lang=$(detect_language "$package")

case "$lang" in
    javascript)
        cd "$package"
        npm run pact:verify || npx jest --testMatch="**/*.pact.spec.js"
        npm run pact:publish || npx pact-broker publish pacts --broker-base-url="$broker_url"
        ;;
    python)
        cd "$package"
        pytest tests/contract/ -v
        pact-verifier --provider-base-url=http://localhost:8000 \
            --pact-broker-url="$broker_url"
        ;;
    java)
        cd "$package"
        mvn pact:verify || gradle pactVerify
        mvn pact:publish || gradle pactPublish
        ;;
    *)
        echo "Contract testing not configured for: $lang"
        ;;
esac
```

### 6. Progress Preservation System

**Progress State Manager (`/.claude-tdd/orchestrator/progress.py`)**
```python
"""
Progress preservation for incremental TDD synthesis
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import git

@dataclass
class ProgressState:
    package: str
    attempt: int
    failures_remaining: List[Dict]
    patches_applied: List[str]
    tests_passing: List[str]
    commit_hash: Optional[str] = None

class ProgressManager:
    def __init__(self, progress_dir: Path):
        self.progress_dir = progress_dir
        self.progress_dir.mkdir(parents=True, exist_ok=True)
        self.repo = git.Repo(search_parent_directories=True)
    
    def save_progress(
        self, 
        package: str, 
        state: ProgressState,
        create_checkpoint: bool = True
    ) -> None:
        """Save current progress state"""
        
        state_file = self.progress_dir / f"{package}.json"
        
        # Create git checkpoint if requested
        if create_checkpoint:
            checkpoint_hash = self._create_checkpoint(package, state.attempt)
            state.commit_hash = checkpoint_hash
        
        # Save state
        with open(state_file, 'w') as f:
            json.dump(asdict(state), f, indent=2)
        
        # Also save to attempt-specific file
        attempt_file = self.progress_dir / f"{package}-attempt-{state.attempt}.json"
        with open(attempt_file, 'w') as f:
            json.dump(asdict(state), f, indent=2)
    
    def load_progress(self, package: str) -> Optional[ProgressState]:
        """Load most recent progress state"""
        
        state_file = self.progress_dir / f"{package}.json"
        if not state_file.exists():
            return None
        
        with open(state_file) as f:
            data = json.load(f)
        
        return ProgressState(**data)
    
    def restore_checkpoint(self, package: str, attempt: int) -> bool:
        """Restore to a previous checkpoint"""
        
        attempt_file = self.progress_dir / f"{package}-attempt-{attempt}.json"
        if not attempt_file.exists():
            return False
        
        with open(attempt_file) as f:
            data = json.load(f)
        
        if commit_hash := data.get('commit_hash'):
            self.repo.git.checkout(commit_hash)
            return True
        
        return False
    
    def _create_checkpoint(self, package: str, attempt: int) -> str:
        """Create a git checkpoint for partial progress"""
        
        # Stage changes
        self.repo.index.add(A=True)
        
        # Create checkpoint commit
        commit_msg = f"checkpoint: {package} attempt {attempt} [claude-tdd]"
        commit = self.repo.index.commit(commit_msg)
        
        return commit.hexsha
    
    def merge_partial_progress(self, package: str) -> None:
        """Merge successful partial attempts into main branch"""
        
        # Find all successful partial attempts
        attempt_files = sorted(self.progress_dir.glob(f"{package}-attempt-*.json"))
        
        for attempt_file in attempt_files:
            with open(attempt_file) as f:
                data = json.load(f)
            
            if data.get('tests_passing'):
                # Cherry-pick successful changes
                if commit_hash := data.get('commit_hash'):
                    try:
                        self.repo.git.cherry_pick(commit_hash)
                    except git.exc.GitCommandError:
                        # Handle conflicts
                        self._resolve_conflicts(package, data)
```

### 7. Claude Code Integration Wrapper

**Claude Code CLI Wrapper (`/.claude-tdd/bin/claude-wrapper.sh`)**
```bash
#!/bin/bash
# Wrapper for Claude Code CLI with TDD-specific options

set -euo pipefail

# Default configuration
CLAUDE_CODE_VERSION="${CLAUDE_CODE_VERSION:-latest}"
MAX_TOKENS="${MAX_TOKENS:-100000}"
TEMPERATURE="${TEMPERATURE:-0.2}"  # Lower for deterministic code generation

# TDD-specific flags
TDD_FLAGS=(
    "--systematic"           # Systematic approach for TDD
    "--preserve-tests"       # Never modify test files
    "--incremental"         # Support incremental changes
    "--contract-aware"      # Consider API contracts
    "--mutation-aware"      # Consider mutation testing feedback
)

# Language-specific configurations
configure_for_language() {
    local lang="$1"
    
    case "$lang" in
        javascript|typescript)
            TDD_FLAGS+=("--prettier" "--eslint")
            ;;
        python)
            TDD_FLAGS+=("--black" "--pylint" "--mypy")
            ;;
        rust)
            TDD_FLAGS+=("--rustfmt" "--clippy")
            ;;
        go)
            TDD_FLAGS+=("--gofmt" "--golint")
            ;;
    esac
}

# Main execution
main() {
    local task_file="$1"
    local working_dir="${2:-.}"
    local language="${3:-auto}"
    
    if [[ "$language" != "auto" ]]; then
        configure_for_language "$language"
    fi
    
    # Execute Claude Code with TDD configuration
    claude-code \
        --task-file "$task_file" \
        --working-dir "$working_dir" \
        --max-tokens "$MAX_TOKENS" \
        --temperature "$TEMPERATURE" \
        "${TDD_FLAGS[@]}" \
        "$@"
}

main "$@"
```

### 8. Setup Action for Test Environments

**Test Environment Setup (`/.github/actions/setup-test-env/action.yml`)**
```yaml
name: Setup Test Environment
description: Language-agnostic test environment setup

inputs:
  language:
    description: Programming language
    required: true
  package:
    description: Package directory
    default: '.'
  node-version:
    default: '20'
  python-version:
    default: '3.11'
  java-version:
    default: '17'
  rust-version:
    default: 'stable'
  go-version:
    default: '1.21'

runs:
  using: composite
  steps:
    - name: Setup Node.js
      if: inputs.language == 'javascript'
      uses: actions/setup-node@v4
      with:
        node-version: ${{ inputs.node-version }}
        cache: 'npm'
        cache-dependency-path: ${{ inputs.package }}/package-lock.json
    
    - name: Setup Python
      if: inputs.language == 'python'
      uses: actions/setup-python@v5
      with:
        python-version: ${{ inputs.python-version }}
        cache: 'pip'
        cache-dependency-path: ${{ inputs.package }}/requirements*.txt
    
    - name: Setup Java
      if: inputs.language == 'java'
      uses: actions/setup-java@v4
      with:
        java-version: ${{ inputs.java-version }}
        distribution: 'temurin'
        cache: 'maven'
    
    - name: Setup Rust
      if: inputs.language == 'rust'
      uses: actions-rust-lang/setup-rust-toolchain@v1
      with:
        toolchain: ${{ inputs.rust-version }}
    
    - name: Setup Go
      if: inputs.language == 'go'
      uses: actions/setup-go@v5
      with:
        go-version: ${{ inputs.go-version }}
        cache-dependency-path: ${{ inputs.package }}/go.sum
    
    - name: Install Dependencies
      shell: bash
      working-directory: ${{ inputs.package }}
      run: |
        case "${{ inputs.language }}" in
          javascript)
            npm ci
            npm install -D @stryker-mutator/core @pact-foundation/pact
            ;;
          python)
            pip install -r requirements.txt
            pip install mutmut pact-python pytest-cov
            ;;
          java)
            mvn dependency:resolve
            ;;
          rust)
            cargo build --tests
            cargo install cargo-mutants
            ;;
          go)
            go mod download
            go install github.com/zimmski/go-mutesting/cmd/go-mutesting@latest
            ;;
        esac
    
    - name: Install Claude Code CLI
      shell: bash
      run: |
        # Install Claude Code CLI if not present
        if ! command -v claude-code &> /dev/null; then
          curl -fsSL https://claude-code.anthropic.com/install.sh | bash
          echo "$HOME/.claude-code/bin" >> $GITHUB_PATH
        fi
```

## Usage Instructions

### 1. Initial Setup

```bash
# Clone the framework
git clone https://github.com/your-org/claude-tdd-framework .claude-tdd

# Initialize for your project
.claude-tdd/init.sh --monorepo-type=auto --languages=javascript,python

# Configure GitHub secrets
gh secret set ANTHROPIC_API_KEY --body="your-api-key"
```

### 2. Create TDD Workflow

```yaml
# .github/workflows/tdd.yml
name: TDD Automation
on:
  pull_request:
    types: [labeled]
    
jobs:
  claude-tdd:
    if: contains(github.event.label.name, 'tdd:auto')
    uses: ./.github/workflows/claude-tdd.yml
    with:
      max_attempts: 5
      patch_budget: 300
      mutation_threshold: 75
      coverage_threshold: 85
      preserve_progress: true
      monorepo_mode: 'auto'
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

### 3. Trigger Automation

```bash
# Write failing tests
git checkout -b feature/new-capability
echo "test('should handle new requirement', () => { ... })" >> tests/feature.test.js
git add tests/
git commit -m "test(red): add failing tests for new feature"
git push origin feature/new-capability

# Create PR and label it
gh pr create --title "New Feature" --label "tdd:auto"
```

## Configuration Files

### Framework Configuration (`/.claude-tdd/config.yml`)

```yaml
version: '1.0'
defaults:
  max_attempts: 5
  patch_budget: 300
  mutation_threshold: 70
  coverage_threshold: 85
  preserve_progress: true

languages:
  javascript:
    test_framework: jest
    mutation_tool: stryker
    contract_tool: pact
    coverage_tool: jest
  python:
    test_framework: pytest
    mutation_tool: mutmut
    contract_tool: pact
    coverage_tool: pytest-cov
  rust:
    test_framework: cargo
    mutation_tool: cargo-mutants
    contract_tool: pact
    coverage_tool: cargo-llvm-cov

monorepo:
  type: auto  # auto|lerna|nx|rush|pnpm|npm-workspaces
  affected_detection: true
  parallel_execution: true
  
claude_code:
  model: claude-3-opus-20240229
  temperature: 0.2
  max_tokens: 100000
  
progress:
  preservation: true
  checkpoint_strategy: per-attempt
  cleanup_after_success: false
```

## Monitoring & Metrics

### Prometheus Metrics Export

```yaml
# .claude-tdd/metrics/prometheus.yml
metrics:
  - name: tdd_synthesis_attempts_total
    type: counter
    help: Total number of synthesis attempts
  - name: tdd_synthesis_success_rate
    type: gauge
    help: Success rate of synthesis attempts
  - name: tdd_mutation_score
    type: gauge
    help: Current mutation testing score
  - name: tdd_time_to_green_seconds
    type: histogram
    help: Time taken to achieve green state
  - name: tdd_partial_progress_saves
    type: counter
    help: Number of partial progress saves
```

## ChatOps Commands

```yaml
# .github/chatops-commands.yml
commands:
  - name: tdd
    description: Control TDD automation
    subcommands:
      - name: start
        description: Start TDD automation
        action: label-pr
        label: tdd:auto
      - name: stop
        description: Stop TDD automation
        action: cancel-workflow
      - name: status
        description: Get TDD status
        action: comment-status
      - name: retry
        description: Retry failed synthesis
        action: restart-workflow
      - name: preserve
        description: Save partial progress
        action: save-checkpoint
```

This framework provides a comprehensive, language-agnostic TDD automation system that leverages Claude Code's capabilities while maintaining support for monorepos, mutation testing, and contract testing as first-class citizens. The progress preservation system ensures that partial successes are not lost, and the framework can be easily extended to support additional languages and testing tools.
