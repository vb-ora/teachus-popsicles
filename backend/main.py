import os
import mimetypes
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
import aiofiles
from fastapi import HTTPException
from starlette.responses import StreamingResponse

from database import engine, Base
import models
from routers import auth, users, stuecke, audios, markierungen, kapitel, favoriten
from auth import hash_password
from database import SessionLocal

app = FastAPI(title="TeachUs", docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(stuecke.router)
app.include_router(audios.router)
app.include_router(markierungen.router)
app.include_router(kapitel.router)
app.include_router(favoriten.router)


@app.on_event("startup")
def startup():
    os.makedirs("/data/uploads", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _create_admin_if_missing()


def _create_admin_if_missing():
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "admin")
    db = SessionLocal()
    try:
        existing = db.query(models.User).filter(models.User.username == username).first()
        if not existing:
            admin = models.User(
                name="Administrator",
                username=username,
                password_hash=hash_password(password),
                rolle="admin",
                stimme=None,
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()


# Audio-Dateien ausliefern mit Range-Request-Support (wichtig für Mobile-Seeking)
@app.get("/files/{audio_id}")
async def serve_audio(audio_id: int, request: Request):
    db = SessionLocal()
    try:
        audio = db.query(models.Audio).filter(models.Audio.id == audio_id).first()
        if not audio or not os.path.exists(audio.dateipfad):
            raise HTTPException(status_code=404, detail="Datei nicht gefunden")
        filepath = audio.dateipfad
        dateiname = audio.dateiname
    finally:
        db.close()

    mime, _ = mimetypes.guess_type(dateiname)
    if not mime:
        mime = "application/octet-stream"

    file_size = os.path.getsize(filepath)
    range_header = request.headers.get("range")

    if range_header:
        try:
            range_val = range_header.replace("bytes=", "")
            start_str, end_str = range_val.split("-")
            start = int(start_str)
            end = int(end_str) if end_str else file_size - 1
        except Exception:
            raise HTTPException(status_code=416, detail="Invalid range")

        if start >= file_size or end > file_size - 1:
            raise HTTPException(
                status_code=416,
                headers={"Content-Range": f"bytes */{file_size}"},
                detail="Range not satisfiable",
            )

        chunk_size = end - start + 1

        async def ranged_stream():
            async with aiofiles.open(filepath, "rb") as f:
                await f.seek(start)
                remaining = chunk_size
                while remaining > 0:
                    data = await f.read(min(65536, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return StreamingResponse(
            ranged_stream(),
            status_code=206,
            media_type=mime,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_size),
                "Content-Disposition": f'inline; filename="{dateiname}"',
            },
        )

    async def full_stream():
        async with aiofiles.open(filepath, "rb") as f:
            while chunk := await f.read(65536):
                yield chunk

    return StreamingResponse(
        full_stream(),
        media_type=mime,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Content-Disposition": f'inline; filename="{dateiname}"',
        },
    )


# Frontend statisch ausliefern
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        # Let API and files routes fall through normally
        if full_path.startswith("api/") or full_path.startswith("files/"):
            raise HTTPException(status_code=404)
        index = os.path.join(static_dir, "index.html")
        if os.path.exists(index):
            return FileResponse(index)
        return Response(content="Not found", status_code=404)
