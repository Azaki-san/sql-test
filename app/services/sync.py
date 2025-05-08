"""
sync.py  –  upload / status helpers for SharedVideo backend
⚠  VIDEO_DIR **must** match the StaticFiles mount in main.py:
    app.mount("/videos", StaticFiles(directory=VIDEO_DIR), name="videos")
"""

from __future__ import annotations
import os
import time
import shutil
import subprocess
from pathlib import Path
from typing import Final

from fastapi import UploadFile, HTTPException
from pymediainfo import MediaInfo

from app.utils.viewer_count import get_viewer_count

# ─────────────────────────────────────────────────────────────────────────────
# configuration
# ─────────────────────────────────────────────────────────────────────────────
VIDEO_DIR: Final[Path] = Path("shared_video")  # writable, persisted via volume
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS: Final[set[str]] = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
ALLOWED_CONTENT_TYPES: Final[dict[str, str]] = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
}

# find ffmpeg once and cache the command
FFMPEG_CMD: str | None = None

# in‑memory playback state
_state: dict[str, float | str | None] = {
    "filename": None,  # str | None
    "start_time": None,  # float | None  (epoch seconds)
    "expected_end": None,  # float | None
}


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────
def _ensure_ffmpeg() -> None:
    """Locate ffmpeg executable the first time we need it."""
    global FFMPEG_CMD
    if FFMPEG_CMD:  # already found
        return

    env = os.environ.get("FFMPEG_PATH")
    if env and Path(env).is_file():
        FFMPEG_CMD = env
        return

    shim = shutil.which("ffmpeg")
    if shim:
        FFMPEG_CMD = "ffmpeg"
        return

    # fall‑back guesses
    guesses = ["/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg",
               "/opt/homebrew/bin/ffmpeg", "/snap/bin/ffmpeg"]
    if os.name == "nt":
        user = os.environ.get("USERPROFILE", "")
        pf = os.environ.get("ProgramFiles", "")
        pfx = os.environ.get("ProgramFiles(x86)", "")
        guesses += [
            Path(user, "AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe"),
            Path(pf, "Gyan/FFmpeg/bin/ffmpeg.exe"),
            Path(pf, "ffmpeg/bin/ffmpeg.exe"),
            Path(pfx, "Gyan/FFmpeg/bin/ffmpeg.exe"),
        ]
    for g in guesses:
        if Path(g).is_file():
            FFMPEG_CMD = str(g)
            return

    raise HTTPException(
        400,
        "'ffmpeg' not found. Install it or set env FFMPEG_PATH to the binary.",
    )


def _ext(fname: str) -> str:
    return Path(fname).suffix.lower()


def _validate_upload(file: UploadFile) -> None:
    ext = _ext(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported extension '{ext}'")

    if file.content_type:
        expected = ALLOWED_CONTENT_TYPES.get(ext)
        if expected and file.content_type != expected:
            raise HTTPException(
                400,
                f"Wrong content‑type '{file.content_type}'"
                f", expected '{expected}'",
            )


def _probe_corruption(path: Path) -> None:
    """Run ffmpeg ‑v error -i <file> -f null - ; raise if non‑zero exit."""
    _ensure_ffmpeg()
    proc = subprocess.run(
        [FFMPEG_CMD, "-loglevel", "error", "-i", str(path), "-f", "null", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if proc.returncode != 0:
        msg = proc.stderr.strip() or "ffmpeg error"
        raise HTTPException(400, f"Video corruption detected: {msg}")


def _parse_duration(path: Path) -> float:
    media = MediaInfo.parse(path)
    for tr in media.tracks:
        if tr.track_type == "Video" and tr.duration:
            return float(tr.duration) / 1000.0
    raise HTTPException(400, "No video track found")


def _expire_if_finished() -> None:
    """Clear state when playback time runs out."""
    if _state["expected_end"] and time.time() >= _state["expected_end"]:
        _state.update(filename=None, start_time=None, expected_end=None)


# ─────────────────────────────────────────────────────────────────────────────
# public API
# ─────────────────────────────────────────────────────────────────────────────
async def upload_video(file: UploadFile) -> dict:
    """Save, validate and start playback.
    409 if something is already playing."""
    _expire_if_finished()
    if _state["filename"]:
        raise HTTPException(409, "A video is already playing")

    _validate_upload(file)

    target = VIDEO_DIR / file.filename
    target.write_bytes(await file.read())

    try:
        _probe_corruption(target)
        duration = _parse_duration(target)
    except HTTPException:
        target.unlink(missing_ok=True)
        raise

    now = time.time()
    _state.update(filename=file.filename,
                  start_time=now, expected_end=now + duration)

    return {"message": "video uploaded",
            "filename": file.filename, "duration": duration}


def get_video_status() -> dict:
    """Return status for /status endpoint."""
    _expire_if_finished()
    if not _state["filename"]:
        return {"status": "idle"}

    elapsed = time.time() - float(_state["start_time"])  # type: ignore
    return {
        "status": "playing",
        "filename": _state["filename"],
        "elapsed": elapsed,
        "viewers": get_viewer_count(),
    }


def end_video() -> None:
    """Force‑stop current playback (used by /end)."""
    _state.update(filename=None, start_time=None, expected_end=None)


def get_video_filename_path() -> tuple[str, str]:
    """Return (abs_path, filename) or 404 if nothing is playing."""
    _expire_if_finished()
    if not _state["filename"]:
        raise HTTPException(404, "No video playing")
    path = VIDEO_DIR / _state["filename"]
    return str(path), _state["filename"]
