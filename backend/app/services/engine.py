from __future__ import annotations

import json
import re
import unicodedata

import httpx

from app.core.settings import settings
from app.schemas.engine import BlogMakerRequest, ProductRangeRequest, ScriptGeneratorRequest


def _clean(text: str) -> str:
    return " ".join(text.split()).strip()


_PROMPT_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bignore\s+(all\s+)?previous\s+instructions\b", re.IGNORECASE),
    re.compile(r"\bdisregard\s+(all\s+)?(prior|previous)\s+instructions\b", re.IGNORECASE),
    re.compile(r"\b(system|developer)\s+prompt\b", re.IGNORECASE),
    re.compile(r"\bjailbreak\b", re.IGNORECASE),
    re.compile(r"\bdo\s+anything\s+now\b", re.IGNORECASE),
    re.compile(r"<\|.*?\|>", re.IGNORECASE),
    re.compile(r"```", re.IGNORECASE),
)


def _sanitize_user_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text or ""))
    # Remove non-printable controls but keep common whitespace.
    normalized = "".join(ch for ch in normalized if ch.isprintable() or ch in "\n\t")
    cleaned = _clean(normalized)

    for pattern in _PROMPT_INJECTION_PATTERNS:
        if pattern.search(cleaned):
            raise ValueError("Potential prompt injection detected in request text")

    return cleaned


def _resolve_provider(requested: str) -> str:
    candidate = (requested or settings.engine_default_provider or "template").strip().lower()
    if candidate in {"template", "anthropic", "groq"}:
        return candidate
    return "template"


def _anthropic_generate(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int = 1200,
    temperature: float = 0.4,
) -> str:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    payload = {
        "model": settings.anthropic_model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    with httpx.Client(timeout=45) as client:
        response = client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    blocks = data.get("content") or []
    text_chunks = [str(block.get("text") or "") for block in blocks if isinstance(block, dict)]
    return "\n".join(chunk for chunk in text_chunks if chunk).strip()


def _groq_generate(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int = 1200,
    temperature: float = 0.4,
) -> str:
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not set")

    payload = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=45) as client:
        response = client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return str(message.get("content") or "").strip()


