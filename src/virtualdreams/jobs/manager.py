import asyncio
import time
from pathlib import Path

from .models import Job, JobStatus

JOB_TTL = 600  # seconds
CLEANUP_INTERVAL = 60  # seconds


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._cleanup_task: asyncio.Task | None = None

    def start(self) -> None:
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    def create_job(self, query: str) -> Job:
        job = Job()
        self._jobs[job.job_id] = job
        asyncio.create_task(self._run_pipeline(job.job_id, query))
        return job

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    async def _run_pipeline(self, job_id: str, query: str) -> None:
        # Implemented in Task 7 — wired after pipeline modules exist
        pass

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(CLEANUP_INTERVAL)
            self._evict_expired()

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [
            jid
            for jid, job in self._jobs.items()
            if now - job.created_at > JOB_TTL
        ]
        for jid in expired:
            job = self._jobs.pop(jid)
            if job.audio_path:
                Path(job.audio_path).unlink(missing_ok=True)
