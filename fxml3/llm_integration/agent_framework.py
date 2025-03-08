"""Agent-oriented framework for Elliott Wave analysis."""

import json
import time
import uuid
import threading
import concurrent.futures
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union, Callable

from fxml3.llm_integration.llm_client import LLMClient
from fxml3.llm_integration.rag import RAGEngine
from fxml3.llm_integration.knowledge_base import ElliotWaveKnowledgeBase
from fxml3.llm_integration.sentiment_analysis import SentimentAgent


class Agent(ABC):
    """Base abstract class for all agents in the system.
    
    The Agent class defines the basic interface that all agents must implement,
    including handling messages, performing tasks, and managing state.
    """
    
    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: str = "BaseAgent",
        llm_client: Optional[LLMClient] = None,
        rag_engine: Optional[RAGEngine] = None,
        knowledge_base: Optional[ElliotWaveKnowledgeBase] = None,
        description: str = "Generic agent",
        tools: Optional[List[Dict]] = None,
    ):
        """Initialize the agent.
        
        Args:
            agent_id: Unique identifier for this agent
            name: Human-readable name for this agent
            llm_client: LLM client for text generation
            rag_engine: RAG engine for knowledge retrieval
            knowledge_base: Knowledge base for Elliott Wave theory
            description: Description of the agent's purpose and capabilities
            tools: List of tools available to this agent
        """
        self.agent_id = agent_id or str(uuid.uuid4())
        self.name = name
        self.llm_client = llm_client or LLMClient()
        
        # Initialize knowledge base first, then RAG engine with the vector store
        self.knowledge_base = knowledge_base or ElliotWaveKnowledgeBase()
        
        # Pass the knowledge base's vector store to the RAG engine if not provided
        if rag_engine is None and hasattr(self.knowledge_base, 'vector_store'):
            self.rag_engine = RAGEngine(vector_store=self.knowledge_base.vector_store)
        else:
            self.rag_engine = rag_engine or RAGEngine()
            
        self.description = description
        self.tools = tools or []
        
        # Initialize agent state
        self.state = {"history": []}
        self.last_task_time = 0
        
    @abstractmethod
    def handle_task(
        self,
        task: Dict,
        context: Optional[Dict] = None,
    ) -> Dict:
        """Handle a task assigned to this agent.
        
        Args:
            task: Task description dictionary
            context: Optional context information
            
        Returns:
            Dictionary with the task result
        """
        pass
    
    def add_to_history(self, event: Dict) -> None:
        """Add an event to the agent's history.
        
        Args:
            event: Event dictionary to add
        """
        # Add timestamp if not present
        if "timestamp" not in event:
            event["timestamp"] = time.time()
            
        # Add to history
        self.state["history"].append(event)
        
        # Limit history size (last 100 events)
        if len(self.state["history"]) > 100:
            self.state["history"] = self.state["history"][-100:]
    
    def get_history(self, n: int = 10) -> List[Dict]:
        """Get the agent's recent history.
        
        Args:
            n: Number of recent history events to retrieve
            
        Returns:
            List of recent history events
        """
        return self.state["history"][-n:]
    
    def update_state(self, state_update: Dict) -> None:
        """Update the agent's state.
        
        Args:
            state_update: Dictionary with state updates
        """
        # Update state, preserving history
        history = self.state["history"]
        self.state.update(state_update)
        self.state["history"] = history
    
    def get_full_state(self) -> Dict:
        """Get the agent's full current state.
        
        Returns:
            Dictionary with the agent's current state
        """
        return self.state.copy()
    
    def to_dict(self) -> Dict:
        """Convert agent to a dictionary representation.
        
        Returns:
            Dictionary representation of the agent
        """
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "type": self.__class__.__name__,
            "tools": [tool["function"]["name"] for tool in self.tools] if self.tools else [],
        }
        

