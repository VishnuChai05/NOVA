#!/usr/bin/env python
"""Get detailed failure logs from the latest scrape run."""

import sys
import json
sys.path.insert(0, "backend")

from fastapi.testclient import TestClient
from app.main import app

print("=" * 60)
print("DETAILED SCRAPER DIAGNOSTICS")
print("=" * 60)

client = TestClient(app)

# Get scrape runs
response = client.get("/api/scrape/runs")
runs = response.json()

if runs:
    latest = runs[0]
    
    print(f"\n📊 Latest Run:")
    print(f"  Run ID: {latest.get('id')}")
    print(f"  Status: {latest.get('status')}")
    print(f"  Fetched: {latest.get('total_fetched')}")
    print(f"  Created: {latest.get('total_created')}")
    
    # Parse and display source stats
    stats_raw = latest.get('source_stats_json', '{}')
    if isinstance(stats_raw, str):
        stats = json.loads(stats_raw)
    else:
        stats = stats_raw
    
    print(f"\n📈 Source Statistics:")
    for source, data in stats.items():
        fetched = data.get('fetched', 0)
        failed = data.get('failed', 0)
        print(f"  {source}:")
        print(f"    Fetched: {fetched}")
        print(f"    Failed: {failed}")
    
    # Parse and display failures
    failures_raw = latest.get('failures_json', '[]')
    if isinstance(failures_raw, str):
        failures = json.loads(failures_raw)
    else:
        failures = failures_raw
    
    if failures:
        print(f"\n❌ Failures ({len(failures)}):")
        for failure in failures[:10]:  # Show first 10
            print(f"  - {failure}")
        if len(failures) > 10:
            print(f"  ... and {len(failures) - 10} more")
    else:
        print(f"\n✅ No failures recorded")
        
    # Show timestamps
    print(f"\n⏱️ Timing:")
    print(f"  Started: {latest.get('started_at')}")
    print(f"  Finished: {latest.get('finished_at')}")
else:
    print("No scrape runs found")

print("\n" + "=" * 60)
