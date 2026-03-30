from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel

from ..jobs.models import JobStatus

router = APIRouter()


class CreateJobRequest(BaseModel):
    query: str


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
