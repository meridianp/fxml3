#!/usr/bin/env python3
"""
FXML4 Claude Code Integration
Provides integration between TDD orchestrator and Claude Code agent system
"""

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class AgentTask:
    """Represents a task for a Claude Code agent"""

    agent_type: str
    description: str
    prompt: str
    files_to_read: List[str]
    files_to_write: List[str]
    context: Dict[str, Any]
    timeout: int = 300


@dataclass
class AgentResult:
    """Result from a Claude Code agent execution"""

    success: bool
    output: str
    files_modified: List[str]
    error: Optional[str] = None
    duration: float = 0.0


class ClaudeCodeIntegration:
    """Integration layer for Claude Code agents in TDD workflows"""

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path.cwd()
        self.temp_dir = Path(tempfile.mkdtemp(prefix="claude_tdd_"))

        # Agent type mapping to Claude Code agent types
        self.agent_mapping = {
            "tdd_orchestrator": "tdd-sre-pipeline-fixer",
            "test_generator": "general-purpose",
            "code_reviewer": "general-purpose",
            "security_analyzer": "general-purpose",
            "frontend_developer": "frontend-developer",
            "lead_architect": "lead-developer-architect",
        }

    def execute_agent_task(self, task: AgentTask) -> AgentResult:
        """Execute a task using Claude Code agents"""
        try:
            # Map agent type
            claude_agent = self.agent_mapping.get(task.agent_type, "general-purpose")

            # Prepare task prompt with context
            enhanced_prompt = self._enhance_prompt_with_context(task)

            # Create task file for Claude Code
            task_file = self._create_task_file(task, enhanced_prompt, claude_agent)

            # Execute Claude Code agent
            result = self._execute_claude_code_agent(
                task_file, claude_agent, task.timeout
            )

            return result

        except Exception as e:
            return AgentResult(
                success=False, output="", files_modified=[], error=str(e)
            )

    def _enhance_prompt_with_context(self, task: AgentTask) -> str:
        """Enhance the task prompt with additional context"""
        context_sections = []

        # Add project context
        context_sections.append(
            f"""
PROJECT CONTEXT:
- Project: FXML4 Financial Trading System
- Type: TDD-driven development
- Architecture: Monorepo with Python/TypeScript components
- Focus: Real-time forex trading with ML and Elliott Wave analysis
"""
        )

        # Add component context
        if "component" in task.context:
            component = task.context["component"]
            context_sections.append(
                f"""
COMPONENT CONTEXT:
- Component: {component}
- Language: {task.context.get('language', 'unknown')}
- Framework: {task.context.get('framework', 'unknown')}
- Test Framework: {task.context.get('test_framework', 'unknown')}
"""
            )

        # Add TDD context
        if "cycle_number" in task.context:
            context_sections.append(
                f"""
TDD CONTEXT:
- Cycle Number: {task.context['cycle_number']}
- Phase: {task.context.get('phase', 'unknown')}
- Objective: Follow strict Red-Green-Refactor methodology
"""
            )

        # Add file context
        if task.files_to_read:
            context_sections.append(
                f"""
FILES TO ANALYZE:
{chr(10).join(f"- {file}" for file in task.files_to_read)}
"""
            )

        # Add test results context
        if "red_results" in task.context:
            red_results = task.context["red_results"]
            context_sections.append(
                f"""
TEST RESULTS:
- Failed Tests: {red_results.get('failed', 0)}
- Passed Tests: {red_results.get('passed', 0)}
- Test Output Available: Yes
"""
            )

        # Combine context with original prompt
        full_prompt = "\n".join(context_sections) + "\n\n" + task.prompt

        # Add specific instructions based on agent type
        if task.agent_type == "tdd_orchestrator":
            full_prompt += self._get_tdd_specific_instructions()
        elif task.agent_type == "test_generator":
            full_prompt += self._get_test_generation_instructions()
        elif task.agent_type == "code_reviewer":
            full_prompt += self._get_code_review_instructions()

        return full_prompt

    def _get_tdd_specific_instructions(self) -> str:
        """Get TDD-specific instructions for the orchestrator agent"""
        return """

TDD SPECIFIC INSTRUCTIONS:
1. Follow strict Red-Green-Refactor methodology
2. Make minimal changes to pass tests (GREEN phase)
3. Do not modify tests unless explicitly in RED phase
4. Ensure all changes maintain financial system security
5. Add appropriate logging for trading operations
6. Consider real-time performance requirements
7. Maintain backward compatibility
8. Use appropriate error handling for financial operations

FINANCIAL TRADING REQUIREMENTS:
- All monetary calculations must be precise (use Decimal)
- Risk management checks are mandatory
- Audit logging is required for all trading operations
- Security must not be compromised
- Performance must be sub-second for real-time operations
"""

    def _get_test_generation_instructions(self) -> str:
        """Get test generation specific instructions"""
        return """

TEST GENERATION INSTRUCTIONS:
1. Write tests that FAIL initially (RED phase requirement)
2. Use descriptive test names that explain the behavior
3. Follow Given-When-Then structure where appropriate
4. Use appropriate pytest markers for categorization
5. Mock external dependencies (brokers, APIs, databases)
6. Test edge cases and error conditions
7. Include performance tests for trading operations
8. Add security tests for authentication/authorization

PYTEST MARKERS TO USE:
- @pytest.mark.unit (fast, isolated tests)
- @pytest.mark.integration (component integration)
- @pytest.mark.security (security-related tests)
- @pytest.mark.performance (performance benchmarks)
- @pytest.mark.trading (trading-specific functionality)
- @pytest.mark.ml (machine learning components)
"""

    def _get_code_review_instructions(self) -> str:
        """Get code review specific instructions"""
        return """

CODE REVIEW INSTRUCTIONS:
1. Ensure tests continue to pass after changes
2. Check for code duplication and suggest DRY improvements
3. Verify error handling is comprehensive
4. Check for security vulnerabilities
5. Ensure financial calculations are accurate
6. Verify logging is appropriate for audit requirements
7. Check performance implications
8. Ensure type hints are present and accurate

FINANCIAL SYSTEM CHECKS:
- Decimal precision for monetary values
- Proper exception handling for trading errors
- Secure handling of API keys and credentials
- Audit trail logging for all operations
- Input validation for all external data
"""

    def _create_task_file(
        self, task: AgentTask, enhanced_prompt: str, claude_agent: str
    ) -> Path:
        """Create a task file for Claude Code execution"""
        task_data = {
            "agent": claude_agent,
            "description": task.description,
            "prompt": enhanced_prompt,
            "files_to_read": task.files_to_read,
            "files_to_write": task.files_to_write,
            "timeout": task.timeout,
            "context": task.context,
        }

        task_file = self.temp_dir / f"task_{task.agent_type}.json"
        with open(task_file, "w") as f:
            json.dump(task_data, f, indent=2)

        return task_file

    def _execute_claude_code_agent(
        self, task_file: Path, agent_type: str, timeout: int
    ) -> AgentResult:
        """Execute Claude Code agent with the task file"""
        # This is a placeholder for actual Claude Code integration
        # In a real implementation, this would call the Claude Code API or CLI

        try:
            # Simulate Claude Code execution
            # In practice, this would be something like:
            # result = subprocess.run(['claude-code', 'agent', agent_type, str(task_file)], ...)

            # For now, return a simulated successful result
            return AgentResult(
                success=True,
                output=f"Simulated execution of {agent_type} agent",
                files_modified=[],
                duration=1.0,
            )

        except subprocess.TimeoutExpired:
            return AgentResult(
                success=False,
                output="",
                files_modified=[],
                error=f"Agent execution timed out after {timeout} seconds",
            )
        except Exception as e:
            return AgentResult(
                success=False, output="", files_modified=[], error=str(e)
            )

    def create_test_generation_task(
        self, component: str, test_category: str, context: Dict[str, Any]
    ) -> AgentTask:
        """Create a task for test generation"""
        component_path = self._get_component_path(component)

        return AgentTask(
            agent_type="test_generator",
            description=f"Generate failing {test_category} tests for {component}",
            prompt=f"""
Generate comprehensive {test_category} tests for the {component} component that will initially fail.

The tests should define the expected behavior but not yet be implemented.
Focus on {test_category} testing patterns and ensure the tests are specific and well-named.

Component Path: {component_path}
Test Category: {test_category}
            """,
            files_to_read=self._get_component_files(component),
            files_to_write=self._get_test_files(component, test_category),
            context=context,
        )

    def create_implementation_task(
        self, component: str, test_results: Dict[str, Any], context: Dict[str, Any]
    ) -> AgentTask:
        """Create a task for implementing code to make tests pass"""
        return AgentTask(
            agent_type="tdd_orchestrator",
            description=f"Implement code to make failing tests pass for {component}",
            prompt=f"""
Implement the minimal amount of code required to make the failing tests pass for the {component} component.

Current failing tests: {test_results.get('failed', 0)}
Do not over-engineer - implement just enough to make the tests pass.

Focus on:
1. Making tests pass with minimal code
2. Maintaining code quality and security
3. Following existing patterns and conventions
4. Proper error handling for financial operations
            """,
            files_to_read=self._get_component_files(component)
            + self._get_test_files(component),
            files_to_write=self._get_component_files(component),
            context=context,
        )

    def create_refactoring_task(
        self, component: str, code_changes: List[str], context: Dict[str, Any]
    ) -> AgentTask:
        """Create a task for refactoring code"""
        return AgentTask(
            agent_type="code_reviewer",
            description=f"Refactor and improve code quality for {component}",
            prompt=f"""
Refactor the code for the {component} component to improve quality while keeping all tests passing.

Recent changes: {len(code_changes)} files modified

Focus on:
1. Code readability and maintainability
2. Performance optimization for real-time trading
3. Security enhancements
4. Error handling improvements
5. Documentation and type hints
6. DRY principle application

Constraints:
- Do NOT modify any tests
- All tests must continue to pass
- Maintain backward compatibility
            """,
            files_to_read=self._get_component_files(component)
            + self._get_test_files(component),
            files_to_write=self._get_component_files(component),
            context=context,
        )

    def _get_component_path(self, component: str) -> str:
        """Get the file system path for a component"""
        component_paths = {
            "core": "core/",
            "elliott_wave": "elliott_wave/",
            "frontend": "frontend/",
        }
        return component_paths.get(component, f"{component}/")

    def _get_component_files(self, component: str) -> List[str]:
        """Get list of source files for a component"""
        component_path = Path(self.project_root) / self._get_component_path(component)

        if not component_path.exists():
            return []

        files = []

        # Get Python files
        for py_file in component_path.rglob("*.py"):
            if not str(py_file).endswith("test.py") and not "/tests/" in str(py_file):
                files.append(str(py_file.relative_to(self.project_root)))

        # Get TypeScript files for frontend
        if component == "frontend":
            for ts_file in component_path.rglob("*.ts"):
                if not ts_file.name.endswith(".test.ts") and not ts_file.name.endswith(
                    ".spec.ts"
                ):
                    files.append(str(ts_file.relative_to(self.project_root)))

            for tsx_file in component_path.rglob("*.tsx"):
                if not tsx_file.name.endswith(
                    ".test.tsx"
                ) and not tsx_file.name.endswith(".spec.tsx"):
                    files.append(str(tsx_file.relative_to(self.project_root)))

        return files[:20]  # Limit to avoid overwhelming the agent

    def _get_test_files(self, component: str, test_category: str = None) -> List[str]:
        """Get list of test files for a component"""
        component_path = Path(self.project_root) / self._get_component_path(component)

        if not component_path.exists():
            return []

        files = []

        # Get test files
        for test_file in component_path.rglob("test_*.py"):
            if not test_category or test_category in str(test_file):
                files.append(str(test_file.relative_to(self.project_root)))

        for test_file in component_path.rglob("*_test.py"):
            if not test_category or test_category in str(test_file):
                files.append(str(test_file.relative_to(self.project_root)))

        # Get TypeScript test files for frontend
        if component == "frontend":
            for test_file in component_path.rglob("*.test.ts"):
                files.append(str(test_file.relative_to(self.project_root)))

            for test_file in component_path.rglob("*.test.tsx"):
                files.append(str(test_file.relative_to(self.project_root)))

        return files

    def cleanup(self):
        """Clean up temporary files"""
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)


def main():
    """Example usage of Claude Code integration"""
    integration = ClaudeCodeIntegration()

    try:
        # Example: Create a test generation task
        task = integration.create_test_generation_task(
            component="core",
            test_category="unit",
            context={
                "component": "core",
                "language": "python",
                "framework": "fastapi",
                "test_framework": "pytest",
                "cycle_number": 1,
            },
        )

        # Execute the task
        result = integration.execute_agent_task(task)

        print(f"Task execution result:")
        print(f"Success: {result.success}")
        print(f"Output: {result.output}")
        print(f"Files modified: {result.files_modified}")
        if result.error:
            print(f"Error: {result.error}")

    finally:
        integration.cleanup()


if __name__ == "__main__":
    main()
