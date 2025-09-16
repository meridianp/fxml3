#!/usr/bin/env python3.12
"""
AI Code Reviewer for Pre-commit Hook
Performs AI-powered code review on staged changes before commit
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def get_staged_changes() -> Tuple[List[str], str]:
    """Get staged changes as a diff."""
    try:
        # Get list of staged files
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return [], ""

        staged_files = [f for f in result.stdout.strip().split("\n") if f]

        # Get the actual diff
        result = subprocess.run(
            ["git", "diff", "--cached"], capture_output=True, text=True, timeout=30
        )

        if result.returncode != 0:
            return staged_files, ""

        return staged_files, result.stdout

    except subprocess.TimeoutExpired:
        print("⚠️ Git command timeout")
        return [], ""
    except Exception as e:
        print(f"⚠️ Error getting staged changes: {e}")
        return [], ""


def analyze_changed_files(staged_files: List[str]) -> Dict:
    """Analyze the types of files changed."""
    analysis = {
        "python_files": [],
        "config_files": [],
        "workflow_files": [],
        "documentation": [],
        "trading_components": [],
        "security_sensitive": [],
        "database_changes": [],
        "api_changes": [],
    }

    for file_path in staged_files:
        if not file_path:
            continue

        path = Path(file_path)

        # Categorize files
        if file_path.endswith(".py"):
            analysis["python_files"].append(file_path)

            # Trading system specific categorization
            if any(
                component in file_path.lower()
                for component in [
                    "broker",
                    "fix",
                    "trading",
                    "strategy",
                    "signal",
                    "ml",
                    "risk",
                ]
            ):
                analysis["trading_components"].append(file_path)

            if any(
                component in file_path.lower()
                for component in [
                    "auth",
                    "security",
                    "encrypt",
                    "crypto",
                    "password",
                    "token",
                ]
            ):
                analysis["security_sensitive"].append(file_path)

            if any(
                component in file_path.lower()
                for component in ["db", "database", "migration", "model", "schema"]
            ):
                analysis["database_changes"].append(file_path)

            if any(
                component in file_path.lower()
                for component in ["api", "endpoint", "router", "fastapi"]
            ):
                analysis["api_changes"].append(file_path)

        elif file_path.endswith((".yml", ".yaml")):
            analysis["config_files"].append(file_path)
            if "workflows" in file_path:
                analysis["workflow_files"].append(file_path)

        elif file_path.endswith((".md", ".rst", ".txt")):
            analysis["documentation"].append(file_path)

    return analysis


def create_review_prompt(
    staged_files: List[str], diff_content: str, analysis: Dict
) -> str:
    """Create AI prompt for code review."""

    prompt = f"""
Perform comprehensive code review for FXML4 trading system changes:

CHANGED FILES ({len(staged_files)}):
{chr(10).join(f"- {f}" for f in staged_files[:20])}  # Limit to first 20

FILE ANALYSIS:
- Python files: {len(analysis['python_files'])}
- Trading components: {len(analysis['trading_components'])}
- Security-sensitive: {len(analysis['security_sensitive'])}
- API changes: {len(analysis['api_changes'])}
- Database changes: {len(analysis['database_changes'])}

REVIEW FOCUS AREAS:

1. CORRECTNESS & FUNCTIONALITY
   - Logic correctness and algorithm efficiency
   - Error handling and edge cases
   - Input validation and output verification
   - Trading system specific logic (signals, risk management, broker integration)

2. SECURITY (Critical for Financial System)
   - OWASP Top 10 vulnerabilities
   - Authentication and authorization flaws
   - Input validation and injection attacks
   - Sensitive data exposure in logs/errors
   - Trading-specific security (order tampering, price manipulation)
   - Cryptographic implementation issues
   - API security (rate limiting, authentication)

3. PERFORMANCE & SCALABILITY
   - Time and space complexity analysis
   - Database query optimization
   - Real-time processing efficiency (critical for trading)
   - Memory usage and resource management
   - Caching strategies

4. MAINTAINABILITY & CODE QUALITY
   - Code clarity and readability
   - Design patterns and architectural consistency
   - Documentation and comments quality
   - Test coverage and quality
   - Technical debt assessment

5. TRADING SYSTEM COMPLIANCE
   - Financial regulations (MiFID II, EMIR, Dodd-Frank)
   - Risk management validation
   - Audit trail maintenance
   - Data integrity and consistency
   - Broker integration standards
   - FIX protocol compliance

