#!/usr/bin/env python3
"""Test OpenAI connection."""

import os

from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Get API key
api_key = os.environ.get("OPENAI_API_KEY")
# Remove quotes if present
if api_key and api_key.startswith("'") and api_key.endswith("'"):
    api_key = api_key[1:-1]
print(f"API Key loaded: {api_key[:10]}...{api_key[-4:]}")

# Initialize client
client = OpenAI(api_key=api_key)

# Test connection with a simple call
try:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": "Say 'API connection successful' in 5 words or less.",
            },
        ],
        max_tokens=20,
    )
    print(f"Response: {response.choices[0].message.content}")
    print("✅ OpenAI API connection successful!")
except Exception as e:
    print(f"❌ Error: {e}")

# Test vision capability
try:
    print("\nTesting vision capability...")
    # Create a simple test image request
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Can you see images? Reply yes or no."},
                ],
            }
        ],
        max_tokens=10,
    )
    print(f"Vision test: {response.choices[0].message.content}")
except Exception as e:
    print(f"❌ Vision Error: {e}")