class WaveDetectionAgent(Agent):
    """Agent responsible for Elliott Wave pattern detection.
    
    This agent specializes in analyzing price data for Elliott Wave patterns
    and providing pattern identification and validation.
    """
    
    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: str = "WaveDetectionAgent",
        llm_client: Optional[LLMClient] = None,
        rag_engine: Optional[RAGEngine] = None,
        knowledge_base: Optional[ElliotWaveKnowledgeBase] = None,
    ):
        """Initialize the wave detection agent.
        
        Args:
            agent_id: Unique identifier for this agent
            name: Human-readable name for this agent
            llm_client: LLM client for text generation
            rag_engine: RAG engine for knowledge retrieval
            knowledge_base: Knowledge base for Elliott Wave theory
        """
        # Define the tools this agent can use
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "detect_elliott_waves",
                    "description": "Detect Elliott Wave patterns in price data",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "price_data": {
                                "type": "object",
                                "description": "Price data to analyze",
                            },
                            "timeframe": {
                                "type": "string",
                                "description": "Timeframe of the data",
                            },
                        },
                        "required": ["price_data"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "validate_wave_pattern",
                    "description": "Validate an Elliott Wave pattern",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "object",
                                "description": "Wave pattern to validate",
                            },
                            "rules": {
                                "type": "array",
                                "description": "Rules to validate against",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["pattern"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "predict_next_move",
                    "description": "Predict the next price movement based on the wave pattern",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "object",
                                "description": "Current wave pattern",
                            },
                            "confidence_threshold": {
                                "type": "number",
                                "description": "Minimum confidence level (0.0-1.0)",
                            },
                        },
                        "required": ["pattern"],
                    },
                },
            },
        ]
        
        # Initialize base class
        super().__init__(
            agent_id=agent_id,
            name=name,
            llm_client=llm_client,
            rag_engine=rag_engine,
            knowledge_base=knowledge_base,
            description="Detects and validates Elliott Wave patterns in price data",
            tools=tools,
        )
        
    def handle_task(
        self,
        task: Dict,
        context: Optional[Dict] = None,
    ) -> Dict:
        """Handle a task assigned to this agent.
        
        Args:
            task: Task description dictionary
            context: Optional context information
            
        Returns:
            Dictionary with the task result
        """
        # Extract task details
        task_type = task.get("type", "")
        task_data = task.get("data", {})
        
        # Log the task
        self.add_to_history({
            "event": "task_received",
            "task_type": task_type,
            "task_id": task.get("task_id", str(uuid.uuid4())),
        })
        
        # Handle different task types
        if task_type == "detect_waves":
            result = self._handle_detect_waves(task_data, context)
        elif task_type == "validate_pattern":
            result = self._handle_validate_pattern(task_data, context)
        elif task_type == "predict_movement":
            result = self._handle_predict_movement(task_data, context)
        else:
            result = {"error": f"Unknown task type: {task_type}"}
            
        # Log the result
        self.add_to_history({
            "event": "task_completed",
            "task_type": task_type,
            "task_id": task.get("task_id", ""),
            "result_summary": "success" if "error" not in result else "error",
        })
            
        return result
    
    def _handle_detect_waves(
        self,
        task_data: Dict,
        context: Optional[Dict] = None,
    ) -> Dict:
        """Handle a wave detection task.
        
        Args:
            task_data: Task data with price information
            context: Optional context information
            
        Returns:
            Dictionary with detected wave patterns
        """
        # In a real implementation, this would use the wave analysis module
        # For now, we'll simulate this with a placeholder
        
        # Gather knowledge from different categories for comprehensive analysis
        impulse_knowledge = self.knowledge_base.query_knowledge_base(
            "Elliott Wave impulse pattern identification and characteristics",
            category="impulse",
            k=2
        )
        
        corrective_knowledge = self.knowledge_base.query_knowledge_base(
            "Elliott Wave corrective pattern identification",
            category="corrective",
            k=2
        )
        
        validation_knowledge = self.knowledge_base.query_knowledge_base(
            "Elliott Wave pattern validation rules",
            category="validation",
            k=2
        )
        
        # Combine knowledge from different categories
        combined_knowledge = []
        combined_knowledge.extend(impulse_knowledge)
        combined_knowledge.extend(corrective_knowledge)
        combined_knowledge.extend(validation_knowledge)
        
        # Extract text from knowledge
        context_docs = "\n\n".join([doc["text"] for doc in combined_knowledge])
        
        # Create a prompt for LLM-based wave detection with comprehensive context
        prompt = (
            f"Based on Elliott Wave theory and the provided price data, "
            f"identify potential wave patterns. Use these Elliott Wave principles:\n\n"
            f"{context_docs}\n\n"
            f"Price data: {json.dumps(task_data.get('price_summary', {}))}\n\n"
            f"1. Analyze the market structure for impulse and corrective waves\n"
            f"2. Identify the wave count based on Elliott Wave rules\n"
            f"3. Validate the pattern using Fibonacci relationships\n"
            f"4. Assess the confidence level of your analysis\n"
            f"5. Provide a detailed explanation of your reasoning"
        )
        
        # Generate LLM analysis to supplement automated detection
        llm_analysis = self.llm_client.generate_text(
            prompt=prompt,
            system_prompt="You are an expert in Elliott Wave analysis with 20+ years of experience. Provide detailed and accurate wave pattern identification.",
            temperature=0.3,
        )
        
        # Return the result with both automated and LLM analysis
        return {
            "detected_patterns": task_data.get("patterns", []),
            "llm_analysis": llm_analysis,
            "knowledge_sources": [
                {"category": doc.get("metadata", {}).get("category", "unknown"),
                 "source": doc.get("metadata", {}).get("source", "unknown")}
                for doc in combined_knowledge
            ],
        }
    
    def _handle_validate_pattern(
        self,
        task_data: Dict,
        context: Optional[Dict] = None,
    ) -> Dict:
        """Handle a pattern validation task.
        
        Args:
            task_data: Task data with pattern information
            context: Optional context information
            
        Returns:
            Dictionary with validation results
        """
        # Extract pattern to validate
        pattern = task_data.get("pattern", {})
        
        # In a real implementation, this would use the wave analysis module
        # For now, we'll simulate this with a placeholder
        
        # Get validation rules from knowledge base
        validation_rules = self.knowledge_base.query_knowledge_base(
            "Elliott Wave pattern validation rules",
            category="validation",
            k=3
        )
        
        # Get Fibonacci relationships
        fibonacci_knowledge = self.knowledge_base.query_knowledge_base(
            "Fibonacci relationships in Elliott Wave patterns",
            category="fibonacci",
            k=2
        )
        
        # Combine knowledge
        combined_knowledge = []
        combined_knowledge.extend(validation_rules)
        combined_knowledge.extend(fibonacci_knowledge)
        
        # Extract text from knowledge
        context_docs = "\n\n".join([doc["text"] for doc in combined_knowledge])
        
        # Create a detailed prompt for LLM-based wave validation
        prompt = (
            f"Validate this Elliott Wave pattern against standard rules and Fibonacci relationships:\n\n"
            f"Pattern: {json.dumps(pattern)}\n\n"
            f"Elliott Wave Rules and Fibonacci Relationships:\n{context_docs}\n\n"
            f"Validation steps:\n"
            f"1. Check if Wave 2 retraces less than 100% of Wave 1\n"
            f"2. Verify Wave 3 is not the shortest of the three impulse waves\n"
            f"3. Confirm Wave 4 does not overlap with Wave 1's price territory\n"
            f"4. Analyze Fibonacci relationships between the waves\n"
            f"5. Assess the adherence to alternation principle\n"
            f"6. Determine overall validity with confidence level\n\n"
            f"Present your conclusion clearly stating if the pattern is valid or not."
        )
            
        # Generate LLM validation with more detailed system prompt
        llm_validation = self.llm_client.generate_text(
            prompt=prompt,
            system_prompt=(
                "You are a world-class expert in Elliott Wave analysis with decades of experience. "
                "Your role is to rigorously validate Elliott Wave patterns against established rules. "
                "Be precise and thorough in your assessment, providing clear reasoning for your conclusion. "
                "Your analysis will determine if a real trading decision should be made."
            ),
            temperature=0.2,
        )
        
        # Determine validity from the LLM response
        is_valid = (
            "valid" in llm_validation.lower() and 
            "not valid" not in llm_validation.lower() and
            "invalid" not in llm_validation.lower()
        )
        
        # Return an enhanced result
        return {
            "pattern": pattern,
            "is_valid": is_valid,
            "validation_details": llm_validation,
            "knowledge_sources": [
                {"category": doc.get("metadata", {}).get("category", "unknown"),
                 "source": doc.get("metadata", {}).get("source", "unknown")}
                for doc in combined_knowledge
            ],
            "confidence": 0.8,  # This would be dynamically determined in a real implementation
        }
        
    def _handle_predict_movement(
        self,
        task_data: Dict,
        context: Optional[Dict] = None,
    ) -> Dict:
        """Handle a movement prediction task.
        
        Args:
            task_data: Task data with pattern information
            context: Optional context information
            
        Returns:
            Dictionary with prediction results
        """
        # Extract pattern for prediction
        pattern = task_data.get("pattern", {})
        
        # Get trading knowledge from knowledge base
        trading_knowledge = self.knowledge_base.query_knowledge_base(
            "Elliott Wave trading strategies and price targets",
            category="trading",
            k=2
        )
        
        # Get prediction techniques from fibonacci relationships
        fibonacci_knowledge = self.knowledge_base.query_knowledge_base(
            "Fibonacci projections and extensions for price targets",
            category="fibonacci",
            k=2
        )
        
        # Get psychological aspects of wave movements
        psychology_knowledge = self.knowledge_base.query_knowledge_base(
            "Market psychology in Elliott Wave movements",
            category="psychology",
            k=1
        )
        
        # Combine all knowledge
        combined_knowledge = []
        combined_knowledge.extend(trading_knowledge)
        combined_knowledge.extend(fibonacci_knowledge)
        combined_knowledge.extend(psychology_knowledge)
        
        # Extract text from knowledge
        context_docs = "\n\n".join([doc["text"] for doc in combined_knowledge])
        
        # Create a comprehensive prompt for LLM-based prediction
        prompt = (
            f"Based on this Elliott Wave pattern, predict the next likely price movement:\n\n"
            f"Pattern: {json.dumps(pattern)}\n\n"
            f"Elliott Wave Knowledge for Price Prediction:\n{context_docs}\n\n"
            f"Prediction steps:\n"
            f"1. Identify the current wave position in the Elliott Wave sequence\n"
            f"2. Calculate potential price targets using Fibonacci projections\n"
            f"3. Assess market psychology at this stage of the pattern\n"
            f"4. Determine the most likely direction and magnitude of the next move\n"
            f"5. Provide alternative scenarios with probabilities\n"
            f"6. Specify exact price targets for different timeframes\n\n"
            f"Format your prediction with clear price targets, direction, and confidence level."
        )
            
        # Generate LLM prediction with enhanced system prompt
        llm_prediction = self.llm_client.generate_text(
            prompt=prompt,
            system_prompt=(
                "You are a renowned Elliott Wave forecaster with a track record of accurate predictions. "
                "Your expertise combines technical analysis, Fibonacci measurements, and market psychology. "
                "Provide precise, actionable price predictions with specific targets and timeframes. "
                "Your forecast will be used for actual trading decisions, so be thorough and exact."
            ),
            temperature=0.3,
        )
        
        # Parse prediction from LLM output (in a real implementation, this would be more robust)
        # For now, we'll use placeholder values and the full LLM output
        
        # Return the enhanced result
        return {
            "pattern": pattern,
            "prediction": {
                "direction": "up",  # This would be extracted from LLM output
                "target_price": pattern.get("wave3_current", 100.0) * 1.1,  # Placeholder calculation
                "confidence": 0.85,  # This would be extracted from LLM output
                "timeframe": "short-term",  # This would be extracted from LLM output
            },
            "alternatives": [
                {
                    "scenario": "consolidation",
                    "probability": 0.15,
                    "description": "Price consolidates in a narrow range before continuing the main trend"
                }
            ],
            "prediction_details": llm_prediction,
            "knowledge_sources": [
                {"category": doc.get("metadata", {}).get("category", "unknown"),
                 "source": doc.get("metadata", {}).get("source", "unknown")}
                for doc in combined_knowledge
            ],
        }


