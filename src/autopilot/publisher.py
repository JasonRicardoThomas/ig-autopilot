"""Publishing: webhook payload for Make.com, URL liveness checks, retries, minimum gap."""
import datetime as dt
import os
import time

import requests

from .util import parse_iso, settings, now_utc, media_url_candidates

OK_TYPES = ("image/jpeg", "image/png", "video/mp4", "video/quicktime")


def build_payload(post):
    """Payload the Make scenario expects."""
    urls = post["media_urls"]
    is_reel = post["kind"] == "reel"
    payload = {
        "post_id": post["id"], "caption": post["caption"], "alt_text": post.get("alt_text", ""),
        "media_type": "REELS" if is_reel else "IMAGE",
        "image_urls": [] if is_reel else urls[:6],
        "image_count": 0 if is_reel else min(len(urls), 6),
        "video_url": urls[0] if is_reel else "",
        "cover_url": post.get("cover_url", "") if is_reel else "",
        "location_name": post.get("location_name") or "", "location_id": post.get("location_id") or "",
    }
    for i in range(6):
        payload[f"image_url_{i + 1}"] = payload["image_urls"][i] if i < len(payload["image_urls"]) else ""
    return payload


def check_url(url, http=requests, retries=3, wait=5, sleep=time.sleep):
    """True when the file is live with an image or video content type."""
    for attempt in range(retries):
        try:
            r = http.head(url, timeout=20, allow_redirects=True)
            if r.status_code in (403, 405):
                r = http.get(url, timeout=20, stream=True)
            ctype = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if r.status_code == 200 and ctype in OK_TYPES:
                return True
        except Exception:
            pass
        if attempt < retries - 1:
            sleep(wait)
    return False


def live_urls(relpaths, http=requests, **kw):
    """For each repo path pick the first CDN base where the file is live. Returns list or None."""
    out = []
    for rel in relpaths:
        found = next((u for u in media_url_candidates(rel) if check_url(u, http=http, **kw)), None)
        if not found:
            return None
        out.append(found)
    return out


def min_gap_ok(last_published_iso, now=None):
    if not last_published_iso:
        return True
    now = now or now_utc()
    return (now - parse_iso(last_published_iso)) >= dt.timedelta(minutes=settings()["min_gap_minutes"])


def due(post, now=None):
    now = now or now_utc()
    return post["status"] == "approved" and parse_iso(post["scheduled_for"]) <= now


def send_webhook(payload, url=None, secret=None, http=requests, retries=None, sleep=time.sleep):
    url = url or os.environ.get("MAKE_WEBHOOK_URL")
    if not url:
        raise RuntimeError("MAKE_WEBHOOK_URL is not set")
    secret = secret or os.environ.get("MAKE_WEBHOOK_SECRET")
    retries = retries or settings()["webhook_retries"]
    headers = {"x-autopilot-secret": secret} if secret else {}
    last = None
    for attempt in range(retries):
        try:
            r = http.post(url, json=payload, headers=headers, timeout=60)
            if r.status_code < 300:
                return {"ok": True, "status": r.status_code, "body": r.text[:300]}
            last = f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            last = str(e)
        if attempt < retries - 1:
            sleep(10 * (attempt + 1))
    return {"ok": False, "error": last}
