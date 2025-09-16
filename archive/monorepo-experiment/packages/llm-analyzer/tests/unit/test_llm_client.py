"""Tests for LLM client classes."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import os
from typing import Dict, List

from fxml4_llm.client import (
    LLMClient, LLMProvider, LLMConfig, BaseLLMClient,
    OpenAIClient, AnthropicClient
)


@pytest.fixture
def llm_config():
    """Create test LLM configuration."""
    return LLMConfig(
        openai_api_key="test_openai_key",
        anthropic_api_key="test_anthropic_key",
        default_provider=LLMProvider.OPENAI,
        default_model="gpt-4",
        max_tokens=1000,
        temperature=0.7,
        retry_attempts=3,
        timeout=30
    )


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client."""
    with patch('fxml4_llm.client.openai.AsyncOpenAI') as mock:
        client_instance = Mock()
        mock.return_value = client_instance
        
        # Mock chat completions
        completion_mock = AsyncMock()
        completion_mock.choices = [
            Mock(message=Mock(content="Test response from OpenAI"))
        ]
        
        client_instance.chat.completions.create = AsyncMock(return_value=completion_mock)
        
        yield client_instance


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client."""
    with patch('fxml4_llm.client.anthropic.AsyncAnthropic') as mock:
        client_instance = Mock()
        mock.return_value = client_instance
        
        # Mock messages
        message_mock = AsyncMock()
        message_mock.content = [Mock(text="Test response from Anthropic")]
        
        client_instance.messages.create = AsyncMock(return_value=message_mock)
        
        yield client_instance


@pytest.fixture
def mock_tiktoken():
    """Mock tiktoken for token counting."""
    with patch('fxml4_llm.client.tiktoken') as mock:
        encoder = Mock()
        encoder.encode = Mock(return_value=[1, 2, 3, 4, 5])  # 5 tokens
        
        mock.encoding_for_model = Mock(return_value=encoder)
        mock.get_encoding = Mock(return_value=encoder)
        
        yield mock


class TestLLMConfig:
    """Test LLMConfig class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = LLMConfig()
        assert config.default_provider == LLMProvider.OPENAI
        assert config.max_tokens == 2000
        assert config.temperature == 0.7
        assert config.retry_attempts == 3
        assert config.timeout == 60
    
    def test_custom_config(self, llm_config):
        """Test custom configuration values."""
        assert llm_config.openai_api_key == "test_openai_key"
        assert llm_config.anthropic_api_key == "test_anthropic_key"
        assert llm_config.default_model == "gpt-4"
        assert llm_config.max_tokens == 1000


class TestLLMProvider:
    """Test LLMProvider enum."""
    
    def test_provider_values(self):
        """Test provider enum values."""
        assert LLMProvider.OPENAI.value == "openai"
        assert LLMProvider.ANTHROPIC.value == "anthropic"
    
    def test_provider_from_string(self):
        """Test creating provider from string."""
        provider = LLMProvider("openai")
        assert provider == LLMProvider.OPENAI


