import time
from fastapi import UploadFile, HTTPException
import os
from pymediainfo import MediaInfo

from app.utils.viewer_count import get_viewer_count

_video_state = {
    "filename": None,
    "start_time": None,
    "expected_end_time": None
}


async def upload_video(file: UploadFile):
    check_and_expire_video()

    if _video_state["filename"]:
        raise HTTPException(status_code=409, detail="Video already playing")

    os.makedirs("shared_video", exist_ok=True)
    contents = await file.read()
    path = f"shared_video/{file.filename}"
    with open(path, "wb") as f:
        f.write(contents)

    try:
        duration = get_video_duration(path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse duration: {e}")

    _video_state["filename"] = file.filename
    _video_state["start_time"] = time.time()
    _video_state["expected_end_time"] = _video_state["start_time"] + duration

    return {"message": "Video uploaded", "filename": file.filename, "duration": duration}


def get_video_duration(path):
    media_info = MediaInfo.parse(path)
    for track in media_info.tracks:
        if track.track_type == "Video":
            return float(track.duration) / 1000
    raise Exception("No video track found")


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

    path = f"shared_video/{_video_state['filename']}"
    return path, _video_state["filename"]


def check_and_expire_video():
    if _video_state["expected_end_time"] and time.time() >= _video_state["expected_end_time"]:
        end_video()


def end_video():
    _video_state["filename"] = None
    _video_state["start_time"] = None
    _video_state["expected_end_time"] = None
