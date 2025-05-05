from fastapi import APIRouter, UploadFile, Request, HTTPException
from starlette.responses import JSONResponse, FileResponse
from app.services.sync import get_video_status, upload_video, end_video, get_video_filename_path
from app.utils.viewer_count import viewer_ping, get_viewer_count
from app.services.weather import get_weather
from app.db.database import increment_video_stat, get_video_stat

router = APIRouter()

@router.post("/upload")
async def upload(file: UploadFile):
    try:
        result = await upload_video(file)
    except HTTPException as exc:
        if exc.status_code == 400:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": exc.detail}
            )
        raise

    increment_video_stat()
    return {"success": True, **result}

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

@router.get("/video")
def get_video_file():
    path, filename = get_video_filename_path()
    return FileResponse(path, media_type="video/mp4", filename=filename)

@router.get("/weather")
def weather():
    return get_weather()
