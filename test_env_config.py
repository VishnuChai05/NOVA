#!/usr/bin/env python
"""Test and verify all .env configuration."""

import sys
sys.path.insert(0, "backend")

from app.core.settings import settings

print("=" * 60)
print("TESTING .ENV CONFIGURATION")
print("=" * 60)

print("\n📋 Database Configuration")
print(f"  Database URL: {settings.database_url}")
print(f"  Frontend URL: {settings.frontend_url}")

print("\n🔑 API Keys")
print(f"  Anthropic API Key: {'SET ✓' if settings.anthropic_api_key else 'NOT SET ⚠'}")
print(f"  Anthropic Model: {settings.anthropic_model}")

print("\n📱 Reddit Configuration")
print(f"  Reddit Mode: {settings.reddit_source_mode}")
print(f"  Reddit Client ID: {'SET ✓' if settings.reddit_client_id else 'NOT SET ⚠'}")
print(f"  Reddit Client Secret: {'SET ✓' if settings.reddit_client_secret else 'NOT SET ⚠'}")

print("\n🔗 Apify Configuration")
print(f"  Apify Token: {'SET ✓' if settings.apify_api_token else 'NOT SET ⚠'}")
if settings.apify_api_token:
    print(f"    Token Prefix: {settings.apify_api_token[:20]}...")
    print(f"    Token Length: {len(settings.apify_api_token)} chars")
print(f"  Reddit Actor ID: {settings.apify_reddit_actor_id}")
print(f"  Quora Actor ID: {settings.apify_quora_actor_id}")

print("\n⚙️ Scraper Configuration")
print(f"  Allow Fallback Seed Data: {settings.allow_fallback_seed_data}")
print(f"  Retry Attempts: {settings.scraper_retry_attempts}")
print(f"  Backoff Base (seconds): {settings.scraper_backoff_base_seconds}")
print(f"  Query Delay (seconds): {settings.reddit_query_delay_seconds}")

print("\n" + "=" * 60)
print("✅ Configuration Test Complete!")
print("=" * 60)
