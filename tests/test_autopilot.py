import datetime as dt
import random

import pytest

from autopilot import captions, moments, photos, planner, publisher, reels, vision
from autopilot.util import cfg


def mk(i, **kw):
    p = {"id": f"p{i}", "origin": "drive", "verified": True, "country": "Mexico", "city": "Mexico City",
         "categories": ["city"], "season": "any", "generic_ok": False}
    p.update(kw)
    return p


CTX = {"categories": ["city"], "themes": [], "city": "Mexico City", "country": "Mexico", "season": "autumn", "needs_place": True}
TODAY = dt.date(2026, 11, 16)


def test_picker_never_reuses_within_90_days():
    idx = {"photos": {"p1": mk(1)}}
    used = {}
    first = photos.pick(idx, used, CTX, TODAY, random.Random(1))
    photos.mark_used(used, first["id"], TODAY, "post-a")
    assert photos.pick(idx, used, CTX, TODAY + dt.timedelta(days=89), random.Random(1)) is None
    assert photos.pick(idx, used, CTX, TODAY + dt.timedelta(days=91), random.Random(1)) is not None


def test_picker_rejects_wrong_country_drawings_and_unverified():
    idx = {"photos": {"a": mk(1, country="Spain"), "b": mk(2, is_drawing=True), "c": mk(3, verified=False), "d": mk(4, country=None)}}
    assert photos.pick(idx, {}, CTX, TODAY) is None


def test_generic_photo_ok_for_non_place_posts_only():
    idx = {"photos": {"g": mk(1, id="g", country=None, generic_ok=True, categories=["study"])}}
    ctx = dict(CTX, categories=["study"], needs_place=False)
    assert photos.pick(idx, {}, ctx, TODAY)["id"] == "g"
    assert photos.pick(idx, {}, dict(ctx, needs_place=True), TODAY) is None


def test_release_post_frees_photo():
    used = {}
    photos.mark_used(used, "x", TODAY, "post-a")
    photos.release_post(used, "post-a")
    assert used == {}


def test_gps_maps_to_city():
    assert photos.city_from_gps(19.43, -99.13) == ("Mexico", "Mexico City")
    assert photos.city_from_gps(40.42, -3.70) == ("Spain", "Madrid")
    assert photos.city_from_gps(48.85, 2.35) == (None, None)


def test_caption_max_five_hashtags_and_booking_call_last():
    pillar = cfg("pillars")[0]
    tags = captions.pick_hashtags(pillar, "madrid", rng=random.Random(2))
    assert len(tags) <= 5 and "#growingconnections" in tags
    cap = captions.build_caption("Body text #one #two #three #four #five #six", tags)
    assert captions.validate_caption(cap) == []
    assert "#six" not in cap and cap.strip().endswith(cfg("brand")["cta_es"])


def test_caption_length_limit():
    cap = captions.build_caption("x" * 5000, ["#a"])
    assert len(cap) <= 2200 and captions.validate_caption(cap) == []


def test_caption_warns_without_booking_call():
    assert any("booking" in w for w in captions.validate_caption("Just a tip #a"))


def test_moments_two_per_week_max():
    state = planner.load_state() if False else {"mix_debt": {}, "pillar_debt": {}, "region_debt": {}, "topic_used": {}, "moment_posts": {}, "moment_week": {}}
    count = 0
    monday = dt.date(2026, 12, 14)
    for d in range(7):
        slots, state = planner.plan_day(monday + dt.timedelta(days=d), state)
        count += sum(1 for s in slots if s["moment"])
    assert count <= 2


def test_mix_is_roughly_80_15_5():
    state = {"mix_debt": {}, "pillar_debt": {}, "region_debt": {}, "topic_used": {}, "moment_posts": {}, "moment_week": {}}
    kinds = []
    for d in range(60):
        slots, state = planner.plan_day(dt.date(2027, 3, 1) + dt.timedelta(days=d), state)
        kinds += [s["kind"] for s in slots]
    n = len(kinds)
    assert 0.74 <= kinds.count("reel") / n <= 0.86
    assert 0.10 <= kinds.count("carousel") / n <= 0.20
    assert kinds.count("single") / n <= 0.10


def test_slot_times_are_three_per_day_in_utc():
    slots, _ = planner.plan_day(dt.date(2026, 12, 1), {"mix_debt": {}, "pillar_debt": {}, "region_debt": {}, "topic_used": {}, "moment_posts": {}, "moment_week": {}})
    assert len(slots) == 3 and all(s["scheduled_for"].endswith("+00:00") for s in slots)


def test_black_friday_rule_and_christmas_window():
    assert any(m["id"] == "black_friday" for m, _ in moments.active_moments(dt.date(2026, 11, 25)))
    assert any(m["id"] == "posadas" for m, _ in moments.active_moments(dt.date(2026, 12, 8)))


def test_reel_command_is_vertical_with_crossfades_and_audio():
    cmd = reels.build_command(["a.jpg", "b.jpg", "c.jpg"], "out.mp4", rng=random.Random(1))
    joined = " ".join(cmd)
    assert "1080x1920" in joined and joined.count("xfade") == 2 and "anullsrc" not in joined and "assets/audio" in joined and cmd[-1] == "out.mp4"
    assert "-t 3.0 -i a.jpg" in joined


def test_pick_audio_finds_bundled_tracks_and_empty_folder_is_none(tmp_path):
    assert reels.pick_audio(random.Random(1)).suffix == ".mp3"
    assert reels.pick_audio(directory=tmp_path) is None


def test_reel_with_music_uses_audio_file():
    cmd = reels.build_command(["a.jpg", "b.jpg"], "o.mp4", audio="song.mp3", rng=random.Random(1))
    assert "song.mp3" in cmd and "anullsrc" not in " ".join(cmd)