DIFF CONTENT:
```diff
{diff_content[:5000]}  # Limit diff size for prompt
{'...(truncated)' if len(diff_content) > 5000 else ''}
```

OUTPUT REQUIREMENTS:

Provide structured review as JSON:
```json
{{
  "overall_assessment": "APPROVE|REQUEST_CHANGES|BLOCK",
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "summary": "Brief overall assessment",
  "categories": {{
    "correctness": {{
      "score": 1-10,
      "issues": ["list of issues"],
      "suggestions": ["list of suggestions"]
    }},
    "security": {{
      "score": 1-10,
      "critical_issues": ["list of critical security issues"],
      "warnings": ["list of security warnings"],
      "suggestions": ["list of security improvements"]
    }},
    "performance": {{
      "score": 1-10,
      "bottlenecks": ["list of performance concerns"],
      "suggestions": ["list of optimizations"]
    }},
    "maintainability": {{
      "score": 1-10,
      "technical_debt": ["list of maintainability issues"],
      "suggestions": ["list of improvements"]
    }},
    "compliance": {{
      "score": 1-10,
      "violations": ["list of compliance issues"],
      "requirements": ["list of regulatory requirements to address"]
    }}
  }},
  "critical_blockers": ["list of issues that must be fixed before merge"],
  "recommendations": ["prioritized list of recommendations"],
  "testing_suggestions": ["specific tests that should be added"],
  "next_steps": ["actionable items for the developer"]
}}
```

SCORING: 1=Poor, 5=Acceptable, 8=Good, 10=Excellent
ASSESSMENT:
- APPROVE: No critical issues, ready to merge
- REQUEST_CHANGES: Issues present but not blocking
- BLOCK: Critical security/correctness issues that prevent merge

Focus on financial trading system requirements:
- Zero tolerance for data corruption or loss
- Real-time performance requirements
- Regulatory compliance mandatory
- Security is paramount (financial data protection)
- High availability requirements (99.9% uptime)

