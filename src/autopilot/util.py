import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(os.environ.get("AUTOPILOT_ROOT", Path(__file__).resolve().parents[2]))
CONFIG = ROOT / "config"
DATA = ROOT / "data"
POSTS = DATA / "posts"
CACHE = ROOT / "cache"
BUILD = ROOT / "build"


def read_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def cfg(name):
    return read_json(CONFIG / f"{name}.json")


def settings():
    return cfg("settings")


def brand():
    return cfg("brand")


def tz():
    return ZoneInfo(settings()["timezone"])


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def today_local():
    return dt.datetime.now(tz()).date()


def slugify(text, limit=40):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:limit].strip("-") or "post"


def sha1(data):
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha1(data).hexdigest()


def parse_iso(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def repo_slug():
    return os.environ.get("GITHUB_REPOSITORY", "JasonRicardoThomas/ig-autopilot")


def media_url_candidates(relpath):
    s = settings()
    return [b.format(repo=repo_slug(), branch=s["media_branch"]) + "/" + relpath.lstrip("/") for b in s["media_bases"]]
