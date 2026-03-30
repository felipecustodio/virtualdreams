import asyncio
import shutil
import tempfile
import time
from pathlib import Path

from .models import Job, JobStatus
from ..pipeline.download import download_audio
from ..pipeline.chorus import extract_chorus
from ..pipeline.effects import apply_vaporwave

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
        job = self._jobs.get(job_id)
        if job is None:
            return
        job.status = JobStatus.RUNNING

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)

                wav_path = await download_audio(query, tmp)
                chorus_path = tmp / "chorus.wav"
                vapor_path = tmp / "vapor.wav"

                await extract_chorus(wav_path, chorus_path)
                await apply_vaporwave(chorus_path, vapor_path)

                # Move out of tmpdir before it is cleaned up
                final = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                final.close()
                shutil.move(str(vapor_path), final.name)

                job.audio_path = final.name
                job.status = JobStatus.COMPLETED

        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)

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
