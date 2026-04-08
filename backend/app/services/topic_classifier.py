from __future__ import annotations

import json
import re

import httpx

from app.core.settings import settings
from app.services.scraped_data_processor import ScrapedDataProcessor

_ALLOWED_TOPICS = {
    "bra",
    "shapewear",
    "panty",
    "fashion",
    "skincare",
    "hygiene",
    "period-care",
    "other",
}


def _extract_json(text: str) -> dict:
    match = re.search(r"\{[\s\S]*\}", str(text or ""))
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def _normalize_topic(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in _ALLOWED_TOPICS:
        return normalized

    aliases = {
        "period": "period-care",
        "period care": "period-care",
        "intimate hygiene": "hygiene",
        "innerwear": "fashion",
    }
    return aliases.get(normalized, "other")


def _template_classify(title: str, body: str) -> str:
    return _normalize_topic(ScrapedDataProcessor.classify_topic(f"{title} {body}"))


def _classify_with_anthropic(title: str, body: str) -> str:
    payload = {
        "model": settings.anthropic_model,
        "max_tokens": 120,
        "temperature": 0,
        "system": (
            "You classify women's comfort and innerwear content into one of these labels only: "
            "bra, shapewear, panty, fashion, skincare, hygiene, period-care, other. "
            "Return strict JSON only: {\"category\": \"<label>\"}."
        ),
        "messages": [
            {
                "role": "user",
                "content": json.dumps({"title": title[:400], "body": body[:1800]}, ensure_ascii=True),
            }
        ],
    }
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    with httpx.Client(timeout=20) as client:
        response = client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    content = "\n".join(
        str(block.get("text") or "") for block in (data.get("content") or []) if isinstance(block, dict)
    )
    return _normalize_topic(_extract_json(content).get("category", "other"))


def _classify_with_groq(title: str, body: str) -> str:
    payload = {
        "model": settings.groq_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Classify input into exactly one label: bra, shapewear, panty, fashion, skincare, hygiene, "
                    "period-care, other. Return strict JSON only: {\"category\": \"<label>\"}."
                ),
            },
            {
                "role": "user",
                "content": json.dumps({"title": title[:400], "body": body[:1800]}, ensure_ascii=True),
            },
        ],
        "temperature": 0,
        "max_tokens": 120,
    }
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "content-type": "application/json",
    }

    with httpx.Client(timeout=20) as client:
        response = client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    content = str((((data.get("choices") or [{}])[0]).get("message") or {}).get("content") or "")
    return _normalize_topic(_extract_json(content).get("category", "other"))


def classify_post_topic(title: str, body: str) -> str:
    """LLM-first topic classification with deterministic template fallback."""
    provider = (settings.scrape_topic_classifier_provider or "template").strip().lower()

    try:
        if provider == "anthropic" and settings.anthropic_api_key:
            return _classify_with_anthropic(title, body)
        if provider == "groq" and settings.groq_api_key:
            return _classify_with_groq(title, body)
    except Exception:  # noqa: BLE001
        pass

    return _template_classify(title, body)
