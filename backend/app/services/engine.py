from __future__ import annotations

from app.schemas.engine import BlogMakerRequest, ProductRangeRequest, ScriptGeneratorRequest


def _clean(text: str) -> str:
    return " ".join(text.split()).strip()


def run_blog_maker(payload: BlogMakerRequest) -> tuple[str, str]:
    keyword = _clean(payload.seo_focus_keyword)
    audience = _clean(payload.target_audience)
    brief = _clean(payload.brief)

    title = f"{payload.brand_name} Blog Blueprint: {keyword.title()}"
    content = (
        f"SEO Keyword: {keyword}\n"
        f"Audience: {audience}\n"
        f"Working Brief: {brief}\n\n"
        "H1: A Comfort-First Guide for Indian Women\n"
        "Meta Description: Real product guidance, fit solutions, and confidence-forward styling for daily Indian life.\n\n"
        "Section 1 - Real Problem Statement\n"
        "Translate the user pain into daily contexts: commute heat, long office wear, and festive layering.\n\n"
        "Section 2 - Product Review Lens\n"
        "Review products using 5 anchors: fabric breathability, support consistency, skin feel, wash durability, and value.\n\n"
        "Section 3 - Smart Buying Framework\n"
        "Give clear suggestions by body need, outfit use-case, and weather adaptability.\n\n"
        "Section 4 - Issue Resolution\n"
        "Cover red marks, rolling waistbands, strap slip, cup gaping, and chafing with direct fixes.\n\n"
        f"CTA: Explore curated solutions at https://ohsou.com/ under {payload.brand_name} essentials."
    )
    return title, content


def run_script_generator(payload: ScriptGeneratorRequest) -> tuple[str, str]:
    audience = _clean(payload.target_audience)
    brief = _clean(payload.brief)
    goal = _clean(payload.campaign_goal)

    title = f"{payload.brand_name} Production Script Pack ({goal.title()})"
    content = (
        f"Audience: {audience}\n"
        f"Campaign Goal: {goal}\n"
        f"Creative Brief: {brief}\n\n"
        "PART A - STORY (Narrative Arc)\n"
        "A young woman moves through a full day from commute to work to evening plans, choosing comfort without compromise.\n"
        "Conflict: products fail at long-hour comfort.\n"
        "Resolution: fit-intelligent, breathable, confidence-boosting essentials.\n\n"
        "PART B - SCRIPT (Dialogue + Voiceover)\n"
        "Hook VO: Comfort is not a luxury. It is your baseline.\n"
        "Beat 1: Morning rush, fast wardrobe choice, calm confidence.\n"
        "Beat 2: Midday movement test, no-adjust experience.\n"
        "Beat 3: Evening transition, same comfort, sharper style.\n"
        "Close VO: Designed for real Indian days. Made by oh so u.\n\n"
        "PART C - SCREENPLAY (Shot List + Direction)\n"
        "Shot 1: Wide morning room light, handheld energy, 3 sec.\n"
        "Shot 2: Mirror fit check macro details, 4 sec.\n"
        "Shot 3: City commute tracking shot, 5 sec.\n"
        "Shot 4: Office desk sit-stand movement, 5 sec.\n"
        "Shot 5: Evening warm tones, layered outfit reveal, 4 sec.\n"
        "Shot 6: Product + brand lockup, 3 sec.\n\n"
        "PART D - EXPLAINER (Why This Works)\n"
        "This pack is engineered for production: clear conflict, daily-life relevance, visual continuity, and direct product proof moments.\n"
        "It can be used for short-form reels, ad films, and PDP story clips with minimal rewrites."
    )
    return title, content


def run_product_range_engine(payload: ProductRangeRequest) -> tuple[str, str]:
    audience = _clean(payload.target_audience)
    brief = _clean(payload.brief)
    catalog = _clean(payload.current_catalog_summary)

    title = f"{payload.brand_name} Range Expansion Plan"
    content = (
        f"Audience: {audience}\n"
        f"Current Catalog: {catalog}\n"
        f"Research Brief: {brief}\n\n"
        "Portfolio Gap Map\n"
        "1. Climate-adaptive comfort line for humid long-wear days.\n"
        "2. Sensitive-skin line with anti-chafe seam architecture.\n"
        "3. Occasion-smart line for saree, kurti, and western silhouettes.\n\n"
        "New Product Concepts\n"
        "- Everyday AirFlex Bra: breathable knit, anti-slip straps, inclusive cup-depth variants.\n"
        "- Motion-Safe Period Briefs: leak-protection tiers for commute, office, and overnight.\n"
        "- SculptLite Shapewear: targeted support zones with low-heat fabric strategy.\n"
        "- Comfort-First Intimate Care Kit: wash, storage, and skin-calming accessories.\n\n"
        "Range Growth Strategy\n"
        "- Launch by need-state collections (Workday, Occasion, Recovery).\n"
        "- Build a review-led roadmap using recurring pain points from Reddit/Quora.\n"
        "- Use fit education bundles to improve conversion and reduce returns.\n\n"
        "90-Day Action Plan\n"
        "Week 1-2: concept validation and material shortlist.\n"
        "Week 3-6: prototyping and wear testing cohorts.\n"
        "Week 7-10: pilot launch in hero sizes and key shades.\n"
        "Week 11-12: optimize by review insights and restock winners."
    )
    return title, content
