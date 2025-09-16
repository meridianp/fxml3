"""
AI-Powered Test Generator for FXML4 Claude TDD Framework
Generates intelligent test cases using LLM capabilities for financial trading systems
"""

import ast
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import openai
from anthropic import Anthropic

logger = logging.getLogger(__name__)


@dataclass
class TestCase:
    """Generated test case with metadata"""
    name: str
    code: str
    description: str
    test_type: str  # unit, integration, edge_case, financial_scenario
    complexity: int  # 1-5 scale
    financial_domain: str  # forex, risk_management, elliott_wave, etc.
    confidence: float  # 0.0-1.0 AI confidence score


@dataclass
class CodeAnalysis:
    """Analysis of code to generate tests for"""
    file_path: str
    functions: List[Dict[str, Any]]
    classes: List[Dict[str, Any]]
    imports: List[str]
    complexity_score: int
    financial_concepts: List[str]
    risk_level: str  # low, medium, high, critical


class AITestGenerator:
    """AI-powered test case generator for financial trading systems"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the AI test generator

        Args:
            config: Configuration containing API keys and model settings
        """
        self.config = config or {}
        self.openai_client = None
        self.anthropic_client = None

        # Initialize API clients if credentials available
        if "openai_api_key" in self.config:
            openai.api_key = self.config["openai_api_key"]
            self.openai_client = openai

        if "anthropic_api_key" in self.config:
            self.anthropic_client = Anthropic(api_key=self.config["anthropic_api_key"])

        # Financial domain patterns for test generation
        self.financial_patterns = {
            "forex": ["price", "pip", "spread", "currency", "exchange_rate", "forex"],
            "risk_management": ["position_size", "stop_loss", "risk", "exposure", "var"],
            "elliott_wave": ["wave", "fibonacci", "correction", "impulse", "trend"],
            "trading": ["order", "trade", "execution", "slippage", "market"],
            "pnl": ["profit", "loss", "pnl", "return", "yield", "performance"],
            "compliance": ["regulation", "limit", "threshold", "compliance", "audit"]
        }

        # Test generation templates
        self.test_templates = {
            "unit": self._get_unit_test_template(),
            "integration": self._get_integration_test_template(),
            "edge_case": self._get_edge_case_template(),
            "financial_scenario": self._get_financial_scenario_template()
        }

    def analyze_code(self, file_path: str) -> CodeAnalysis:
        """Analyze code file to understand structure and financial concepts

        Args:
            file_path: Path to Python file to analyze

        Returns:
            CodeAnalysis object with extracted information
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)

            functions = []
            classes = []
            imports = []

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append({
                        "name": node.name,
                        "args": [arg.arg for arg in node.args.args],
                        "line": node.lineno,
                        "docstring": ast.get_docstring(node) or "",
                        "complexity": self._calculate_complexity(node)
                    })
                elif isinstance(node, ast.ClassDef):
                    classes.append({
                        "name": node.name,
                        "line": node.lineno,
                        "methods": [m.name for m in node.body if isinstance(m, ast.FunctionDef)],
                        "docstring": ast.get_docstring(node) or ""
                    })
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        imports.extend([alias.name for alias in node.names])
                    else:
                        imports.append(node.module or "")

            # Identify financial concepts
            financial_concepts = self._identify_financial_concepts(content)

            # Calculate overall complexity
            complexity_score = sum(f["complexity"] for f in functions) // max(len(functions), 1)

            # Determine risk level based on financial concepts
            risk_level = self._determine_risk_level(financial_concepts, content)

            return CodeAnalysis(
                file_path=file_path,
                functions=functions,
                classes=classes,
                imports=imports,
                complexity_score=complexity_score,
                financial_concepts=financial_concepts,
                risk_level=risk_level
            )

        except Exception as e:
            logger.error(f"Error analyzing code {file_path}: {e}")
            return CodeAnalysis(
                file_path=file_path,
                functions=[],
                classes=[],
                imports=[],
                complexity_score=1,
                financial_concepts=[],
                risk_level="low"
            )

    def generate_tests(self, analysis: CodeAnalysis, test_types: List[str] = None) -> List[TestCase]:
        """Generate test cases based on code analysis

        Args:
            analysis: Code analysis results
            test_types: Types of tests to generate (unit, integration, edge_case, financial_scenario)

        Returns:
            List of generated test cases
        """
        test_types = test_types or ["unit", "integration", "edge_case", "financial_scenario"]
        generated_tests = []

        for test_type in test_types:
            if test_type == "unit":
                generated_tests.extend(self._generate_unit_tests(analysis))
            elif test_type == "integration":
                generated_tests.extend(self._generate_integration_tests(analysis))
            elif test_type == "edge_case":
                generated_tests.extend(self._generate_edge_case_tests(analysis))
            elif test_type == "financial_scenario":
                generated_tests.extend(self._generate_financial_scenario_tests(analysis))

        return generated_tests

    def _generate_unit_tests(self, analysis: CodeAnalysis) -> List[TestCase]:
        """Generate unit tests for functions and methods"""
        tests = []

        for func in analysis.functions:
            # Generate basic unit test
            test_code = self._generate_unit_test_code(func, analysis)

            tests.append(TestCase(
                name=f"test_{func['name']}_basic",
                code=test_code,
                description=f"Basic unit test for {func['name']} function",
                test_type="unit",
                complexity=func["complexity"],
                financial_domain=self._get_primary_financial_domain(analysis.financial_concepts),
                confidence=0.8
            ))

            # Generate parameter validation tests
            if func["args"]:
                validation_test = self._generate_validation_test_code(func, analysis)
                tests.append(TestCase(
                    name=f"test_{func['name']}_validation",
                    code=validation_test,
                    description=f"Parameter validation test for {func['name']}",
                    test_type="unit",
                    complexity=2,
                    financial_domain=self._get_primary_financial_domain(analysis.financial_concepts),
                    confidence=0.7
                ))

        return tests

    def _generate_integration_tests(self, analysis: CodeAnalysis) -> List[TestCase]:
        """Generate integration tests for class interactions"""
        tests = []

        if len(analysis.classes) > 1:
            # Generate class interaction tests
            for i, class1 in enumerate(analysis.classes):
                for class2 in analysis.classes[i+1:]:
                    test_code = self._generate_integration_test_code(class1, class2, analysis)

                    tests.append(TestCase(
                        name=f"test_{class1['name']}_{class2['name']}_integration",
                        code=test_code,
                        description=f"Integration test between {class1['name']} and {class2['name']}",
                        test_type="integration",
                        complexity=3,
                        financial_domain=self._get_primary_financial_domain(analysis.financial_concepts),
                        confidence=0.6
                    ))

        return tests

    def _generate_edge_case_tests(self, analysis: CodeAnalysis) -> List[TestCase]:
        """Generate edge case tests for boundary conditions"""
        tests = []

        for func in analysis.functions:
            # Financial edge cases
            edge_cases = self._identify_financial_edge_cases(func, analysis)

            for edge_case in edge_cases:
                test_code = self._generate_edge_case_test_code(func, edge_case, analysis)

                tests.append(TestCase(
                    name=f"test_{func['name']}_edge_{edge_case['name']}",
                    code=test_code,
                    description=f"Edge case test: {edge_case['description']}",
                    test_type="edge_case",
                    complexity=4,
                    financial_domain=edge_case["domain"],
                    confidence=0.7
                ))

        return tests

    def _generate_financial_scenario_tests(self, analysis: CodeAnalysis) -> List[TestCase]:
        """Generate financial scenario-based tests"""
        tests = []

        scenarios = self._get_financial_scenarios(analysis)

        for scenario in scenarios:
            test_code = self._generate_scenario_test_code(scenario, analysis)

            tests.append(TestCase(
                name=f"test_scenario_{scenario['name']}",
                code=test_code,
                description=f"Financial scenario test: {scenario['description']}",
                test_type="financial_scenario",
                complexity=5,
                financial_domain=scenario["domain"],
                confidence=0.8
            ))

        return tests

    def generate_with_llm(self, analysis: CodeAnalysis, prompt_type: str = "comprehensive") -> List[TestCase]:
        """Generate tests using LLM capabilities

        Args:
            analysis: Code analysis results
            prompt_type: Type of prompt to use (comprehensive, focused, edge_cases)

        Returns:
            List of LLM-generated test cases
        """
        if not (self.openai_client or self.anthropic_client):
            logger.warning("No LLM clients available. Falling back to template-based generation.")
            return self.generate_tests(analysis)

        prompt = self._build_llm_prompt(analysis, prompt_type)

        try:
            if self.anthropic_client:
                response = self._generate_with_anthropic(prompt)
            elif self.openai_client:
                response = self._generate_with_openai(prompt)
            else:
                return []

            return self._parse_llm_response(response, analysis)

        except Exception as e:
            logger.error(f"Error generating tests with LLM: {e}")
            return self.generate_tests(analysis)

    def _generate_with_anthropic(self, prompt: str) -> str:
        """Generate tests using Anthropic Claude"""
        response = self.anthropic_client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=4000,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    def _generate_with_openai(self, prompt: str) -> str:
        """Generate tests using OpenAI GPT"""
        response = self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000,
            temperature=0.3
        )
        return response.choices[0].message.content

    def _build_llm_prompt(self, analysis: CodeAnalysis, prompt_type: str) -> str:
        """Build LLM prompt for test generation"""
        base_prompt = f"""
