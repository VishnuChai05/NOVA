from fastapi.testclient import TestClient

from app.main import app


def test_scrape_then_generate() -> None:
    with TestClient(app) as client:
        scrape = client.post("/api/scrape/run")
        assert scrape.status_code == 200
        assert scrape.json()["run_id"]

        posts = client.get("/api/scraped-posts")
        assert posts.status_code == 200
        payload = posts.json()
        assert len(payload) >= 1

        post_id = payload[0]["id"]
        generated = client.post("/api/generate", json={"post_id": post_id, "output_type": "blog"})

        assert generated.status_code == 200
        assert generated.json()["type"] == "blog"

        outputs = client.get("/api/outputs")
        assert outputs.status_code == 200
        assert len(outputs.json()) >= 1

        runs = client.get("/api/scrape/runs")
        assert runs.status_code == 200
        assert len(runs.json()) >= 1
