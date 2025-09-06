#!/usr/bin/env python3
"""Test script to check OpenAI API connectivity."""

import os
import sys
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Direct OpenAI test
import openai


def main():
    """Test OpenAI API connectivity."""
    # Load environment variables
    load_dotenv()
    
    # Get API key
    api_key = os.environ.get("OPENAI_API_KEY")
    
    if not api_key:
        print("Error: OpenAI API key not found in environment")
        return
    
    # Create client
    print("Testing OpenAI API connectivity...")
    try:
        client = openai.OpenAI(api_key=api_key)
        
        # Test embedding generation
        print("\nTesting embedding generation...")
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input="Hello, world!"
        )
        
        embedding = response.data[0].embedding
        print(f"Successfully generated embedding with {len(embedding)} dimensions")
        print(f"First 5 values: {embedding[:5]}")
        
        # Test chat completion
        print("\nTesting chat completion...")
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say hello!"}
            ]
        )
        
        print(f"Response: {completion.choices[0].message.content}")
        print("OpenAI API is working correctly!")
        
    except Exception as e:
        print(f"Error connecting to OpenAI: {str(e)}")


if __name__ == "__main__":
    main()