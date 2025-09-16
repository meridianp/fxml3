"""
LLM client for multiple providers.
"""

import os
from enum import Enum
from typing import Dict, List, Optional, Any, Union
import asyncio
from abc import ABC, abstractmethod

import openai
import anthropic
import tiktoken
from tenacity import retry, stop_after_attempt, wait_exponential

from fxml4_core.logging import get_logger
from fxml4_core.config import BaseConfig

logger = get_logger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class LLMConfig(BaseConfig):
    """LLM configuration."""
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    default_provider: LLMProvider = LLMProvider.OPENAI
    default_model: Optional[str] = None
    max_tokens: int = 2000
    temperature: float = 0.7
    retry_attempts: int = 3
    timeout: int = 60


class BaseLLMClient(ABC):
    """Base class for LLM clients."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
    
    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Generate completion."""
        pass
    
    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Chat completion."""
        pass
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        pass


class OpenAIClient(BaseLLMClient):
    """OpenAI API client."""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        
        api_key = config.openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not found")
        
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = config.default_model or "gpt-4-turbo-preview"
        
        # Initialize tokenizer
        try:
            self.tokenizer = tiktoken.encoding_for_model(self.model)
        except:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60)
    )
    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Generate completion using OpenAI."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens or self.config.max_tokens,
                temperature=temperature or self.config.temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Chat completion using OpenAI."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens or self.config.max_tokens,
                temperature=temperature or self.config.temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI chat error: {e}")
            raise
    
    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken."""
        return len(self.tokenizer.encode(text))


class AnthropicClient(BaseLLMClient):
    """Anthropic API client."""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        
        api_key = config.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Anthropic API key not found")
        
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = config.default_model or "claude-3-opus-20240229"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60)
    )
    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Generate completion using Anthropic."""
        try:
            response = await self.client.messages.create(
                model=self.model,
                system=system or "",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens or self.config.max_tokens,
                temperature=temperature or self.config.temperature
            )
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Chat completion using Anthropic."""
        # Extract system message if present
        system = None
        chat_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                chat_messages.append(msg)
        
        try:
            response = await self.client.messages.create(
                model=self.model,
                system=system or "",
                messages=chat_messages,
                max_tokens=max_tokens or self.config.max_tokens,
                temperature=temperature or self.config.temperature
            )
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Anthropic chat error: {e}")
            raise
    
    def count_tokens(self, text: str) -> int:
        """Estimate token count for Anthropic."""
        # Rough estimate: 1 token ≈ 4 characters
        return len(text) // 4


class LLMClient:
    """Unified LLM client supporting multiple providers."""
    
    def __init__(
        self,
        provider: Optional[Union[str, LLMProvider]] = None,
        model: Optional[str] = None,
        config: Optional[LLMConfig] = None
    ):
        self.config = config or LLMConfig()
        
        # Override config with parameters
        if provider:
            if isinstance(provider, str):
                self.config.default_provider = LLMProvider(provider)
            else:
                self.config.default_provider = provider
        
        if model:
            self.config.default_model = model
        
        # Initialize client based on provider
        self._client = self._create_client()
        
        logger.info(f"Initialized LLM client: {self.config.default_provider.value}")
    
    def _create_client(self) -> BaseLLMClient:
        """Create provider-specific client."""
        if self.config.default_provider == LLMProvider.OPENAI:
            return OpenAIClient(self.config)
        elif self.config.default_provider == LLMProvider.ANTHROPIC:
            return AnthropicClient(self.config)
        else:
            raise ValueError(f"Unsupported provider: {self.config.default_provider}")
    
    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Generate completion."""
        return await self._client.complete(prompt, system, max_tokens, temperature)
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Chat completion."""
        return await self._client.chat(messages, max_tokens, temperature)
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return self._client.count_tokens(text)
    
    async def analyze_market(
        self,
        market_data: Dict[str, Any],
        analysis_type: str = "comprehensive"
    ) -> Dict[str, Any]:
        """Analyze market conditions."""
        prompt = self._build_market_analysis_prompt(market_data, analysis_type)
        
        system = """You are an expert forex trader and market analyst with deep knowledge 
        of technical analysis, Elliott Wave theory, and market psychology. Provide clear, 
        actionable insights based on the data provided."""
        
        response = await self.complete(prompt, system=system)
        
        return {
            "analysis": response,
            "timestamp": market_data.get("timestamp"),
            "symbol": market_data.get("symbol"),
            "type": analysis_type
        }
    
    def _build_market_analysis_prompt(
        self,
        market_data: Dict[str, Any],
        analysis_type: str
    ) -> str:
        """Build market analysis prompt."""
        symbol = market_data.get("symbol", "Unknown")
        timeframe = market_data.get("timeframe", "Unknown")
        
        prompt = f"""Analyze the following {timeframe} market data for {symbol}:

Current Price: {market_data.get('close', 'N/A')}
24h Change: {market_data.get('change_24h', 'N/A')}%

Technical Indicators:
- RSI: {market_data.get('rsi', 'N/A')}
- MACD: {market_data.get('macd', 'N/A')}
- SMA 50: {market_data.get('sma_50', 'N/A')}
- SMA 200: {market_data.get('sma_200', 'N/A')}

"""
        
        if analysis_type == "comprehensive":
            prompt += """Provide a comprehensive analysis including:
1. Current market trend and momentum
2. Key support and resistance levels
3. Potential Elliott Wave count
4. Risk factors and opportunities
5. Trading recommendation with specific entry/exit points"""
        
        elif analysis_type == "elliott_wave":
            prompt += """Focus on Elliott Wave analysis:
1. Current wave count and degree
2. Expected next move based on wave structure
3. Key Fibonacci levels
4. Invalidation points"""
        
        elif analysis_type == "risk_assessment":
            prompt += """Focus on risk assessment:
1. Current market risks
2. Volatility analysis
3. Position sizing recommendations
4. Stop loss placement"""
        
        return prompt