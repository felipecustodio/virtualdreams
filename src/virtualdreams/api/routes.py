import asyncio
import json
import os
import tempfile
from pathlib import Path

import aiofiles
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from ..jobs.models import JobStatus

router = APIRouter()


class CreateJobRequest(BaseModel):
    query: str


def youtube_input_enabled() -> bool:
    return os.getenv("ENABLE_YOUTUBE_INPUT", "false").lower() in {"1", "true", "yes", "on"}


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@router.get("/config")
async def config() -> dict:
    return {"youtube_input_enabled": youtube_input_enabled()}


@router.post("/jobs", status_code=202)
async def create_job(body: CreateJobRequest, request: Request) -> dict:
    if not youtube_input_enabled():
        raise HTTPException(
            status_code=403,
            detail="YouTube input is disabled on this deployment. Upload audio instead.",
        )
    job = request.app.state.job_manager.create_query_job(body.query)
    return {"job_id": job.job_id}


@router.post("/jobs/upload", status_code=202)
async def create_upload_job(
    request: Request,
    file: UploadFile = File(...),
) -> dict:
    suffix = Path(file.filename or "upload.bin").suffix or ".bin"
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_path = Path(temp_file.name)
    temp_file.close()

    try:
        async with aiofiles.open(temp_path, "wb") as uploaded:
            while chunk := await file.read(1024 * 1024):
                await uploaded.write(chunk)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    job = request.app.state.job_manager.create_upload_job(str(temp_path))
    return {"job_id": job.job_id}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, request: Request) -> dict:
    job = request.app.state.job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job.job_id, "status": job.status, "error": job.error}


@router.get("/jobs/{job_id}/events")
async def stream_job(job_id: str, request: Request) -> StreamingResponse:
    job = request.app.state.job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_stream():
        last_payload: str | None = None

        while True:
            current = request.app.state.job_manager.get_job(job_id)
            if current is None:
                payload = json.dumps({"job_id": job_id, "status": "missing", "error": None})
                yield f"event: missing\ndata: {payload}\n\n"
                break

            payload = json.dumps(
                {
                    "job_id": current.job_id,
                    "status": current.status,
                    "error": current.error,
                }
            )
            if payload != last_payload:
                yield f"data: {payload}\n\n"
                last_payload = payload

            if current.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                break

            if await request.is_disconnected():
                break

            await asyncio.sleep(0.25)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/jobs/{job_id}/audio")
async def get_audio(
    job_id: str, request: Request, background_tasks: BackgroundTasks
) -> FileResponse:
    job = request.app.state.job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=404, detail="Job not completed")
    if job.fetched:
        raise HTTPException(status_code=410, detail="Audio already fetched")

    path = Path(job.audio_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    job.fetched = True
    background_tasks.add_task(path.unlink, missing_ok=True)
    return FileResponse(path=str(path), media_type="audio/wav", filename="vapor.wav")