Generate comprehensive but concise review focusing on the most impactful issues.
"""

    return prompt


def perform_ai_review(
    staged_files: List[str], diff_content: str, analysis: Dict
) -> Tuple[bool, Dict]:
    """Perform AI-powered code review."""
    if not check_ai_availability():
        return False, {"error": "AI not available"}

    prompt = create_review_prompt(staged_files, diff_content, analysis)

    try:
        # Use Codex CLI for review
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(prompt)
            prompt_file = f.name

        result = subprocess.run(
            [
                "codex",
                "exec",
                "-p",
                "fxml4_ci",
                "--sandbox",
                "read-only",
                f"$(cat {prompt_file})",
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )

        # Clean up temp file
        os.unlink(prompt_file)

        if result.returncode == 0:
            # Extract JSON from output
            review_data = extract_json_from_output(result.stdout)
            if review_data:
                return True, review_data
            else:
                return False, {"error": "Could not parse AI review output"}
        else:
            error_msg = result.stderr or result.stdout
            return False, {"error": f"AI review failed: {error_msg}"}

    except subprocess.TimeoutExpired:
        return False, {"error": "AI review timeout"}
    except Exception as e:
        return False, {"error": f"AI review error: {e}"}


def extract_json_from_output(output: str) -> Optional[Dict]:
    """Extract JSON review data from AI output."""
    lines = output.split("\n")
    json_lines = []
    in_json = False
    brace_count = 0

    for line in lines:
        # Look for JSON start
        if "{" in line and not in_json:
            in_json = True
            json_start_idx = line.find("{")
            json_lines.append(line[json_start_idx:])
            brace_count = line[json_start_idx:].count("{") - line[
                json_start_idx:
            ].count("}")
        elif in_json:
            json_lines.append(line)
            brace_count += line.count("{") - line.count("}")

            # Check if JSON is complete
            if brace_count <= 0:
                break

    if not json_lines:
        return None

    try:
        json_str = "\n".join(json_lines)
        # Try to find the end of JSON if there's extra content
        last_brace = json_str.rfind("}")
        if last_brace > -1:
            json_str = json_str[: last_brace + 1]

        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse AI review JSON: {e}")
        # Try to extract partial JSON or fallback
        return None


def format_review_output(review_data: Dict) -> str:
    """Format review data for human-readable output."""
    if "error" in review_data:
        return f"❌ Review Error: {review_data['error']}"

    output = []

    # Overall assessment
    assessment = review_data.get("overall_assessment", "UNKNOWN")
    risk_level = review_data.get("risk_level", "UNKNOWN")
    summary = review_data.get("summary", "No summary provided")

    # Format header based on assessment
    if assessment == "APPROVE":
        output.append(f"✅ APPROVED - {summary}")
    elif assessment == "REQUEST_CHANGES":
        output.append(f"⚠️ CHANGES REQUESTED - {summary}")
    elif assessment == "BLOCK":
        output.append(f"❌ BLOCKED - {summary}")
    else:
        output.append(f"❓ {assessment} - {summary}")

    output.append(f"Risk Level: {risk_level}")
    output.append("")

    # Critical blockers
    critical_blockers = review_data.get("critical_blockers", [])
    if critical_blockers:
        output.append("🚫 CRITICAL BLOCKERS (Must Fix Before Merge):")
        for blocker in critical_blockers:
            output.append(f"  - {blocker}")
        output.append("")

    # Category scores and issues
    categories = review_data.get("categories", {})
    for category, data in categories.items():
        if not isinstance(data, dict):
            continue

        score = data.get("score", 0)
        emoji = "🔴" if score < 5 else "🟡" if score < 8 else "🟢"

        output.append(f"{emoji} {category.upper()} (Score: {score}/10)")

        # Show issues/warnings
        issues_key = "critical_issues" if category == "security" else "issues"
        issues = data.get(issues_key, [])
        violations = data.get("violations", [])
        warnings = data.get("warnings", [])
        bottlenecks = data.get("bottlenecks", [])
        technical_debt = data.get("technical_debt", [])

        all_issues = issues + violations + warnings + bottlenecks + technical_debt

        if all_issues:
            for issue in all_issues[:3]:  # Limit to top 3 issues per category
                output.append(f"  - {issue}")

        # Show top suggestions
        suggestions = data.get("suggestions", [])
        if (
            suggestions and score < 8
        ):  # Only show suggestions for categories that need improvement
            output.append(f"  💡 Suggestions:")
            for suggestion in suggestions[:2]:  # Top 2 suggestions
                output.append(f"     - {suggestion}")

        output.append("")

    # Recommendations
    recommendations = review_data.get("recommendations", [])
    if recommendations:
        output.append("💡 TOP RECOMMENDATIONS:")
        for rec in recommendations[:5]:  # Top 5 recommendations
            output.append(f"  - {rec}")
        output.append("")

    # Testing suggestions
    testing_suggestions = review_data.get("testing_suggestions", [])
    if testing_suggestions:
        output.append("🧪 TESTING SUGGESTIONS:")
        for test in testing_suggestions[:3]:  # Top 3 testing suggestions
            output.append(f"  - {test}")
        output.append("")

    # Next steps
    next_steps = review_data.get("next_steps", [])
    if next_steps:
        output.append("📋 NEXT STEPS:")
        for step in next_steps:
            output.append(f"  - {step}")

    return "\n".join(output)


def save_review_report(review_data: Dict, staged_files: List[str]) -> str:
    """Save detailed review report to file."""
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    # Generate report filename
    import datetime

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = reports_dir / f"ai-code-review-{timestamp}.json"

    # Add metadata to report
    full_report = {
        "timestamp": timestamp,
        "files_reviewed": staged_files,
        "review_data": review_data,
    }

    try:
        with open(report_file, "w") as f:
            json.dump(full_report, f, indent=2)
        return str(report_file)
    except Exception as e:
        print(f"⚠️ Could not save review report: {e}")
        return ""


def check_ai_availability() -> bool:
    """Check if AI tools are available in test context/environment."""
    try:
        # Check Codex CLI availability
        result = subprocess.run(["codex", "--version"], capture_output=True, timeout=10)
        if result.returncode != 0:
            print("❌ Codex CLI not available - return code:", result.returncode)
            print("stderr:", result.stderr.decode() if result.stderr else "No stderr")
            return False

        print("✅ Codex CLI available:", result.stdout.decode().strip())

        # Check Node.js availability (required for Codex CLI)
        node_result = subprocess.run(
            ["node", "--version"], capture_output=True, timeout=5
        )
        if node_result.returncode != 0:
            print("❌ Node.js not available (required for Codex CLI)")
            return False

        print("✅ Node.js available:", node_result.stdout.decode().strip())

        # Ensure Codex CLI is in PATH
        which_result = subprocess.run(
            ["which", "codex"], capture_output=True, timeout=5
        )
        if which_result.returncode != 0:
            print("❌ Codex CLI not found in PATH")
            return False

        print("✅ Codex CLI path:", which_result.stdout.decode().strip())

        # Check for configuration profile
        try:
            profile_result = subprocess.run(
                ["codex", "-p", "fxml4_ci", "--help"], capture_output=True, timeout=10
            )
            if profile_result.returncode == 0:
                print("✅ FXML4 CI profile available")
            else:
                print("⚠️ FXML4 CI profile not configured - using default")
        except subprocess.TimeoutExpired:
            print("⚠️ Profile check timeout - continuing with default")

        # Test basic Codex CLI functionality
        try:
            test_result = subprocess.run(
                ["codex", "--help"], capture_output=True, timeout=10
            )
            if test_result.returncode != 0:
                print("❌ Codex CLI help command failed")
                return False
            print("✅ Codex CLI basic functionality verified")
        except subprocess.TimeoutExpired:
            print("❌ Codex CLI help command timeout")
            return False

        return True

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"❌ Codex CLI not installed or not accessible: {e}")
        print("   Install with: npm install -g @openai/codex")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="AI-powered code review for staged changes"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on any issues (not just critical ones)",
    )
    parser.add_argument(
        "--save-report", action="store_true", help="Save detailed review report to file"
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=6,
        help="Minimum acceptable score for each category (1-10)",
    )
    parser.add_argument(
        "--skip-ai", action="store_true", help="Skip AI review (for testing)"
    )

    args = parser.parse_args()

    # Get staged changes
    staged_files, diff_content = get_staged_changes()

    if not staged_files:
        print("✅ No staged changes to review")
        return 0

    if not diff_content:
        print("✅ No diff content to review")
        return 0

    print(f"🤖 AI Code Reviewer - Analyzing {len(staged_files)} files")

    # Analyze changed files
    analysis = analyze_changed_files(staged_files)

    # Show what we're reviewing
    print(f"📊 Analysis:")
    print(f"  Python files: {len(analysis['python_files'])}")
    print(f"  Trading components: {len(analysis['trading_components'])}")
    print(f"  Security-sensitive: {len(analysis['security_sensitive'])}")
    print(f"  API changes: {len(analysis['api_changes'])}")

    if args.skip_ai:
        print("⏭️ Skipping AI review")
        return 0

    if not check_ai_availability():
        print("⚠️ AI not available - skipping review")
        return 0

    # Perform AI review
    print("🤖 Performing AI code review...")
    success, review_data = perform_ai_review(staged_files, diff_content, analysis)

    if not success:
        print(f"❌ AI review failed: {review_data.get('error', 'Unknown error')}")
        return 1

    # Format and display results
    review_output = format_review_output(review_data)
    print("\n" + "=" * 60)
    print("AI CODE REVIEW RESULTS")
    print("=" * 60)
    print(review_output)

    # Save detailed report if requested
    if args.save_report:
        report_file = save_review_report(review_data, staged_files)
        if report_file:
            print(f"\n📄 Detailed report saved: {report_file}")

    # Determine exit code based on review results
    assessment = review_data.get("overall_assessment", "UNKNOWN")
    critical_blockers = review_data.get("critical_blockers", [])

    if assessment == "BLOCK" or critical_blockers:
        print(f"\n❌ Review FAILED - Critical issues must be resolved")
        return 1

    if args.strict and assessment != "APPROVE":
        print(f"\n❌ Review FAILED - Strict mode enabled")
        return 1

    # Check category scores against minimum
    categories = review_data.get("categories", {})
    failed_categories = []
    for category, data in categories.items():
        if isinstance(data, dict):
            score = data.get("score", 0)
            if score < args.min_score:
                failed_categories.append(f"{category}({score})")

    if failed_categories:
        print(f"\n⚠️ Review WARNING - Low scores: {', '.join(failed_categories)}")
        if args.strict:
            return 1

    if assessment == "REQUEST_CHANGES":
        print(f"\n⚠️ Review PASSED with recommendations")
        return 0  # Don't fail, but show warnings

    print(f"\n✅ Review PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
