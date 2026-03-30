import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from virtualdreams.jobs.manager import JobManager
from virtualdreams.jobs.models import JobStatus


async def test_pipeline_completes(tmp_path):
    manager = JobManager()

    async def fake_download(query, output_dir):
        wav = output_dir / "test.wav"
        wav.write_bytes(b"RIFF")
        return wav

    async def fake_chorus(input_path, output_path, duration=15):
        output_path.write_bytes(b"RIFF")

    async def fake_effects(input_path, output_path):
        output_path.write_bytes(b"RIFF")

    with (
        patch("virtualdreams.jobs.manager.download_audio", side_effect=fake_download),
        patch("virtualdreams.jobs.manager.extract_chorus", side_effect=fake_chorus),
        patch("virtualdreams.jobs.manager.apply_vaporwave", side_effect=fake_effects),
    ):
        job = manager.create_job("lofi chill")
        await asyncio.sleep(0.1)

    assert job.status == JobStatus.COMPLETED
    assert job.audio_path is not None
    assert Path(job.audio_path).exists()

    Path(job.audio_path).unlink(missing_ok=True)


async def test_pipeline_marks_failed_on_error():
    manager = JobManager()

    with patch(
        "virtualdreams.jobs.manager.download_audio",
        side_effect=RuntimeError("yt-dlp failed: no results"),
    ):
        job = manager.create_job("nonexistent song xyz")
        await asyncio.sleep(0.1)

    assert job.status == JobStatus.FAILED
    assert "yt-dlp failed" in job.error
