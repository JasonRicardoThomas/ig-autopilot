"""Facebook/Instagram location IDs: looked up once via the Graph API, stored in data/location_ids.json."""
import os

import requests

from .util import DATA, cfg, read_json, write_json

IDS_PATH = DATA / "location_ids.json"
GRAPH = "https://graph.facebook.com/v21.0"


def load_ids():
    return read_json(IDS_PATH, {})


def lookup_all(token=None, session=None):
    """Search each configured place once; never overwrites an ID already stored."""
    token = token or os.environ.get("META_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("META_ACCESS_TOKEN is not set")
    http = session or requests
    ids = load_ids()
    for key, loc in cfg("locations").items():
        if key in ids and ids[key].get("id"):
            continue
        r = http.get(f"{GRAPH}/pages/search", params={"q": loc["query"], "fields": "id,name,location", "access_token": token}, timeout=30)
        data = r.json().get("data", []) if r.ok else []
        best = next((d for d in data if loc["name"].split(",")[0].lower() in d.get("name", "").lower()), data[0] if data else None)
        ids[key] = {"id": best["id"], "name": best["name"]} if best else {"id": None, "name": loc["name"]}
    write_json(IDS_PATH, ids)
    return ids


def resolve(place_key):
    """Return (location_name, location_id or None). Always gives a name so the caption can carry it."""
    loc = cfg("locations")[place_key]
    rec = load_ids().get(place_key) or {}
    return rec.get("name") or loc["name"], rec.get("id")
