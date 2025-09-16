"""LLM client for connecting to various model providers.

This is adapted from FXML3's LLM client implementation to provide a uniform
interface for connecting to different LLM providers like OpenAI and Anthropic.
"""

import os
from typing import Dict, List, Optional, Union

import openai
from dotenv import load_dotenv


class LLMClient:
    """Client for interacting with large language models.

    This class provides a unified interface for interacting with
    different LLM providers (OpenAI, Anthropic, etc.) and handles
    API key management, rate limiting, and error handling.
    """

    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """Initialize the LLM client.

        Args:
            provider: The LLM provider ("openai", "anthropic", "local")
            model: The specific model to use (defaults to provider's default)
            api_key: API key for the provider (if None, read from environment)
        """
        # Load environment variables
        load_dotenv()

        self.provider = provider.lower()

        # Set API keys
        if api_key:
            self.api_key = api_key
        else:
            if self.provider == "openai":
                # First try to read directly from .env file for fresh key
                try:
                    with open(".env", "r") as f:
                        for line in f:
                            if line.startswith("OPENAI_API_KEY="):
                                self.api_key = line.strip().split("=", 1)[1]
                                # Remove quotes if present
                                if self.api_key.startswith(
                                    "'"
                                ) and self.api_key.endswith("'"):
                                    self.api_key = self.api_key[1:-1]
                                break
                except:
                    # Fallback to environment variable
                    self.api_key = os.environ.get("OPENAI_API_KEY")
                    # Remove quotes if present
                    if (
                        self.api_key
                        and self.api_key.startswith("'")
                        and self.api_key.endswith("'")
                    ):
                        self.api_key = self.api_key[1:-1]
            elif self.provider == "anthropic":
                self.api_key = os.environ.get("ANTHROPIC_API_KEY")
                # Remove quotes if present
                if (
                    self.api_key
                    and self.api_key.startswith("'")
                    and self.api_key.endswith("'")
                ):
                    self.api_key = self.api_key[1:-1]
            else:
                self.api_key = None

        # Set default models if not specified
        if model:
            self.model = model
        else:
            # Read model directly from .env file first
            llm_model = None
            try:
                with open(".env", "r") as f:
                    for line in f:
                        if line.startswith("LLM_MODEL="):
                            llm_model = (
                                line.strip().split("=", 1)[1].split("#")[0].strip()
                            )
                            break
            except Exception:
                # Fallback to environment variable if file reading fails
                pass

            if not llm_model:
                llm_model = os.environ.get("LLM_MODEL")

            if self.provider == "openai":
                self.model = llm_model or "gpt-3.5-turbo"
            elif self.provider == "anthropic":
                self.model = llm_model or "claude-3-opus-20240229"
            else:
                self.model = llm_model or "gpt-3.5-turbo"

        # Initialize the API client
        self.openai_client = None
        if self.provider == "openai":
            from openai import OpenAI

            self.openai_client = OpenAI(api_key=self.api_key)

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        stop_sequences: Optional[List[str]] = None,
    ) -> str:
        """Generate text using the LLM.

        Args:
            prompt: The user prompt to generate from
            system_prompt: Optional system prompt for context
            temperature: Controls randomness (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            stop_sequences: Optional list of strings that stop generation

        Returns:
            Generated text response

        Raises:
            ValueError: If the provider is not supported
            Exception: For API errors
        """
        if self.provider == "openai":
            return self._generate_openai(
                prompt, system_prompt, temperature, max_tokens, stop_sequences
            )
        elif self.provider == "anthropic":
            return self._generate_anthropic(
                prompt, system_prompt, temperature, max_tokens, stop_sequences
            )
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _generate_openai(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        stop_sequences: Optional[List[str]] = None,
    ) -> str:
        """Generate text using OpenAI API.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Controls randomness
            max_tokens: Maximum tokens to generate
            stop_sequences: Optional list of strings that stop generation

        Returns:
            Generated text response
        """
        messages = []

        # Add system prompt if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Add user prompt
        messages.append({"role": "user", "content": prompt})

        # Make the API call
        try:
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stop=stop_sequences,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")

    def _generate_anthropic(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        stop_sequences: Optional[List[str]] = None,
    ) -> str:
        """Generate text using Anthropic API.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Controls randomness
            max_tokens: Maximum tokens to generate
            stop_sequences: Optional list of strings that stop generation

        Returns:
            Generated text response
        """
        # Import anthropic only if needed
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "Anthropic Python package not installed. "
                "Install it with: pip install anthropic"
            )

        # Configure the client
        client = anthropic.Anthropic(api_key=self.api_key)

        # Make the API call
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt if system_prompt else None,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                stop_sequences=stop_sequences,
            )
            return response.content[0].text
        except Exception as e:
            raise Exception(f"Anthropic API error: {str(e)}")

    def get_embedding(self, text: str, model: Optional[str] = None) -> List[float]:
        """Generate an embedding vector for the given text.

        Args:
            text: The text to embed
            model: Optional specific embedding model to use

        Returns:
            List of floats representing the embedding vector

        Raises:
            ValueError: If the provider doesn't support embeddings
            Exception: For API errors
        """
        if self.provider == "openai":
            return self._get_embedding_openai(text, model)
        else:
            raise ValueError(f"Embeddings not supported for provider: {self.provider}")

    def _get_embedding_openai(
        self, text: str, model: Optional[str] = None
    ) -> List[float]:
        """Generate an embedding vector using OpenAI API.

        Args:
            text: The text to embed
            model: Optional specific embedding model to use

        Returns:
            List of floats representing the embedding vector
        """
        embedding_model = model or os.environ.get(
            "EMBEDDING_MODEL", "text-embedding-3-large"
        )

        try:
            response = self.openai_client.embeddings.create(
                model=embedding_model,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            raise Exception(f"OpenAI Embedding API error: {str(e)}")

    async def generate_text_async(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        stop_sequences: Optional[List[str]] = None,
    ) -> str:
        """Async version of generate_text for non-blocking calls.

        Args:
            prompt: The user prompt to generate from
            system_prompt: Optional system prompt for context
            temperature: Controls randomness (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            stop_sequences: Optional list of strings that stop generation

        Returns:
            Generated text response
        """
        # For now, wrap the sync call - could be optimized with async clients
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.generate_text,
            prompt,
            system_prompt,
            temperature,
            max_tokens,
            stop_sequences,
        )

    async def generate_multimodal_response(
        self,
        prompt: str,
        image_base64: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """Generate response using multi-modal capabilities (text + image).

        Args:
            prompt: The user prompt
            image_base64: Base64 encoded image
            system_prompt: Optional system prompt
            temperature: Controls randomness
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text response
        """
        if self.provider == "openai":
            return await self._generate_multimodal_openai(
                prompt, image_base64, system_prompt, temperature, max_tokens
            )
        elif self.provider == "anthropic":
            return await self._generate_multimodal_anthropic(
                prompt, image_base64, system_prompt, temperature, max_tokens
            )
        else:
            # Fallback to text-only
            return await self.generate_text_async(
                prompt, system_prompt, temperature, max_tokens
            )

    async def _generate_multimodal_openai(
        self,
        prompt: str,
        image_base64: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """Generate multi-modal response using OpenAI GPT-4 Vision.

        Args:
            prompt: Text prompt
            image_base64: Base64 encoded image
            system_prompt: Optional system prompt
            temperature: Controls randomness
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text response
        """
        messages = []

        # Add system prompt if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Build user message with image
        user_message = {"role": "user", "content": []}

        # Add text
        user_message["content"].append({"type": "text", "text": prompt})

        # Add image if provided
        if image_base64:
            user_message["content"].append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}",
                        "detail": "high",
                    },
                }
            )

        messages.append(user_message)

        try:
            # Use GPT-4.1 model as requested
            import asyncio

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.openai_client.chat.completions.create(
                    model="gpt-4o",  # Using GPT-4o for vision capabilities
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise Exception(f"OpenAI Vision API error: {str(e)}")

    async def _generate_multimodal_anthropic(
        self,
        prompt: str,
        image_base64: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """Generate multi-modal response using Anthropic Claude.

        Args:
            prompt: Text prompt
            image_base64: Base64 encoded image
            system_prompt: Optional system prompt
            temperature: Controls randomness
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text response
        """
        try:
            import anthropic
        except ImportError:
            raise ImportError("Anthropic package not installed")

        client = anthropic.Anthropic(api_key=self.api_key)

        # Build message content
        content = []

        # Add image if provided
        if image_base64:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": image_base64,
                    },
                }
            )

        # Add text prompt
        content.append({"type": "text", "text": prompt})

        try:
            import asyncio

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt if system_prompt else None,
                    messages=[{"role": "user", "content": content}],
                ),
            )
            return response.content[0].text
        except Exception as e:
            raise Exception(f"Anthropic Vision API error: {str(e)}")
