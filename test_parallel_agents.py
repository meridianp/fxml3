#!/usr/bin/env python3
"""Test script for parallel task execution in the multi-agent system."""

import json
import os
import sys
import time
from pprint import pprint

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fxml3.llm_integration.agent_framework import (
    AgentCoordinator, WaveDetectionAgent, StrategyAgent
)
from fxml3.llm_integration.knowledge_base import ElliotWaveKnowledgeBase
from fxml3.llm_integration.llm_client import LLMClient
from fxml3.llm_integration.rag import RAGEngine


def main():
    """Test the parallel task execution in the Elliott Wave multi-agent system."""
    print("Initializing Elliott Wave Multi-Agent System with Parallel Task Execution")
    
    try:
        # Initialize the knowledge base
        print("\nInitializing Elliott Wave Knowledge Base...")
        knowledge_base = ElliotWaveKnowledgeBase(namespace="elliott-wave-theory")
        
        # Initialize the LLM client
        llm_client = LLMClient()
        
        # Initialize the RAG engine with the knowledge base's vector store
        rag_engine = RAGEngine(
            vector_store=knowledge_base.vector_store,
            llm_client=llm_client
        )
        
        # Create the agent coordinator with parallel processing
        coordinator = AgentCoordinator(
            llm_client=llm_client,
            rag_engine=rag_engine,
            max_workers=4  # Allow up to 4 concurrent tasks
        )
        
        # Create and register the wave detection agent
        wave_agent = WaveDetectionAgent(
            name="WaveDetectionAgent",
            llm_client=llm_client,
            rag_engine=rag_engine,
            knowledge_base=knowledge_base
        )
        coordinator.register_agent(wave_agent)
        
        # Create and register the strategy agent
        strategy_agent = StrategyAgent(
            name="StrategyAgent",
            llm_client=llm_client,
            rag_engine=rag_engine,
            knowledge_base=knowledge_base
        )
        coordinator.register_agent(strategy_agent)
        
        # Test 1: Run multiple pattern validations in parallel
        print("\nTest 1: Parallel Pattern Validation")
        
        # Create test patterns
        test_patterns = [
            {
                "type": "impulse",
                "wave_count": 3,
                "wave1_start": 1.0550,
                "wave1_end": 1.0650,
                "wave2_start": 1.0650,
                "wave2_end": 1.0580,
                "wave3_start": 1.0580,
                "wave3_current": 1.0750,
                "confidence": 0.75,
                "current_price": 1.0750,
            },
            {
                "type": "impulse",
                "wave_count": 5,
                "wave1_start": 0.9800,
                "wave1_end": 1.0200,
                "wave2_start": 1.0200,
                "wave2_end": 0.9900,
                "wave3_start": 0.9900,
                "wave3_end": 1.0800,
                "wave4_start": 1.0800,
                "wave4_end": 1.0500,
                "wave5_start": 1.0500,
                "wave5_current": 1.0700,
                "confidence": 0.65,
                "current_price": 1.0700,
            },
            {
                "type": "corrective",
                "wave_count": 2,
                "waveA_start": 1.1000,
                "waveA_end": 1.0700,
                "waveB_start": 1.0700,
                "waveB_current": 1.0850,
                "confidence": 0.60,
                "current_price": 1.0850,
            },
        ]
        
        # Create tasks for parallel validation
        validation_tasks = []
        for i, pattern in enumerate(test_patterns):
            validation_tasks.append({
                "task_type": "validate_pattern",
                "task_data": {"pattern": pattern},
                "target_agent_name": "WaveDetectionAgent",
            })
            
        # Measure sequential execution time for comparison
        print("\nSequential Execution:")
        start_time = time.time()
        sequential_results = []
        
        for task in validation_tasks:
            result = coordinator.create_task(
                task_type=task["task_type"],
                task_data=task["task_data"],
                target_agent_name=task["target_agent_name"]
            )
            sequential_results.append(result)
            
        sequential_time = time.time() - start_time
        print(f"Sequential execution time: {sequential_time:.2f} seconds")
        
        # Now measure parallel execution time
        print("\nParallel Execution:")
        start_time = time.time()
        
        parallel_results = coordinator.create_parallel_tasks(validation_tasks)
        
        parallel_time = time.time() - start_time
        print(f"Parallel execution time: {parallel_time:.2f} seconds")
        print(f"Speedup: {sequential_time / parallel_time:.2f}x")
        
        # Test 2: Execute the same function across multiple agents
        print("\nTest 2: Execute Same Function Across Multiple Agents")
        
        # Create test pattern for strategy generation
        test_pattern = {
            "type": "impulse",
            "wave_count": 3,
            "wave1_start": 1.0550,
            "wave1_end": 1.0650,
            "wave2_start": 1.0650,
            "wave2_end": 1.0580,
            "wave3_start": 1.0580,
            "wave3_current": 1.0750,
            "confidence": 0.85,
            "current_price": 1.0750,
        }
        
        # Create a duplicate StrategyAgent for testing
        strategy_agent2 = StrategyAgent(
            name="StrategyAgent2",
            llm_client=llm_client,
            rag_engine=rag_engine,
            knowledge_base=knowledge_base
        )
        coordinator.register_agent(strategy_agent2)
        
        # Execute the same function across multiple agents
        print("\nGenerating strategies from multiple agents:")
        multi_agent_results = coordinator.execute_agent_function(
            function_name="entry_strategy",
            function_args={
                "pattern": test_pattern,
                "risk_tolerance": "medium",
            },
            agent_names=["StrategyAgent", "StrategyAgent2"]
        )
        
        # Print results summary
        print(f"\nReceived {len(multi_agent_results)} strategy recommendations")
        for i, result in enumerate(multi_agent_results):
            strategy = result.get("strategy", {})
            print(f"\nStrategy {i+1}:")
            print(f"  Entry price: {strategy.get('entry_price', 'N/A')}")
            print(f"  Stop loss: {strategy.get('stop_loss', 'N/A')}")
            print(f"  Direction: {strategy.get('direction', 'N/A')}")
            
        # Test 3: End-to-end workflow using parallel execution
        print("\nTest 3: End-to-end Workflow with Parallel Execution")
        
        query = "Analyze EURUSD daily chart for wave 3 impulse patterns with medium risk"
        
        start_time = time.time()
        workflow_result = coordinator.run_workflow(query)
        workflow_time = time.time() - start_time
        
        print(f"Workflow execution time: {workflow_time:.2f} seconds")
        print(f"Execution mode: {workflow_result.get('execution_mode', 'sequential')}")
        
        # Print key results from the workflow
        if "error" in workflow_result:
            print(f"Workflow error: {workflow_result['error']}")
        else:
            print("\nWorkflow results:")
            print(f"Pattern valid: {workflow_result.get('pattern_validation', {}).get('is_valid', False)}")
            if workflow_result.get('pattern_validation', {}).get('is_valid', False):
                print(f"Recommendation: {workflow_result.get('recommendation', 'N/A')}")
                print(f"Risk-reward ratio: {workflow_result.get('risk_reward', {}).get('risk_reward_ratio', 'N/A')}")
            
        print("\nParallel task execution test completed successfully!")
        
    except Exception as e:
        print(f"Error in parallel task execution test: {str(e)}")


if __name__ == "__main__":
    main()