"""Rendered files live on the `media` branch so they get public CDN URLs. Branch is squashed to stay small."""
import subprocess
from pathlib import Path

from .util import BUILD, ROOT, settings


def sh(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def push_media(files, message="media"):
    """files: {repo_path: local_path}. Commits them to the media branch using a worktree."""
    branch = settings()["media_branch"]
    wt = BUILD / "media-worktree"
    if not wt.exists():
        try:
            sh("git", "fetch", "origin", branch, cwd=ROOT)
            sh("git", "worktree", "add", "-B", branch, str(wt), f"origin/{branch}", cwd=ROOT)
        except subprocess.CalledProcessError:
            sh("git", "worktree", "add", "--detach", str(wt), cwd=ROOT)
            sh("git", "checkout", "--orphan", branch, cwd=wt)
            sh("git", "rm", "-rf", "--ignore-unmatch", ".", cwd=wt)
    for rel, local in files.items():
        dest = wt / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(Path(local).read_bytes())
    sh("git", "add", "-A", cwd=wt)
    if sh("git", "status", "--porcelain", cwd=wt):
        sh("git", "-c", "user.name=autopilot", "-c", "user.email=autopilot@users.noreply.github.com", "commit", "-m", message, cwd=wt)
    sh("git", "push", "origin", f"HEAD:{branch}", cwd=wt)


def squash_media(keep_last=60):
    """Collapse media history to one commit (files stay, history goes)."""
    branch = settings()["media_branch"]
    wt = BUILD / "media-worktree"
    if not wt.exists():
        return
    sh("git", "checkout", "--orphan", "tmp-squash", cwd=wt)
    sh("git", "add", "-A", cwd=wt)
    sh("git", "-c", "user.name=autopilot", "-c", "user.email=autopilot@users.noreply.github.com", "commit", "-m", "squash media", cwd=wt)
    sh("git", "push", "--force", "origin", f"HEAD:{branch}", cwd=wt)
