"""
Test Optimization Engine for FXML4 Claude TDD Framework
Advanced algorithms for test suite optimization, parallelization, and resource allocation
"""

import asyncio
import json
import logging
import multiprocessing
import pickle
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


@dataclass
class TestProfile:
    """Profile of a test including performance and dependency information"""
    test_id: str
    file_path: str
    execution_time: float
    memory_usage: float
    cpu_usage: float
    dependencies: List[str]
    coverage_areas: List[str]
    financial_domain: str
    risk_level: str
    stability_score: float  # 0-1, higher = more stable
    parallel_safe: bool


@dataclass
class OptimizationResult:
    """Result of test suite optimization"""
    original_count: int
    optimized_count: int
    estimated_time_savings: float
    redundant_tests: List[str]
    test_clusters: Dict[str, List[str]]
    parallel_groups: List[List[str]]
    execution_plan: Dict[str, Any]
    resource_allocation: Dict[str, Any]
    confidence_score: float


@dataclass
class ParallelizationPlan:
    """Plan for parallel test execution"""
    total_groups: int
    max_parallel_workers: int
    group_assignments: Dict[str, int]
    estimated_total_time: float
    resource_requirements: Dict[str, float]
    dependencies_resolved: bool


class TestOptimizer:
    """Advanced test optimization engine for financial trading systems"""

    def __init__(self, data_dir: str = None, cache_dir: str = None):
        """Initialize the test optimizer

        Args:
            data_dir: Directory containing test execution data
            cache_dir: Directory for caching optimization results
        """
        self.data_dir = Path(data_dir) if data_dir else Path.cwd() / ".claude-tdd" / "ml" / "data"
        self.cache_dir = Path(cache_dir) if cache_dir else Path.cwd() / ".claude-tdd" / "ml" / "cache"

        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Test profiles and execution history
        self.test_profiles: Dict[str, TestProfile] = {}
        self.execution_history: List[Dict[str, Any]] = []

        # Optimization parameters
        self.max_parallel_workers = multiprocessing.cpu_count()
        self.memory_limit_gb = 8.0
        self.redundancy_threshold = 0.85  # Similarity threshold for redundancy detection
        self.optimization_cache_ttl = timedelta(hours=6)

        # Financial domain weights for optimization
        self.domain_priorities = {
            "order_execution": 1.0,
            "risk_management": 0.95,
            "pnl_calculation": 0.9,
            "position_management": 0.85,
            "compliance": 0.8,
            "market_data": 0.75,
            "elliott_wave": 0.7,
            "forex": 0.7,
            "analytics": 0.6,
            "reporting": 0.5,
            "ui": 0.3,
            "general": 0.4
        }

        # Text vectorizer for similarity analysis
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )

        # Load existing data
        self._load_test_profiles()
        self._load_execution_history()

    def analyze_test_suite(self, test_list: List[str]) -> Dict[str, Any]:
        """Analyze test suite for optimization opportunities

        Args:
            test_list: List of test identifiers to analyze

        Returns:
            Analysis results with optimization recommendations
        """
        analysis = {
            "total_tests": len(test_list),
            "estimated_total_time": 0.0,
            "redundancy_candidates": [],
            "parallel_unsafe_tests": [],
            "high_resource_tests": [],
            "optimization_potential": {},
            "recommendations": []
        }

        # Collect test profiles
        profiles = []
        for test_id in test_list:
            profile = self.test_profiles.get(test_id)
            if not profile:
                profile = self._create_test_profile(test_id)
                self.test_profiles[test_id] = profile
            profiles.append(profile)

        # Calculate total execution time
        analysis["estimated_total_time"] = sum(p.execution_time for p in profiles)

        # Find redundancy candidates
        analysis["redundancy_candidates"] = self._find_redundant_tests(profiles)

        # Identify parallel-unsafe tests
        analysis["parallel_unsafe_tests"] = [
            p.test_id for p in profiles if not p.parallel_safe
        ]

        # Find high resource usage tests
        analysis["high_resource_tests"] = [
            p.test_id for p in profiles
            if p.memory_usage > 1000 or p.execution_time > 30  # MB and seconds
        ]

        # Calculate optimization potential
        analysis["optimization_potential"] = self._calculate_optimization_potential(profiles)

        # Generate recommendations
        analysis["recommendations"] = self._generate_optimization_recommendations(analysis)

        return analysis

    def optimize_test_suite(
        self,
        test_list: List[str],
        strategy: str = "comprehensive",
        constraints: Dict[str, Any] = None
    ) -> OptimizationResult:
        """Optimize test suite using specified strategy

        Args:
            test_list: List of test identifiers to optimize
            strategy: Optimization strategy (comprehensive, fast, conservative)
            constraints: Additional constraints for optimization

        Returns:
            Optimization result with execution plan
        """
        constraints = constraints or {}

        # Check cache first
        cache_key = self._generate_cache_key(test_list, strategy, constraints)
        cached_result = self._get_cached_optimization(cache_key)
        if cached_result:
            logger.info("Using cached optimization result")
            return cached_result

        logger.info(f"Optimizing test suite with {len(test_list)} tests using {strategy} strategy")

        # Get test profiles
        profiles = [
            self.test_profiles.get(test_id, self._create_test_profile(test_id))
            for test_id in test_list
        ]

        # Store profiles
        for profile in profiles:
            self.test_profiles[profile.test_id] = profile

        # Apply optimization strategy
        if strategy == "comprehensive":
            result = self._optimize_comprehensive(profiles, constraints)
        elif strategy == "fast":
            result = self._optimize_fast(profiles, constraints)
        elif strategy == "conservative":
            result = self._optimize_conservative(profiles, constraints)
        else:
            raise ValueError(f"Unknown optimization strategy: {strategy}")

        # Cache result
        self._cache_optimization_result(cache_key, result)

        # Save updated profiles
        self._save_test_profiles()

        return result

    def create_parallelization_plan(
        self,
        test_list: List[str],
        max_workers: int = None,
        memory_limit: float = None
    ) -> ParallelizationPlan:
        """Create optimized plan for parallel test execution

        Args:
            test_list: List of test identifiers
            max_workers: Maximum parallel workers (None for auto-detect)
            memory_limit: Memory limit in GB (None for default)

        Returns:
            Parallelization plan with resource allocation
        """
        max_workers = max_workers or self.max_parallel_workers
        memory_limit = memory_limit or self.memory_limit_gb

        logger.info(f"Creating parallelization plan for {len(test_list)} tests")

        # Get test profiles
        profiles = [
            self.test_profiles.get(test_id, self._create_test_profile(test_id))
            for test_id in test_list
        ]

        # Build dependency graph
        dependency_graph = self._build_dependency_graph(profiles)

        # Resolve dependencies and create execution order
        execution_order = list(nx.topological_sort(dependency_graph))

        # Group tests for parallel execution
        parallel_groups = self._create_parallel_groups(
            profiles, dependency_graph, max_workers, memory_limit
        )

        # Calculate resource requirements
        resource_requirements = self._calculate_resource_requirements(parallel_groups, profiles)

        # Estimate total execution time
        estimated_time = self._estimate_parallel_execution_time(parallel_groups, profiles)

        # Create group assignments
        group_assignments = {}
        for group_id, test_ids in enumerate(parallel_groups):
            for test_id in test_ids:
                group_assignments[test_id] = group_id

        return ParallelizationPlan(
            total_groups=len(parallel_groups),
            max_parallel_workers=max_workers,
            group_assignments=group_assignments,
            estimated_total_time=estimated_time,
            resource_requirements=resource_requirements,
            dependencies_resolved=nx.is_directed_acyclic_graph(dependency_graph)
        )

    def detect_redundant_tests(self, test_list: List[str], threshold: float = None) -> Dict[str, List[str]]:
        """Detect redundant tests based on coverage and behavior similarity

        Args:
            test_list: List of test identifiers
            threshold: Similarity threshold (0-1, higher = more similar required)

        Returns:
            Dictionary mapping primary tests to their redundant counterparts
        """
        threshold = threshold or self.redundancy_threshold

        logger.info(f"Detecting redundant tests with threshold {threshold}")

        # Get test profiles
        profiles = [
            self.test_profiles.get(test_id, self._create_test_profile(test_id))
            for test_id in test_list
        ]

        return self._find_redundant_tests(profiles, threshold)

    def optimize_resource_allocation(self, parallel_groups: List[List[str]]) -> Dict[str, Any]:
        """Optimize resource allocation for parallel test execution

        Args:
            parallel_groups: Groups of tests to run in parallel

        Returns:
            Resource allocation plan
        """
        logger.info("Optimizing resource allocation for parallel execution")

        allocation = {
            "memory_allocation": {},
            "cpu_allocation": {},
            "worker_assignment": {},
            "priority_scheduling": {},
            "resource_constraints": {}
        }

        total_memory = self.memory_limit_gb * 1024  # Convert to MB
        total_cpu_cores = self.max_parallel_workers

        for group_id, test_ids in enumerate(parallel_groups):
            group_profiles = [
                self.test_profiles.get(test_id, self._create_test_profile(test_id))
                for test_id in test_ids
            ]

            # Memory allocation
            group_memory = sum(p.memory_usage for p in group_profiles)
            allocation["memory_allocation"][f"group_{group_id}"] = {
                "total_mb": group_memory,
                "per_test": {p.test_id: p.memory_usage for p in group_profiles}
            }

            # CPU allocation
            group_cpu = sum(p.cpu_usage for p in group_profiles)
            allocation["cpu_allocation"][f"group_{group_id}"] = {
                "total_cores": min(group_cpu, total_cpu_cores),
                "per_test": {p.test_id: p.cpu_usage for p in group_profiles}
            }

            # Worker assignment based on financial priority
            priorities = [
                self.domain_priorities.get(p.financial_domain, 0.5)
                for p in group_profiles
            ]
            allocation["worker_assignment"][f"group_{group_id}"] = {
                "priority_score": np.mean(priorities),
                "recommended_workers": min(len(test_ids), total_cpu_cores)
            }

            # Priority scheduling within group
            sorted_tests = sorted(
                zip(test_ids, priorities),
                key=lambda x: x[1],
                reverse=True
            )
            allocation["priority_scheduling"][f"group_{group_id}"] = [
                test_id for test_id, _ in sorted_tests
            ]

        # Resource constraints
        allocation["resource_constraints"] = {
            "max_memory_mb": total_memory,
            "max_cpu_cores": total_cpu_cores,
            "constraint_violations": self._check_resource_constraints(allocation)
        }

        return allocation

    # Private optimization methods

    def _optimize_comprehensive(self, profiles: List[TestProfile], constraints: Dict[str, Any]) -> OptimizationResult:
        """Comprehensive optimization strategy"""
        logger.info("Applying comprehensive optimization strategy")

        original_count = len(profiles)

        # 1. Remove redundant tests
        redundant_tests = self._find_redundant_tests(profiles)
        non_redundant_profiles = self._remove_redundant_tests(profiles, redundant_tests)

        # 2. Cluster similar tests
        test_clusters = self._cluster_tests(non_redundant_profiles)

        # 3. Create parallel groups
        parallel_groups = self._create_parallel_groups_optimized(non_redundant_profiles)

        # 4. Create execution plan
        execution_plan = self._create_execution_plan(non_redundant_profiles, parallel_groups)

        # 5. Optimize resource allocation
        resource_allocation = self.optimize_resource_allocation(parallel_groups)

        # Calculate time savings
        original_time = sum(p.execution_time for p in profiles)
        optimized_time = self._estimate_optimized_execution_time(execution_plan)
        time_savings = original_time - optimized_time

        return OptimizationResult(
            original_count=original_count,
            optimized_count=len(non_redundant_profiles),
            estimated_time_savings=time_savings,
            redundant_tests=list(redundant_tests.keys()),
            test_clusters=test_clusters,
            parallel_groups=parallel_groups,
            execution_plan=execution_plan,
            resource_allocation=resource_allocation,
            confidence_score=0.85
        )

    def _optimize_fast(self, profiles: List[TestProfile], constraints: Dict[str, Any]) -> OptimizationResult:
        """Fast optimization strategy with minimal analysis"""
        logger.info("Applying fast optimization strategy")

        original_count = len(profiles)

        # Simple redundancy detection based on file paths
        redundant_tests = self._find_simple_redundancies(profiles)
        non_redundant_profiles = self._remove_redundant_tests(profiles, redundant_tests)

        # Basic parallel grouping
        parallel_groups = self._create_basic_parallel_groups(non_redundant_profiles)

        # Simple execution plan
        execution_plan = {"strategy": "fast", "groups": parallel_groups}

        # Basic resource allocation
        resource_allocation = {"strategy": "basic", "workers": min(len(parallel_groups), self.max_parallel_workers)}

        return OptimizationResult(
            original_count=original_count,
            optimized_count=len(non_redundant_profiles),
            estimated_time_savings=0.0,  # Not calculated for fast strategy
            redundant_tests=list(redundant_tests.keys()),
            test_clusters={},
            parallel_groups=parallel_groups,
            execution_plan=execution_plan,
            resource_allocation=resource_allocation,
            confidence_score=0.6
        )

    def _optimize_conservative(self, profiles: List[TestProfile], constraints: Dict[str, Any]) -> OptimizationResult:
        """Conservative optimization strategy with safety focus"""
        logger.info("Applying conservative optimization strategy")

        original_count = len(profiles)

        # Very strict redundancy detection
        redundant_tests = self._find_redundant_tests(profiles, threshold=0.95)
        non_redundant_profiles = self._remove_redundant_tests(profiles, redundant_tests)

        # Conservative parallel grouping (prioritize stability)
        parallel_groups = self._create_conservative_parallel_groups(non_redundant_profiles)

        # Safety-first execution plan
        execution_plan = self._create_conservative_execution_plan(non_redundant_profiles)

        # Conservative resource allocation
        resource_allocation = self._create_conservative_resource_allocation(parallel_groups)

        return OptimizationResult(
            original_count=original_count,
            optimized_count=len(non_redundant_profiles),
            estimated_time_savings=0.0,  # Conservative - no time savings promised
            redundant_tests=list(redundant_tests.keys()),
            test_clusters={},
            parallel_groups=parallel_groups,
            execution_plan=execution_plan,
            resource_allocation=resource_allocation,
            confidence_score=0.95
        )

    def _find_redundant_tests(self, profiles: List[TestProfile], threshold: float = None) -> Dict[str, List[str]]:
        """Find tests that are redundant based on coverage and similarity"""
        threshold = threshold or self.redundancy_threshold
        redundant_groups = {}

        if len(profiles) < 2:
            return redundant_groups

        # Create feature vectors for similarity analysis
        test_texts = []
        for profile in profiles:
            # Combine various text features for similarity comparison
            text = f"{profile.file_path} {' '.join(profile.coverage_areas)} {profile.financial_domain}"
            test_texts.append(text)

        try:
            # Fit vectorizer and compute similarity matrix
            tfidf_matrix = self.vectorizer.fit_transform(test_texts)
            similarity_matrix = cosine_similarity(tfidf_matrix)

            # Find redundant pairs
            processed = set()
            for i, profile_i in enumerate(profiles):
                if profile_i.test_id in processed:
                    continue

                redundant_list = []
                for j, profile_j in enumerate(profiles):
                    if i != j and similarity_matrix[i][j] > threshold:
                        # Additional checks for redundancy
                        if self._are_tests_redundant(profile_i, profile_j):
                            redundant_list.append(profile_j.test_id)
                            processed.add(profile_j.test_id)

                if redundant_list:
                    redundant_groups[profile_i.test_id] = redundant_list

        except Exception as e:
            logger.warning(f"Error in redundancy detection: {e}")

        logger.info(f"Found {len(redundant_groups)} groups of redundant tests")
        return redundant_groups

    def _are_tests_redundant(self, profile1: TestProfile, profile2: TestProfile) -> bool:
        """Check if two tests are truly redundant"""
        # Same file path (different test methods in same file)
        if profile1.file_path == profile2.file_path:
            return False  # Methods in same file likely test different aspects

        # Different financial domains - not redundant
        if profile1.financial_domain != profile2.financial_domain:
            return False

        # High coverage overlap
        coverage_overlap = len(
            set(profile1.coverage_areas) & set(profile2.coverage_areas)
        ) / max(len(profile1.coverage_areas), len(profile2.coverage_areas), 1)

        # Similar execution characteristics
        time_ratio = min(profile1.execution_time, profile2.execution_time) / max(
            profile1.execution_time, profile2.execution_time
        )

        return coverage_overlap > 0.8 and time_ratio > 0.7

    def _cluster_tests(self, profiles: List[TestProfile]) -> Dict[str, List[str]]:
        """Cluster tests based on similarity"""
        if len(profiles) < 3:
            return {"cluster_0": [p.test_id for p in profiles]}

        # Create feature matrix
        features = []
        for profile in profiles:
            feature_vector = [
                profile.execution_time,
                profile.memory_usage,
                profile.cpu_usage,
                self.domain_priorities.get(profile.financial_domain, 0.5),
                profile.stability_score,
                len(profile.coverage_areas),
                len(profile.dependencies)
            ]
            features.append(feature_vector)

        features_array = np.array(features)

        # Determine optimal number of clusters
        n_clusters = min(max(len(profiles) // 5, 2), 8)

        try:
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            cluster_labels = kmeans.fit_predict(features_array)

            # Group tests by cluster
            clusters = defaultdict(list)
            for i, label in enumerate(cluster_labels):
                clusters[f"cluster_{label}"].append(profiles[i].test_id)

            return dict(clusters)

        except Exception as e:
            logger.warning(f"Error in test clustering: {e}")
            return {"cluster_0": [p.test_id for p in profiles]}

    def _create_parallel_groups(
        self,
        profiles: List[TestProfile],
        dependency_graph: nx.DiGraph,
        max_workers: int,
        memory_limit: float
    ) -> List[List[str]]:
        """Create optimal parallel execution groups"""
        groups = []
        remaining_tests = set(p.test_id for p in profiles)
        current_memory = 0.0

        # Create profile lookup
        profile_map = {p.test_id: p for p in profiles}

        while remaining_tests:
            current_group = []
            group_memory = 0.0

            # Find tests that can run in parallel
            for test_id in list(remaining_tests):
                profile = profile_map[test_id]

                # Check memory constraints
                if group_memory + profile.memory_usage > memory_limit * 1024:  # Convert GB to MB
                    continue

                # Check if test can run in parallel with current group
                if self._can_run_in_parallel(test_id, current_group, dependency_graph, profile_map):
                    current_group.append(test_id)
                    group_memory += profile.memory_usage
                    remaining_tests.remove(test_id)

                # Limit group size to available workers
                if len(current_group) >= max_workers:
                    break

            # If no tests can be added, force add one to avoid infinite loop
            if not current_group and remaining_tests:
                test_id = remaining_tests.pop()
                current_group.append(test_id)

            if current_group:
                groups.append(current_group)

        return groups

    def _can_run_in_parallel(
        self,
        test_id: str,
        current_group: List[str],
        dependency_graph: nx.DiGraph,
        profile_map: Dict[str, TestProfile]
    ) -> bool:
        """Check if a test can run in parallel with current group"""
        profile = profile_map[test_id]

        # Check if test is parallel safe
        if not profile.parallel_safe:
            return len(current_group) == 0  # Can only run alone

        # Check dependencies
        for group_test in current_group:
            if dependency_graph.has_edge(test_id, group_test) or dependency_graph.has_edge(group_test, test_id):
                return False

        # Check resource conflicts (simplified)
        group_profiles = [profile_map[t] for t in current_group]
        for group_profile in group_profiles:
            # Check for conflicting coverage areas (potential conflicts)
            if len(set(profile.coverage_areas) & set(group_profile.coverage_areas)) > 0:
                # Allow if both have high stability scores
                if profile.stability_score < 0.8 or group_profile.stability_score < 0.8:
                    return False

        return True

    def _build_dependency_graph(self, profiles: List[TestProfile]) -> nx.DiGraph:
        """Build dependency graph for tests"""
        graph = nx.DiGraph()

        # Add all tests as nodes
        for profile in profiles:
            graph.add_node(profile.test_id)

        # Add dependency edges
        for profile in profiles:
            for dep in profile.dependencies:
                if any(p.test_id == dep for p in profiles):
                    graph.add_edge(dep, profile.test_id)

        return graph

    def _create_test_profile(self, test_id: str) -> TestProfile:
        """Create a test profile for analysis"""
        # In a real implementation, this would analyze the actual test
        # For now, we'll create reasonable defaults based on test name

        # Extract information from test ID
        file_path = test_id.split("::")[0] if "::" in test_id else test_id
        test_name = test_id.split("::")[-1] if "::" in test_id else test_id

        # Estimate execution time based on test type
        execution_time = 1.0  # Default 1 second
        if "integration" in test_name.lower():
            execution_time = 5.0
        elif "performance" in test_name.lower():
            execution_time = 10.0
        elif "end_to_end" in test_name.lower():
            execution_time = 15.0

        # Estimate memory usage
        memory_usage = 50.0  # Default 50MB
        if "large" in test_name.lower() or "batch" in test_name.lower():
            memory_usage = 200.0

        # Determine financial domain
        financial_domain = "general"
        for domain in self.domain_priorities.keys():
            if domain.replace("_", "") in test_name.lower() or domain.replace("_", "") in file_path.lower():
                financial_domain = domain
                break

        # Determine parallel safety
        parallel_unsafe_keywords = ["database", "file", "network", "order", "execute"]
        parallel_safe = not any(keyword in test_name.lower() for keyword in parallel_unsafe_keywords)

        return TestProfile(
            test_id=test_id,
            file_path=file_path,
            execution_time=execution_time,
            memory_usage=memory_usage,
            cpu_usage=0.5,  # Assume 50% CPU usage
            dependencies=[],  # Would be analyzed from actual test
            coverage_areas=[file_path],  # Simplified
            financial_domain=financial_domain,
            risk_level="medium",
            stability_score=0.8,  # Default stability
            parallel_safe=parallel_safe
        )

    # Helper methods for different optimization strategies

    def _find_simple_redundancies(self, profiles: List[TestProfile]) -> Dict[str, List[str]]:
        """Simple redundancy detection based on file paths"""
        file_groups = defaultdict(list)
        for profile in profiles:
            file_groups[profile.file_path].append(profile.test_id)

        redundant_groups = {}
        for file_path, test_ids in file_groups.items():
            if len(test_ids) > 3:  # If more than 3 tests in same file, some might be redundant
                # Keep first 3, mark rest as potentially redundant
                redundant_groups[test_ids[0]] = test_ids[3:]

        return redundant_groups

    def _create_basic_parallel_groups(self, profiles: List[TestProfile]) -> List[List[str]]:
        """Create basic parallel groups without complex dependency analysis"""
        groups = []
        current_group = []
        max_group_size = min(self.max_parallel_workers, 4)  # Conservative group size

        for profile in profiles:
            if profile.parallel_safe and len(current_group) < max_group_size:
                current_group.append(profile.test_id)
            else:
                if current_group:
                    groups.append(current_group)
                current_group = [profile.test_id]

        if current_group:
            groups.append(current_group)

        return groups

    def _create_conservative_parallel_groups(self, profiles: List[TestProfile]) -> List[List[str]]:
        """Create conservative parallel groups prioritizing safety"""
        groups = []

        # Group only very safe tests together
        safe_tests = [p for p in profiles if p.parallel_safe and p.stability_score > 0.9]
        unsafe_tests = [p for p in profiles if p not in safe_tests]

        # Create small groups of safe tests
        for i in range(0, len(safe_tests), 2):  # Groups of 2 for safety
            group = [p.test_id for p in safe_tests[i:i+2]]
            groups.append(group)

        # Unsafe tests run individually
        for profile in unsafe_tests:
            groups.append([profile.test_id])

        return groups

    def _create_execution_plan(self, profiles: List[TestProfile], parallel_groups: List[List[str]]) -> Dict[str, Any]:
        """Create detailed execution plan"""
        return {
            "strategy": "comprehensive",
            "total_groups": len(parallel_groups),
            "groups": parallel_groups,
            "estimated_time": self._estimate_parallel_execution_time(parallel_groups, profiles),
            "resource_requirements": self._calculate_resource_requirements(parallel_groups, profiles),
            "execution_order": self._determine_execution_order(parallel_groups, profiles)
        }

    def _create_conservative_execution_plan(self, profiles: List[TestProfile]) -> Dict[str, Any]:
        """Create conservative execution plan"""
        return {
            "strategy": "conservative",
            "sequential_execution": True,
            "test_order": [p.test_id for p in sorted(profiles, key=lambda x: self.domain_priorities.get(x.financial_domain, 0.5), reverse=True)],
            "estimated_time": sum(p.execution_time for p in profiles),
            "safety_checks": True
        }

    def _create_conservative_resource_allocation(self, parallel_groups: List[List[str]]) -> Dict[str, Any]:
        """Create conservative resource allocation"""
        return {
            "strategy": "conservative",
            "max_workers": min(self.max_parallel_workers // 2, 2),  # Use half available workers
            "memory_limit": self.memory_limit_gb * 0.7,  # Use 70% of available memory
            "safety_margin": 0.3
        }

    # Utility methods

    def _remove_redundant_tests(self, profiles: List[TestProfile], redundant_tests: Dict[str, List[str]]) -> List[TestProfile]:
        """Remove redundant tests from profiles"""
        redundant_ids = set()
        for redundant_list in redundant_tests.values():
            redundant_ids.update(redundant_list)

        return [p for p in profiles if p.test_id not in redundant_ids]

    def _create_parallel_groups_optimized(self, profiles: List[TestProfile]) -> List[List[str]]:
        """Create optimized parallel groups"""
        dependency_graph = self._build_dependency_graph(profiles)
        return self._create_parallel_groups(profiles, dependency_graph, self.max_parallel_workers, self.memory_limit_gb)

    def _estimate_parallel_execution_time(self, parallel_groups: List[List[str]], profiles: List[TestProfile]) -> float:
        """Estimate total execution time for parallel groups"""
        profile_map = {p.test_id: p for p in profiles}
        total_time = 0.0

        for group in parallel_groups:
            group_times = [profile_map[test_id].execution_time for test_id in group if test_id in profile_map]
            group_time = max(group_times) if group_times else 0.0
            total_time += group_time

        return total_time

    def _estimate_optimized_execution_time(self, execution_plan: Dict[str, Any]) -> float:
        """Estimate execution time from execution plan"""
        return execution_plan.get("estimated_time", 0.0)

    def _calculate_resource_requirements(self, parallel_groups: List[List[str]], profiles: List[TestProfile]) -> Dict[str, float]:
        """Calculate resource requirements for parallel groups"""
        profile_map = {p.test_id: p for p in profiles}

        max_memory = 0.0
        max_cpu = 0.0

        for group in parallel_groups:
            group_memory = sum(profile_map.get(test_id, TestProfile("", "", 0, 0, 0, [], [], "", "", 0, True)).memory_usage for test_id in group)
            group_cpu = sum(profile_map.get(test_id, TestProfile("", "", 0, 0, 0, [], [], "", "", 0, True)).cpu_usage for test_id in group)

            max_memory = max(max_memory, group_memory)
            max_cpu = max(max_cpu, group_cpu)

        return {
            "max_memory_mb": max_memory,
            "max_cpu_cores": max_cpu,
            "total_workers_needed": max(len(group) for group in parallel_groups) if parallel_groups else 0
        }

    def _determine_execution_order(self, parallel_groups: List[List[str]], profiles: List[TestProfile]) -> List[str]:
        """Determine optimal execution order for groups"""
        profile_map = {p.test_id: p for p in profiles}

        # Sort groups by financial priority
        group_priorities = []
        for group in parallel_groups:
            group_priority = max(
                self.domain_priorities.get(profile_map.get(test_id, TestProfile("", "", 0, 0, 0, [], [], "general", "", 0, True)).financial_domain, 0.5)
                for test_id in group
            )
            group_priorities.append((group_priority, group))

        group_priorities.sort(key=lambda x: x[0], reverse=True)

        # Flatten to execution order
        execution_order = []
        for _, group in group_priorities:
            execution_order.extend(group)

        return execution_order

    def _calculate_optimization_potential(self, profiles: List[TestProfile]) -> Dict[str, float]:
        """Calculate optimization potential metrics"""
        total_time = sum(p.execution_time for p in profiles)
        total_memory = sum(p.memory_usage for p in profiles)

        # Estimate potential savings
        parallelization_potential = min(0.7, len(profiles) / self.max_parallel_workers)
        redundancy_potential = 0.1  # Assume 10% redundancy
        optimization_potential = 0.05  # 5% from other optimizations

        time_savings = total_time * (parallelization_potential + redundancy_potential + optimization_potential)
        memory_savings = total_memory * redundancy_potential

        return {
            "potential_time_savings_seconds": time_savings,
            "potential_memory_savings_mb": memory_savings,
            "parallelization_factor": parallelization_potential,
            "redundancy_factor": redundancy_potential,
            "optimization_factor": optimization_potential
        }

    def _generate_optimization_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate optimization recommendations based on analysis"""
        recommendations = []

        if len(analysis["redundancy_candidates"]) > 0:
            recommendations.append(f"Remove {len(analysis['redundancy_candidates'])} redundant tests to save execution time")

        if len(analysis["parallel_unsafe_tests"]) > 5:
            recommendations.append("Consider refactoring parallel-unsafe tests to improve parallelization")

        if len(analysis["high_resource_tests"]) > 0:
            recommendations.append(f"Optimize {len(analysis['high_resource_tests'])} high-resource tests")

        potential = analysis["optimization_potential"]
        if potential.get("potential_time_savings_seconds", 0) > 60:
            recommendations.append(f"Potential time savings of {potential['potential_time_savings_seconds']:.1f} seconds through optimization")

        # Financial domain specific recommendations
        recommendations.append("Prioritize critical financial domain tests in execution order")
        recommendations.append("Ensure proper isolation for order execution and risk management tests")

        return recommendations

    def _check_resource_constraints(self, allocation: Dict[str, Any]) -> List[str]:
        """Check for resource constraint violations"""
        violations = []

        # Check memory constraints
        for group_id, memory_info in allocation["memory_allocation"].items():
            if memory_info["total_mb"] > self.memory_limit_gb * 1024:
                violations.append(f"{group_id}: Memory usage exceeds limit")

        # Check CPU constraints
        for group_id, cpu_info in allocation["cpu_allocation"].items():
            if cpu_info["total_cores"] > self.max_parallel_workers:
                violations.append(f"{group_id}: CPU usage exceeds available cores")

        return violations

    # Caching methods

    def _generate_cache_key(self, test_list: List[str], strategy: str, constraints: Dict[str, Any]) -> str:
        """Generate cache key for optimization result"""
        import hashlib
        content = f"{sorted(test_list)}_{strategy}_{sorted(constraints.items())}"
        return hashlib.md5(content.encode()).hexdigest()

    def _get_cached_optimization(self, cache_key: str) -> Optional[OptimizationResult]:
        """Get cached optimization result"""
        cache_file = self.cache_dir / f"{cache_key}.pkl"

        if not cache_file.exists():
            return None

        try:
            # Check if cache is still valid
            if datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime) > self.optimization_cache_ttl:
                cache_file.unlink()  # Remove expired cache
                return None

            with open(cache_file, 'rb') as f:
                return pickle.load(f)

        except Exception as e:
            logger.warning(f"Error loading cached optimization: {e}")
            return None

    def _cache_optimization_result(self, cache_key: str, result: OptimizationResult) -> None:
        """Cache optimization result"""
        cache_file = self.cache_dir / f"{cache_key}.pkl"

        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(result, f)
        except Exception as e:
            logger.warning(f"Error caching optimization result: {e}")

    # Data persistence methods

    def _load_test_profiles(self) -> None:
        """Load test profiles from persistent storage"""
        profiles_file = self.data_dir / "test_profiles.json"

        if not profiles_file.exists():
            return

        try:
            with open(profiles_file, 'r') as f:
                data = json.load(f)

            for test_id, profile_data in data.items():
                self.test_profiles[test_id] = TestProfile(**profile_data)

            logger.info(f"Loaded {len(self.test_profiles)} test profiles")

        except Exception as e:
            logger.error(f"Error loading test profiles: {e}")

    def _save_test_profiles(self) -> None:
        """Save test profiles to persistent storage"""
        profiles_file = self.data_dir / "test_profiles.json"

        try:
            data = {}
            for test_id, profile in self.test_profiles.items():
                data[test_id] = {
                    "test_id": profile.test_id,
                    "file_path": profile.file_path,
                    "execution_time": profile.execution_time,
                    "memory_usage": profile.memory_usage,
                    "cpu_usage": profile.cpu_usage,
                    "dependencies": profile.dependencies,
                    "coverage_areas": profile.coverage_areas,
                    "financial_domain": profile.financial_domain,
                    "risk_level": profile.risk_level,
                    "stability_score": profile.stability_score,
                    "parallel_safe": profile.parallel_safe
                }

            with open(profiles_file, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved {len(self.test_profiles)} test profiles")

        except Exception as e:
            logger.error(f"Error saving test profiles: {e}")

    def _load_execution_history(self) -> None:
        """Load execution history from persistent storage"""
        history_file = self.data_dir / "execution_history.json"

        if not history_file.exists():
            return

        try:
            with open(history_file, 'r') as f:
                self.execution_history = json.load(f)

            logger.info(f"Loaded {len(self.execution_history)} execution records")

        except Exception as e:
            logger.error(f"Error loading execution history: {e}")

    def get_optimization_analytics(self) -> Dict[str, Any]:
        """Get analytics about test optimization performance"""
        analytics = {
            "total_tests_profiled": len(self.test_profiles),
            "optimization_cache_size": len(list(self.cache_dir.glob("*.pkl"))),
            "average_execution_time": 0.0,
            "parallelization_efficiency": 0.0,
            "domain_distribution": {},
            "recent_optimizations": len(self.execution_history)
        }

        if self.test_profiles:
            # Calculate average execution time
            analytics["average_execution_time"] = np.mean([
                p.execution_time for p in self.test_profiles.values()
            ])

            # Calculate domain distribution
            domain_counts = defaultdict(int)
            for profile in self.test_profiles.values():
                domain_counts[profile.financial_domain] += 1

            analytics["domain_distribution"] = dict(domain_counts)

            # Calculate parallelization efficiency
            parallel_safe_count = sum(1 for p in self.test_profiles.values() if p.parallel_safe)
            analytics["parallelization_efficiency"] = parallel_safe_count / len(self.test_profiles) * 100

        return analytics