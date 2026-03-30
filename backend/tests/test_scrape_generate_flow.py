import time

from fastapi.testclient import TestClient

from app.core.settings import settings
from app.main import app


def test_scrape_then_generate() -> None:
    headers = {"X-API-Key": settings.operational_api_key}

    with TestClient(app) as client:
        # Keep test deterministic: avoid overlap with background scheduler run.
        client.post("/api/scrape/scheduler/stop", headers=headers)

        scrape = None
        last_attempt = None
        for _ in range(12):
            attempt = client.post("/api/scrape/run", headers=headers)
            last_attempt = attempt
            if attempt.status_code == 200:
                scrape = attempt
                break
            assert attempt.status_code == 409
            time.sleep(1)

        scrape = scrape or last_attempt
        assert scrape is not None
        assert scrape.status_code in (200, 409)
        if scrape.status_code == 200:
            assert scrape.json()["run_id"]

        posts = client.get("/api/scraped-posts", headers=headers)
        assert posts.status_code == 200
        payload = posts.json()
        assert len(payload) >= 1

        post_id = payload[0]["id"]
        generated = client.post(
            "/api/generate",
            json={"post_id": post_id, "output_type": "blog"},
            headers=headers,
        )

        assert generated.status_code == 200
        assert generated.json()["type"] == "blog"

        outputs = client.get("/api/outputs", headers=headers)
        assert outputs.status_code == 200
        assert len(outputs.json()) >= 1

        runs = client.get("/api/scrape/runs", headers=headers)
        assert runs.status_code == 200
        assert len(runs.json()) >= 1
