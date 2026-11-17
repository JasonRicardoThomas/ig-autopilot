"""CLIP first pass + Claude vision verdicts. Verdicts are cached so no photo is checked twice."""
import base64
import io
import json
import re

from .photos import CATEGORIES, VERDICTS_PATH
from .util import read_json, settings, sha1, write_json

_CLIP = {}
CLIP_PROMPTS = ["a real photograph", "an illustration or drawing", "a cartoon or vector graphic", "a logo or text graphic"]


def clip_first_pass(path):
    """Return {'photo_prob': float} or None when CLIP is not installed."""
    try:
        import torch
        from PIL import Image
        from transformers import CLIPModel, CLIPProcessor
    except Exception:
        return None
    if "m" not in _CLIP:
        _CLIP["m"] = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        _CLIP["p"] = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    inputs = _CLIP["p"](text=CLIP_PROMPTS, images=Image.open(path).convert("RGB"), return_tensors="pt", padding=True)
    with torch.no_grad():
        probs = _CLIP["m"](**inputs).logits_per_image.softmax(dim=1)[0].tolist()
    return {"photo_prob": probs[0]}


def _encode(path, max_edge=1024):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    im.thumbnail((max_edge, max_edge))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


PROMPT = (
    "You verify photos for an Instagram account about English teaching, writing and business, "
    "targeting Mexico City, Madrid and Seville. Look at the image and answer ONLY with JSON: "
    '{"is_photograph": bool, "is_drawing_or_graphic": bool, "country": "Mexico|Spain|other|unknown", '
    '"city": "string or unknown", "place": "string or unknown", '
    f'"categories": [subset of {CATEGORIES}], "season": "winter|spring|summer|autumn|any", '
    '"people_present": bool, "has_text_or_logo": bool, "generic_scene": bool (indoor/desk scene with no place clues), '
    '"confidence": 0..1, "alt": "one sentence describing the photo"}. '
    "Judge the country only from visible evidence (architecture, signs, plates, landmarks). If unsure, say unknown."
)


def claude_check(path, client):
    """Ask Claude to describe the photo. Returns a dict, or None if no usable JSON came back."""
    s = settings()
    for _ in range(2):
        try:
            msg = client.messages.create(
                model=s["vision_model"], max_tokens=1200,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _encode(path)}},
                    {"type": "text", "text": PROMPT}]}])
        except Exception as e:  # API/network/model errors must not stop the whole run
            print(f"vision: API error for {path}: {type(e).__name__}: {str(e)[:200]}")
            continue
        text = "".join(getattr(b, "text", "") for b in msg.content)
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            print(f"vision: no JSON in reply for {path} (stop_reason={getattr(msg, 'stop_reason', '?')}): {text[:160]!r}")
            continue
        try:
            return json.loads(m.group(0))
        except ValueError:
            print(f"vision: bad JSON for {path}: {m.group(0)[:160]!r}")
    return None


def analyze(path, key, client, clip=True):
    """Cached verdict. Returns verdict dict (with 'accepted' and 'reasons')."""
    verdicts = read_json(VERDICTS_PATH, {})
    if key in verdicts:
        return verdicts[key]
    verdict = {"source_key": key}
    first = clip_first_pass(path) if clip else None
    if first is not None and first["photo_prob"] < settings().get("clip_reject_below", 0.0):
        verdict.update({"is_photograph": False, "is_drawing_or_graphic": True, "confidence": 1 - first["photo_prob"],
                        "stage": "clip", "reasons": ["CLIP: looks like an illustration or graphic"]})
    else:
        result = claude_check(path, client)
        if result is None:
            # Not cached, so it can be retried on a later run.
            return {"source_key": key, "is_photograph": False, "is_drawing_or_graphic": False, "confidence": 0,
                    "stage": "error", "reasons": ["vision check failed"]}
        verdict.update(result)
        verdict["stage"] = "claude"
    verdicts[key] = verdict
    write_json(VERDICTS_PATH, verdicts)
    return verdict


def judge(verdict, needs_place=False, target_country=None):
    """Turn a raw verdict into (accepted, reasons)."""
    s = settings()
    reasons = []
    if not verdict.get("is_photograph") or verdict.get("is_drawing_or_graphic"):
        reasons.append("not a real photograph")
    if verdict.get("has_text_or_logo"):
        reasons.append("contains text or a logo")
    if verdict.get("confidence", 0) < s["min_vision_confidence"]:
        reasons.append("low confidence")
    country = verdict.get("country")
    if country in s["allowed_countries"]:
        if needs_place and target_country and country != target_country:
            reasons.append(f"photo is from {country}, post is about {target_country}")
    elif country in ("other",):
        reasons.append("photo is from another country")
    elif not verdict.get("generic_scene"):
        reasons.append("country could not be verified")
    return (not reasons), reasons


def to_photo_record(pid, origin, verdict, extra=None):
    country = verdict.get("country")
    rec = {
        "id": pid, "origin": origin, "verified": True,
        "country": country if country in settings()["allowed_countries"] else None,
        "city": None if verdict.get("city") in (None, "unknown") else verdict["city"],
        "place": None if verdict.get("place") in (None, "unknown") else verdict["place"],
        "categories": verdict.get("categories", []), "season": verdict.get("season", "any"),
        "people_present": bool(verdict.get("people_present")),
        "generic_ok": bool(verdict.get("generic_scene")) and country not in ("other",),
        "alt": verdict.get("alt", ""),
    }
    rec.update(extra or {})
    return rec