class MarketSentimentAgent(Agent):
    """Agent responsible for market sentiment analysis.
    
    This agent specializes in gathering news and analyzing sentiment
    to provide additional context for Elliott Wave patterns.
    """
    
    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: str = "MarketSentimentAgent",
        llm_client: Optional[LLMClient] = None,
        rag_engine: Optional[RAGEngine] = None,
        knowledge_base: Optional[ElliotWaveKnowledgeBase] = None,
        cache_dir: Optional[str] = None,
        use_yahoo: bool = True,
        use_ibkr: bool = False,
    ):
        """Initialize the market sentiment agent.
        
        Args:
            agent_id: Unique identifier for this agent
            name: Human-readable name for this agent
            llm_client: LLM client for text generation
            rag_engine: RAG engine for knowledge retrieval
            knowledge_base: Knowledge base for Elliott Wave theory
            cache_dir: Directory to cache sentiment data
            use_yahoo: Whether to use Yahoo Finance API
            use_ibkr: Whether to use Interactive Brokers API
        """
        # Define the tools this agent can use
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "analyze_market_sentiment",
                    "description": "Analyze market sentiment for a currency pair",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Symbol or currency pair (e.g., 'EURUSD')",
                            },
                            "days_back": {
                                "type": "integer",
                                "description": "Number of days to look back",
                            },
                            "timeframe": {
                                "type": "string",
                                "description": "Timeframe for aggregation (hourly, daily, weekly)",
                            },
                        },
                        "required": ["symbol"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "validate_wave_with_sentiment",
                    "description": "Validate a wave pattern using sentiment analysis",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "wave_pattern": {
                                "type": "object",
                                "description": "Wave pattern to validate",
                            },
                            "symbol": {
                                "type": "string",
                                "description": "Symbol or currency pair",
                            },
                            "days_back": {
                                "type": "integer",
                                "description": "Number of days to look back",
                            },
                        },
                        "required": ["wave_pattern", "symbol"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_sentiment_for_period",
                    "description": "Get sentiment for a specific time period",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Symbol or currency pair",
                            },
                            "start_date": {
                                "type": "string",
                                "description": "Start date (ISO format)",
                            },
                            "end_date": {
                                "type": "string",
                                "description": "End date (ISO format)",
                            },
                        },
                        "required": ["symbol", "start_date"],
                    },
                },
            },
        ]
        
        # Initialize base class
        super().__init__(
            agent_id=agent_id,
            name=name,
            llm_client=llm_client,
            rag_engine=rag_engine,
            knowledge_base=knowledge_base,
            description="Analyzes market sentiment from news and social media",
            tools=tools,
        )
        
        # Initialize sentiment agent
        self.sentiment_agent = SentimentAgent(
            cache_dir=cache_dir,
            use_yahoo=use_yahoo,
            use_ibkr=use_ibkr,
            llm_client=llm_client,
        )
        
    def handle_task(
        self,
        task: Dict,
        context: Optional[Dict] = None,
    ) -> Dict:
        """Handle a task assigned to this agent.
        
        Args:
            task: Task description dictionary
            context: Optional context information
            
        Returns:
            Dictionary with the task result
        """
        # Extract task details
        task_type = task.get("type", "")
        task_data = task.get("data", {})
        
        # Log the task
        self.add_to_history({
            "event": "task_received",
            "task_type": task_type,
            "task_id": task.get("task_id", str(uuid.uuid4())),
        })
        
        # Handle different task types
        if task_type == "analyze_sentiment":
            result = self._handle_analyze_sentiment(task_data, context)
        elif task_type == "validate_wave":
            result = self._handle_validate_wave(task_data, context)
        elif task_type == "sentiment_period":
            result = self._handle_sentiment_period(task_data, context)
        else:
            result = {"error": f"Unknown task type: {task_type}"}
            
        # Log the result
        self.add_to_history({
            "event": "task_completed",
            "task_type": task_type,
            "task_id": task.get("task_id", ""),
            "result_summary": "success" if "error" not in result else "error",
        })
            
        return result
    
    def _handle_analyze_sentiment(
        self,
        task_data: Dict,
        context: Optional[Dict] = None,
    ) -> Dict:
        """Handle market sentiment analysis task.
        
        Args:
            task_data: Task data with symbol and time parameters
            context: Optional context information
            
        Returns:
            Dictionary with sentiment analysis results
        """
        # Extract parameters
        symbol = task_data.get("symbol", "")
        days_back = task_data.get("days_back", 7)
        timeframe = task_data.get("timeframe", "daily")
        
        # Validate parameters
        if not symbol:
            return {"error": "Symbol is required"}
            
        # Get market sentiment
        try:
            sentiment_data = self.sentiment_agent.get_market_sentiment(
                symbol=symbol,
                days_back=days_back,
                timeframe=timeframe,
            )
            
            return sentiment_data
        except Exception as e:
            return {"error": f"Error analyzing market sentiment: {str(e)}"}
    
    def _handle_validate_wave(
        self,
        task_data: Dict,
        context: Optional[Dict] = None,
    ) -> Dict:
        """Handle wave validation with sentiment task.
        
        Args:
            task_data: Task data with wave pattern and symbol
            context: Optional context information
            
        Returns:
            Dictionary with validation results
        """
        # Extract parameters
        wave_pattern = task_data.get("wave_pattern", {})
        symbol = task_data.get("symbol", "")
        days_back = task_data.get("days_back", 7)
        
        # Validate parameters
        if not wave_pattern:
            return {"error": "Wave pattern is required"}
            
        if not symbol:
            return {"error": "Symbol is required"}
            
        # Validate wave with sentiment
        try:
            validation = self.sentiment_agent.validate_wave(
                wave_pattern=wave_pattern,
                symbol=symbol,
                days_back=days_back,
            )
            
            return validation
        except Exception as e:
            return {"error": f"Error validating wave with sentiment: {str(e)}"}
    
    def _handle_sentiment_period(
        self,
        task_data: Dict,
        context: Optional[Dict] = None,
    ) -> Dict:
        """Handle sentiment for specific period task.
        
        Args:
            task_data: Task data with symbol and period
            context: Optional context information
            
        Returns:
            Dictionary with sentiment analysis results
        """
        # Extract parameters
        symbol = task_data.get("symbol", "")
        start_date = task_data.get("start_date", "")
        end_date = task_data.get("end_date")
        
        # Validate parameters
        if not symbol:
            return {"error": "Symbol is required"}
            
        if not start_date:
            return {"error": "Start date is required"}
            
        # Get sentiment for period
        try:
            sentiment_data = self.sentiment_agent.get_sentiment_for_period(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
            )
            
            return sentiment_data
        except Exception as e:
            return {"error": f"Error getting sentiment for period: {str(e)}"}


