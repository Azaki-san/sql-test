import os
import time
import shutil
import subprocess

from fastapi import UploadFile, HTTPException
from pymediainfo import MediaInfo

from app.utils.viewer_count import get_viewer_count

FFMPEG_CMD: str | None = None

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
ALLOWED_CONTENT_TYPES = {
    ".mp4":  "video/mp4",
    ".mov":  "video/quicktime",
    ".avi":  "video/x-msvideo",
    ".mkv":  "video/x-matroska",
    ".webm": "video/webm",
}

_shared_dir = "shared_video"
_video_state = {
    "filename": None,
    "start_time": None,
    "expected_end_time": None,
}


def _ensure_ffmpeg_available():
    global FFMPEG_CMD
    if FFMPEG_CMD:
        return

    env = os.environ.get("FFMPEG_PATH")
    if env and os.path.isfile(env):
        FFMPEG_CMD = env
        return

    shim = shutil.which("ffmpeg")
    if shim:
        FFMPEG_CMD = "ffmpeg"
        return

    candidates = []
    if os.name == "nt":
        user = os.environ.get("USERPROFILE", "")
        pf   = os.environ.get("ProgramFiles", "")
        pfx  = os.environ.get("ProgramFiles(x86)", "")
        candidates.extend([
            os.path.join(user, "AppData", "Local", "Microsoft", "WinGet", "Links", "ffmpeg.exe"),
            os.path.join(pf,  "Gyan", "FFmpeg", "bin", "ffmpeg.exe"),
            os.path.join(pf,  "ffmpeg", "bin", "ffmpeg.exe"),
            os.path.join(pfx, "Gyan", "FFmpeg", "bin", "ffmpeg.exe"),
        ])
    else:
        candidates.extend([
            "/usr/local/bin/ffmpeg",
            "/opt/homebrew/bin/ffmpeg",  # Apple Silicon
            "/usr/bin/ffmpeg",
            "/snap/bin/ffmpeg",
        ])

    for p in candidates:
        if os.path.isfile(p):
            FFMPEG_CMD = p
            return

    raise HTTPException(
        status_code=400,
        detail=(
            "'ffmpeg' not found: install ffmpeg and ensure it's on your PATH, "
            "or set FFMPEG_PATH to the full path of the ffmpeg executable."
        )
    )


def _get_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def _validate_extension(filename: str):
    ext = _get_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid extension '{ext}': only {', '.join(sorted(ALLOWED_EXTENSIONS))} are allowed."
        )


def _validate_content_type(content_type: str | None, filename: str):
    if not content_type:
        return
    ext = _get_extension(filename)
    expected = ALLOWED_CONTENT_TYPES.get(ext)
    if expected and content_type != expected:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content type '{content_type}' for '{ext}', expected '{expected}'."
        )


def _get_upload_path(filename: str) -> str:
    os.makedirs(_shared_dir, exist_ok=True)
    return os.path.join(_shared_dir, filename)


async def _save_file(file: UploadFile, path: str):
    contents = await file.read()
    with open(path, "wb") as f:
        f.write(contents)


def _cleanup_file(path: str):
    try:
        os.remove(path)
    except OSError:
        pass


def _check_video_corruption(path: str):
    _ensure_ffmpeg_available()
    cmd = [FFMPEG_CMD, "-loglevel", "error", "-i", path, "-f", "null", "-"]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        errs = proc.stderr.strip() or "unknown error"
        raise HTTPException(status_code=400, detail=f"Video corruption detected: {errs}")


def _get_video_duration(path: str) -> float:
    media_info = MediaInfo.parse(path)
    for track in media_info.tracks:
        if track.track_type == "Video" and track.duration:
            return float(track.duration) / 1000.0
    raise HTTPException(status_code=400, detail="No video track found in file.")


def check_and_expire_video():
    exp = _video_state["expected_end_time"]
    if exp and time.time() >= exp:
        end_video()


def _set_video_state(filename: str, duration: float):
    now = time.time()
    _video_state["filename"] = filename
    _video_state["start_time"] = now
    _video_state["expected_end_time"] = now + duration


def end_video():
    _video_state["filename"] = None
    _video_state["start_time"] = None
    _video_state["expected_end_time"] = None


async def upload_video(file: UploadFile):
    check_and_expire_video()
    if _video_state["filename"]:
        raise HTTPException(status_code=409, detail="Video already playing")

    try:
        _validate_extension(file.filename)
        _validate_content_type(file.content_type, file.filename)
    except HTTPException as e:
        return {"success": False, "error": e.detail}

    path = _get_upload_path(file.filename)
    await _save_file(file, path)

    try:
        _check_video_corruption(path)
        duration = _get_video_duration(path)
    except HTTPException as e:
        _cleanup_file(path)
        return {"success": False, "error": e.detail}
    except Exception as e:
        _cleanup_file(path)
        return {"success": False, "error": str(e)}

    _set_video_state(file.filename, duration)
    return {
        "success": True,
        "message": "Video uploaded",
        "filename": file.filename,
        "duration": duration
    }


def get_video_status():
    check_and_expire_video()

    if not _video_state["filename"]:
        return {"status": "no_video"}

    elapsed = time.time() - _video_state["start_time"]
    return {
        "filename": _video_state["filename"],
        "elapsed": elapsed,
        "status": "playing",
        "viewers": get_viewer_count()
    }




def end_video():
    _video_state["filename"] = None
    _video_state["start_time"] = None
    _video_state["duration"] = None


def get_video_filename_path():
    check_and_expire_video()
    if not _video_state["filename"]:
        raise HTTPException(status_code=404, detail="No video playing")
    path = _get_upload_path(_video_state["filename"])
    return path, _video_state["filename"]


def check_and_expire_video():
    if _video_state["expected_end_time"] and time.time() >= _video_state["expected_end_time"]:
        end_video()


def end_video():
    _video_state["filename"] = None
    _video_state["start_time"] = None
    _video_state["expected_end_time"] = None
