#!/usr/bin/env python3
"""Test script for market sentiment integration with agent framework."""

import os
import sys
import json
from pprint import pprint

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fxml3.llm_integration.agent_framework import (
    AgentCoordinator, WaveDetectionAgent, StrategyAgent, MarketSentimentAgent
)
from fxml3.llm_integration.knowledge_base import ElliotWaveKnowledgeBase
from fxml3.llm_integration.llm_client import LLMClient
from fxml3.llm_integration.rag import RAGEngine


def main():
    """Test the sentiment integration with agent framework."""
    print("Initializing Multi-Agent System with Sentiment Integration")
    
    try:
        # Create cache directory
        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
        os.makedirs(cache_dir, exist_ok=True)
        
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
        
        # Create and register the sentiment agent
        sentiment_agent = MarketSentimentAgent(
            name="MarketSentimentAgent",
            llm_client=llm_client,
            rag_engine=rag_engine,
            knowledge_base=knowledge_base,
            cache_dir=os.path.join(cache_dir, "sentiment")
        )
        coordinator.register_agent(sentiment_agent)
        
        # List all registered agents
        print("\nRegistered Agents:")
        agents = coordinator.list_agents()
        for agent in agents:
            print(f"- {agent['name']} ({agent['type']})")
        
        # Test 1: Sample market sentiment analysis
        print("\nTest 1: Market Sentiment Analysis")
        
        # Create test data
        symbol = "EURUSD"
        
        # Create a task for sentiment analysis
        sentiment_task = {
            "task_type": "analyze_sentiment",
            "task_data": {
                "symbol": symbol,
                "days_back": 3,
            },
            "target_agent_name": "MarketSentimentAgent",
        }
        
        # Execute the sentiment analysis task
        print(f"Analyzing sentiment for {symbol}...")
        results = coordinator.create_parallel_tasks([sentiment_task])
        sentiment_result = list(results.values())[0] if results else {}
        
        print("\nSentiment Analysis Result:")
        if sentiment_result.get("status") == "success":
            summary = sentiment_result.get("data", {}).get("sentiment_summary", {})
            pprint(summary)
        else:
            print(f"Error: {sentiment_result.get('message', 'Unknown error')}")
        
        # Test 2: Wave validation with sentiment
        print("\nTest 2: Wave Validation with Sentiment")
        
        # Create test wave pattern
        wave_pattern = {
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
        
        # First validate the wave with technical rules
        validate_task = {
            "task_type": "validate_pattern",
            "task_data": {"pattern": wave_pattern},
            "target_agent_name": "WaveDetectionAgent",
        }
        
        # Execute the validation task
        print("Validating wave pattern with technical rules...")
        results = coordinator.create_parallel_tasks([validate_task])
        validate_result = list(results.values())[0] if results else {}
        
        # Then validate with sentiment
        sentiment_validate_task = {
            "task_type": "validate_wave",
            "task_data": {
                "wave_pattern": wave_pattern,
                "symbol": symbol,
            },
            "target_agent_name": "MarketSentimentAgent",
        }
        
        # Execute the sentiment validation task
        print("Validating wave pattern with sentiment...")
        results = coordinator.create_parallel_tasks([sentiment_validate_task])
        sentiment_validate_result = list(results.values())[0] if results else {}
        
        # Extract validation results
        technical_valid = validate_result.get("is_valid", False)
        sentiment_valid = sentiment_validate_result.get("validation", {}).get("sentiment_aligned", False)
        
        # Combine validation results
        print("\nValidation Results:")
        print(f"Technical Validation: {'Valid' if technical_valid else 'Invalid'}")
        print(f"Sentiment Alignment: {'Aligned' if sentiment_valid else 'Not aligned'}")
        print(f"Overall Validation: {'Valid' if technical_valid and sentiment_valid else 'Invalid'}")
        
        if "explanation" in sentiment_validate_result.get("validation", {}):
            print(f"\nSentiment Validation Explanation:")
            print(sentiment_validate_result["validation"]["explanation"])
        
        # Test 3: Strategy generation with sentiment
        print("\nTest 3: Strategy Generation with Sentiment")
        
        # Only generate strategy if wave is valid
        if technical_valid:
            # Create entry strategy task
            entry_task = {
                "task_type": "entry_strategy",
                "task_data": {
                    "pattern": wave_pattern,
                    "risk_tolerance": "medium",
                },
                "target_agent_name": "StrategyAgent",
            }
            
            # Execute the entry strategy task
            print("Generating entry strategy...")
            results = coordinator.create_parallel_tasks([entry_task])
            entry_result = list(results.values())[0] if results else {}
            
            # Extract strategy
            strategy = entry_result.get("strategy", {})
            
            # Get current sentiment to adjust strategy
            if sentiment_valid:
                print("\nAdjusting strategy based on sentiment...")
                
                # Adjust entry price based on sentiment
                sentiment_score = sentiment_validate_result.get("sentiment_data", {}).get("data", {}).get("sentiment_summary", {}).get("weighted_score", 0)
                
                # Adjust entry price (more aggressive if strongly bullish)
                if sentiment_score > 3 and strategy.get("direction") == "long":
                    strategy["entry_price"] = strategy.get("entry_price", 0) * 1.001  # 0.1% higher
                    print("Adjusted entry price higher due to strong bullish sentiment")
                elif sentiment_score < -3 and strategy.get("direction") == "short":
                    strategy["entry_price"] = strategy.get("entry_price", 0) * 0.999  # 0.1% lower
                    print("Adjusted entry price lower due to strong bearish sentiment")
            
            # Print strategy
            print("\nFinal Trading Strategy:")
            print(f"Entry Price: {strategy.get('entry_price', 'N/A')}")
            print(f"Stop Loss: {strategy.get('stop_loss', 'N/A')}")
            print(f"Direction: {strategy.get('direction', 'N/A')}")
            print(f"Position Size: {strategy.get('position_size', 'N/A')}")
        else:
            print("Skipping strategy generation due to invalid wave pattern")
        
        print("\nSentiment integration test completed successfully!")
        
    except Exception as e:
        print(f"Error in sentiment integration test: {str(e)}")


if __name__ == "__main__":
    main()