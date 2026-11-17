"""Reels with ffmpeg: slides -> 1080x1920 video with slow zooms/pans, clip overlay, booking card at the end."""
import random
import subprocess
from pathlib import Path

AUDIO_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "audio"
AUDIO_EXT = (".mp3", ".m4a", ".wav", ".aac", ".ogg")
W, H, FPS = 1080, 1920, 30
STYLES = ("zoom_in", "zoom_out", "pan_left", "pan_right")


def pick_audio(rng=None, directory=None):
    """Random track from assets/audio (generated or your own licensed music); None only if the folder is empty."""
    rng = rng or random.Random()
    tracks = sorted(f for f in Path(directory or AUDIO_DIR).glob("*") if f.suffix.lower() in AUDIO_EXT)
    return rng.choice(tracks) if tracks else None


def zoompan_expr(style, frames):
    z_end = 1.12
    if style == "zoom_in":
        return f"z='1+({z_end}-1)*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    if style == "zoom_out":
        return f"z='{z_end}-({z_end}-1)*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    if style == "pan_left":
        return f"z=1.12:x='(iw-iw/zoom)*(1-on/{frames})':y='ih/2-(ih/zoom/2)'"
    return f"z=1.12:x='(iw-iw/zoom)*on/{frames}':y='ih/2-(ih/zoom/2)'"


def build_command(images, out, seconds_each=3.0, fade=0.5, styles=None, audio=None, rng=None):
    """Return the ffmpeg argv list. Pure function so tests need no ffmpeg or network."""
    rng = rng or random.Random()
    audio = audio or pick_audio(rng)
    styles = styles or [rng.choice(STYLES) for _ in images]
    frames = int(seconds_each * FPS)
    cmd = ["ffmpeg", "-y"]
    for img in images:
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{seconds_each}", "-i", str(img)]
    if audio:
        cmd += ["-stream_loop", "-1", "-i", str(audio)]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    parts = []
    for i, st in enumerate(styles):
        parts.append(f"[{i}:v]scale=2160:-1,zoompan={zoompan_expr(st, frames)}:d={frames}:s={W}x{H}:fps={FPS},setsar=1,format=yuv420p[v{i}]")
    last = "v0"
    offset = seconds_each - fade
    for i in range(1, len(images)):
        nxt = f"x{i}"
        parts.append(f"[{last}][v{i}]xfade=transition=fade:duration={fade}:offset={offset:.2f}[{nxt}]")
        last = nxt
        offset += seconds_each - fade
    total = seconds_each * len(images) - fade * (len(images) - 1)
    cmd += ["-filter_complex", ";".join(parts), "-map", f"[{last}]", "-map", f"{len(images)}:a",
            "-t", f"{total:.2f}", "-af", f"afade=t=out:st={max(0, total - 1):.2f}:d=1", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(out)]
    return cmd


def build_reel(images, out, **kw):
    cmd = build_command(images, out, **kw)
    subprocess.run(cmd, check=True, capture_output=True)
    return Path(out)


def clip_command(clip, card_image, out, card_seconds=3.0, max_seconds=24, audio=None):
    """Short clip scaled/cropped to 1080x1920, then the booking card."""
    flt = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,format=yuv420p[a];"
           f"[1:v]scale={W}:{H},fps={FPS},setsar=1,format=yuv420p[b];[a][b]concat=n=2:v=1:a=0[v]")
    audio = audio or pick_audio()
    src = ["-stream_loop", "-1", "-i", str(audio)] if audio else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    return ["ffmpeg", "-y", "-t", str(max_seconds), "-i", str(clip), "-loop", "1", "-t", str(card_seconds), "-i", str(card_image),
            *src, "-filter_complex", flt, "-map", "[v]", "-map", "2:a",
            "-af", "afade=t=out:st=%s:d=1" % max(0, max_seconds + card_seconds - 1), "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-shortest", "-movflags", "+faststart", str(out)]


def build_clip_reel(clip, card_image, out, **kw):
    subprocess.run(clip_command(clip, card_image, out, **kw), check=True, capture_output=True)
    return Path(out)
