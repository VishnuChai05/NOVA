from datetime import datetime, timezone
import json
import re

from sqlalchemy.orm import Session

from app.models.evaluation_result import EvaluationResult
from app.models.generated_output import GeneratedOutput
from app.models.scraped_post import ScrapedPost


def _extract_signal_points(body: str) -> list[str]:
    sentences = [s.strip() for s in re.split(r"[\n\.!?]+", body or "") if len(s.strip()) > 30]
    points: list[str] = []
    for sentence in sentences[:20]:
        lowered = sentence.lower()
        if any(
            term in lowered
            for term in ["pain", "dig", "sweat", "fit", "support", "leak", "roll", "chafe", "size", "strap", "comfort"]
        ):
            points.append(sentence[:140])
    if not points:
        points = [s[:140] for s in sentences[:5]]
    return points[:6]


def _build_output(post: ScrapedPost, output_type: str) -> tuple[str, str]:
    topic = f"{post.category_tag}: {post.title}"
    signal_points = _extract_signal_points(post.body)
    point_block = "\n".join(f"- {point}" for point in signal_points) or "- Consumers want better comfort and fit confidence."

    if output_type == "blog":
        title = f"The Complete {post.category_tag.title()} Comfort Guide: Fit, Fabric, and Real-Life Solutions"
        content = (
            f"SEO Title: {title}\n"
            f"Meta Description: A practical, body-positive playbook to solve {post.category_tag} comfort problems with clear buying criteria and confident product choices.\n"
            f"Primary Keyword: {post.category_tag} comfort guide\n"
            "Secondary Keywords: breathable innerwear India, support fit checklist, anti-chafe comfort, all-day wear confidence\n\n"
            f"# {title}\n\n"
            "## Search intent snapshot\n"
            f"People searching this topic want practical help that connects comfort problems to purchase decisions. Current topic signal: {topic}.\n\n"
            f"## Why this topic matters\nWomen across communities are discussing: {topic}.\n\n"
            "## What women are actually struggling with\n"
            f"{point_block}\n\n"
            "## Root-cause diagnostics (before buying)\n"
            "- Fit architecture mismatch between body movement and garment structure\n"
            "- Fabric choice that ignores heat, humidity, and long-hour wear\n"
            "- Weak support distribution causing digging, pressure, or roll-down\n"
            "- Product messaging that sounds attractive but lacks measurable comfort checks\n\n"
            "## Root causes to check before buying\n"
            "1. Wrong band or base size causes pressure and shoulder load.\n"
            "2. Fabric mismatch for local climate creates sweat and irritation.\n"
            "3. Strap/cup mismatch creates movement, digging, or rolling.\n"
            "4. Occasion mismatch (office, commute, event) causes all-day discomfort.\n\n"
            "## Technical fit and fabric checklist\n"
            "1. Support map: verify where support is distributed (under-bust, side panel, strap) and where pressure concentrates.\n"
            "2. Breathability map: prioritize airflow and moisture movement for warm climates and commute-heavy routines.\n"
            "3. Recovery behavior: test shape retention after 6-8 hours and after wash cycles.\n"
            "4. Friction points: check seams and edge construction in high-movement zones.\n\n"
            "## Buying checklist (save this)\n"
            "1. Do a 6-hour comfort test, not just a trial-room test.\n"
            "2. Check under-bust support without deep marks.\n"
            "3. Confirm fabric breathability for warm days.\n"
            "4. Test movement: bend, stretch, walk fast, sit long.\n"
            "5. Prefer size-inclusive options and exchange-friendly brands.\n\n"
            "## Product shortlisting framework\n"
            "Score each option from 1-5 across support stability, skin comfort, movement security, climate suitability, and value-per-wear.\n"
            "Pick winners only if they score at least 4 in support and climate suitability.\n\n"
            "## Product direction for Indian conditions\n"
            "- Lightweight support for humid weather\n"
            "- Seam-minimized construction for long wear\n"
            "- Skin-safe soft-touch fabric blends\n"
            "- Inclusive grading across body types\n\n"
            "## Frequently asked objections\n"
            "- 'Will this feel too tight by afternoon?' -> Use movement and pressure checks, not static fitting alone.\n"
            "- 'Is premium pricing worth it?' -> Compare durability and comfort retention per wear, not tag price only.\n"
            "- 'What if my fit changes across cycles?' -> Keep two fit-intent options and rotate by comfort state.\n\n"
            "## Content CTA\n"
            "Use this guide to shortlist products and compare fit outcomes, not just style claims.\n"
            "Explore options at https://ohsou.com\n"
        )
        return title, content

    if output_type == "reel":
        title = f"Reel Script: {post.category_tag.title()} Fixes"
        content = (
            "Runtime target: 30 seconds\n"
            "Hook (0-3s): If your support fails by lunch, your fit strategy is broken.\n"
            "Beat 1 (4-9s): Show real movement test and where discomfort appears.\n"
            "Beat 2 (10-16s): Explain one fit correction and one fabric correction.\n"
            "Beat 3 (17-24s): Show confidence shift with stable support and breathability.\n"
            "Close (25-30s): Comfort is not compromise. It is your baseline.\n"
            "CTA: Build your comfort shortlist at ohsou.com\n"
            "On-screen text: Fit check > Fabric check > Movement check > Repeat\n"
            "Hashtags: #InnerwearIndia #BodyPositive #ComfortFirst #BraFit #Shapewear #StyleTips #Ohsou #WomenWellness\n"
        )
        return title, content

    title = f"Detailed Product Suggestions: {post.category_tag.title()} Comfort Series"
    content = (
        f"Customer Signal: {post.title}\n"
        f"Evidence from scraped content:\n{point_block}\n\n"
        "Product Suggestion 1: Everyday Climate-Smart Support\n"
        "- Target user: long commute + office wear + high movement day\n"
        "- Fit architecture: stable under-band support with anti-dig strap geometry\n"
        "- Material direction: breathable moisture-managed blend with soft skin-contact finish\n"
        "- Price band: mid-tier (core volume driver)\n"
        "- Why now: recurring comfort + sweat complaints in warm urban conditions\n"
        "- Validation metric: >=4/5 comfort retention after 6-hour wear test\n\n"
        "Product Suggestion 2: Occasion-Ready Invisible Layer\n"
        "- Target user: saree/gown/fitted outfit occasions requiring profile confidence\n"
        "- Fit architecture: anti-slip anchor points with smooth-edge seam strategy\n"
        "- Material direction: low-profile stretch fabric balancing hold and breathability\n"
        "- Price band: premium\n"
        "- Why now: strong demand for secure support without visible lines\n"
        "- Validation metric: no roll/slip events during 3-hour movement simulation\n\n"
        "Product Suggestion 3: Recovery and Lounge Comfort Line\n"
        "- Target user: postpartum or home-first routines prioritizing pressure relief\n"
        "- Fit architecture: non-restrictive support zones with soft edge construction\n"
        "- Material direction: skin-calming touch blend with low-friction interior\n"
        "- Price band: affordable-mid\n"
        "- Why now: repeated need for all-day gentle support without stiffness\n"
        "- Validation metric: reduced pressure-mark feedback in first 2-week pilot\n\n"
        "Product Suggestion 4: Adaptive Size-Confidence Capsule\n"
        "- Target user: shoppers with periodic fit variation and size uncertainty\n"
        "- Fit architecture: adaptive stretch zones with structured support checkpoints\n"
        "- Material direction: resilient knit with shape recovery after wash\n"
        "- Price band: mid-premium\n"
        "- Why now: high return risk from fit confusion and inconsistent sizing journeys\n"
        "- Validation metric: lower size-exchange rate vs baseline category average\n\n"
        "Merchandising and Growth Notes:\n"
        "- Bundle by use-case (workday, occasion, recovery, adaptive sizing)\n"
        "- Include visual fit scorecards and quick decision checklists in PDPs\n"
        "- Pair each product with one educational short-form content piece\n"
        "- Use comfort-outcome messaging and exchange confidence to lift conversion\n"
    )
    return title, content


