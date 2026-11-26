"""Draft, publish, redo, reset. One JSON file per post in data/posts/ so commits never conflict."""
import datetime as dt
import os
import shutil

from . import captions, content, locations, photos, planner, publisher, sources
from .util import BUILD, DATA, POSTS, ROOT, cfg, now_utc, read_json, settings, slugify, today_local, write_json


def post_path(pid):
    return POSTS / f"{pid}.json"


def load_posts():
    return [read_json(p) for p in sorted(POSTS.glob("*.json"))]


def drafted_days():
    return {p["scheduled_for"][:10] for p in load_posts() if p["status"] != "rejected"} | {
        p["date"] for p in load_posts() if p["status"] != "rejected"}


def recent_headlines():
    return [p["headline"] for p in sorted(load_posts(), key=lambda p: p["scheduled_for"])][-30:]


def make_post(plan, day, index, used, render=True, client=None):
    pillars = {p["id"]: p for p in cfg("pillars")}
    pillar = pillars[plan["pillar"]]
    moment = next((m for m in cfg("moments") if m["id"] == plan["moment"]), None) if plan["moment"] else None
    ctx = photos.context_for(plan, pillar, moment, day)
    photo = photos.pick(index, used, ctx, day)
    c = content.generate_content(plan, client=client, recent_headlines=recent_headlines())
    loc_name, loc_id = locations.resolve(plan["place"])
    pid = f"{day.isoformat()}-{plan['slot']}-{slugify(c['headline'], 24)}"
    tags = captions.pick_hashtags(pillar, plan["region"], moment)
    caption = captions.build_caption(c["caption_body"], tags, captions.credit_line_for(photo), loc_name)
    warnings = captions.validate_caption(caption)
    if photo is None:
        warnings.append("no verified real photo available; slides use the brand background")
    if plan.get("moment_approx"):
        warnings.append("event dates are approximate: check before approving")
    if plan["kind"] == "reel" and not loc_id:
        warnings.append("Reels location tag may not be applied through the API; place name is in the caption")
    if not loc_id:
        warnings.append("no Facebook location ID yet (run Find location IDs)")
    post = {
        "id": pid, "date": day.isoformat(), "status": "pending", "kind": plan["kind"], "pillar": plan["pillar"],
        "region": plan["region"], "moment": plan["moment"], "scheduled_for": plan["scheduled_for"],
        "headline": c["headline"], "slides": c["slides"], "caption": caption, "alt_text": captions.build_alt_text(c["headline"], photo, loc_name),
        "location_name": loc_name, "location_id": loc_id, "photo": photo["id"] if photo else None,
        "photo_credit": (photo or {}).get("credit"), "warnings": warnings, "media": [], "attempts": 0,
        "created": now_utc().isoformat(),
        "topic_id": plan["topic"]["id"], "place": plan["place"],
    }
    if photo:
        photos.mark_used(used, photo["id"], day, pid)
    if render:
        post["media"] = render_post(post, photo)
    return post


def render_post(post, photo):
    from . import media_store, reels, render
    work = BUILD / "posts" / post["id"]
    shutil.rmtree(work, ignore_errors=True)
    fmt = "reel" if post["kind"] == "reel" else "feed"
    local = sources.ensure_local(photo) if photo else None
    files = render.render_slides(post["slides"], fmt, work, photo_path=local)
    out = {}
    if post["kind"] == "reel":
        mp4 = reels.build_reel(files, work / "reel.mp4")
        out[f"posts/{post['id']}/reel.mp4"] = mp4
        out[f"posts/{post['id']}/cover.jpg"] = files[0]
        post["cover_path"] = f"posts/{post['id']}/cover.jpg"
    else:
        for i, f in enumerate(files, 1):
            out[f"posts/{post['id']}/slide_{i}.jpg"] = f
    media_store.push_media(out, f"media for {post['id']}")
    return list(out.keys())


