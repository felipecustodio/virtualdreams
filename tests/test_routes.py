import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from virtualdreams.jobs.models import JobStatus


@pytest.fixture
async def client():
    from virtualdreams.main import app
    from virtualdreams.jobs.manager import JobManager

    # ASGITransport doesn't trigger lifespan, so wire state manually
    app.state.job_manager = JobManager()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_create_job_returns_202(client):
    with patch("virtualdreams.jobs.manager.JobManager._run_pipeline", new=AsyncMock()):
        resp = await client.post("/jobs", json={"query": "lofi chill"})
    assert resp.status_code == 202
    assert "job_id" in resp.json()


async def test_get_job_pending(client):
    with patch("virtualdreams.jobs.manager.JobManager._run_pipeline", new=AsyncMock()):
        create = await client.post("/jobs", json={"query": "lofi chill"})
    job_id = create.json()["job_id"]

    resp = await client.get(f"/jobs/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == job_id
    assert data["status"] in ("pending", "running")


async def test_get_job_not_found(client):
    resp = await client.get("/jobs/nonexistent-id")
    assert resp.status_code == 404


async def test_get_audio_completed(client, tmp_path):
    audio_file = tmp_path / "vapor.wav"
    audio_file.write_bytes(b"RIFF" + b"\x00" * 100)

    with patch("virtualdreams.jobs.manager.JobManager._run_pipeline", new=AsyncMock()):
        create = await client.post("/jobs", json={"query": "lofi chill"})
    job_id = create.json()["job_id"]

    job_manager = client._transport.app.state.job_manager  # type: ignore[attr-defined]
    job = job_manager.get_job(job_id)
    job.status = JobStatus.COMPLETED
    job.audio_path = str(audio_file)

    resp = await client.get(f"/jobs/{job_id}/audio")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/wav"
    assert job.fetched is True


async def test_get_audio_already_fetched(client, tmp_path):
    audio_file = tmp_path / "vapor.wav"
    audio_file.write_bytes(b"RIFF" + b"\x00" * 100)

    with patch("virtualdreams.jobs.manager.JobManager._run_pipeline", new=AsyncMock()):
        create = await client.post("/jobs", json={"query": "lofi chill"})
    job_id = create.json()["job_id"]

    job_manager = client._transport.app.state.job_manager  # type: ignore[attr-defined]
    job = job_manager.get_job(job_id)
    job.status = JobStatus.COMPLETED
    job.audio_path = str(audio_file)
    job.fetched = True

    resp = await client.get(f"/jobs/{job_id}/audio")
    assert resp.status_code == 410


async def test_get_audio_not_completed(client):
    with patch("virtualdreams.jobs.manager.JobManager._run_pipeline", new=AsyncMock()):
        create = await client.post("/jobs", json={"query": "lofi chill"})
    job_id = create.json()["job_id"]

    resp = await client.get(f"/jobs/{job_id}/audio")
    assert resp.status_code == 404
