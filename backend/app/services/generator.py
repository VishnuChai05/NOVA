from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.evaluation_result import EvaluationResult
from app.models.generated_output import GeneratedOutput
from app.models.scraped_post import ScrapedPost


def _build_output(post: ScrapedPost, output_type: str) -> tuple[str, str]:
    topic = f"{post.category_tag}: {post.title}"

    if output_type == "blog":
        title = f"How to Solve {post.category_tag.title()} Comfort Issues: A Guide for Indian Women"
        content = (
            f"SEO Title: {title}\n"
            f"Meta Description: Practical body-positive advice for {post.category_tag} concerns.\n"
            f"Intro: Women across communities are discussing {topic}.\n"
            "H2: Why this issue matters\n"
            "H2: What to look for before buying\n"
            "H2: Everyday comfort checklist\n"
            "CTA: Explore options at https://ohsou.com\n"
        )
        return title, content

    if output_type == "reel":
        title = f"Reel Script: {post.category_tag.title()} Fixes"
        content = (
            "Hook: If your innerwear feels wrong by lunch, this is for you.\n"
            "Script: Real comfort starts with fit, fabric, and confidence.\n"
            "CTA: Try your best fit at ohsou.com\n"
            "Hashtags: #InnerwearIndia #BodyPositive #ComfortFirst #BraFit #Shapewear #StyleTips #Ohsou #WomenWellness\n"
        )
        return title, content

    title = f"Product Idea: {post.category_tag.title()} Comfort Series"
    content = (
        f"Pain Point: {post.title}\n"
        "Concept: Light-support product designed for long wear in Indian weather.\n"
        "Use Case: Daily commute + office + occasion layering.\n"
        "Differentiation: Breathable seamless blend and size-inclusive grading.\n"
        "Priority: High\n"
    )
    return title, content


def evaluate_output(title: str, content: str) -> tuple[float, str]:
    # Deterministic baseline evaluator for scaffolding; replace with model-based rubric scorer.
    score = 0.0
    checks = {
        "has_title": bool(title.strip()),
        "mentions_ohsou": "ohsou" in content.lower(),
        "body_positive_tone": "comfort" in content.lower() or "body-positive" in content.lower(),
    }

    score = round(sum(1.0 for ok in checks.values() if ok) / len(checks), 2)
    rubric = str(checks)
    return score, rubric


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