def draft(days_ahead=2, render=True, client=None, today=None):
    today = today or today_local()
    index = photos.load_index()
    used = photos.load_used()
    state = planner.load_state()
    have = {p["date"] for p in load_posts() if p["status"] != "rejected"}
    made = []
    for d in range(1, days_ahead + 1):
        day = today + dt.timedelta(days=d)
        if day.isoformat() in have:
            continue
        slots, state = planner.plan_day(day, state)
        for plan in slots:
            post = make_post(plan, day, index, used, render=render, client=client)
            write_json(post_path(post["id"]), post)
            made.append(post["id"])
    planner.save_state(state)
    photos.save_used(used)
    return made


def _redo_plan(p):
    """Rebuild the plan a post was made from, keeping its topic, place, format and size."""
    pillar = next(pl for pl in cfg("pillars") if pl["id"] == p["pillar"])
    topic = (next((t for t in pillar["topics"] if t["id"] == p.get("topic_id")), None)
             or next((t for t in pillar["topics"] if t["title"].strip().lower() == p["headline"].strip().lower()), None)
             or pillar["topics"][0])
    region = cfg("regions")[p["region"]]
    places = region["places"]
    place = p.get("place") if p.get("place") in places else None
    if not place:
        locs = cfg("locations")
        place = next((k for k in places if (locs.get(k) or {}).get("name") and
                      (p.get("location_name") or "").startswith(locs[k]["name"])), places[0])
    return {"slot": int(p["id"].split("-")[3]) if p["id"].count("-") > 3 else 0, "scheduled_for": p["scheduled_for"],
            "kind": p["kind"], "pillar": p["pillar"], "region": p["region"], "moment": p["moment"], "moment_approx": False,
            "n_slides": p.get("n_slides") or len(p["slides"]), "place": place, "topic": topic}


def redo_unapproved(render=True, client=None):
    """Rebuild every pending or rejected post; approved and published posts are never touched."""
    used = photos.load_used()
    index = photos.load_index()
    redone = []
    for p in load_posts():
        if p["status"] not in ("pending", "rejected"):
            continue
        photos.release_post(used, p["id"])
        day = dt.date.fromisoformat(p["date"])
        plan = _redo_plan(p)
        post_path(p["id"]).unlink()
        new = make_post(plan, day, index, used, render=render, client=client)
        write_json(post_path(new["id"]), new)
        redone.append(new["id"])
    photos.save_used(used)
    return redone


def reset_everything(wipe_index=False):
    for p in POSTS.glob("*.json"):
        p.unlink()
    for f in (planner.STATE_PATH, photos.USED_PATH):
        if f.exists():
            f.unlink()
    if wipe_index:
        for f in (photos.INDEX_PATH, photos.VERDICTS_PATH):
            if f.exists():
                f.unlink()


def publish_due(http=None, now=None, dry_run=False):
    """Publish at most ONE approved post whose time has come, respecting the minimum gap."""
    now = now or now_utc()
    state = planner.load_state()
    if not publisher.min_gap_ok(state.get("last_published"), now):
        return {"skipped": "minimum gap not reached"}
    due = sorted([p for p in load_posts() if publisher.due(p, now)], key=lambda p: p["scheduled_for"])
    if not due:
        return {"skipped": "nothing due"}
    post = due[0]
    kw = {"http": http} if http else {}
    urls = publisher.live_urls(post["media"], **kw)
    post["attempts"] = post.get("attempts", 0) + 1
    if urls is None:
        post["last_error"] = "media files are not live yet"
        if post["attempts"] >= settings()["max_publish_attempts"]:
            post["status"] = "failed"
        write_json(post_path(post["id"]), post)
        return {"post": post["id"], "ok": False, "error": post["last_error"]}
    post["media_urls"] = urls
    if post["kind"] == "reel" and post.get("cover_path"):
        post["cover_url"] = next(iter(publisher.live_urls([post["cover_path"]], **kw) or []), "")
    payload = publisher.build_payload(post)
    if dry_run:
        return {"post": post["id"], "payload": payload}
    res = publisher.send_webhook(payload, **kw)
    if res["ok"]:
        post["status"] = "published"
        post["published_at"] = now.isoformat()
        state["last_published"] = now.isoformat()
        planner.save_state(state)
    else:
        post["last_error"] = res["error"]
        if post["attempts"] >= settings()["max_publish_attempts"]:
            post["status"] = "failed"
    write_json(post_path(post["id"]), post)
    return {"post": post["id"], **res}
