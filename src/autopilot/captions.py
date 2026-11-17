"""Caption building and validation: <=5 hashtags, ends with a booking call, alt text."""
import random
import re

from .util import brand, cfg, settings

HASHTAG_RE = re.compile(r"#\w+", re.UNICODE)


def strip_hashtags(text):
    return re.sub(r"\s{2,}", " ", HASHTAG_RE.sub("", text)).strip()


def pick_hashtags(pillar, region_key=None, moment=None, rng=None, limit=None):
    """Search-intent tags first, one city tag, brand tag last. Never more than the limit."""
    limit = limit or settings()["max_hashtags"]
    rng = rng or random.Random()
    tags = list(pillar.get("hashtags", []))
    rng.shuffle(tags)
    chosen = tags[:3]
    if region_key:
        city_tags = cfg("regions")[region_key].get("tags", [])
        chosen.extend(city_tags[:1])
    chosen.append(brand()["brand_hashtag"])
    seen, out = set(), []
    for t in chosen:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out[:limit]


def cta_block():
    b = brand()
    return f"{b['cta_en']}\n{b['cta_es']}"


def build_caption(body, hashtags, credit_line=None, location_name=None):
    s = settings()
    b = brand()
    parts = [strip_hashtags(body).strip()]
    if credit_line:
        parts.append(credit_line)
    parts.append(" ".join(hashtags[: s["max_hashtags"]]))
    parts.append(cta_block())
    cap = "\n\n".join(p for p in parts if p)
    limit = s["caption_max_chars"]
    if len(cap) > limit:
        overflow = len(cap) - limit + 3
        parts[0] = parts[0][: max(0, len(parts[0]) - overflow)].rstrip() + "…"
        cap = "\n\n".join(p for p in parts if p)
    return cap


def validate_caption(caption):
    """Return a list of warning strings (empty = OK)."""
    s = settings()
    b = brand()
    warns = []
    tags = HASHTAG_RE.findall(caption)
    if len(tags) > s["max_hashtags"]:
        warns.append(f"{len(tags)} hashtags (max {s['max_hashtags']})")
    if len(caption) > s["caption_max_chars"]:
        warns.append("caption longer than 2200 characters")
    tail = caption.strip().splitlines()[-2:]
    if not any(b["whatsapp_display"] in line or "livinwithme.net" in line for line in tail):
        warns.append("caption does not end with a booking call")
    return warns


def build_alt_text(headline, photo=None, location_name=None):
    where = f" in {location_name}" if location_name else ""
    subject = (photo or {}).get("alt") or "Photo"
    return f"{subject}{where}. Text on the image: {headline}"[:400]


def credit_line_for(photo):
    if photo and photo.get("attribution_required") and photo.get("credit"):
        return f"📷 {photo['credit']}"
    return None
