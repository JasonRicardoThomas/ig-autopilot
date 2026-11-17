import argparse
import json
import os
import subprocess
import sys

from . import boost, calendar, locations, photos, pipeline, sources, vision
from .util import ROOT, cfg


def cmd_index(args):
    """Index own photos (inbox + Drive) and optionally a few web photos per category with Claude vision."""
    import anthropic
    client = anthropic.Anthropic()
    idx = photos.load_index()
    budget = cfg("settings")["max_vision_calls_per_run"]
    calls = 0
    for path in sorted((ROOT / "inbox" / "photos").glob("*")):
        if path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        pid = f"inbox-{sources.sha1(path.read_bytes())[:12]}" if hasattr(sources, "sha1") else f"inbox-{path.stem}"
        if pid in idx["photos"] or calls >= budget:
            continue
        gps = sources.exif_gps(path)
        v = vision.analyze(path, pid, client)
        calls += 1
        if gps:
            country, city = photos.city_from_gps(*gps)
            if country:
                v["country"], v["city"] = country, city
        ok, why = vision.judge(v)
        if ok:
            idx["photos"][pid] = vision.to_photo_record(pid, "inbox", v, {"inbox_path": str(path.relative_to(ROOT))})
    svc = sources.drive_service()
    folder = os.environ.get("DRIVE_FOLDER_ID")
    if svc and folder:
        for f in sources.list_drive_photos(svc, folder):
            pid = f"drive-{f['id']}"
            if pid in idx["photos"] or calls >= budget:
                continue
            raw = sources.CACHE / "raw" / pid
            sources.download_drive(svc, f["id"], raw)
            small = sources.normalise_jpeg(raw, sources.CACHE / "photos" / f"{pid}.jpg")
            v = vision.analyze(small, pid, client)
            calls += 1
            loc = (f.get("imageMediaMetadata") or {}).get("location")
            if loc:
                country, city = photos.city_from_gps(loc["latitude"], loc["longitude"])
                if country:
                    v["country"], v["city"] = country, city
            ok, why = vision.judge(v)
            if ok:
                idx["photos"][pid] = vision.to_photo_record(pid, "drive", v, {"drive_id": f["id"]})
    for cat, q in [("people", "business meeting professionals"), ("study", "student studying laptop"), ("books", "open book desk"),
                   ("writing", "writing notebook pen"), ("classroom", "classroom teacher"), ("city", "Mexico City street"),
                   ("architecture", "Madrid architecture"), ("culture", "Seville plaza")]:
        for fn in sources.WEB_SOURCES:
            if calls >= budget:
                break
            for cand in fn(q, 3):
                if cand["id"] in idx["photos"] or calls >= budget:
                    continue
                dest = sources.CACHE / "photos" / f"{cand['id']}.jpg"
                sources.normalise_jpeg(sources.download(cand["url"], sources.CACHE / "raw" / cand["id"]), dest)
                v = vision.analyze(dest, cand["id"], client)
                calls += 1
                ok, why = vision.judge(v)
                if ok:
                    idx["photos"][cand["id"]] = vision.to_photo_record(cand["id"], cand["origin"], v, {
                        k: cand[k] for k in ("url", "credit", "license", "attribution_required") if k in cand})
    photos.save_index(idx)
    print(f"indexed {len(idx['photos'])} photos, {calls} vision calls")


def cmd_refresh_token(args):
    import requests
    r = requests.get("https://graph.facebook.com/v21.0/oauth/access_token", params={
        "grant_type": "fb_exchange_token", "client_id": os.environ["META_APP_ID"], "client_secret": os.environ["META_APP_SECRET"],
        "fb_exchange_token": os.environ["META_ACCESS_TOKEN"]}, timeout=30)
    r.raise_for_status()
    new = r.json()["access_token"]
    subprocess.run(["gh", "secret", "set", "META_ACCESS_TOKEN", "--body", new], check=True,
                   env={**os.environ, "GH_TOKEN": os.environ["GH_PAT"]})
    print("token refreshed (value not printed)")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="autopilot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draft"); d.add_argument("--days", type=int, default=2); d.add_argument("--no-render", action="store_true")
    r = sub.add_parser("redo"); r.add_argument("--no-render", action="store_true")
    x = sub.add_parser("reset"); x.add_argument("--wipe-index", action="store_true")
    pb = sub.add_parser("publish"); pb.add_argument("--dry-run", action="store_true")
    sub.add_parser("index"); sub.add_parser("locations"); sub.add_parser("refresh-token")
    c = sub.add_parser("calendar"); c.add_argument("--year", type=int)
    sub.add_parser("boost")
    sub.add_parser("test")
    a = ap.parse_args(argv)
    if a.cmd == "draft":
        print(json.dumps(pipeline.draft(a.days, render=not a.no_render)))
    elif a.cmd == "redo":
        print(json.dumps(pipeline.redo_unapproved(render=not a.no_render)))
    elif a.cmd == "reset":
        pipeline.reset_everything(a.wipe_index); print("reset done")
    elif a.cmd == "publish":
        print(json.dumps(pipeline.publish_due(dry_run=a.dry_run)))
    elif a.cmd == "index":
        cmd_index(a)
    elif a.cmd == "locations":
        print(json.dumps(locations.lookup_all()))
    elif a.cmd == "refresh-token":
        cmd_refresh_token(a)
    elif a.cmd == "calendar":
        print(calendar.as_markdown(a.year))
    elif a.cmd == "boost":
        print(json.dumps(boost.plan(), indent=2))
    elif a.cmd == "test":
        sys.exit(subprocess.call([sys.executable, "-m", "pytest", "-q", str(ROOT / "tests")]))


if __name__ == "__main__":
    main()
