#!/usr/bin/env python
"""Test backend scraper API endpoints."""

import sys
sys.path.insert(0, "backend")

from fastapi.testclient import TestClient
from app.main import app

print("=" * 60)
print("TESTING BACKEND SCRAPER ENDPOINTS")
print("=" * 60)

client = TestClient(app)

# Test 1: Health endpoint
print("\n✓ Testing /api/health")
response = client.get("/api/health")
print(f"  Status: {response.status_code}")
print(f"  Response: {response.json()}")

# Test 2: Scrape run endpoint
print("\n✓ Testing POST /api/scrape/run")
try:
    response = client.post("/api/scrape/run")
    print(f"  Status: {response.status_code}")
    result = response.json()
    print(f"  Run ID: {result.get('run_id')}")
    print(f"  Created: {result.get('created')}")
    print(f"  Fetched: {result.get('fetched')}")
    print(f"  Status: {result.get('status')}")
except Exception as e:
    print(f"  ❌ Error: {str(e)}")

# Test 3: Get scrape runs
print("\n✓ Testing GET /api/scrape/runs")
try:
    response = client.get("/api/scrape/runs")
    print(f"  Status: {response.status_code}")
    runs = response.json()
    print(f"  Total runs: {len(runs)}")
    
    if runs:
        latest = runs[0]
        print(f"\n  Latest run:")
        print(f"    Run ID: {latest.get('run_id')}")
        print(f"    Status: {latest.get('status')}")
        print(f"    Created: {latest.get('created')}")
        print(f"    Fetched: {latest.get('fetched')}")
        
        # Parse source stats
        import json
        stats = latest.get('source_stats_json')
        if isinstance(stats, str):
            stats = json.loads(stats)
        
        print(f"\n  Source Statistics:")
        for source, data in stats.items():
            print(f"    {source}: {data}")
            
except Exception as e:
    print(f"  ❌ Error: {str(e)}")

# Test 4: Get scraped posts
print("\n✓ Testing GET /api/scraped-posts")
try:
    response = client.get("/api/scraped-posts")
    print(f"  Status: {response.status_code}")
    posts = response.json()
    print(f"  Total posts: {len(posts)}")
    
    if posts:
        first = posts[0]
        print(f"\n  First post:")
        print(f"    Title: {first.get('title')[:60]}...")
        print(f"    Source: {first.get('source')}")
        print(f"    URL: {first.get('url')[:50]}...")
        
except Exception as e:
    print(f"  ❌ Error: {str(e)}")

print("\n" + "=" * 60)
print("✅ API Testing Complete!")
print("=" * 60)