def evaluate_output(title: str, content: str) -> tuple[float, str]:
    """Score generated content on multiple quality dimensions. Returns (score, rubric_json)."""
    lower_content = content.lower()
    sentences = [s.strip() for s in content.replace("\n", ". ").split(".") if s.strip()]
    lines = [ln for ln in content.split("\n") if ln.strip()]

    rubric: dict[str, dict] = {}

    # 1. Title quality
    title_len = len(title.strip())
    rubric["title_quality"] = {
        "pass": 10 <= title_len <= 200,
        "detail": f"length={title_len}",
        "weight": 0.10,
    }

    # 2. Has a call-to-action
    cta_keywords = ["cta", "explore", "visit", "try", "shop", "discover", "learn more", "check out"]
    has_cta = any(kw in lower_content for kw in cta_keywords)
    rubric["has_cta"] = {"pass": has_cta, "weight": 0.10}

    # 3. Brand mention
    has_brand = "ohsou" in lower_content or "oh so u" in lower_content or "nova" in lower_content
    rubric["brand_mention"] = {"pass": has_brand, "weight": 0.10}

    # 4. Readability — average sentence length (ideal: 12-25 words)
    avg_sentence_words = (
        sum(len(s.split()) for s in sentences) / max(1, len(sentences))
    )
    readable = 8 <= avg_sentence_words <= 30
    rubric["readability"] = {
        "pass": readable,
        "detail": f"avg_words_per_sentence={avg_sentence_words:.1f}",
        "weight": 0.15,
    }

    # 5. Structure — has at least 2 header-like lines (lines starting with H1/H2/Section/Part or ending with :)
    header_patterns = ["h1:", "h2:", "h3:", "section", "part ", "##", "**"]
    header_count = sum(
        1 for ln in lines
        if any(ln.lower().strip().startswith(p) for p in header_patterns) or ln.strip().endswith(":")
    )
    rubric["structure"] = {
        "pass": header_count >= 2,
        "detail": f"headers_found={header_count}",
        "weight": 0.15,
    }

    # 6. Content length (at least 150 chars for blog, 80 for reel)
    content_len = len(content.strip())
    rubric["content_length"] = {
        "pass": content_len >= 100,
        "detail": f"chars={content_len}",
        "weight": 0.15,
    }

    # 7. Keyword relevance — mentions product/comfort/women context
    relevance_terms = ["comfort", "product", "women", "fit", "support", "quality", "review", "recommend"]
    relevance_hits = sum(1 for t in relevance_terms if t in lower_content)
    rubric["keyword_relevance"] = {
        "pass": relevance_hits >= 2,
        "detail": f"hits={relevance_hits}/{len(relevance_terms)}",
        "weight": 0.15,
    }

    # 8. Formatting variety — uses multiple line types (not a wall of text)
    rubric["formatting"] = {
        "pass": len(lines) >= 4,
        "detail": f"lines={len(lines)}",
        "weight": 0.10,
    }

    # Weighted aggregate
    score = sum(
        dim["weight"] for dim in rubric.values() if dim["pass"]
    )
    score = round(min(1.0, score), 2)

    return score, json.dumps(rubric)


def generate_output(db: Session, post_id: str, output_type: str, evaluator_model: str) -> GeneratedOutput:
    post = db.query(ScrapedPost).filter(ScrapedPost.id == post_id).first()
    if not post:
        raise ValueError("Post not found")

    title, content = _build_output(post, output_type)
    output = GeneratedOutput(
        post_id=post.id,
        output_type=output_type,
        title=title,
        content=content,
        status="draft",
        generated_at=datetime.now(timezone.utc),
    )
    db.add(output)
    db.flush()

    score, rubric = evaluate_output(title, content)
    db.add(
        EvaluationResult(
            output_id=output.id,
            evaluator_model=evaluator_model,
            score=score,
            rubric_json=rubric,
        )
    )

    post.processed = True
    db.commit()
    db.refresh(output)
    return output
