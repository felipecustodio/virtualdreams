import asyncio
import time
import pytest
from unittest.mock import AsyncMock, patch
from virtualdreams.jobs.manager import JobManager, JOB_TTL
from virtualdreams.jobs.models import JobStatus


@pytest.fixture
def manager():
    return JobManager()


async def test_create_job_returns_job(manager):
    with patch.object(manager, "_run_pipeline", new=AsyncMock()):
        job = manager.create_job("test query")
    assert job.job_id
    assert job.status == JobStatus.PENDING


async def test_get_job_returns_existing(manager):
    with patch.object(manager, "_run_pipeline", new=AsyncMock()):
        job = manager.create_job("test query")
    found = manager.get_job(job.job_id)
    assert found is job


def test_get_job_returns_none_for_missing(manager):
    assert manager.get_job("nonexistent") is None


async def test_evict_expired_removes_old_jobs(manager):
    with patch.object(manager, "_run_pipeline", new=AsyncMock()):
        job = manager.create_job("test query")
    job.created_at = time.time() - (JOB_TTL + 1)
    manager._evict_expired()
    assert manager.get_job(job.job_id) is None


async def test_evict_expired_deletes_audio_file(manager, tmp_path):
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"fake")
    with patch.object(manager, "_run_pipeline", new=AsyncMock()):
        job = manager.create_job("test query")
    job.audio_path = str(audio)
    job.created_at = time.time() - (JOB_TTL + 1)
    manager._evict_expired()
    assert not audio.exists()


async def test_evict_expired_keeps_fresh_jobs(manager):
    with patch.object(manager, "_run_pipeline", new=AsyncMock()):
        job = manager.create_job("test query")
    manager._evict_expired()
    assert manager.get_job(job.job_id) is job


async def test_create_upload_job_returns_job(manager, tmp_path):
    upload = tmp_path / "upload.mp3"
    upload.write_bytes(b"fake")

    with patch.object(manager, "_run_pipeline", new=AsyncMock()):
        job = manager.create_upload_job(str(upload))

    assert job.job_id
    assert job.status == JobStatus.PENDING
