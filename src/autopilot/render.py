"""Branded slides: HTML templates -> JPEG via headless Chromium (Playwright). Feed 1080x1350, Reels 1080x1920."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .util import ROOT, brand

ENV = Environment(loader=FileSystemLoader(str(ROOT / "templates")), autoescape=select_autoescape(["html"]))
SIZES = {"feed": (1080, 1350), "reel": (1080, 1920)}


def slide_html(slide, fmt, photo_path=None, index="", tag="Our Days & Futures"):
    b, c = brand(), brand()["colors"]
    w, h = SIZES[fmt]
    reel = fmt == "reel"
    headline = slide["headline"]
    return ENV.get_template("slide.html").render(
        w=w, h=h, role=slide["role"], headline=headline, body=slide.get("body", ""),
        photo=Path(photo_path).resolve().as_uri() if photo_path else "",
        ink=c["ink"], teal=c["teal"], gold=c["gold"], cream=c["cream"], white=c["white"],
        handle=b["handle"], url=b["booking_card"]["url"], index=index, tag=tag,
        h1=82 if len(headline) < 50 else 66,
        safe_top=250 if reel else 120, safe_bottom=420 if reel else 200, foot_bottom=300 if reel else 70)


def render_slides(slides, fmt, out_dir, photo_path=None, photos=None):
    """Render every slide to out_dir/slide_N.jpg. Needs playwright + chromium. Returns the file list."""
    from playwright.sync_api import sync_playwright
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    w, h = SIZES[fmt]
    files = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": w, "height": h})
        for i, s in enumerate(slides, 1):
            ph = (photos or {}).get(i) or (photo_path if s["role"] != "cta" else None)
            html = slide_html(s, fmt, ph, index=f"{i}/{len(slides)}" if len(slides) > 1 else "")
            hp = out_dir / f"slide_{i}.html"
            hp.write_text(html, encoding="utf-8")
            page.goto(hp.resolve().as_uri())
            page.wait_for_timeout(150)
            dest = out_dir / f"slide_{i}.jpg"
            page.screenshot(path=str(dest), type="jpeg", quality=90)
            hp.unlink()
            files.append(dest)
        browser.close()
    return files
