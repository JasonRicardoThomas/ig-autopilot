"""Photo library and picker: real photos only, allowed countries, topic + season match, 90-day no-reuse."""
import datetime as dt
import math
import random

from .util import DATA, cfg, read_json, settings, write_json

INDEX_PATH = DATA / "photo_index.json"
USED_PATH = DATA / "used_photos.json"
VERDICTS_PATH = DATA / "verdicts.json"
CREDITS_PATH = DATA / "credits.json"

CATEGORIES = ["people", "food", "culture", "city", "architecture", "cafe", "work", "study", "books",
              "writing", "classroom", "events", "nature", "sunrise", "sunset", "attractions", "nightlife", "beach"]


def season_for(day):
    m = day.month
    return "winter" if m in (12, 1, 2) else "spring" if m in (3, 4, 5) else "summer" if m in (6, 7, 8) else "autumn"


def load_index():
    return read_json(INDEX_PATH, {"photos": {}})


def save_index(idx):
    write_json(INDEX_PATH, idx)


def load_used():
    return read_json(USED_PATH, {})


def save_used(used):
    write_json(USED_PATH, used)


def is_available(photo, used, today, days=None):
    days = days if days is not None else settings()["no_reuse_days"]
    rec = used.get(photo["id"])
    if not rec:
        return True
    last = dt.date.fromisoformat(rec["date"])
    return (today - last).days >= days


def mark_used(used, photo_id, day, post_id):
    used[photo_id] = {"date": day.isoformat(), "post": post_id}


def release_post(used, post_id):
    for pid in [k for k, v in used.items() if v.get("post") == post_id]:
        del used[pid]


def eligible(photo, ctx, allowed_countries):
    if not photo.get("verified", True) or photo.get("is_drawing"):
        return False
    country = photo.get("country")
    if ctx["needs_place"]:
        return country == ctx["country"]
    if country:
        return country in allowed_countries
    return bool(photo.get("generic_ok"))


def score(photo, ctx):
    s = 0.0
    cats = set(photo.get("categories", []))
    s += 2.0 * len(cats & set(ctx["categories"]))
    s += 1.5 * len(cats & set(ctx.get("themes", [])))
    if photo.get("city") == ctx.get("city"):
        s += 3.0
    if photo.get("season") in (ctx["season"], "any", None):
        s += 1.0
    if photo.get("origin") in ("drive", "inbox"):
        s += 0.5  # prefer the owner's real photos
    return s


def pick(index, used, ctx, today, rng=None, min_score=2.0):
    rng = rng or random.Random()
    allowed = settings()["allowed_countries"]
    pool = []
    for photo in index["photos"].values():
        if not eligible(photo, ctx, allowed) or not is_available(photo, used, today):
            continue
        sc = score(photo, ctx)
        if sc >= min_score:
            pool.append((sc, photo))
    if not pool:
        return None
    pool.sort(key=lambda t: -t[0])
    top = [p for sc, p in pool if sc >= pool[0][0] - 1.0][:3]
    return rng.choice(top)


def context_for(plan, pillar, moment=None, today=None):
    regions = cfg("regions")
    r = regions[plan["region"]]
    today = today or dt.date.today()
    return {
        "categories": pillar["categories"], "themes": (moment or {}).get("photo_themes", []),
        "city": r["city"], "country": r["country"], "season": season_for(today),
        "needs_place": bool(pillar.get("needs_place")) and settings()["require_verified_country"] != "never",
    }


def haversine_km(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2 +
         math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(a))


def city_from_gps(lat, lon):
    best = None
    for key, r in cfg("regions").items():
        d = haversine_km(lat, lon, r["lat"], r["lon"])
        if d <= r["radius_km"] and (best is None or d < best[0]):
            best = (d, r)
    return (best[1]["country"], best[1]["city"]) if best else (None, None)
