#!/usr/bin/env python3
"""Test script for Elliott Wave multi-agent system with RAG integration."""

import json
import os
import sys
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
    """Test the Elliott Wave multi-agent system with RAG integration."""
    print("Initializing Elliott Wave Multi-Agent System with RAG integration")
    
    try:
        # Initialize the knowledge base
        print("\nInitializing Elliott Wave Knowledge Base...")
        knowledge_base = ElliotWaveKnowledgeBase(namespace="elliott-wave-theory")
        
        # Seed the knowledge base with basic Elliott Wave knowledge if needed
        try:
            print("Seeding knowledge base with basic Elliott Wave knowledge...")
            basic_knowledge_ids = knowledge_base.seed_basic_knowledge()
            print(f"Added {len(basic_knowledge_ids)} basic knowledge entries")
        except Exception as e:
            print(f"Error seeding knowledge base: {str(e)}")
            print("Continuing with existing knowledge...")
        
        # Initialize the LLM client
        llm_client = LLMClient()
        
        # Initialize the RAG engine with the knowledge base's vector store
        rag_engine = RAGEngine(
            vector_store=knowledge_base.vector_store,
            llm_client=llm_client
        )
        
        # Create the agent coordinator
        coordinator = AgentCoordinator(
            llm_client=llm_client,
            rag_engine=rag_engine
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
        
        # Test the system with a sample query
        print("\nTesting agent system with sample query...")
        
        # Sample market data for EUR/USD
        test_data = {
            "symbol": "EURUSD",
            "timeframe": "daily",
            "pattern_type": "impulse",
            "price_summary": {
                "recent_high": 1.0850,
                "recent_low": 1.0550,
                "current_price": 1.0750,
                "trend": "upward",
            },
            # Sample wave pattern (would be detected by the wave detection algorithm)
            "patterns": [
                {
                    "type": "impulse",
                    "wave_count": 3,  # Currently in wave 3
                    "wave1_start": 1.0550,
                    "wave1_end": 1.0650,
                    "wave2_start": 1.0650,
                    "wave2_end": 1.0580,
                    "wave3_start": 1.0580,
                    "wave3_current": 1.0750,
                    "confidence": 0.75,
                    "current_price": 1.0750,
                }
            ],
        }
        
        # Step 1: Task for wave detection
        print("\nTask 1: Wave Detection")
        detect_result = coordinator.create_task(
            task_type="detect_waves",
            task_data=test_data,
            target_agent_name="WaveDetectionAgent"
        )
        
        # Step 2: Task for pattern validation
        print("\nTask 2: Pattern Validation")
        pattern = detect_result.get("detected_patterns", [])[0] if detect_result.get("detected_patterns") else {}
        
        # Format the pattern nicely for output
        print("Pattern to validate:")
        pprint(pattern)
        
        validate_result = coordinator.create_task(
            task_type="validate_pattern",
            task_data={"pattern": pattern},
            target_agent_name="WaveDetectionAgent"
        )
        
        # Check if the pattern is valid
        is_valid = validate_result.get("is_valid", False)
        print(f"Pattern validation result: {is_valid}")
        
        if is_valid:
            # Step 3: Task for entry strategy
            print("\nTask 3: Entry Strategy Generation")
            entry_result = coordinator.create_task(
                task_type="entry_strategy",
                task_data={
                    "pattern": pattern,
                    "risk_tolerance": "medium",
                },
                target_agent_name="StrategyAgent"
            )
            
            # Format the entry strategy nicely for output
            print("Entry Strategy:")
            pprint(entry_result.get("strategy", {}))
            
            # Step 4: Task for exit strategy
            print("\nTask 4: Exit Strategy Generation")
            exit_result = coordinator.create_task(
                task_type="exit_strategy",
                task_data={
                    "pattern": pattern,
                    "entry_point": entry_result.get("strategy", {}),
                },
                target_agent_name="StrategyAgent"
            )
            
            # Format the exit strategy nicely for output
            print("Exit Strategy:")
            pprint(exit_result.get("exit_strategy", {}))
            
            # Step 5: Task for risk-reward calculation
            print("\nTask 5: Risk-Reward Calculation")
            risk_reward_result = coordinator.create_task(
                task_type="risk_reward",
                task_data={
                    "entry_price": entry_result.get("strategy", {}).get("entry_price", 0),
                    "stop_loss": entry_result.get("strategy", {}).get("stop_loss", 0),
                    "take_profit": exit_result.get("exit_strategy", {}).get("take_profit", 0),
                },
                target_agent_name="StrategyAgent"
            )
            
            # Format the risk-reward result nicely for output
            print("Risk-Reward Analysis:")
            pprint({k: v for k, v in risk_reward_result.items() if k not in ["entry_price", "stop_loss", "take_profit"]})
            
            # Final recommendation
            print(f"\nFinal Recommendation: {risk_reward_result.get('recommendation', 'No recommendation')}")
            
        else:
            print("\nSkipping strategy generation due to invalid pattern")
            
        print("\nMulti-Agent System test completed successfully!")
        
    except Exception as e:
        print(f"Error in multi-agent system test: {str(e)}")


if __name__ == "__main__":
    main()