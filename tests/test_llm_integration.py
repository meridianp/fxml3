"""Tests for the LLM integration module."""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from fxml3.llm_integration.agent_framework import (Agent, AgentCoordinator,
                                                 StrategyAgent,
                                                 WaveDetectionAgent)
from fxml3.llm_integration.knowledge_base import ElliotWaveKnowledgeBase
from fxml3.llm_integration.llm_client import LLMClient
from fxml3.llm_integration.rag import RAGEngine
from fxml3.llm_integration.vector_store import PineconeVectorStore


class TestLLMClient(unittest.TestCase):
    """Tests for the LLMClient class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock LLMClient
        self.llm_client = LLMClient()
    
    @patch("openai.chat.completions.create")
    def test_generate_text(self, mock_create):
        """Test the generate_text method."""
        # Mock the OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_create.return_value = mock_response
        
        # Call the method
        result = self.llm_client.generate_text("Test prompt")
        
        # Check if OpenAI API was called correctly
        mock_create.assert_called_once()
        self.assertEqual(result, "Test response")
    
    @patch("openai.embeddings.create")
    def test_get_embedding(self, mock_create):
        """Test the get_embedding method."""
        # Mock the OpenAI response
        mock_response = MagicMock()
        mock_response.data = [MagicMock()]
        mock_response.data[0].embedding = [0.1, 0.2, 0.3]
        mock_create.return_value = mock_response
        
        # Call the method
        result = self.llm_client.get_embedding("Test text")
        
        # Check if OpenAI API was called correctly
        mock_create.assert_called_once()
        self.assertEqual(result, [0.1, 0.2, 0.3])


@patch("pinecone.init")
@patch("pinecone.list_indexes")
@patch("pinecone.Index")
class TestPineconeVectorStore(unittest.TestCase):
    """Tests for the PineconeVectorStore class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Set up environment variables
        os.environ["PINECONE_API_TOKEN"] = "test_api_key"
        os.environ["PINECONE_ENVIRONMENT"] = "test_environment"
        
    def test_init(self, mock_index, mock_list_indexes, mock_init):
        """Test the __init__ method."""
        # Mock the Pinecone responses
        mock_list_indexes.return_value = ["wave"]
        
        # Create an instance
        vector_store = PineconeVectorStore()
        
        # Check if Pinecone was initialized correctly
        mock_init.assert_called_once_with(
            api_key="test_api_key",
            environment="test_environment",
        )
        
        # Check if the index was initialized correctly
        mock_index.assert_called_once()
    
    @patch("fxml3.llm_integration.vector_store.LLMClient")
    def test_add_texts(self, mock_llm_client, mock_index, mock_list_indexes, mock_init):
        """Test the add_texts method."""
        # Mock the Pinecone responses
        mock_list_indexes.return_value = ["wave"]
        
        # Mock the LLMClient
        mock_client = MagicMock()
        mock_client.get_embedding.return_value = [0.1, 0.2, 0.3]
        mock_llm_client.return_value = mock_client
        
        # Mock the index
        mock_index_instance = MagicMock()
        mock_index.return_value = mock_index_instance
        
        # Create an instance
        vector_store = PineconeVectorStore()
        
        # Call the method
        texts = ["Test text 1", "Test text 2"]
        metadatas = [{"key1": "value1"}, {"key2": "value2"}]
        result = vector_store.add_texts(texts, metadatas)
        
        # Check if the embeddings were generated correctly
        self.assertEqual(mock_client.get_embedding.call_count, 2)
        
        # Check if the vectors were upserted correctly
        mock_index_instance.upsert.assert_called_once()
        
        # Check the return value
        self.assertEqual(len(result), 2)


class TestAgentFramework(unittest.TestCase):
    """Tests for the agent framework."""
    
    def test_agent_coordinator(self):
        """Test the AgentCoordinator class."""
        # Mock components
        llm_client = MagicMock()
        rag_engine = MagicMock()
        
        # Create agents
        wave_agent = WaveDetectionAgent(llm_client=llm_client, rag_engine=rag_engine)
        strategy_agent = StrategyAgent(llm_client=llm_client, rag_engine=rag_engine)
        
        # Create coordinator
        coordinator = AgentCoordinator(llm_client=llm_client, rag_engine=rag_engine)
        
        # Register agents
        coordinator.register_agent(wave_agent)
        coordinator.register_agent(strategy_agent)
        
        # Test listing agents
        agents = coordinator.list_agents()
        self.assertEqual(len(agents), 2)
        
        # Test getting agent by name
        agent = coordinator.get_agent_by_name("WaveDetectionAgent")
        self.assertIsNotNone(agent)
        self.assertEqual(agent.name, "WaveDetectionAgent")
        
        # Test getting agent by ID
        agent = coordinator.get_agent(wave_agent.agent_id)
        self.assertIsNotNone(agent)
        self.assertEqual(agent.agent_id, wave_agent.agent_id)
    
    def test_wave_detection_agent(self):
        """Test the WaveDetectionAgent class."""
        # Mock components
        llm_client = MagicMock()
        llm_client.generate_text.return_value = "LLM analysis result"
        rag_engine = MagicMock()
        rag_engine.query.return_value = {"answer": "RAG result", "source_documents": []}
        
        # Create agent
        agent = WaveDetectionAgent(llm_client=llm_client, rag_engine=rag_engine)
        
        # Create a task
        task = {
            "task_id": "test_task_id",
            "type": "detect_waves",
            "data": {
                "symbol": "EURUSD",
                "timeframe": "daily",
                "patterns": [{"type": "impulse", "confidence": 0.8}],
                "price_summary": {"trend": "up"},
            },
        }
        
        # Call the method
        result = agent.handle_task(task)
        
        # Check if LLM and RAG were called
        llm_client.generate_text.assert_called_once()
        rag_engine.query.assert_called_once()
        
        # Check the result
        self.assertIn("detected_patterns", result)
        self.assertIn("llm_analysis", result)
        self.assertEqual(result["llm_analysis"], "LLM analysis result")


if __name__ == "__main__":
    unittest.main()