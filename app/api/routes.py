from fastapi import APIRouter, UploadFile, Request
from app.services.sync import get_video_status, upload_video, end_video
from app.utils.viewer_count import viewer_ping, get_viewer_count
from app.services.weather import get_weather
from app.db.database import increment_video_stat
from app.services.sync import get_video_filename_path
from app.db.database import get_video_stat

router = APIRouter()


@router.post("/upload")
async def upload(file: UploadFile):
    response = await upload_video(file)
    increment_video_stat()
    return response

@router.get("/stats")
def stats():
    return {"total_played": get_video_stat()}



@router.get("/status")
def status():
    return get_video_status()


@router.post("/ping")
def ping(request: Request):
    viewer_id = request.client.host
    viewer_ping(viewer_id)
    return {"viewers": get_viewer_count()}


@router.post("/end")
def end():
    end_video()
    return {"message": "Video ended"}


from fastapi.responses import FileResponse


@router.get("/video")
def get_video_file():
    path, filename = get_video_filename_path()
    return FileResponse(path, media_type="video/mp4", filename=filename)


@router.get("/weather")
def weather():
    return get_weather()
