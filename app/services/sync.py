import time
from pathlib import Path

from fastapi import UploadFile, HTTPException
import os
from pymediainfo import MediaInfo

from app.utils.viewer_count import get_viewer_count

VIDEO_DIR = Path("shared_video")          # <- KEEP in sync with main.py
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

_video_state: dict[str, float | str | None] = {
    "filename": None,          # str | None
    "start_time": None,        # float | None (epoch seconds)
    "expected_end": None,      # float | None
}

def _parse_duration(path: Path) -> float:
    """Return video duration in seconds (float)."""
    media = MediaInfo.parse(path)
    for track in media.tracks:
        if track.track_type == "Video" and track.duration:          # ms
            return float(track.duration) / 1000.0
    raise RuntimeError("No video track found")


def _expire_if_finished() -> None:
    """Clear state when the current video has finished playing."""
    if _video_state["expected_end"] and time.time() >= _video_state["expected_end"]:
        _video_state.update(filename=None, start_time=None, expected_end=None)

# --------------------------------------------------------------------------- #
# public API used by the routers
# --------------------------------------------------------------------------- #
async def upload_video(file: UploadFile) -> dict:
    """Save the file and start a new session. Raises 409 if one is active."""
    _expire_if_finished()
    if _video_state["filename"]:
        raise HTTPException(status_code=409, detail="Video already playing")

    target = VIDEO_DIR / file.filename
    contents = await file.read()
    target.write_bytes(contents)

    try:
        duration = _parse_duration(target)
    except Exception as e:                      # duration extraction failed
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Failed to parse duration: {e}")

    now = time.time()
    _video_state.update(
        filename=file.filename,
        start_time=now,
        expected_end=now + duration,
    )
    return {"message": "video uploaded", "filename": file.filename, "duration": duration}


def get_video_status() -> dict:
    """Return current state − called by /status."""
    _expire_if_finished()
    if not _video_state["filename"]:
        return {"status": "idle"}

    elapsed = time.time() - float(_video_state["start_time"])      # type: ignore
    return {
        "status": "playing",
        "filename": _video_state["filename"],
        "elapsed": elapsed,
        "viewers": get_viewer_count(),
    }


def end_video() -> None:
    """Force‑stop the current session."""
    _video_state.update(filename=None, start_time=None, expected_end=None)


def get_video_filename_path() -> tuple[str, str]:
    """Return (absolute_path, filename) for the current file or 404."""
    _expire_if_finished()
    if not _video_state["filename"]:
        raise HTTPException(status_code=404, detail="No video playing")
    path = VIDEO_DIR / _video_state["filename"]
    return str(path), _video_state["filename"]