Generate comprehensive test cases for a financial trading system component.

FILE: {analysis.file_path}
FUNCTIONS: {[f['name'] for f in analysis.functions]}
CLASSES: {[c['name'] for c in analysis.classes]}
FINANCIAL_CONCEPTS: {analysis.financial_concepts}
RISK_LEVEL: {analysis.risk_level}
COMPLEXITY: {analysis.complexity_score}

Requirements:
1. Generate pytest-compatible test functions
2. Include financial domain-specific test scenarios
3. Cover edge cases relevant to forex trading and risk management
4. Include proper mocking for external dependencies
5. Add comprehensive assertions for financial calculations
6. Consider precision requirements for monetary values
7. Include boundary testing for trading limits and thresholds

Focus areas for {prompt_type} testing:
"""

        if prompt_type == "comprehensive":
            base_prompt += """
- Unit tests for all public methods
- Integration tests for component interactions
- Edge cases for financial calculations
- Error handling for invalid market data
- Performance tests for real-time requirements
"""
        elif prompt_type == "focused":
            base_prompt += """
- Focus on the most critical functions
- Prioritize tests for functions with financial calculations
- Include risk management scenarios
"""
        elif prompt_type == "edge_cases":
            base_prompt += """
- Extreme market conditions (flash crashes, gaps)
- Boundary values for position sizes and prices
- Invalid input handling
- Network failures and timeout scenarios
"""

        base_prompt += f"""

