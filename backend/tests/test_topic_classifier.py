from __future__ import annotations

from app.services.topic_classifier import classify_post_topic


def test_classify_post_topic_template_fallback(monkeypatch) -> None:
    monkeypatch.setattr("app.services.topic_classifier.settings.scrape_topic_classifier_provider", "template")

    label = classify_post_topic(
        "Need a comfortable sports bra for office commute",
        "The straps dig in and I need better support and breathable fit for long hours.",
    )

    assert label == "bra"


def test_classify_post_topic_groq_parses_json(monkeypatch) -> None:
    monkeypatch.setattr("app.services.topic_classifier.settings.scrape_topic_classifier_provider", "groq")
    monkeypatch.setattr("app.services.topic_classifier.settings.groq_api_key", "test-key")

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"category":"period-care"}'
                        }
                    }
                ]
            }

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def post(self, url, headers=None, json=None):
            assert "groq" in url
            return FakeResponse()

    monkeypatch.setattr("app.services.topic_classifier.httpx.Client", lambda timeout=20: FakeClient())

    label = classify_post_topic("period cramps and leaks", "Need better pad comfort and period confidence")
    assert label == "period-care"


def test_classify_post_topic_llm_failure_falls_back(monkeypatch) -> None:
    monkeypatch.setattr("app.services.topic_classifier.settings.scrape_topic_classifier_provider", "groq")
    monkeypatch.setattr("app.services.topic_classifier.settings.groq_api_key", "test-key")

    class FailingClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def post(self, url, headers=None, json=None):
            raise RuntimeError("provider down")

    monkeypatch.setattr("app.services.topic_classifier.httpx.Client", lambda timeout=20: FailingClient())

    label = classify_post_topic(
        "How to pick shapewear for saree",
        "Rolling and breathability issues with current shapewear options",
    )
    assert label == "shapewear"