class StrategyAgent(Agent):
    """Agent responsible for developing trading strategies.
    
    This agent specializes in translating wave patterns into actionable
    trading strategies with entry, exit, and risk management rules.
    """
    
    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: str = "StrategyAgent",
        llm_client: Optional[LLMClient] = None,
        rag_engine: Optional[RAGEngine] = None,
        knowledge_base: Optional[ElliotWaveKnowledgeBase] = None,
    ):
        """Initialize the strategy agent.
        
        Args:
            agent_id: Unique identifier for this agent
            name: Human-readable name for this agent
            llm_client: LLM client for text generation
            rag_engine: RAG engine for knowledge retrieval
            knowledge_base: Knowledge base for Elliott Wave theory
        """
        # Define the tools this agent can use
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "generate_entry_strategy",
                    "description": "Generate entry strategy based on wave pattern",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "object",
                                "description": "Current wave pattern",
                            },
                            "risk_tolerance": {
                                "type": "string",
                                "description": "Risk tolerance (low, medium, high)",
                            },
                        },
                        "required": ["pattern"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_exit_strategy",
                    "description": "Generate exit strategy based on wave pattern",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {
                                "type": "object",
                                "description": "Current wave pattern",
                            },
                            "entry_point": {
                                "type": "object",
                                "description": "Entry point information",
                            },
                        },
                        "required": ["pattern", "entry_point"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calculate_risk_reward",
                    "description": "Calculate risk-reward ratio for a trade",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entry_price": {
                                "type": "number",
                                "description": "Entry price",
                            },
                            "stop_loss": {
                                "type": "number",
                                "description": "Stop loss price",
                            },
                            "take_profit": {
                                "type": "number",
                                "description": "Take profit price",
                            },
                        },
                        "required": ["entry_price", "stop_loss", "take_profit"],
                    },
                },
            },
        ]
        
        # Initialize base class
        super().__init__(
            agent_id=agent_id,
            name=name,
            llm_client=llm_client,
            rag_engine=rag_engine,
            knowledge_base=knowledge_base,
            description="Develops trading strategies based on Elliott Wave patterns",
            tools=tools,
        )
        
    def handle_task(
        self,
        task: Dict,
        context: Optional[Dict] = None,
    ) -> Dict:
        """Handle a task assigned to this agent.
        
        Args:
            task: Task description dictionary
            context: Optional context information
            
        Returns:
            Dictionary with the task result
        """
        # Extract task details
        task_type = task.get("type", "")
        task_data = task.get("data", {})
        
        # Log the task
        self.add_to_history({
            "event": "task_received",
            "task_type": task_type,
            "task_id": task.get("task_id", str(uuid.uuid4())),
        })
        
        # Handle different task types
        if task_type == "entry_strategy":
            result = self._handle_entry_strategy(task_data, context)
        elif task_type == "exit_strategy":
            result = self._handle_exit_strategy(task_data, context)
        elif task_type == "risk_reward":
            result = self._handle_risk_reward(task_data, context)
        else:
            result = {"error": f"Unknown task type: {task_type}"}
            
        # Log the result
        self.add_to_history({
            "event": "task_completed",
            "task_type": task_type,
            "task_id": task.get("task_id", ""),
            "result_summary": "success" if "error" not in result else "error",
        })
            
        return result
    
    def _handle_entry_strategy(
        self,
        task_data: Dict,
        context: Optional[Dict] = None,
    ) -> Dict:
        """Handle an entry strategy generation task.
        
        Args:
            task_data: Task data with pattern information
            context: Optional context information
            
        Returns:
            Dictionary with entry strategy
        """
        # Extract pattern and risk tolerance
        pattern = task_data.get("pattern", {})
        risk_tolerance = task_data.get("risk_tolerance", "medium")
        
        # Get trading strategy knowledge from knowledge base
        trading_knowledge = self.knowledge_base.query_knowledge_base(
            "Elliott Wave entry strategies for different wave patterns",
            category="trading",
            k=3
        )
        
        # Get risk management knowledge
        risk_knowledge = self.knowledge_base.query_knowledge_base(
            "Stop loss placement in Elliott Wave trading",
            category="trading",
            k=1
        )
        
        # Get wave validation knowledge to confirm entry points
        validation_knowledge = self.knowledge_base.query_knowledge_base(
            "Elliott Wave pattern confirmation signals",
            category="validation",
            k=1
        )
        
        # Combine all knowledge
        combined_knowledge = []
        combined_knowledge.extend(trading_knowledge)
        combined_knowledge.extend(risk_knowledge)
        combined_knowledge.extend(validation_knowledge)
        
        # Extract text from knowledge
        context_docs = "\n\n".join([doc["text"] for doc in combined_knowledge])
        
        # Create a comprehensive prompt for LLM-based entry strategy generation
        prompt = (
            f"Generate a detailed entry strategy for trading based on this Elliott Wave pattern:\n\n"
            f"Pattern: {json.dumps(pattern)}\n"
            f"Risk Tolerance: {risk_tolerance}\n\n"
            f"Elliott Wave Knowledge for Entry Strategy:\n{context_docs}\n\n"
            f"Strategy development steps:\n"
            f"1. Identify the current wave position and determine optimal entry points\n"
            f"2. Specify precise entry price levels (exact numbers, not ranges)\n"
            f"3. Calculate appropriate stop loss levels based on risk tolerance\n"
            f"4. Determine position sizing appropriate for the risk profile\n"
            f"5. List confirmation signals to validate the entry\n"
            f"6. Provide entry execution instructions (limit order, market order, etc.)\n\n"
            f"Your strategy must include specific price levels, stop loss placement, and clear entry criteria."
        )
        
        # Generate LLM strategy with enhanced system prompt
        llm_strategy = self.llm_client.generate_text(
            prompt=prompt,
            system_prompt=(
                "You are a professional hedge fund trader specializing in Elliott Wave strategies. "
                "You create precise, actionable trading plans with specific entry points, stop loss levels, "
                "and execution instructions. Your strategies are used by professional traders to enter positions "
                "with clear risk management rules. Be exact with price levels and entry criteria."
            ),
            temperature=0.2,
        )
        
        # Parse the strategy into a structured format
        # In a real implementation, this would use more advanced parsing
        entry_price = pattern.get("current_price", 100.0)
        
        # Adjust stop loss based on risk tolerance
        stop_loss_percentages = {
            "low": 0.005,  # 0.5% for low risk tolerance
            "medium": 0.02,  # 2% for medium risk tolerance
            "high": 0.05    # 5% for high risk tolerance
        }
        stop_loss_pct = stop_loss_percentages.get(risk_tolerance, 0.02)
        
        # Calculate stop loss price based on direction and risk tolerance
        direction = "long"  # This would be determined from pattern analysis
        if direction == "long":
            stop_loss = entry_price * (1 - stop_loss_pct)
        else:
            stop_loss = entry_price * (1 + stop_loss_pct)
        
        # Calculate position size based on risk tolerance (in a real implementation)
        account_size = 10000  # Placeholder value
        risk_per_trade = {
            "low": 0.01,     # 1% of account per trade
            "medium": 0.02,  # 2% of account per trade
            "high": 0.05     # 5% of account per trade
        }
        
        risk_amount = account_size * risk_per_trade.get(risk_tolerance, 0.02)
        risk_per_unit = abs(entry_price - stop_loss)
        position_size = risk_amount / risk_per_unit if risk_per_unit > 0 else 0
        
        # Return enhanced result
        return {
            "pattern": pattern,
            "strategy": {
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "direction": direction,
                "risk_tolerance": risk_tolerance,
                "position_size": position_size,
                "account_risk_percentage": risk_per_trade.get(risk_tolerance, 0.02) * 100,
                "entry_type": "limit",  # This would be extracted from LLM output
            },
            "strategy_details": llm_strategy,
            "knowledge_sources": [
                {"category": doc.get("metadata", {}).get("category", "unknown"),
                 "source": doc.get("metadata", {}).get("source", "unknown")}
                for doc in combined_knowledge
            ],
        }
    
    def _handle_exit_strategy(
        self,
        task_data: Dict,
        context: Optional[Dict] = None,
    ) -> Dict:
        """Handle an exit strategy generation task.
        
        Args:
            task_data: Task data with pattern and entry information
            context: Optional context information
            
        Returns:
            Dictionary with exit strategy
        """
        # Extract information
        pattern = task_data.get("pattern", {})
        entry_point = task_data.get("entry_point", {})
        
        # Use the RAG engine to get exit strategy knowledge
        exit_knowledge = self.rag_engine.query(
            "Elliott Wave exit strategies and profit targets",
            filter={"category": "trading"},
            return_source_documents=True,
        )
        
        # Create a prompt for LLM-based exit strategy generation
        if isinstance(exit_knowledge, dict):
            context_docs = "\n\n".join([doc["text"] for doc in exit_knowledge["source_documents"]])
            prompt = (
                f"Generate an exit strategy based on this Elliott Wave pattern and entry point:\n\n"
                f"Pattern: {json.dumps(pattern)}\n"
                f"Entry Point: {json.dumps(entry_point)}\n\n"
                f"Exit strategies:\n{context_docs}\n\n"
                f"Provide a detailed exit strategy with take profit levels, trailing stop conditions, and rationale."
            )
        else:
            prompt = (
                f"Generate an exit strategy based on this Elliott Wave pattern and entry point:\n\n"
                f"Pattern: {json.dumps(pattern)}\n"
                f"Entry Point: {json.dumps(entry_point)}\n\n"
                f"Provide a detailed exit strategy with take profit levels, trailing stop conditions, and rationale."
            )
            
        # Generate LLM exit strategy
        llm_strategy = self.llm_client.generate_text(
            prompt=prompt,
            system_prompt="You are an expert trading strategist specializing in Elliott Wave trading. Create practical, actionable exit strategies.",
            temperature=0.3,
        )
        
        # Parse the strategy into a structured format
        # In a real implementation, this would be more robust
        entry_price = entry_point.get("entry_price", 100.0)
        direction = entry_point.get("direction", "long")
        
        # Calculate take profit based on direction
        if direction == "long":
            take_profit = entry_price * 1.05
        else:
            take_profit = entry_price * 0.95
            
        # Return the result
        return {
            "pattern": pattern,
            "entry_point": entry_point,
            "exit_strategy": {
                "take_profit": take_profit,
                "trailing_stop": True,
                "trailing_stop_pct": 1.5,
            },
            "strategy_details": llm_strategy,
        }
    
    def _handle_risk_reward(
        self,
        task_data: Dict,
        context: Optional[Dict] = None,
    ) -> Dict:
        """Handle a risk-reward calculation task.
        
        Args:
            task_data: Task data with price information
            context: Optional context information
            
        Returns:
            Dictionary with risk-reward calculation
        """
        # Extract information
        entry_price = task_data.get("entry_price", 0)
        stop_loss = task_data.get("stop_loss", 0)
        take_profit = task_data.get("take_profit", 0)
        
        # Calculate risk and reward
        risk = abs(entry_price - stop_loss)
        reward = abs(entry_price - take_profit)
        
        # Calculate risk-reward ratio
        risk_reward_ratio = reward / risk if risk > 0 else 0
        
        # Return the result
        return {
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk": risk,
            "reward": reward,
            "risk_reward_ratio": risk_reward_ratio,
            "recommendation": "Take trade" if risk_reward_ratio >= 2.0 else "Avoid trade",
        }