Please generate test code in the following JSON format:
{{
  "tests": [
    {{
      "name": "test_function_name",
      "code": "def test_function_name():\\n    # Test implementation",
      "description": "Test description",
      "test_type": "unit|integration|edge_case|financial_scenario",
      "complexity": 1-5,
      "financial_domain": "forex|risk_management|elliott_wave|trading|pnl|compliance",
      "confidence": 0.0-1.0
    }}
  ]
}}
"""

        return base_prompt

    def _parse_llm_response(self, response: str, analysis: CodeAnalysis) -> List[TestCase]:
        """Parse LLM response into TestCase objects"""
        try:
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                logger.warning("No JSON found in LLM response")
                return []

            data = json.loads(json_match.group())
            tests = []

            for test_data in data.get("tests", []):
                tests.append(TestCase(
                    name=test_data["name"],
                    code=test_data["code"],
                    description=test_data["description"],
                    test_type=test_data["test_type"],
                    complexity=test_data["complexity"],
                    financial_domain=test_data["financial_domain"],
                    confidence=test_data["confidence"]
                ))

            return tests

        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return []

    # Helper methods for template-based generation

    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity of a function"""
        complexity = 1  # Base complexity

        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.Try, ast.With)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1

        return min(complexity, 5)  # Cap at 5

    def _identify_financial_concepts(self, content: str) -> List[str]:
        """Identify financial concepts in code"""
        concepts = []
        content_lower = content.lower()

        for domain, keywords in self.financial_patterns.items():
            if any(keyword in content_lower for keyword in keywords):
                concepts.append(domain)

        return concepts

    def _determine_risk_level(self, financial_concepts: List[str], content: str) -> str:
        """Determine risk level based on financial concepts"""
        critical_keywords = ["order", "trade", "execute", "money", "fund", "position"]
        high_risk_keywords = ["leverage", "margin", "derivative", "option"]

        content_lower = content.lower()

        if any(keyword in content_lower for keyword in critical_keywords):
            return "critical"
        elif any(keyword in content_lower for keyword in high_risk_keywords):
            return "high"
        elif len(financial_concepts) > 2:
            return "medium"
        else:
            return "low"

    def _get_primary_financial_domain(self, concepts: List[str]) -> str:
        """Get primary financial domain from concepts"""
        if not concepts:
            return "general"
        return concepts[0]  # Return first identified concept

    def _identify_financial_edge_cases(self, func: Dict[str, Any], analysis: CodeAnalysis) -> List[Dict[str, Any]]:
        """Identify financial edge cases for a function"""
        edge_cases = []

        # Common financial edge cases
        if "price" in func["name"].lower():
            edge_cases.extend([
                {"name": "zero_price", "description": "Zero price handling", "domain": "forex"},
                {"name": "negative_price", "description": "Negative price handling", "domain": "forex"},
                {"name": "extreme_price", "description": "Extreme price values", "domain": "forex"}
            ])

        if "position" in func["name"].lower():
            edge_cases.extend([
                {"name": "max_position", "description": "Maximum position size", "domain": "risk_management"},
                {"name": "zero_position", "description": "Zero position handling", "domain": "risk_management"}
            ])

        if "calculate" in func["name"].lower():
            edge_cases.extend([
                {"name": "precision", "description": "Floating point precision", "domain": "trading"},
                {"name": "overflow", "description": "Numeric overflow handling", "domain": "trading"}
            ])

        return edge_cases

    def _get_financial_scenarios(self, analysis: CodeAnalysis) -> List[Dict[str, Any]]:
        """Get relevant financial scenarios for testing"""
        scenarios = []

        if "forex" in analysis.financial_concepts:
            scenarios.extend([
                {"name": "flash_crash", "description": "Sudden market crash scenario", "domain": "forex"},
                {"name": "low_liquidity", "description": "Low liquidity market conditions", "domain": "forex"},
                {"name": "high_volatility", "description": "High volatility trading scenario", "domain": "forex"}
            ])

        if "risk_management" in analysis.financial_concepts:
            scenarios.extend([
                {"name": "margin_call", "description": "Margin call scenario", "domain": "risk_management"},
                {"name": "stop_loss_trigger", "description": "Stop loss activation", "domain": "risk_management"}
            ])

        return scenarios

    # Template methods (simplified for brevity)

    def _generate_unit_test_code(self, func: Dict[str, Any], analysis: CodeAnalysis) -> str:
        """Generate unit test code for a function"""
        return f"""def test_{func['name']}_basic():
    \"\"\"Test basic functionality of {func['name']}\"\"\"
    # TODO: Implement test for {func['name']}
    # Function args: {func['args']}
    assert True  # Replace with actual test
"""

    def _generate_validation_test_code(self, func: Dict[str, Any], analysis: CodeAnalysis) -> str:
        """Generate validation test code"""
        return f"""def test_{func['name']}_validation():
    \"\"\"Test parameter validation for {func['name']}\"\"\"
    # TODO: Test invalid parameters
    # Function args: {func['args']}
    assert True  # Replace with actual validation tests
"""

    def _generate_integration_test_code(self, class1: Dict[str, Any], class2: Dict[str, Any], analysis: CodeAnalysis) -> str:
        """Generate integration test code"""
        return f"""def test_{class1['name'].lower()}_{class2['name'].lower()}_integration():
    \"\"\"Test integration between {class1['name']} and {class2['name']}\"\"\"
    # TODO: Implement integration test
    assert True  # Replace with actual integration test
"""

    def _generate_edge_case_test_code(self, func: Dict[str, Any], edge_case: Dict[str, Any], analysis: CodeAnalysis) -> str:
        """Generate edge case test code"""
        return f"""def test_{func['name']}_edge_{edge_case['name']}():
    \"\"\"Test edge case: {edge_case['description']}\"\"\"
    # TODO: Implement edge case test for {edge_case['description']}
    assert True  # Replace with actual edge case test
"""

    def _generate_scenario_test_code(self, scenario: Dict[str, Any], analysis: CodeAnalysis) -> str:
        """Generate financial scenario test code"""
        return f"""def test_scenario_{scenario['name']}():
    \"\"\"Test financial scenario: {scenario['description']}\"\"\"
    # TODO: Implement scenario test for {scenario['description']}
    assert True  # Replace with actual scenario test
"""

    def _get_unit_test_template(self) -> str:
        """Get unit test template"""
        return """def test_{function_name}():
    \"\"\"Test {function_name} functionality\"\"\"
    # Arrange
    # Act
    # Assert
    pass
"""

    def _get_integration_test_template(self) -> str:
        """Get integration test template"""
        return """def test_{component1}_{component2}_integration():
    \"\"\"Test integration between components\"\"\"
    # Arrange
    # Act
    # Assert
    pass
"""

    def _get_edge_case_template(self) -> str:
        """Get edge case test template"""
        return """def test_{function_name}_edge_case():
    \"\"\"Test edge case for {function_name}\"\"\"
    # Test boundary conditions
    pass
"""

    def _get_financial_scenario_template(self) -> str:
        """Get financial scenario test template"""
        return """def test_financial_scenario():
    \"\"\"Test specific financial scenario\"\"\"
    # Setup market conditions
    # Execute scenario
    # Verify results
    pass
"""