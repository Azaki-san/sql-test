from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.routes import router

VIDEO_DIR = Path("shared_video")

app = FastAPI(title="SharedVideo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.mount("/videos", StaticFiles(directory=VIDEO_DIR), name="videos")
app.include_router(router)
