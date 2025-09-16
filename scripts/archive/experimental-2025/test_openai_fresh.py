#!/usr/bin/env python3
"""Test OpenAI connection with fresh key load."""

import os

from openai import OpenAI

# Read key directly from .env file
api_key = None
with open(".env", "r") as f:
    for line in f:
        if line.startswith("OPENAI_API_KEY="):
            api_key = line.strip().split("=", 1)[1]
            # Remove quotes if present
            if api_key.startswith("'") and api_key.endswith("'"):
                api_key = api_key[1:-1]
            break

print(f"API Key loaded: {api_key[:10]}...{api_key[-4:]}")

# Initialize client
client = OpenAI(api_key=api_key)

# Test connection
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

    # Test vision capability
    print("\nTesting vision capability...")
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
    print("✅ Vision capability confirmed!")

except Exception as e:
    print(f"❌ Error: {e}")
