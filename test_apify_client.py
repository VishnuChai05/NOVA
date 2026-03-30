#!/usr/bin/env python
"""Test Apify client authentication and API endpoints."""

import sys
sys.path.insert(0, "backend")

from app.core.settings import settings
from apify_client import ApifyClient

print("=" * 60)
print("TESTING APIFY CLIENT")
print("=" * 60)

if not settings.apify_api_token:
    print("❌ No Apify token configured")
    sys.exit(1)

print(f"\n🔑 Authenticating with token: {settings.apify_api_token[:20]}...")

try:
    client = ApifyClient(settings.apify_api_token)
    print("✅ ApifyClient initialized")
    
    # Check actor availability
    print(f"\n🎬 Testing actor access:")
    
    # Test Reddit actor
    reddit_actor = settings.apify_reddit_actor_id
    print(f"\n  Reddit Actor: {reddit_actor}")
    try:
        actor_info = client.actor(reddit_actor).get()
        print(f"    ✅ Accessible")
        print(f"    Name: {actor_info.get('name', 'N/A')}")
    except Exception as e:
        print(f"    ⚠ Error: {str(e)[:100]}")
    
    # Test Quora actor
    quora_actor = settings.apify_quora_actor_id
    print(f"\n  Quora Actor: {quora_actor}")
    try:
        actor_info = client.actor(quora_actor).get()
        print(f"    ✅ Accessible")
        print(f"    Name: {actor_info.get('name', 'N/A')}")
    except Exception as e:
        print(f"    ⚠ Error: {str(e)[:100]}")
        
    print("\n✅ Apify client test complete!")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