def _generate_with_provider(
    provider: str,
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int,
    temperature: float,
) -> str:
    if provider == "anthropic":
        return _anthropic_generate(
            system_prompt,
            user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    if provider == "groq":
        return _groq_generate(
            system_prompt,
            user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    return ""


def _build_content(
    *,
    requested_provider: str,
    system_prompt: str,
    user_prompt: str,
    fallback_content: str,
    generation_max_tokens: int,
    generation_temperature: float,
) -> tuple[str, str, bool]:
    provider = _resolve_provider(requested_provider)
    if provider == "template":
        return fallback_content, provider, False

    try:
        generated = _generate_with_provider(
            provider,
            system_prompt,
            user_prompt,
            max_tokens=generation_max_tokens,
            temperature=generation_temperature,
        )
    except (httpx.HTTPStatusError, httpx.TimeoutException, RuntimeError) as exc:
        fallback_note = "\n\nProvider fallback reason: provider unavailable"
        return f"{fallback_content}{fallback_note}", provider, True

    if not generated:
        return f"{fallback_content}\n\nProvider fallback reason: empty model response", provider, True

    return generated, provider, False


def run_blog_maker(payload: BlogMakerRequest) -> tuple[str, str, str, bool]:
    keyword = _sanitize_user_text(payload.seo_focus_keyword)
    audience = _sanitize_user_text(payload.target_audience)
    brief = _sanitize_user_text(payload.brief)
    brand_name = _sanitize_user_text(payload.brand_name)

    title = f"{brand_name} Blog Blueprint: {keyword.title()}"
    fallback_content = (
        f"SEO Keyword: {keyword}\n"
        f"Audience: {audience}\n"
        f"Working Brief: {brief}\n\n"
        f"SEO Title: {brand_name} Comfort Playbook for {keyword.title()}\n"
        "Meta Description: A practical long-form guide to solve real fit and comfort issues with confident product decisions.\n"
        "Primary Keyword: " + keyword + "\n"
        "Secondary Keywords: comfort fit guide India, breathable innerwear, all-day support, size confidence\n\n"
        "# Comfort-First Strategy Guide\n\n"
        "## Search Intent and Reader Promise\n"
        "The reader wants practical clarity, not generic claims. Promise specific fit, fabric, and usage guidance for long-day comfort.\n\n"
        "## Real Problems to Solve\n"
        "- Shoulder pressure from incorrect straps\n"
        "- Band and cup mismatch across activity levels\n"
        "- Heat and sweat discomfort in Indian weather\n"
        "- Product confusion due to unclear comparison language\n\n"
        "## Product Review Framework\n"
        "Use this scorecard for each recommendation: support stability, fabric airflow, skin comfort, movement retention, and value-per-wear.\n"
        "Give what-to-check signs, red flags, and ideal outcomes for each criterion.\n\n"
        "## Buying Blueprint by Use Case\n"
        "1. Office and commute: low-adjust, breathable support\n"
        "2. Occasion wear: profile control with zero-slip confidence\n"
        "3. Home and recovery: soft structure and pressure relief\n"
        "4. High movement days: anchor points that hold without digging\n\n"
        "## Technical Product Direction\n"
        "Recommend seam strategy, strap architecture, cup construction, and fabric blend logic with climate-aware reasoning.\n\n"
        "## FAQ and Objection Handling\n"
        "Answer cost-value concerns, fit uncertainty, and return anxiety with direct practical guidance.\n\n"
        f"## Brand-Aligned CTA\nExplore comfort-first solutions from {brand_name} at https://ohsou.com with a fit-first shortlist."
    )
    system_prompt = (
        "You are a Senior Editorial Director, SEO Strategist, and Conversion Copy Lead for an Indian women's comfort and intimatewear brand. "
        "Write detailed long-form editorial content that combines search intent, trust-building education, and conversion-ready product clarity. "
        "You must preserve a warm, empowering, body-positive voice and avoid unsafe medical claims or fear-based wording. "
        "Use practical language grounded in Indian climate, daily movement, and real wardrobe scenarios. "
        "Every section should drive decision confidence through concrete checks, comparisons, and actionable next steps."
    )
    user_prompt = (
        "Create a high-detail, long-form blog blueprint.\n"
        "Hard requirements:\n"
        "1) Length target: 900-1400 words.\n"
        "2) Output plain text only. Use clear H2/H3 headings and short paragraphs.\n"
        "3) Include this exact high-level structure:\n"
        "   - SEO package: SEO Title (50-65 chars), Meta Description (145-160 chars), Primary Keyword, 4-6 Secondary Keywords\n"
        "   - Hook with emotional tension + practical promise\n"
        "   - Pain-point diagnosis grounded in audience context\n"
        "   - Product review framework with measurable checks\n"
        "   - Use-case buying paths (office, occasion, recovery, high movement)\n"
        "   - Technical fabric and fit guidance for Indian weather\n"
        "   - Objection handling and FAQ\n"
        "   - Strong but non-pushy brand CTA\n"
        "4) Keep advice concrete: include checklists, comparison language, and decision criteria.\n"
        "5) Avoid generic filler and avoid unsupported health claims.\n"
        "6) Make brand mention natural and trust-led, not hard sell.\n"
        f"Context JSON:\n{json.dumps({'brand': brand_name, 'brief': brief, 'audience': audience, 'keyword': keyword}, indent=2)}"
    )
    content, provider_used, used_fallback = _build_content(
        requested_provider=payload.llm_provider,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        fallback_content=fallback_content,
        generation_max_tokens=2200,
        generation_temperature=0.42,
    )
    return title, content, provider_used, used_fallback


def run_script_generator(payload: ScriptGeneratorRequest) -> tuple[str, str, str, bool]:
    audience = _sanitize_user_text(payload.target_audience)
    brief = _sanitize_user_text(payload.brief)
    goal = _sanitize_user_text(payload.campaign_goal)
    brand_name = _sanitize_user_text(payload.brand_name)

    title = f"{brand_name} Production Script Pack ({goal.title()})"
    fallback_content = (
        f"Audience: {audience}\n"
        f"Campaign Goal: {goal}\n"
        f"Creative Brief: {brief}\n\n"
        "PART A - Narrative Arc\n"
        "Lead with a specific discomfort moment that immediately signals audience relevance.\n"
        "Escalate to social and emotional cost (self-conscious adjustment, lost confidence, wardrobe compromise).\n"
        "Resolve with product-backed relief and visible confidence shift.\n\n"
        "PART B - Script + Dialogue\n"
        "Hook (0-3 sec): one line that reframes comfort as power.\n"
        "Body (4-22 sec): 4-6 beats combining visual proof and concise voiceover lines.\n"
        "Close (23-30 sec): one memorable benefit stack + direct CTA.\n"
        "Include optional on-screen text overlays for each beat.\n\n"
        "PART C - Screenplay + Shot Plan\n"
        "Provide shot-by-shot plan with timing, angle, movement, framing, and lighting mood.\n"
        "Include wardrobe notes, prop notes, and one alternate low-budget shot path.\n\n"
        "PART D - Creative Explainer\n"
        "Explain why this concept will convert: audience psychology, trust cue design, and platform fit.\n"
        "Add a short testing matrix with 2 hook variants and 2 CTA variants for A/B launch."
    )
    system_prompt = (
        "You are a high-performance Creative Director and short-form conversion script architect for Indian D2C intimatewear brands. "
        "You build production-ready scripts that combine emotional hook, product proof, and sales intent without sounding ad-heavy. "
        "Your output must be cinematic, practical for real production teams, and optimized for Reels/Shorts watch retention. "
        "Prioritize visual specificity, hook strength, pacing clarity, and confidence-led storytelling rooted in real wear scenarios."
    )
    user_prompt = (
        "Generate a production-ready script pack in plain text.\n"
        "Hard requirements:\n"
        "1) Target runtime: 25-35 seconds.\n"
        "2) Exactly 4 sections in this order: Narrative Arc, Script and Dialogue, Screenplay, Director Explainer.\n"
        "3) Include hook options, on-screen text options, and CTA options that can be tested.\n"
        "4) Each beat must map to one clear visual proof point.\n"
        "5) Tone: empowering, stylish, practical, and culturally grounded for Indian urban and semi-urban audiences.\n"
        "6) Avoid generic marketing language. Prefer concrete visual/action instructions.\n"
        f"Context JSON:\n{json.dumps({'brand': brand_name, 'brief': brief, 'audience': audience, 'goal': goal}, indent=2)}"
    )
    content, provider_used, used_fallback = _build_content(
        requested_provider=payload.llm_provider,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        fallback_content=fallback_content,
        generation_max_tokens=1900,
        generation_temperature=0.62,
    )
    return title, content, provider_used, used_fallback


def run_product_range_engine(payload: ProductRangeRequest) -> tuple[str, str, str, bool]:
    audience = _sanitize_user_text(payload.target_audience)
    brief = _sanitize_user_text(payload.brief)
    catalog = _sanitize_user_text(payload.current_catalog_summary)
    brand_name = _sanitize_user_text(payload.brand_name)

    title = f"{brand_name} Range Expansion Plan"
    fallback_content = (
        f"Audience: {audience}\n"
        f"Current Catalog: {catalog}\n"
        f"Research Brief: {brief}\n\n"
        "Market Gap Thesis\n"
        "1. Existing assortments under-serve humid, long-wear, movement-heavy routines.\n"
        "2. Shoppers need clearer fit-intent pathways by body shape and outfit use case.\n"
        "3. Period-care and recovery comfort remain underserved in style-led catalogs.\n\n"
        "New Product Concepts\n"
        "Concept 1: Climate-Control Everyday Support\n"
        "- Feature stack: moisture-managed knit, anti-dig strap geometry, shape-stable cup frame\n"
        "- Price logic: core mid-tier with premium fabric upgrade variant\n"
        "- Merchandising: daily wear bundle with fit-check guide\n\n"
        "Concept 2: Occasion Confidence Line\n"
        "- Feature stack: low-profile support architecture, anti-slip anchor design, smooth-edge seams\n"
        "- Price logic: premium capsule for festive and event wear\n"
        "- Merchandising: outfit-based recommendation rails\n\n"
        "Concept 3: Period and Recovery Comfort Capsule\n"
        "- Feature stack: soft compression zones, irritation-safe fabric touches, movement-safe absorbency options\n"
        "- Price logic: entry-mid affordability with multipack economics\n"
        "- Merchandising: lifecycle bundles and educational content pairing\n\n"
        "Go-To-Market Strategy\n"
        "- Position by pain-state and use-case, not only product category.\n"
        "- Build conversion assets: fit matrix, comfort scorecards, wear-time proofs.\n"
        "- Reduce returns through pre-purchase sizing pathways and expectation framing.\n\n"
        "90-Day Rollout\n"
        "Weeks 1-2: insight synthesis + concept prioritization\n"
        "Weeks 3-5: material sourcing + prototype sprint\n"
        "Weeks 6-8: wear tests across climate and activity scenarios\n"
        "Weeks 9-10: pilot drop + creator education kit\n"
        "Weeks 11-12: review loop, SKU refinement, and scale plan"
    )
    system_prompt = (
        "You are a VP of Product Strategy and Category Innovation for an Indian women's comfortwear and intimatewear brand. "
        "Produce executive-ready plans that connect customer pain signals to launchable product architecture. "
        "Your recommendations must be technically grounded, commercially practical, and tuned for Indian climate, fit diversity, and occasion behavior. "
        "Use clear prioritization logic, price-tier thinking, and launch sequencing that a product and growth team can execute immediately."
    )
    user_prompt = (
        "Design a comprehensive product-range expansion strategy in plain text.\n"
        "Hard requirements:\n"
        "1) Cover four sections in this exact order: Market Gap Thesis, New Product Concepts, Go-To-Market Strategy, 90-Day Execution Rollout.\n"
        "2) Provide at least 3 concrete concepts; each must include target user, technical construction, material direction, use-case fit, price-band logic, and risk notes.\n"
        "3) Explicitly map each concept to a demand signal or catalog gap.\n"
        "4) Include conversion and retention considerations (bundles, education assets, return-risk mitigation).\n"
        "5) Keep recommendations realistic for staged rollout and budget-aware decisions.\n"
        f"Context JSON:\n{json.dumps({'brand': brand_name, 'brief': brief, 'audience': audience, 'catalog': catalog}, indent=2)}"
    )
    content, provider_used, used_fallback = _build_content(
        requested_provider=payload.llm_provider,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        fallback_content=fallback_content,
        generation_max_tokens=2100,
        generation_temperature=0.5,
    )
    return title, content, provider_used, used_fallback
