from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter

import httpx
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models.scraped_insight import ScrapedInsight
from app.models.scraped_post import ScrapedPost


def _clean(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _sanitize(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text or ""))
    normalized = "".join(ch for ch in normalized if ch.isprintable() or ch in "\n\t")
    return _clean(normalized)


def _extract_json(text: str) -> dict:
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


_TOPIC_RULES: list[tuple[str, tuple[str, ...], str]] = [
    (
        "bra fit and comfort",
        (
            "bra",
            "strap",
            "underwire",
            "cup",
            "band",
            "support",
            "chaf",
            "digging",
            "back pain",
            "shoulder pain",
        ),
        "Bra",
    ),
    (
        "period comfort and leak prevention",
        (
            "period",
            "menstrual",
            "pad",
            "tampon",
            "leak",
            "stain",
            "cramp",
            "bloating",
        ),
        "Period care",
    ),
    (
        "shapewear fit and breathability",
        (
            "shapewear",
            "compression",
            "rolling",
            "seamless",
            "bodysuit",
            "thigh",
            "waist",
            "breathable",
        ),
        "Shapewear",
    ),
    (
        "size and measurement clarity",
        (
            "size",
            "sizing",
            "measurement",
            "inbetween",
            "size chart",
            "return",
            "exchange",
        ),
        "Sizing",
    ),
    (
        "skin-safe fabric and irritation prevention",
        (
            "itch",
            "rash",
            "irritation",
            "sensitive skin",
            "fabric",
            "seam",
            "allergy",
        ),
        "Fabric care",
    ),
]

_PAIN_POINT_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("strap digging", ("strap", "digging", "shoulder")),
    ("support mismatch", ("support", "sag", "bounce")),
    ("size confusion", ("size", "fitting", "fit", "measurement")),
    ("heat and sweat discomfort", ("sweat", "hot", "humidity", "breathable")),
    ("rolling or slipping", ("rolling", "slipping", "ride up")),
    ("leak anxiety", ("leak", "stain", "spotting")),
    ("visibility anxiety under outfits", ("visible", "line", "seam", "silhouette", "outfit")),
    ("post-wash durability concern", ("wash", "shrink", "stretch", "durable", "fade")),
    ("price-value hesitation", ("price", "expensive", "worth", "budget", "value")),
]


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _derive_topic(text: str) -> tuple[str, str, int]:
    best_topic = "general comfort education"
    best_label = "comfort"
    best_score = 0
    for topic, keywords, label in _TOPIC_RULES:
        score = sum(1 for keyword in keywords if keyword in text)
        if score > best_score:
            best_topic = topic
            best_label = label
            best_score = score
    return best_topic, best_label, best_score


def _derive_pain_points(text: str) -> list[str]:
    matched: list[str] = []
    for pain_point, keywords in _PAIN_POINT_RULES:
        if _contains_any(text, keywords):
            matched.append(pain_point)
    if matched:
        return matched[:3]
    return ["fit confusion", "everyday comfort"]


def derive_template_insight(post: ScrapedPost) -> tuple[str, float, list[str], str]:
    title = _sanitize(post.title)
    body = _sanitize(post.body)
    text = f"{title} {body}".lower()

    topic, topic_label, signal_score = _derive_topic(text)
    pain_points = _derive_pain_points(text)
    dominant_pain = pain_points[0]
    secondary_pain = pain_points[1] if len(pain_points) > 1 else "buyer hesitation"

    topic_tokens = Counter(re.findall(r"[a-z]{4,}", text))
    frequent = [token for token, _ in topic_tokens.most_common(8)]
    content_hook = " / ".join(frequent[:2]) if frequent else "real customer stories"

    suggestions = [
        (
            f"Publish a myth-vs-fact explainer on {dominant_pain} for {topic_label.lower()} buyers, "
            "including 3 measurable comfort checks and one clear buying threshold."
        ),
        (
            f"Write a long-form decision checklist addressing {secondary_pain}, structured as "
            "problem signal -> root cause -> fit/fabric test -> purchase action."
        ),
        (
            f"Script a 30-second reel using '{content_hook}' as the opening hook, then show one "
            "before/after comfort test and a direct CTA to shortlist products."
        ),
        (
            "Create a comparison carousel: budget vs premium options with comfort-outcome criteria "
            "(support stability, breathability, movement security, value per wear)."
        ),
    ]

    # Rotate ordering deterministically so one format does not always appear first in previews.
    rotation_seed = sum(ord(ch) for ch in _sanitize(post.url or post.title))
    rotate_by = rotation_seed % len(suggestions)
    suggestions = suggestions[rotate_by:] + suggestions[:rotate_by]

    confidence = min(0.88, 0.52 + (0.06 * min(signal_score, 5)) + (0.03 * min(len(pain_points), 3)))
    rationale = (
        f"Matched {topic_label.lower()} intent with pain signals ({', '.join(pain_points)}) "
        f"and recurring lexical cues: {', '.join(frequent[:4]) if frequent else 'general comfort language'}."
    )
    return topic, confidence, suggestions[: settings.insight_max_suggestions], rationale


