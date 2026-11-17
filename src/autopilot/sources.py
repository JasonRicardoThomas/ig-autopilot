"""Photo sources: own Drive folder, inbox/photos, Pexels, Unsplash, Pixabay, Wikimedia Commons.
Pinterest is intentionally not a source: it has no free-licence API; use it only for mood boards."""
import io
import json
import os
from pathlib import Path

import requests

from .util import CACHE, ROOT, sha1  # noqa

UA = {"User-Agent": "ig-autopilot/1.0 (https://livinwithme.net)"}
TIMEOUT = 30


def http_get(url, **kw):
    kw.setdefault("timeout", TIMEOUT)
    kw.setdefault("headers", UA)
    return requests.get(url, **kw)


def search_pexels(query, n=10):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return []
    r = http_get("https://api.pexels.com/v1/search", params={"query": query, "per_page": n, "orientation": "portrait"},
                 headers={**UA, "Authorization": key})
    r.raise_for_status()
    return [{"id": f"pexels-{p['id']}", "origin": "pexels", "url": p["src"]["large2x"], "page": p["url"],
             "credit": f"{p['photographer']} / Pexels", "license": "Pexels License", "attribution_required": False,
             "alt": p.get("alt", "")} for p in r.json().get("photos", [])]


def search_unsplash(query, n=10):
    key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not key:
        return []
    h = {**UA, "Authorization": f"Client-ID {key}"}
    r = http_get("https://api.unsplash.com/search/photos", params={"query": query, "per_page": n, "orientation": "portrait"}, headers=h)
    r.raise_for_status()
    out = []
    for p in r.json().get("results", []):
        out.append({"id": f"unsplash-{p['id']}", "origin": "unsplash", "url": p["urls"]["regular"], "page": p["links"]["html"],
                    "credit": f"{p['user']['name']} / Unsplash", "license": "Unsplash License", "attribution_required": False,
                    "alt": p.get("alt_description") or "", "_download_ping": p["links"].get("download_location")})
    return out


def search_pixabay(query, n=10):
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        return []
    r = http_get("https://pixabay.com/api/", params={"key": key, "q": query, "image_type": "photo", "orientation": "vertical",
                                                      "per_page": max(n, 3), "safesearch": "true"})
    r.raise_for_status()
    return [{"id": f"pixabay-{h['id']}", "origin": "pixabay", "url": h["largeImageURL"], "page": h["pageURL"],
             "credit": f"{h['user']} / Pixabay", "license": "Pixabay Content License", "attribution_required": False,
             "alt": h.get("tags", "")} for h in r.json().get("hits", [])]


OK_LICENSES = ("cc0", "public domain", "pdm", "cc by 4.0", "cc by 3.0", "cc by 2.0", "cc by-sa 4.0", "cc by-sa 3.0", "cc by-sa 2.0")


def search_wikimedia(query, n=10):
    r = http_get("https://commons.wikimedia.org/w/api.php", params={
        "action": "query", "generator": "search", "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": n,
        "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 1600, "format": "json"})
    r.raise_for_status()
    out = []
    for pg in (r.json().get("query", {}).get("pages", {}) or {}).values():
        info = (pg.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "").lower()
        if not any(lic.startswith(o) for o in OK_LICENSES) or "nd" in lic.split():
            continue
        artist = meta.get("Artist", {}).get("value", "Unknown")
        artist = "".join(ch for ch in artist if ch not in "<>")[:80]
        pd = lic.startswith(("cc0", "public domain", "pdm"))
        out.append({"id": f"wikimedia-{pg['pageid']}", "origin": "wikimedia", "url": info.get("thumburl") or info.get("url"),
                    "page": info.get("descriptionurl"), "credit": f"{artist} / Wikimedia Commons ({meta.get('LicenseShortName', {}).get('value', '')})",
                    "license": meta.get("LicenseShortName", {}).get("value", ""), "attribution_required": not pd,
                    "alt": meta.get("ImageDescription", {}).get("value", "")[:120]})
    return out


WEB_SOURCES = [search_pexels, search_unsplash, search_pixabay, search_wikimedia]


def download(url, dest):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = http_get(url, stream=True)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return dest


def normalise_jpeg(src, dest, max_edge=2000):
    """Resize and re-save as JPEG without EXIF (removes GPS data before anything is published)."""
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    im.thumbnail((max_edge, max_edge))
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "JPEG", quality=88)
    return dest


# ---- own photos ----

def drive_service():
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        return None
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_info(json.loads(raw), scopes=["https://www.googleapis.com/auth/drive.readonly"])
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_drive_photos(service, folder_id):
    out, stack = [], [folder_id]
    while stack:
        fid = stack.pop()
        token = None
        while True:
            resp = service.files().list(q=f"'{fid}' in parents and trashed=false", pageToken=token, pageSize=200,
                                        fields="nextPageToken, files(id,name,mimeType,imageMediaMetadata(location,time))").execute()
            for f in resp.get("files", []):
                if f["mimeType"] == "application/vnd.google-apps.folder":
                    stack.append(f["id"])
                elif f["mimeType"].startswith("image/"):
                    out.append(f)
            token = resp.get("nextPageToken")
            if not token:
                break
    return out


def download_drive(service, file_id, dest):
    from googleapiclient.http import MediaIoBaseDownload
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, service.files().get_media(fileId=file_id))
    done = False
    while not done:
        _, done = dl.next_chunk()
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    Path(dest).write_bytes(buf.getvalue())
    return dest


def exif_gps(path):
    from PIL import Image
    try:
        exif = Image.open(path).getexif().get_ifd(0x8825)
        if not exif:
            return None
        def conv(v, ref):
            d = float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
            return -d if ref in ("S", "W") else d
        return conv(exif[2], exif[1]), conv(exif[4], exif[3])
    except Exception:
        return None


def ensure_local(photo):
    """Return a local normalised JPEG path for an indexed photo, downloading it again if needed."""
    dest = CACHE / "photos" / f"{photo['id']}.jpg"
    if dest.exists():
        return dest
    raw = CACHE / "raw" / photo["id"]
    if photo["origin"] == "inbox":
        raw = ROOT / photo["inbox_path"]
    elif photo["origin"] == "drive":
        download_drive(drive_service(), photo["drive_id"], raw)
    else:
        download(photo["url"], raw)
    return normalise_jpeg(raw, dest)
