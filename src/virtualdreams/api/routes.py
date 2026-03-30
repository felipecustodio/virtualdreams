import asyncio
import json
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pathlib import Path
from pydantic import BaseModel

from ..jobs.models import JobStatus

router = APIRouter()


class CreateJobRequest(BaseModel):
    query: str


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@router.post("/jobs", status_code=202)
async def create_job(body: CreateJobRequest, request: Request) -> dict:
    job = request.app.state.job_manager.create_job(body.query)
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