def _template_insight(post: ScrapedPost) -> tuple[str, str, float, list[str], str]:
    topic, confidence, suggestions, rationale = derive_template_insight(post)
    return topic, "template", confidence, suggestions, rationale


def _parse_llm_insight(content: str, provider_name: str) -> tuple[str, str, float, list[str], str] | None:
    parsed = _extract_json(content)
    if not parsed:
        return None

    suggestions = [str(s).strip() for s in parsed.get("suggestions", []) if str(s).strip()]
    return (
        _clean(parsed.get("primary_topic") or "other") or "other",
        provider_name,
        float(parsed.get("confidence") or 0.0),
        suggestions[: settings.insight_max_suggestions],
        _clean(parsed.get("rationale") or ""),
    )


def _llm_validate(post: ScrapedPost, provider: str) -> tuple[str, str, float, list[str], str]:
    title = _sanitize(post.title)
    body = _sanitize(post.body)

    # Prompt engineering best practices: explicit role, constraints, output schema, and bounded scope.
    system_prompt = (
        "You are a principal content-intelligence strategist for a women-focused innerwear and comfort brand. "
        "Your job is to convert noisy scraped conversations into high-confidence, conversion-oriented editorial opportunities. "
        "Prioritize actionable insights tied to fit, comfort, climate suitability, confidence, and purchase decision friction. "
        "Always return strict JSON only with no markdown, prose preamble, or trailing commentary."
    )
    user_prompt = (
        "Analyze the following scraped content and produce actionable topic suggestions for a content and merchandising team.\n"
        "Rules:\n"
        "1) Identify the strongest customer intent and pain points that can influence conversion.\n"
        "2) Focus on practical, non-medical guidance. Never make diagnostic or treatment claims.\n"
        "3) Suggestions must be directly executable and include a clear angle plus intended outcome.\n"
        "4) Prefer specificity over generic advice; avoid placeholders and vague wording.\n"
        "5) Return strict JSON with this schema exactly:\n"
        "{\"primary_topic\": string, \"confidence\": number(0..1), \"suggestions\": string[], \"rationale\": string}\n"
        "Output quality constraints:\n"
        "- primary_topic: 3 to 8 words, concrete and editorially usable.\n"
        "- confidence: calibrated to textual evidence strength.\n"
        "- suggestions: 3 to 5 strings, each with format + angle + expected benefit.\n"
        "- rationale: one compact sentence citing observed signals.\n"
        f"Content:\n{json.dumps({'title': title, 'body': body[:6000]}, ensure_ascii=True)}"
    )

    if provider == "anthropic" and settings.anthropic_api_key:
        payload = {
            "model": settings.anthropic_model,
            "max_tokens": 500,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        headers = {
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        with httpx.Client(timeout=30) as client:
            response = client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        content = "\n".join(
            str(block.get("text") or "")
            for block in (data.get("content") or [])
            if isinstance(block, dict)
        )
        parsed = _parse_llm_insight(content, "anthropic")
        if parsed:
            return parsed

    if provider == "groq" and settings.groq_api_key:
        payload = {
            "model": settings.groq_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 500,
        }
        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "content-type": "application/json",
        }
        with httpx.Client(timeout=30) as client:
            response = client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        content = str(
            (((data.get("choices") or [{}])[0]).get("message") or {}).get("content") or ""
        )
        parsed = _parse_llm_insight(content, "groq")
        if parsed:
            return parsed

    return _template_insight(post)


def create_post_insight(db: Session, post: ScrapedPost) -> ScrapedInsight:
    existing = db.query(ScrapedInsight).filter(ScrapedInsight.post_id == post.id).first()
    if existing:
        return existing

    provider = (settings.insight_validator_provider or settings.engine_default_provider or "template").strip().lower()
    topic, provider_used, confidence, suggestions, rationale = _llm_validate(post, provider)

    insight = ScrapedInsight(
        post_id=post.id,
        provider_used=provider_used,
        model_used=(
            settings.anthropic_model
            if provider_used == "anthropic"
            else settings.groq_model
            if provider_used == "groq"
            else "template"
        ),
        confidence=max(0.0, min(1.0, float(confidence))),
        primary_topic=_clean(topic)[:120] or "other",
        suggestions_json=json.dumps(suggestions),
        rationale=_clean(rationale),
    )
    db.add(insight)
    db.flush()
    return insight