class AgentCoordinator:
    """Coordinates multiple agents to solve complex tasks.
    
    This class manages communication between agents, assigns tasks,
    and aggregates results to solve multi-step problems.
    """
    
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        rag_engine: Optional[RAGEngine] = None,
        max_workers: int = 4,
    ):
        """Initialize the agent coordinator.
        
        Args:
            llm_client: LLM client for text generation
            rag_engine: RAG engine for knowledge retrieval
            max_workers: Maximum number of worker threads for parallel task execution
        """
        self.llm_client = llm_client or LLMClient()
        self.rag_engine = rag_engine or RAGEngine()
        
        # Initialize agent registry
        self.agents = {}
        
        # Initialize task history
        self.task_history = []
        
        # For parallel task execution
        self.max_workers = max_workers
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.task_locks = {}
        
    def register_agent(self, agent: Agent) -> None:
        """Register an agent with the coordinator.
        
        Args:
            agent: The agent to register
        """
        self.agents[agent.agent_id] = agent
        
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID.
        
        Args:
            agent_id: The agent ID to look up
            
        Returns:
            The agent with the given ID, or None if not found
        """
        return self.agents.get(agent_id)
    
    def get_agent_by_name(self, name: str) -> Optional[Agent]:
        """Get an agent by name.
        
        Args:
            name: The agent name to look up
            
        Returns:
            The first agent with the given name, or None if not found
        """
        for agent in self.agents.values():
            if agent.name == name:
                return agent
        return None
    
    def list_agents(self) -> List[Dict]:
        """List all registered agents.
        
        Returns:
            List of agent information dictionaries
        """
        return [agent.to_dict() for agent in self.agents.values()]
    
    def create_task(
        self,
        task_type: str,
        task_data: Dict,
        target_agent_id: Optional[str] = None,
        target_agent_name: Optional[str] = None,
    ) -> Dict:
        """Create and assign a task to an agent.
        
        Args:
            task_type: Type of task to create
            task_data: Task data
            target_agent_id: ID of the agent to assign the task to
            target_agent_name: Name of the agent to assign the task to
            
        Returns:
            Dictionary with the task result
            
        Raises:
            ValueError: If the target agent is not found
        """
        # Generate a task ID
        task_id = str(uuid.uuid4())
        
        # Find the target agent
        target_agent = None
        if target_agent_id:
            target_agent = self.get_agent(target_agent_id)
        elif target_agent_name:
            target_agent = self.get_agent_by_name(target_agent_name)
            
        # Ensure we have a target agent
        if not target_agent:
            raise ValueError("Target agent not found")
            
        # Create the task
        task = {
            "task_id": task_id,
            "type": task_type,
            "data": task_data,
            "timestamp": time.time(),
        }
        
        # Record the task in history
        self.task_history.append({
            "task_id": task_id,
            "type": task_type,
            "target_agent_id": target_agent.agent_id,
            "target_agent_name": target_agent.name,
            "timestamp": task["timestamp"],
            "status": "created",
        })
        
        # Assign the task to the agent
        result = target_agent.handle_task(task)
        
        # Update task status in history
        for task_record in self.task_history:
            if task_record["task_id"] == task_id:
                task_record["status"] = "completed"
                task_record["completion_time"] = time.time()
                break
                
        # Return the result
        return result
        
    def _execute_task_async(
        self,
        task_type: str,
        task_data: Dict,
        target_agent: Agent,
    ) -> Tuple[str, Dict]:
        """Execute a task asynchronously.
        
        Args:
            task_type: Type of task to create
            task_data: Task data
            target_agent: Agent to assign the task to
            
        Returns:
            Tuple containing the task ID and result dictionary
        """
        # Generate a task ID
        task_id = str(uuid.uuid4())
        
        # Create the task
        task = {
            "task_id": task_id,
            "type": task_type,
            "data": task_data,
            "timestamp": time.time(),
        }
        
        # Get lock for this agent to prevent race conditions
        if target_agent.agent_id not in self.task_locks:
            self.task_locks[target_agent.agent_id] = threading.Lock()
            
        with self.task_locks[target_agent.agent_id]:
            # Record the task in history
            self.task_history.append({
                "task_id": task_id,
                "type": task_type,
                "target_agent_id": target_agent.agent_id,
                "target_agent_name": target_agent.name,
                "timestamp": task["timestamp"],
                "status": "created",
            })
            
            # Assign the task to the agent
            result = target_agent.handle_task(task)
            
            # Update task status in history
            for task_record in self.task_history:
                if task_record["task_id"] == task_id:
                    task_record["status"] = "completed"
                    task_record["completion_time"] = time.time()
                    break
        
        return task_id, result
        
    def create_parallel_tasks(
        self,
        tasks: List[Dict],
    ) -> Dict[str, Dict]:
        """Create and assign multiple tasks to be executed in parallel.
        
        Args:
            tasks: List of task specifications, each containing:
                - task_type: Type of task to create
                - task_data: Task data
                - target_agent_id: Optional ID of the agent to assign the task to
                - target_agent_name: Optional name of the agent to assign the task to
            
        Returns:
            Dictionary mapping task IDs to task results
            
        Raises:
            ValueError: If any target agent is not found
        """
        future_to_task = {}
        task_to_id = {}
        
        # Submit all tasks to the thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for i, task_spec in enumerate(tasks):
                # Extract task specification
                task_type = task_spec.get("task_type")
                task_data = task_spec.get("task_data", {})
                target_agent_id = task_spec.get("target_agent_id")
                target_agent_name = task_spec.get("target_agent_name")
                
                # Find the target agent
                target_agent = None
                if target_agent_id:
                    target_agent = self.get_agent(target_agent_id)
                elif target_agent_name:
                    target_agent = self.get_agent_by_name(target_agent_name)
                    
                # Ensure we have a target agent
                if not target_agent:
                    raise ValueError(f"Target agent not found for task {i}")
                
                # Submit the task
                future = executor.submit(
                    self._execute_task_async,
                    task_type,
                    task_data,
                    target_agent,
                )
                future_to_task[future] = task_spec
                
        # Collect results
        results = {}
        for future in concurrent.futures.as_completed(future_to_task):
            task_id, result = future.result()
            results[task_id] = result
            
        return results
        
    def execute_agent_function(
        self,
        function_name: str,
        function_args: Dict,
        agent_names: List[str],
    ) -> List[Dict]:
        """Execute a function across multiple agents in parallel.
        
        Args:
            function_name: Name of the function to execute
            function_args: Arguments to pass to the function
            agent_names: List of agent names to execute the function on
            
        Returns:
            List of function results from each agent
            
        Raises:
            ValueError: If any agent is not found or function is not supported
        """
        # Validate agents and function
        tasks = []
        for agent_name in agent_names:
            agent = self.get_agent_by_name(agent_name)
            if not agent:
                raise ValueError(f"Agent not found: {agent_name}")
                
            # Map task types to associated function names in tools
            task_to_function_map = {
                "entry_strategy": "generate_entry_strategy",
                "exit_strategy": "generate_exit_strategy",
                "risk_reward": "calculate_risk_reward",
                "detect_waves": "detect_elliott_waves",
                "validate_pattern": "validate_wave_pattern",
                "predict_movement": "predict_next_move"
            }
            
            # Check if agent supports this function (based on tools or task type)
            function_supported = False
            
            # First check if the task type matches directly with a function
            if function_name in task_to_function_map:
                tool_function_name = task_to_function_map[function_name]
            else:
                tool_function_name = function_name
                
            if agent.tools:
                for tool in agent.tools:
                    if tool.get("type") == "function" and tool.get("function", {}).get("name") == tool_function_name:
                        function_supported = True
                        break
                        
            # Special case: if the agent has a handle_task method that can handle this task type
            if hasattr(agent, 'handle_task') and hasattr(agent, '_handle_' + function_name.replace('-', '_')):
                function_supported = True
                
            if not function_supported:
                raise ValueError(f"Function {function_name} not supported by agent {agent_name}")
                
            # Create task specification
            tasks.append({
                "task_type": function_name,
                "task_data": function_args,
                "target_agent_name": agent_name,
            })
            
        # Execute tasks in parallel
        return list(self.create_parallel_tasks(tasks).values())
    
    def run_workflow(
        self,
        query: str,
        workflow_type: str = "wave_detection_and_strategy",
    ) -> Dict:
        """Run a predefined workflow involving multiple agents.
        
        Args:
            query: The user's query to process
            workflow_type: Type of workflow to run
            
        Returns:
            Dictionary with the workflow results
            
        Raises:
            ValueError: If the workflow type is not supported
        """
        if workflow_type == "wave_detection_and_strategy":
            return self._run_wave_detection_and_strategy_workflow(query)
        else:
            raise ValueError(f"Unsupported workflow type: {workflow_type}")
    
    def _run_wave_detection_and_strategy_workflow(self, query: str) -> Dict:
        """Run a workflow for wave detection and strategy generation.
        
        Args:
            query: The user's query to process
            
        Returns:
            Dictionary with the workflow results
        """
        # Step 1: Extract parameters from query using LLM
        params_prompt = (
            f"Extract parameters for Elliott Wave analysis from this query: '{query}'\n\n"
            f"Return a JSON object with these fields:\n"
            f"- symbol: The trading symbol/pair mentioned (default: 'EURUSD')\n"
            f"- timeframe: The timeframe mentioned (default: 'daily')\n"
            f"- pattern_type: The pattern type to look for (impulse, corrective, or any)\n"
            f"- risk_tolerance: The risk tolerance level (low, medium, high)\n"
        )
        
        params_json = self.llm_client.generate_text(
            prompt=params_prompt,
            system_prompt="You are a parameter extraction assistant. Extract structured parameters from natural language queries and output valid JSON only.",
            temperature=0.1,
        )
        
        # Parse the parameters
        try:
            params = json.loads(params_json)
        except Exception:
            # Fallback to default parameters
            params = {
                "symbol": "EURUSD",
                "timeframe": "daily",
                "pattern_type": "any",
                "risk_tolerance": "medium",
            }
            
        # Step 2: Get or create wave detection agent
        wave_agent = self.get_agent_by_name("WaveDetectionAgent")
        if not wave_agent:
            wave_agent = WaveDetectionAgent(
                llm_client=self.llm_client,
                rag_engine=self.rag_engine,
            )
            self.register_agent(wave_agent)
            
        # Step 3: Get or create strategy agent
        strategy_agent = self.get_agent_by_name("StrategyAgent")
        if not strategy_agent:
            strategy_agent = StrategyAgent(
                llm_client=self.llm_client,
                rag_engine=self.rag_engine,
            )
            self.register_agent(strategy_agent)
            
        # Step 4: Create a task for wave detection
        # In a real implementation, this would include actual price data
        detect_task = {
            "task_type": "detect_waves",
            "task_data": {
                "symbol": params["symbol"],
                "timeframe": params["timeframe"],
                "pattern_type": params["pattern_type"],
                "price_summary": {
                    "recent_high": 1.05,
                    "recent_low": 0.95,
                    "current_price": 1.0,
                    "trend": "upward",
                },
                # Placeholder for pattern data
                "patterns": [
                    {
                        "type": "impulse",
                        "wave_count": 3,  # Currently in wave 3
                        "wave1_start": 0.98,
                        "wave1_end": 1.02,
                        "wave2_start": 1.02,
                        "wave2_end": 0.99,
                        "wave3_start": 0.99,
                        "wave3_current": 1.05,
                        "confidence": 0.8,
                    }
                ],
            },
            "target_agent_id": wave_agent.agent_id,
        }
        
        # Execute the wave detection task
        detect_results = self.create_parallel_tasks([detect_task])
        detect_result = list(detect_results.values())[0] if detect_results else {}
        
        # Extract the pattern
        pattern = detect_result.get("detected_patterns", [])[0] if detect_result.get("detected_patterns") else {}
        
        # Step 5: Create validation task
        validate_task = {
            "task_type": "validate_pattern",
            "task_data": {"pattern": pattern},
            "target_agent_id": wave_agent.agent_id,
        }
        
        # Execute the validation task
        validate_results = self.create_parallel_tasks([validate_task])
        validate_result = list(validate_results.values())[0] if validate_results else {}
        
        # Step 6: Generate strategy tasks if pattern is valid
        if validate_result.get("is_valid", False):
            # Create tasks for parallel execution
            strategy_tasks = [
                {
                    "task_type": "entry_strategy",
                    "task_data": {
                        "pattern": pattern,
                        "risk_tolerance": params["risk_tolerance"],
                    },
                    "target_agent_id": strategy_agent.agent_id,
                }
            ]
            
            # Execute entry strategy task
            strategy_results = self.create_parallel_tasks(strategy_tasks)
            entry_result = list(strategy_results.values())[0] if strategy_results else {}
            
            # Create exit strategy and risk-reward tasks for parallel execution
            final_tasks = [
                {
                    "task_type": "exit_strategy",
                    "task_data": {
                        "pattern": pattern,
                        "entry_point": entry_result.get("strategy", {}),
                    },
                    "target_agent_id": strategy_agent.agent_id,
                },
                {
                    "task_type": "risk_reward",
                    "task_data": {
                        "entry_price": entry_result.get("strategy", {}).get("entry_price", 0),
                        "stop_loss": entry_result.get("strategy", {}).get("stop_loss", 0),
                        # We need to estimate take_profit since exit_strategy hasn't run yet
                        "take_profit": entry_result.get("strategy", {}).get("entry_price", 0) * 1.05,
                    },
                    "target_agent_id": strategy_agent.agent_id,
                }
            ]
            
            # Execute exit strategy and risk-reward tasks in parallel
            final_results = self.create_parallel_tasks(final_tasks)
            
            # Extract results
            results_list = list(final_results.values())
            exit_result = next((r for r in results_list if "exit_strategy" in r), {})
            risk_reward_result = next((r for r in results_list if "risk_reward_ratio" in r), {})
            
            # Update risk-reward with actual take profit from exit strategy
            if "take_profit" in exit_result.get("exit_strategy", {}) and "entry_price" in entry_result.get("strategy", {}):
                # Recalculate with correct take profit
                risk_reward_task = {
                    "task_type": "risk_reward",
                    "task_data": {
                        "entry_price": entry_result.get("strategy", {}).get("entry_price", 0),
                        "stop_loss": entry_result.get("strategy", {}).get("stop_loss", 0),
                        "take_profit": exit_result.get("exit_strategy", {}).get("take_profit", 0),
                    },
                    "target_agent_id": strategy_agent.agent_id,
                }
                risk_reward_results = self.create_parallel_tasks([risk_reward_task])
                risk_reward_result = list(risk_reward_results.values())[0] if risk_reward_results else risk_reward_result
            
            # Compile the final result
            return {
                "query": query,
                "parameters": params,
                "wave_detection": detect_result,
                "pattern_validation": validate_result,
                "entry_strategy": entry_result,
                "exit_strategy": exit_result,
                "risk_reward": risk_reward_result,
                "recommendation": risk_reward_result.get("recommendation", ""),
                "execution_mode": "parallel",
            }
        else:
            # No valid pattern detected
            return {
                "query": query,
                "parameters": params,
                "wave_detection": detect_result,
                "pattern_validation": validate_result,
                "error": "No valid Elliott Wave pattern detected",
                "execution_mode": "parallel",
            }