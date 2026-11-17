"""Daily planning: mix of Reels/carousels/singles, pillars, regions, and max 2 moments per week."""
import datetime as dt
import random

from . import moments as mom
from .util import cfg, read_json, settings, tz, DATA, write_json

STATE_PATH = DATA / "state.json"


def load_state():
    return read_json(STATE_PATH, {"mix_debt": {}, "pillar_debt": {}, "region_debt": {}, "topic_used": {},
                                  "moment_posts": {}, "moment_week": {}, "last_published": None})


def save_state(state):
    write_json(STATE_PATH, state)


def pick_weighted(weights, debt):
    """Deterministic weighted rotation: hits the target mix over time."""
    total = sum(weights.values())
    for k, w in weights.items():
        debt[k] = debt.get(k, 0.0) + w / total
    chosen = max(weights, key=lambda k: (debt[k], k))
    debt[chosen] -= 1.0
    return chosen


def iso_week_key(day):
    y, w, _ = day.isocalendar()
    return f"{y}-W{w:02d}"


def pick_topic(pillar, state, day, rng):
    used = state["topic_used"]
    topics = pillar["topics"]
    topics_sorted = sorted(topics, key=lambda t: (used.get(t["id"], "0000-00-00"), rng.random()))
    topic = topics_sorted[0]
    used[topic["id"]] = day.isoformat()
    return topic


def slot_times(day, n):
    s = settings()
    times = s["post_times_local"]
    out = []
    for i in range(n):
        hh, mm = map(int, times[i % len(times)].split(":"))
        local = dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=tz())
        out.append(local.astimezone(dt.timezone.utc).isoformat())
    return out


def plan_day(day, state=None, rng=None, count=None):
    """Return a list of slot plans for `day` and mutate `state`."""
    s = settings()
    state = state if state is not None else load_state()
    rng = rng or random.Random(day.toordinal())
    n = count or s["posts_per_day"]
    pillars = {p["id"]: p for p in cfg("pillars")}
    regions = cfg("regions")
    times = slot_times(day, n)
    week = iso_week_key(day)
    moment_slot = None
    chosen_moment = None
    if state["moment_week"].get(week, 0) < s["moments_per_week"] and day.weekday() in s["moment_weekdays"]:
        for m, window in mom.active_moments(day):
            key = mom.occurrence_key(m, window)
            if state["moment_posts"].get(key, 0) < (4 if m.get("campaign") else 2):
                chosen_moment = (m, window, key)
                moment_slot = min(1, n - 1)
                break
    slots = []
    for i in range(n):
        kind = pick_weighted(s["mix"], state["mix_debt"])
        pillar_id = pick_weighted({p["id"]: p["weight"] for p in pillars.values()}, state["pillar_debt"])
        region_key = pick_weighted({k: v["weight"] for k, v in regions.items()}, state["region_debt"])
        moment = None
        if chosen_moment and i == moment_slot:
            m, window, key = chosen_moment
            if mom.region_ok(m, region_key) or True:
                moment = m
                state["moment_posts"][key] = state["moment_posts"].get(key, 0) + 1
                state["moment_week"][week] = state["moment_week"].get(week, 0) + 1
                if "all" not in m.get("regions", ["all"]) and region_key not in m["regions"]:
                    region_key = m["regions"][0]
        pillar = pillars[pillar_id]
        topic = pick_topic(pillar, state, day, rng)
        place_key = rng.choice(regions[region_key]["places"])
        if kind == "carousel":
            n_slides = rng.choice(s["carousel_sizes"])
        elif kind == "reel":
            n_slides = rng.choice(s["reel_frames"])
        else:
            n_slides = 1
        slots.append({
            "slot": i, "scheduled_for": times[i], "kind": kind, "pillar": pillar_id,
            "topic": topic, "region": region_key, "place": place_key,
            "moment": moment["id"] if moment else None,
            "moment_approx": bool(moment and moment.get("approx")),
            "n_slides": n_slides,
        })
    return slots, state
