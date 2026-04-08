#!/usr/bin/env python3
"""Check if .env file is being loaded correctly."""
import os
from dotenv import load_dotenv

# Load .env
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Check all environment variables
key = os.environ.get('ANTHROPIC_API_KEY')
neo4j_uri = os.environ.get('NEO4J_URI')
pg_host = os.environ.get('PG_HOST')

print("Environment Variables Status:")
print(f"  ANTHROPIC_API_KEY: {'LOADED' if key else 'NOT FOUND'} (first 20 chars: {key[:20] if key else 'N/A'})")
print(f"  NEO4J_URI: {neo4j_uri}")
print(f"  PG_HOST: {pg_host}")

# Test if API works
if key:
    import anthropic
    try:
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        print("\n[SUCCESS] API key is valid and Claude API is responsive!")
    except Exception as e:
        print(f"\n[ERROR] API key test failed: {type(e).__name__}: {str(e)[:100]}")
