"""Slide copy and caption body: Claude when an API key exists, deterministic fallback otherwise."""
import json
import os
import re

from . import moments as mom
from .util import brand, cfg, settings


def city_for(plan):
    return cfg("regions")[plan["region"]]["city"]


def fill_city(text, plan):
    return text.replace("{city}", city_for(plan))


def fallback_content(plan):
    b = brand()
    topic = plan["topic"]
    title = fill_city(topic["title"], plan)
    points = [fill_city(p, plan) for p in topic["points"]]
    n = plan["n_slides"]
    slides = [{"role": "cover", "headline": title, "body": ""}]
    if n == 1:
        slides[0]["body"] = points[0]
    else:
        body_count = max(n - 2, 0)
        for i in range(body_count):
            p = points[i % len(points)]
            slides.append({"role": "body", "headline": str(i + 1), "body": p})
        slides.append({"role": "cta", "headline": b["booking_card"]["headline"], "body": b["booking_card"]["sub"]})
    hook = ""
    if plan.get("moment"):
        m = next((x for x in cfg("moments") if x["id"] == plan["moment"]), None)
        hook = (m["hook"] + ". ") if m else ""
    caption_body = f"{hook}{title}.\n\n" + "\n".join(f"• {p}" for p in points)
    return {"headline": title, "slides": slides, "caption_body": caption_body,
            "alt_subject": "Photo related to learning, work or writing"}


def _extract_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON in model output")
    return json.loads(m.group(0))


SYSTEM = (
    "You write Instagram content for Our Days & Futures (@growing.connections): premium English teaching, "
    "Business English consulting, learning resources and writing, for professionals in Mexico City, Madrid and Seville. "
    "Voice: warm, precise, practical, never salesy. Rules: no discounts, prices, statistics or testimonials you were not given; "
    "no hashtags; no calls to action in the caption body (a booking line is added later); real, useful teaching content; "
    "short slide text (headline max 8 words, body max 22 words). Return ONLY valid JSON."
)


def llm_content(plan, client, recent_headlines=()):
    s = settings()
    topic = plan["topic"]
    moment = next((x for x in cfg("moments") if x["id"] == plan.get("moment")), None)
    brief = {
        "format": plan["kind"], "slides_including_cover_and_booking_slide": plan["n_slides"],
        "pillar": plan["pillar"], "seed_idea": fill_city(topic["title"], plan), "seed_points": topic["points"],
        "city": city_for(plan), "seasonal_moment": moment["hook"] if moment else None,
        "avoid_repeating": list(recent_headlines)[-15:],
        "schema": {"headline": "str", "slides": [{"role": "cover|body|cta", "headline": "str", "body": "str"}],
                   "caption_body": "str, max 800 chars", "alt_subject": "str, describes the ideal photo"},
    }
    msg = client.messages.create(model=s["text_model"], max_tokens=1500, system=SYSTEM,
                                 messages=[{"role": "user", "content": json.dumps(brief, ensure_ascii=False)}])
    out = _extract_json("".join(getattr(b, "text", "") for b in msg.content))
    if len(out["slides"]) != plan["n_slides"] and plan["n_slides"] > 1:
        raise ValueError("wrong slide count")
    return out


def generate_content(plan, client=None, recent_headlines=()):
    if client is None and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            client = anthropic.Anthropic()
        except Exception:
            client = None
    if client is not None:
        try:
            return llm_content(plan, client, recent_headlines)
        except Exception:
            pass
    return fallback_content(plan)
