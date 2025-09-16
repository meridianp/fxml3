#!/usr/bin/env python3
"""Test OpenAI vision with actual image."""

import base64
import io
import os

from openai import OpenAI
from PIL import Image

# Read key directly from .env file
api_key = None
with open(".env", "r") as f:
    for line in f:
        if line.startswith("OPENAI_API_KEY="):
            api_key = line.strip().split("=", 1)[1]
            if api_key.startswith("'") and api_key.endswith("'"):
                api_key = api_key[1:-1]
            break

print(f"API Key loaded: {api_key[:10]}...{api_key[-4:]}")

# Initialize client
client = OpenAI(api_key=api_key)

# Create a simple test image
print("\nCreating test image...")
img = Image.new("RGB", (200, 100), color="white")
from PIL import ImageDraw

draw = ImageDraw.Draw(img)
draw.text((50, 40), "TEST IMAGE", fill="black")

# Convert to base64
buffer = io.BytesIO()
img.save(buffer, format="PNG")
img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

# Test vision with image
try:
    print("Testing vision with image...")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What text do you see in this image?"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_base64}"},
                    },
                ],
            }
        ],
        max_tokens=50,
    )
    print(f"Vision response: {response.choices[0].message.content}")
    print("✅ Vision with image works!")

except Exception as e:
    print(f"❌ Error: {e}")
    # Try with gpt-4-vision-preview
    try:
        print("\nTrying with gpt-4-vision-preview...")
        response = client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What text do you see in this image?"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_base64}"},
                        },
                    ],
                }
            ],
            max_tokens=50,
        )
        print(f"Vision response: {response.choices[0].message.content}")
        print("✅ Vision works with gpt-4-vision-preview!")
    except Exception as e2:
        print(f"❌ Error with gpt-4-vision-preview: {e2}")