def test_payload_for_carousel_and_reel():
    post = {"id": "x", "kind": "carousel", "caption": "c", "alt_text": "a", "media_urls": [f"https://u/{i}.jpg" for i in range(4)],
            "location_name": "Polanco", "location_id": "123"}
    p = publisher.build_payload(post)
    assert p["media_type"] == "IMAGE" and p["image_count"] == 4 and p["image_url_4"].endswith("3.jpg") and p["image_url_5"] == ""
    assert p["location_id"] == "123" and p["video_url"] == ""
    r = publisher.build_payload({**post, "kind": "reel", "media_urls": ["https://u/r.mp4"]})
    assert r["media_type"] == "REELS" and r["video_url"].endswith(".mp4") and r["image_count"] == 0


class FakeResp:
    def __init__(self, code, ctype="image/jpeg", text=""):
        self.status_code, self.headers, self.text = code, {"Content-Type": ctype}, text


class FakeHttp:
    def __init__(self, seq):
        self.seq, self.calls = list(seq), 0

    def head(self, *a, **k):
        self.calls += 1
        return self.seq.pop(0) if self.seq else FakeResp(404)

    def post(self, *a, **k):
        self.calls += 1
        return self.seq.pop(0)


def test_url_check_retries_then_accepts_video():
    http = FakeHttp([FakeResp(404), FakeResp(200, "video/mp4")])
    assert publisher.check_url("u", http=http, retries=3, sleep=lambda s: None)
    assert http.calls == 2


def test_url_check_rejects_html():
    assert not publisher.check_url("u", http=FakeHttp([FakeResp(200, "text/html")] * 3), retries=3, sleep=lambda s: None)


def test_webhook_retries_then_succeeds():
    http = FakeHttp([FakeResp(500, text="err"), FakeResp(200, text="ok")])
    res = publisher.send_webhook({"a": 1}, url="https://hook", http=http, retries=3, sleep=lambda s: None)
    assert res["ok"] and http.calls == 2


def test_min_gap():
    now = dt.datetime(2026, 11, 16, 12, tzinfo=dt.timezone.utc)
    assert not publisher.min_gap_ok((now - dt.timedelta(minutes=30)).isoformat(), now)
    assert publisher.min_gap_ok((now - dt.timedelta(minutes=120)).isoformat(), now)


def test_vision_judge_rules():
    good = {"is_photograph": True, "is_drawing_or_graphic": False, "country": "Mexico", "confidence": 0.9}
    assert vision.judge(good, needs_place=True, target_country="Mexico")[0]
    assert not vision.judge(dict(good, country="Spain"), needs_place=True, target_country="Mexico")[0]
    assert not vision.judge(dict(good, is_drawing_or_graphic=True))[0]
    assert not vision.judge(dict(good, country="other"))[0]
    assert not vision.judge(dict(good, confidence=0.3))[0]
    assert vision.judge(dict(good, country="unknown", generic_scene=True))[0]
    assert not vision.judge(dict(good, country="unknown", generic_scene=False))[0]


def test_network_is_blocked():
    import socket
    with pytest.raises(RuntimeError):
        socket.create_connection(("example.com", 80))


def test_vision_survives_non_json_reply(tmp_path, monkeypatch):
    from autopilot import vision
    monkeypatch.setattr(vision, "VERDICTS_PATH", tmp_path / "verdicts.json")
    monkeypatch.setattr(vision, "_encode", lambda p: "xx")

    class Block:  # a reply with no JSON at all
        text = "I can't help with that."

    class Msg:
        content = [Block()]
        stop_reason = "end_turn"

    class Client:
        class messages:
            @staticmethod
            def create(**k):
                return Msg()

    v = vision.analyze(tmp_path / "x.jpg", "k1", Client(), clip=False)
    assert v["stage"] == "error"
    ok, _ = vision.judge(v)
    assert not ok
    assert not (tmp_path / "verdicts.json").exists()  # failures are not cached


def test_every_region_place_has_a_location_and_sectors_are_covered():
    from autopilot.util import cfg
    locs = cfg("locations")
    for key, r in cfg("regions").items():
        assert all(p in locs and locs[p]["region"] == key for p in r["places"])
    assert abs(sum(r["weight"] for r in cfg("regions").values()) - 1) < 1e-9
    sectors = next(p for p in cfg("pillars") if p["id"] == "sectors")
    assert len(sectors["topics"]) >= 22
    assert {"Basque", "Cantabria", "Galicia", "Valladolid", "Mallorca", "Barcelona"} <= {r["city"].split()[0] if r["city"] not in ("Bilbao", "Santander", "Santiago de Compostela", "Palma de Mallorca") else {"Bilbao": "Basque", "Santander": "Cantabria", "Santiago de Compostela": "Galicia", "Palma de Mallorca": "Mallorca"}[r["city"]] for r in cfg("regions").values()}


def test_redo_keeps_topic_place_and_size_of_rejected_post():
    from autopilot import pipeline
    p = {"id": "2026-11-27-1-the-three-sounds-of-ed-e", "status": "rejected", "pillar": "english_tips",
         "region": "mexico_city", "moment": None, "kind": "carousel", "n_slides": 5,
         "scheduled_for": "2026-11-27T19:00:00+00:00", "headline": "The three sounds of -ed endings",
         "slides": [{"headline": "x"}], "location_name": "Polanco, Mexico City"}
    plan = pipeline._redo_plan(p)
    assert plan["topic"]["id"] == "et_ed_endings"
    assert plan["place"] == "polanco_cdmx"
    assert plan["kind"] == "carousel" and plan["n_slides"] == 5 and plan["slot"] == 1