class TestBaseLLMClient:
    """Test BaseLLMClient abstract class."""
    
    def test_cannot_instantiate_directly(self, llm_config):
        """Test that BaseLLMClient cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            BaseLLMClient(llm_config)
    
    def test_abstract_methods(self):
        """Test that abstract methods are defined."""
        assert hasattr(BaseLLMClient, 'complete')
        assert hasattr(BaseLLMClient, 'chat')
        assert hasattr(BaseLLMClient, 'count_tokens')


class TestOpenAIClient:
    """Test OpenAIClient class."""
    
    def test_initialization_with_api_key(self, llm_config, mock_openai_client, mock_tiktoken):
        """Test OpenAIClient initialization with API key."""
        client = OpenAIClient(llm_config)
        assert client.model == "gpt-4"
        assert client.config == llm_config
    
    def test_initialization_with_env_var(self, mock_openai_client, mock_tiktoken):
        """Test OpenAIClient initialization with environment variable."""
        config = LLMConfig()
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'env_api_key'}):
            client = OpenAIClient(config)
            assert client.model == "gpt-4-turbo-preview"  # default
    
    def test_initialization_without_api_key(self):
        """Test OpenAIClient initialization without API key fails."""
        config = LLMConfig()
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="OpenAI API key not found"):
                OpenAIClient(config)
    
    @pytest.mark.asyncio
    async def test_complete(self, llm_config, mock_openai_client, mock_tiktoken):
        """Test complete method."""
        client = OpenAIClient(llm_config)
        
        result = await client.complete(
            prompt="Test prompt",
            system="Test system",
            max_tokens=500,
            temperature=0.5
        )
        
        assert result == "Test response from OpenAI"
        
        # Verify API call
        mock_openai_client.chat.completions.create.assert_called_once()
        call_args = mock_openai_client.chat.completions.create.call_args
        
        assert call_args.kwargs['model'] == "gpt-4"
        assert call_args.kwargs['max_tokens'] == 500
        assert call_args.kwargs['temperature'] == 0.5
        assert len(call_args.kwargs['messages']) == 2
        assert call_args.kwargs['messages'][0]['role'] == 'system'
        assert call_args.kwargs['messages'][1]['role'] == 'user'
    
    @pytest.mark.asyncio
    async def test_complete_without_system(self, llm_config, mock_openai_client, mock_tiktoken):
        """Test complete method without system message."""
        client = OpenAIClient(llm_config)
        
        result = await client.complete(prompt="Test prompt")
        
        assert result == "Test response from OpenAI"
        
        # Verify only user message
        call_args = mock_openai_client.chat.completions.create.call_args
        assert len(call_args.kwargs['messages']) == 1
        assert call_args.kwargs['messages'][0]['role'] == 'user'
    
    @pytest.mark.asyncio
    async def test_chat(self, llm_config, mock_openai_client, mock_tiktoken):
        """Test chat method."""
        client = OpenAIClient(llm_config)
        
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"}
        ]
        
        result = await client.chat(messages, max_tokens=200)
        
        assert result == "Test response from OpenAI"
        
        # Verify API call
        mock_openai_client.chat.completions.create.assert_called_once()
        call_args = mock_openai_client.chat.completions.create.call_args
        assert call_args.kwargs['messages'] == messages
        assert call_args.kwargs['max_tokens'] == 200
    
    @pytest.mark.asyncio
    async def test_error_handling(self, llm_config, mock_openai_client, mock_tiktoken):
        """Test error handling in API calls."""
        client = OpenAIClient(llm_config)
        
        # Make API call raise an exception
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")
        
        with pytest.raises(Exception, match="API Error"):
            await client.complete("Test prompt")
    
    def test_count_tokens(self, llm_config, mock_openai_client, mock_tiktoken):
        """Test token counting."""
        client = OpenAIClient(llm_config)
        
        count = client.count_tokens("Test text")
        assert count == 5  # Based on mock returning 5 tokens
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self, llm_config, mock_openai_client, mock_tiktoken):
        """Test retry mechanism on API failure."""
        client = OpenAIClient(llm_config)
        
        # First two calls fail, third succeeds
        completion_mock = AsyncMock()
        completion_mock.choices = [
            Mock(message=Mock(content="Success after retries"))
        ]
        
        mock_openai_client.chat.completions.create.side_effect = [
            Exception("Temporary error"),
            Exception("Another temporary error"),
            completion_mock
        ]
        
        result = await client.complete("Test prompt")
        assert result == "Success after retries"
        assert mock_openai_client.chat.completions.create.call_count == 3


class TestAnthropicClient:
    """Test AnthropicClient class."""
    
    def test_initialization_with_api_key(self, llm_config, mock_anthropic_client):
        """Test AnthropicClient initialization with API key."""
        client = AnthropicClient(llm_config)
        assert client.model == "gpt-4"  # Uses config default
        assert client.config == llm_config
    
    def test_initialization_without_api_key(self):
        """Test AnthropicClient initialization without API key fails."""
        config = LLMConfig(anthropic_api_key=None)
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Anthropic API key not found"):
                AnthropicClient(config)
    
    @pytest.mark.asyncio
    async def test_complete(self, llm_config, mock_anthropic_client):
        """Test complete method."""
        client = AnthropicClient(llm_config)
        
        result = await client.complete(
            prompt="Test prompt",
            system="Test system",
            max_tokens=500,
            temperature=0.5
        )
        
        assert result == "Test response from Anthropic"
        
        # Verify API call
        mock_anthropic_client.messages.create.assert_called_once()
        call_args = mock_anthropic_client.messages.create.call_args
        
        assert call_args.kwargs['model'] == "gpt-4"
        assert call_args.kwargs['system'] == "Test system"
        assert call_args.kwargs['max_tokens'] == 500
        assert call_args.kwargs['temperature'] == 0.5
        assert call_args.kwargs['messages'][0]['content'] == "Test prompt"
    
    @pytest.mark.asyncio
    async def test_chat_with_system(self, llm_config, mock_anthropic_client):
        """Test chat method with system message."""
        client = AnthropicClient(llm_config)
        
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
            {"role": "user", "content": "How are you?"}
        ]
        
        result = await client.chat(messages)
        
        assert result == "Test response from Anthropic"
        
        # Verify system message extraction
        call_args = mock_anthropic_client.messages.create.call_args
        assert call_args.kwargs['system'] == "You are helpful"
        assert len(call_args.kwargs['messages']) == 3  # System removed
        assert call_args.kwargs['messages'][0]['role'] == 'user'
    
    def test_count_tokens(self, llm_config, mock_anthropic_client):
        """Test token counting estimation."""
        client = AnthropicClient(llm_config)
        
        # Anthropic uses character-based estimation
        count = client.count_tokens("Test text here!")  # 15 chars
        assert count == 3  # 15 / 4 = 3.75, rounded down


class TestLLMClient:
    """Test unified LLMClient class."""
    
    def test_initialization_default(self, mock_openai_client, mock_tiktoken):
        """Test default initialization."""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            client = LLMClient()
            assert isinstance(client._client, OpenAIClient)
    
    def test_initialization_with_provider_string(self, llm_config):
        """Test initialization with provider as string."""
        with patch('fxml4_llm.client.AnthropicClient') as mock_anthropic:
            client = LLMClient(provider="anthropic", config=llm_config)
            mock_anthropic.assert_called_once_with(llm_config)
    
    def test_initialization_with_provider_enum(self, llm_config):
        """Test initialization with provider as enum."""
        with patch('fxml4_llm.client.OpenAIClient') as mock_openai:
            client = LLMClient(provider=LLMProvider.OPENAI, config=llm_config)
            mock_openai.assert_called_once_with(llm_config)
    
    def test_initialization_with_model_override(self, llm_config):
        """Test initialization with model override."""
        client = LLMClient(model="gpt-3.5-turbo", config=llm_config)
        assert client.config.default_model == "gpt-3.5-turbo"
    
    def test_unsupported_provider(self):
        """Test initialization with unsupported provider."""
        config = LLMConfig()
        config.default_provider = Mock()  # Invalid provider
        
        with pytest.raises(ValueError, match="Unsupported provider"):
            LLMClient(config=config)
    
    @pytest.mark.asyncio
    async def test_complete_delegation(self, mock_openai_client, mock_tiktoken):
        """Test that complete method delegates to underlying client."""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            client = LLMClient()
            
            # Mock the underlying client's complete method
            client._client.complete = AsyncMock(return_value="Delegated response")
            
            result = await client.complete("Test", system="System")
            
            assert result == "Delegated response"
            client._client.complete.assert_called_once_with("Test", "System", None, None)
    
    @pytest.mark.asyncio
    async def test_chat_delegation(self, mock_openai_client, mock_tiktoken):
        """Test that chat method delegates to underlying client."""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            client = LLMClient()
            
            messages = [{"role": "user", "content": "Hello"}]
            client._client.chat = AsyncMock(return_value="Chat response")
            
            result = await client.chat(messages)
            
            assert result == "Chat response"
            client._client.chat.assert_called_once_with(messages, None, None)
    
    def test_count_tokens_delegation(self, mock_openai_client, mock_tiktoken):
        """Test that count_tokens delegates to underlying client."""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            client = LLMClient()
            
            client._client.count_tokens = Mock(return_value=42)
            
            result = client.count_tokens("Test text")
            
            assert result == 42
            client._client.count_tokens.assert_called_once_with("Test text")
    
    @pytest.mark.asyncio
    async def test_analyze_market(self, mock_openai_client, mock_tiktoken):
        """Test analyze_market method."""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            client = LLMClient()
            
            market_data = {
                "symbol": "EURUSD",
                "timeframe": "1h",
                "close": 1.0850,
                "change_24h": 0.15,
                "rsi": 65,
                "macd": 0.0012,
                "sma_50": 1.0840,
                "sma_200": 1.0820,
                "timestamp": "2024-01-15T12:00:00Z"
            }
            
            client._client.complete = AsyncMock(return_value="Market analysis result")
            
            result = await client.analyze_market(market_data, "comprehensive")
            
            assert result["analysis"] == "Market analysis result"
            assert result["symbol"] == "EURUSD"
            assert result["type"] == "comprehensive"
            assert result["timestamp"] == "2024-01-15T12:00:00Z"
            
            # Verify prompt was built correctly
            call_args = client._client.complete.call_args
            prompt = call_args[0][0]
            assert "EURUSD" in prompt
            assert "1h" in prompt
            assert "1.0850" in prompt
            assert "comprehensive analysis" in prompt
    
    @pytest.mark.asyncio
    async def test_analyze_market_elliott_wave(self, mock_openai_client, mock_tiktoken):
        """Test analyze_market with Elliott Wave analysis type."""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            client = LLMClient()
            
            market_data = {"symbol": "GBPUSD", "timeframe": "4h"}
            
            client._client.complete = AsyncMock(return_value="Elliott Wave analysis")
            
            result = await client.analyze_market(market_data, "elliott_wave")
            
            # Verify Elliott Wave specific prompt
            call_args = client._client.complete.call_args
            prompt = call_args[0][0]
            assert "Elliott Wave analysis" in prompt
            assert "wave count" in prompt
            assert "Fibonacci levels" in prompt
    
    @pytest.mark.asyncio
    async def test_analyze_market_risk_assessment(self, mock_openai_client, mock_tiktoken):
        """Test analyze_market with risk assessment type."""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            client = LLMClient()
            
            market_data = {"symbol": "USDJPY", "timeframe": "1d"}
            
            client._client.complete = AsyncMock(return_value="Risk assessment")
            
            result = await client.analyze_market(market_data, "risk_assessment")
            
            # Verify risk assessment specific prompt
            call_args = client._client.complete.call_args
            prompt = call_args[0][0]
            assert "risk assessment" in prompt
            assert "Position sizing" in prompt
            assert "Stop loss" in prompt