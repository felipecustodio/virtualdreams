# VirtualDreams Modernization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the old Telegram bot monolith with a clean async REST API backed by a Rust chorus detector and ffmpeg effects pipeline.

**Architecture:** FastAPI app with in-memory async job queue; three pipeline stages (yt-dlp download → Rust chorus detector → ffmpeg vaporwave) run as asyncio background tasks inside a temporary directory. A TTL-based cleanup loop evicts stale jobs and orphaned audio files every 60 seconds.

**Tech Stack:** Python 3.14, FastAPI, uvicorn, asyncio, yt-dlp (subprocess), ffmpeg (subprocess), Rust + hound + rustfft + clap (subprocess binary)

---

## Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/virtualdreams/__init__.py`
- Create: `src/virtualdreams/main.py` (empty placeholder)
- Create: `src/virtualdreams/api/__init__.py`
- Create: `src/virtualdreams/jobs/__init__.py`
- Create: `src/virtualdreams/pipeline/__init__.py`
- Create: `tests/__init__.py`
- Create: `.env.example`

**Step 1: Create `pyproject.toml`**

```toml
[project]
name = "virtualdreams"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.24",
    "httpx>=0.27",
]

[project.scripts]
virtualdreams = "virtualdreams.main:run"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/virtualdreams"]

[tool.ruff]
line-length = 88
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 2: Create `.env.example`**

```
CHORUS_DETECTOR_BIN=./chorus-detector/target/release/chorus-detector
HOST=0.0.0.0
PORT=8000
```

**Step 3: Create package `__init__.py` files and directory stubs**

All `__init__.py` files are empty. Create the directories:
- `src/virtualdreams/api/`
- `src/virtualdreams/jobs/`
- `src/virtualdreams/pipeline/`
- `tests/`

**Step 4: Install dependencies**

```bash
uv sync --extra dev
```

Expected: environment created, all packages installed.

**Step 5: Commit**

```bash
git add pyproject.toml .env.example src/ tests/
git commit -m "chore: scaffold project structure"
```

---

## Task 2: Job models

**Files:**
- Create: `src/virtualdreams/jobs/models.py`
- Create: `tests/test_job_models.py`

**Step 1: Write the failing test**

```python
# tests/test_job_models.py
import time
from virtualdreams.jobs.models import Job, JobStatus

def test_job_defaults():
    job = Job()
    assert job.job_id  # non-empty string
    assert job.status == JobStatus.PENDING
    assert job.error is None
    assert job.audio_path is None
    assert job.fetched is False
    assert job.created_at <= time.time()

def test_job_id_unique():
    a = Job()
    b = Job()
    assert a.job_id != b.job_id

def test_job_status_values():
    assert JobStatus.PENDING == "pending"
    assert JobStatus.RUNNING == "running"
    assert JobStatus.COMPLETED == "completed"
    assert JobStatus.FAILED == "failed"
```

**Step 2: Run to verify failure**

```bash
uv run pytest tests/test_job_models.py -v
```

Expected: `ModuleNotFoundError`

**Step 3: Implement**

```python
# src/virtualdreams/jobs/models.py
from dataclasses import dataclass, field
from enum import StrEnum
import time
import uuid


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.PENDING
    error: str | None = None
    audio_path: str | None = None
    fetched: bool = False
    created_at: float = field(default_factory=time.time)
```

**Step 4: Run to verify pass**

```bash
uv run pytest tests/test_job_models.py -v
```

Expected: all 3 tests PASS.

**Step 5: Commit**

```bash
git add src/virtualdreams/jobs/models.py tests/test_job_models.py
git commit -m "feat: add Job model and JobStatus enum"
```

---

## Task 3: Job manager

**Files:**
- Create: `src/virtualdreams/jobs/manager.py`
- Create: `tests/test_job_manager.py`

**Step 1: Write the failing tests**

```python
# tests/test_job_manager.py
import asyncio
import time
import pytest
from unittest.mock import AsyncMock, patch
from virtualdreams.jobs.manager import JobManager, JOB_TTL
from virtualdreams.jobs.models import JobStatus


@pytest.fixture
def manager():
    return JobManager()


def test_create_job_returns_job(manager):
    with patch.object(manager, "_run_pipeline", new=AsyncMock()):
        job = manager.create_job("test query")
    assert job.job_id
    assert job.status == JobStatus.PENDING


def test_get_job_returns_existing(manager):
    with patch.object(manager, "_run_pipeline", new=AsyncMock()):
        job = manager.create_job("test query")
    found = manager.get_job(job.job_id)
    assert found is job


def test_get_job_returns_none_for_missing(manager):
    assert manager.get_job("nonexistent") is None


def test_evict_expired_removes_old_jobs(manager, tmp_path):
    with patch.object(manager, "_run_pipeline", new=AsyncMock()):
        job = manager.create_job("test query")
    # Backdate the job
    job.created_at = time.time() - (JOB_TTL + 1)
    manager._evict_expired()
    assert manager.get_job(job.job_id) is None


def test_evict_expired_deletes_audio_file(manager, tmp_path):
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"fake")
    with patch.object(manager, "_run_pipeline", new=AsyncMock()):
        job = manager.create_job("test query")
    job.audio_path = str(audio)
    job.created_at = time.time() - (JOB_TTL + 1)
    manager._evict_expired()
    assert not audio.exists()


def test_evict_expired_keeps_fresh_jobs(manager):
    with patch.object(manager, "_run_pipeline", new=AsyncMock()):
        job = manager.create_job("test query")
    manager._evict_expired()
    assert manager.get_job(job.job_id) is job
```

**Step 2: Run to verify failure**

```bash
uv run pytest tests/test_job_manager.py -v
```

Expected: `ModuleNotFoundError`

**Step 3: Implement**

```python
# src/virtualdreams/jobs/manager.py
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
```

**Step 4: Run to verify pass**

```bash
uv run pytest tests/test_job_manager.py -v
```

Expected: all 6 tests PASS.

**Step 5: Commit**

```bash
git add src/virtualdreams/jobs/manager.py tests/test_job_manager.py
git commit -m "feat: add JobManager with TTL-based cleanup"
```

---

## Task 4: Pipeline — download

**Files:**
- Create: `src/virtualdreams/pipeline/download.py`
- Create: `tests/test_pipeline_download.py`

**Step 1: Write the failing tests**

```python
# tests/test_pipeline_download.py
import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from virtualdreams.pipeline.download import download_audio


@pytest.fixture
def tmp(tmp_path):
    return tmp_path


async def _mock_proc(returncode: int, stdout: bytes = b"", stderr: bytes = b""):
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


async def test_download_success(tmp):
    # Simulate yt-dlp creating a wav file
    fake_wav = tmp / "abc123.wav"
    fake_wav.write_bytes(b"RIFF")

    with patch("asyncio.create_subprocess_exec", return_value=await _mock_proc(0)):
        result = await download_audio("lofi chill", tmp)

    assert result == fake_wav


async def test_download_raises_on_nonzero(tmp):
    with patch("asyncio.create_subprocess_exec", return_value=await _mock_proc(1, stderr=b"error")):
        with pytest.raises(RuntimeError, match="yt-dlp failed"):
            await download_audio("lofi chill", tmp)


async def test_download_raises_if_no_wav(tmp):
    with patch("asyncio.create_subprocess_exec", return_value=await _mock_proc(0)):
        with pytest.raises(RuntimeError, match="no WAV file"):
            await download_audio("lofi chill", tmp)


async def test_url_passthrough(tmp):
    fake_wav = tmp / "abc123.wav"
    fake_wav.write_bytes(b"RIFF")

    with patch("asyncio.create_subprocess_exec", return_value=await _mock_proc(0)) as mock_exec:
        await download_audio("https://www.youtube.com/watch?v=abc123", tmp)

    args = mock_exec.call_args[0]
    # URL queries should NOT have --default-search
    assert "--default-search" not in args
```

**Step 2: Run to verify failure**

```bash
uv run pytest tests/test_pipeline_download.py -v
```

Expected: `ModuleNotFoundError`

**Step 3: Implement**

```python
# src/virtualdreams/pipeline/download.py
import asyncio
from pathlib import Path

YOUTUBE_URL_PREFIXES = (
    "https://www.youtube.com/",
    "http://www.youtube.com/",
    "https://youtu.be/",
    "http://youtu.be/",
    "youtube.com/",
    "youtu.be/",
)
MAX_DURATION = 420  # seconds


async def download_audio(query: str, output_dir: Path) -> Path:
    """Download audio from YouTube as WAV. Returns path to WAV file."""
    is_url = query.lower().startswith(YOUTUBE_URL_PREFIXES)

    args = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "wav",
        "--no-playlist",
        "--quiet",
        "-o", str(output_dir / "%(id)s.%(ext)s"),
    ]

    if not is_url:
        args += ["--default-search", "ytsearch1:"]

    args += ["--match-filter", f"duration<={MAX_DURATION}", query]

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {stderr.decode()}")

    wav_files = list(output_dir.glob("*.wav"))
    if not wav_files:
        raise RuntimeError("yt-dlp produced no WAV file")

    return wav_files[0]
```

**Step 4: Run to verify pass**

```bash
uv run pytest tests/test_pipeline_download.py -v
```

Expected: all 4 tests PASS.

**Step 5: Commit**

```bash
git add src/virtualdreams/pipeline/download.py tests/test_pipeline_download.py
git commit -m "feat: add yt-dlp download pipeline step"
```

---

## Task 5: Pipeline — chorus

**Files:**
- Create: `src/virtualdreams/pipeline/chorus.py`
- Create: `tests/test_pipeline_chorus.py`

**Step 1: Write the failing tests**

```python
# tests/test_pipeline_chorus.py
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from virtualdreams.pipeline.chorus import extract_chorus


async def _mock_proc(returncode: int):
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(b"", b""))
    return proc


async def test_chorus_success(tmp_path):
    input_wav = tmp_path / "input.wav"
    output_wav = tmp_path / "chorus.wav"
    input_wav.write_bytes(b"RIFF")

    def fake_exec(*args, **kwargs):
        # Simulate chorus-detector creating output file
        output_wav.write_bytes(b"RIFF")
        return _mock_proc(0)

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        await extract_chorus(input_wav, output_wav)

    assert output_wav.exists()


async def test_chorus_fallback_on_nonzero(tmp_path):
    input_wav = tmp_path / "input.wav"
    output_wav = tmp_path / "chorus.wav"
    input_wav.write_bytes(b"RIFF")

    call_count = 0

    async def fake_exec(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # chorus-detector fails
            return await _mock_proc(1)
        else:
            # ffmpeg trim succeeds and creates file
            output_wav.write_bytes(b"RIFF")
            return await _mock_proc(0)

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        await extract_chorus(input_wav, output_wav)

    assert call_count == 2  # chorus-detector + ffmpeg fallback


async def test_chorus_fallback_on_missing_output(tmp_path):
    input_wav = tmp_path / "input.wav"
    output_wav = tmp_path / "chorus.wav"
    input_wav.write_bytes(b"RIFF")

    call_count = 0

    async def fake_exec(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # chorus-detector exits 0 but produces no file
            return await _mock_proc(0)
        else:
            output_wav.write_bytes(b"RIFF")
            return await _mock_proc(0)

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        await extract_chorus(input_wav, output_wav)

    assert call_count == 2


async def test_chorus_raises_if_fallback_fails(tmp_path):
    input_wav = tmp_path / "input.wav"
    output_wav = tmp_path / "chorus.wav"
    input_wav.write_bytes(b"RIFF")

    with patch("asyncio.create_subprocess_exec", return_value=await _mock_proc(1)):
        with pytest.raises(RuntimeError, match="ffmpeg trim"):
            await extract_chorus(input_wav, output_wav)
```

**Step 2: Run to verify failure**

```bash
uv run pytest tests/test_pipeline_chorus.py -v
```

Expected: `ModuleNotFoundError`

**Step 3: Implement**

```python
# src/virtualdreams/pipeline/chorus.py
import asyncio
import os
from pathlib import Path

CHORUS_DETECTOR_BIN = os.getenv(
    "CHORUS_DETECTOR_BIN",
    "./chorus-detector/target/release/chorus-detector",
)
CHORUS_DURATION = 15  # seconds


async def extract_chorus(input_path: Path, output_path: Path, duration: int = CHORUS_DURATION) -> None:
    """Extract chorus segment. Falls back to first N seconds on failure."""
    proc = await asyncio.create_subprocess_exec(
        CHORUS_DETECTOR_BIN,
        str(input_path),
        str(output_path),
        "--duration", str(duration),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

    if proc.returncode != 0 or not output_path.exists():
        await _ffmpeg_trim(input_path, output_path, duration)


async def _ffmpeg_trim(input_path: Path, output_path: Path, duration: int) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-t", str(duration),
        "-c", "copy",
        str(output_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()
    if proc.returncode != 0 or not output_path.exists():
        raise RuntimeError("ffmpeg trim fallback failed")
```

**Step 4: Run to verify pass**

```bash
uv run pytest tests/test_pipeline_chorus.py -v
```

Expected: all 4 tests PASS.

**Step 5: Commit**

```bash
git add src/virtualdreams/pipeline/chorus.py tests/test_pipeline_chorus.py
git commit -m "feat: add chorus extraction pipeline step"
```

---

## Task 6: Pipeline — effects

**Files:**
- Create: `src/virtualdreams/pipeline/effects.py`
- Create: `tests/test_pipeline_effects.py`

**Step 1: Write the failing tests**

```python
# tests/test_pipeline_effects.py
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from virtualdreams.pipeline.effects import apply_vaporwave


async def _mock_proc(returncode: int):
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(b"", b""))
    return proc


async def test_effects_success(tmp_path):
    input_wav = tmp_path / "chorus.wav"
    output_wav = tmp_path / "vapor.wav"
    input_wav.write_bytes(b"RIFF")

    async def fake_exec(*args, **kwargs):
        output_wav.write_bytes(b"RIFF")
        return await _mock_proc(0)

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        await apply_vaporwave(input_wav, output_wav)

    assert output_wav.exists()


async def test_effects_raises_on_failure(tmp_path):
    input_wav = tmp_path / "chorus.wav"
    output_wav = tmp_path / "vapor.wav"
    input_wav.write_bytes(b"RIFF")

    with patch("asyncio.create_subprocess_exec", return_value=await _mock_proc(1)):
        with pytest.raises(RuntimeError, match="ffmpeg vaporwave"):
            await apply_vaporwave(input_wav, output_wav)


async def test_effects_uses_correct_filters(tmp_path):
    input_wav = tmp_path / "chorus.wav"
    output_wav = tmp_path / "vapor.wav"
    input_wav.write_bytes(b"RIFF")

    captured_args = []

    async def fake_exec(*args, **kwargs):
        captured_args.extend(args)
        output_wav.write_bytes(b"RIFF")
        return await _mock_proc(0)

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        await apply_vaporwave(input_wav, output_wav)

    cmd = " ".join(captured_args)
    assert "atempo" in cmd
    assert "aecho" in cmd
```

**Step 2: Run to verify failure**

```bash
uv run pytest tests/test_pipeline_effects.py -v
```

Expected: `ModuleNotFoundError`

**Step 3: Implement**

The vaporwave effect is:
- Speed: `atempo=0.8,atempo=0.7875` (chained, product ≈ 0.63×, safe across ffmpeg versions)
- Reverb: `aecho=0.8:0.88:60:0.4`

```python
# src/virtualdreams/pipeline/effects.py
import asyncio
from pathlib import Path

_VAPORWAVE_FILTER = "atempo=0.8,atempo=0.7875,aecho=0.8:0.88:60:0.4"


async def apply_vaporwave(input_path: Path, output_path: Path) -> None:
    """Apply vaporwave effects: 0.63× slowdown + reverb via ffmpeg."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-af", _VAPORWAVE_FILTER,
        str(output_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()
    if proc.returncode != 0 or not output_path.exists():
        raise RuntimeError("ffmpeg vaporwave effects failed")
```

**Step 4: Run to verify pass**

```bash
uv run pytest tests/test_pipeline_effects.py -v
```

Expected: all 3 tests PASS.

**Step 5: Commit**

```bash
git add src/virtualdreams/pipeline/effects.py tests/test_pipeline_effects.py
git commit -m "feat: add ffmpeg vaporwave effects pipeline step"
```

---

## Task 7: Pipeline orchestrator

Wire the three pipeline steps into `JobManager._run_pipeline`.

**Files:**
- Modify: `src/virtualdreams/jobs/manager.py`
- Create: `tests/test_pipeline_orchestrator.py`

**Step 1: Write the failing tests**

```python
# tests/test_pipeline_orchestrator.py
import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from virtualdreams.jobs.manager import JobManager
from virtualdreams.jobs.models import JobStatus


async def _make_manager() -> JobManager:
    m = JobManager()
    return m


async def test_pipeline_completes(tmp_path):
    manager = await _make_manager()

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
        await asyncio.sleep(0.1)  # let background task run

    assert job.status == JobStatus.COMPLETED
    assert job.audio_path is not None
    assert Path(job.audio_path).exists()

    # Cleanup
    Path(job.audio_path).unlink(missing_ok=True)


async def test_pipeline_marks_failed_on_error():
    manager = await _make_manager()

    with patch(
        "virtualdreams.jobs.manager.download_audio",
        side_effect=RuntimeError("yt-dlp failed: no results"),
    ):
        job = manager.create_job("nonexistent song xyz")
        await asyncio.sleep(0.1)

    assert job.status == JobStatus.FAILED
    assert "yt-dlp failed" in job.error
```

**Step 2: Run to verify failure**

```bash
uv run pytest tests/test_pipeline_orchestrator.py -v
```

Expected: tests fail (imports missing from manager).

**Step 3: Implement — replace the stub `_run_pipeline`**

Add imports and implement the method in `manager.py`. Replace the `pass` stub:

```python
# Add to top of src/virtualdreams/jobs/manager.py
import shutil
import tempfile
from pathlib import Path

from ..pipeline.download import download_audio
from ..pipeline.chorus import extract_chorus
from ..pipeline.effects import apply_vaporwave
```

```python
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

                # Move vapor.wav out of the temp dir before it's cleaned up
                final = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                final.close()
                shutil.move(str(vapor_path), final.name)

                job.audio_path = final.name
                job.status = JobStatus.COMPLETED

        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
```

**Step 4: Run to verify pass**

```bash
uv run pytest tests/test_pipeline_orchestrator.py tests/test_job_manager.py -v
```

Expected: all tests PASS.

**Step 5: Commit**

```bash
git add src/virtualdreams/jobs/manager.py tests/test_pipeline_orchestrator.py
git commit -m "feat: wire pipeline into JobManager"
```

---

## Task 8: API routes

**Files:**
- Create: `src/virtualdreams/api/routes.py`
- Create: `tests/test_routes.py`

**Step 1: Write the failing tests**

```python
# tests/test_routes.py
import asyncio
import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock, MagicMock
from virtualdreams.jobs.models import Job, JobStatus


@pytest.fixture
async def client(tmp_path):
    from virtualdreams.main import app
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

    # Manually mark job as completed
    job_manager = client._transport.app.state.job_manager
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

    job_manager = client._transport.app.state.job_manager
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
```

**Step 2: Run to verify failure**

```bash
uv run pytest tests/test_routes.py -v
```

Expected: `ModuleNotFoundError` (main.py empty)

**Step 3: Implement routes**

```python
# src/virtualdreams/api/routes.py
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
```

**Step 4: Implement main.py (needed for route tests)**

```python
# src/virtualdreams/main.py
import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from .api.routes import router
from .jobs.manager import JobManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    job_manager = JobManager()
    app.state.job_manager = job_manager
    job_manager.start()
    yield
    await job_manager.stop()


app = FastAPI(title="VirtualDreams", lifespan=lifespan)
app.include_router(router)


def run() -> None:
    load_dotenv()
    uvicorn.run(
        "virtualdreams.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )
```

**Step 5: Run to verify pass**

```bash
uv run pytest tests/test_routes.py -v
```

Expected: all 6 tests PASS.

**Step 6: Run full test suite**

```bash
uv run pytest -v
```

Expected: all tests PASS.

**Step 7: Commit**

```bash
git add src/virtualdreams/api/routes.py src/virtualdreams/main.py tests/test_routes.py
git commit -m "feat: add API routes and FastAPI app"
```

---

## Task 9: Rust crate — chorus-detector

**Files:**
- Create: `chorus-detector/Cargo.toml`
- Create: `chorus-detector/src/main.rs`

The binary reads a WAV file, finds the most repeated segment using chroma-based self-similarity, and writes it to the output WAV. If the audio is shorter than `--duration`, it exits with code 1.

**Step 1: Create `Cargo.toml`**

```toml
[package]
name = "chorus-detector"
version = "0.1.0"
edition = "2021"

[[bin]]
name = "chorus-detector"
path = "src/main.rs"

[dependencies]
clap = { version = "4", features = ["derive"] }
hound = "3"
rustfft = "6"
```

**Step 2: Create `src/main.rs`**

```rust
use clap::Parser;
use hound::{SampleFormat, WavReader, WavSpec, WavWriter};
use rustfft::{num_complex::Complex, FftPlanner};
use std::path::PathBuf;

#[derive(Parser)]
#[command(about = "Detect and extract the chorus from an audio file")]
struct Args {
    input: PathBuf,
    output: PathBuf,
    #[arg(long, default_value = "15")]
    duration: u32,
}

fn main() {
    let args = Args::parse();
    if let Err(e) = run(&args) {
        eprintln!("Error: {e}");
        std::process::exit(1);
    }
}

fn run(args: &Args) -> Result<(), Box<dyn std::error::Error>> {
    let (samples, sample_rate) = read_wav_mono(&args.input)?;

    let duration_samples = args.duration as usize * sample_rate as usize;
    if samples.len() < duration_samples {
        return Err(format!(
            "Audio ({:.1}s) is shorter than requested duration ({}s)",
            samples.len() as f32 / sample_rate as f32,
            args.duration
        )
        .into());
    }

    let start_sample = find_chorus_start(&samples, sample_rate, args.duration);
    let end_sample = (start_sample + duration_samples).min(samples.len());

    write_wav_mono(&args.output, &samples[start_sample..end_sample], sample_rate)?;
    Ok(())
}

// ---------------------------------------------------------------------------
// WAV I/O
// ---------------------------------------------------------------------------

fn read_wav_mono(path: &PathBuf) -> Result<(Vec<f32>, u32), Box<dyn std::error::Error>> {
    let mut reader = WavReader::open(path)?;
    let spec = reader.spec();
    let sample_rate = spec.sample_rate;
    let channels = spec.channels as usize;

    let samples: Vec<f32> = match (spec.sample_format, spec.bits_per_sample) {
        (SampleFormat::Float, 32) => {
            let raw: Vec<f32> = reader
                .samples::<f32>()
                .collect::<hound::Result<_>>()?;
            if channels == 2 {
                raw.chunks(2).map(|c| (c[0] + c[1]) / 2.0).collect()
            } else {
                raw
            }
        }
        (SampleFormat::Int, 16) => {
            let raw: Vec<i16> = reader
                .samples::<i16>()
                .collect::<hound::Result<_>>()?;
            let scale = i16::MAX as f32;
            if channels == 2 {
                raw.chunks(2)
                    .map(|c| (c[0] as f32 + c[1] as f32) / (2.0 * scale))
                    .collect()
            } else {
                raw.iter().map(|&s| s as f32 / scale).collect()
            }
        }
        (fmt, bits) => {
            return Err(format!("Unsupported WAV format: {fmt:?} {bits}bit").into())
        }
    };

    Ok((samples, sample_rate))
}

fn write_wav_mono(
    path: &PathBuf,
    samples: &[f32],
    sample_rate: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    let spec = WavSpec {
        channels: 1,
        sample_rate,
        bits_per_sample: 32,
        sample_format: SampleFormat::Float,
    };
    let mut writer = WavWriter::create(path, spec)?;
    for &s in samples {
        writer.write_sample(s)?;
    }
    writer.finalize()?;
    Ok(())
}

// ---------------------------------------------------------------------------
// Chorus detection
// ---------------------------------------------------------------------------

fn find_chorus_start(samples: &[f32], sample_rate: u32, duration_secs: u32) -> usize {
    const FRAME_SIZE: usize = 2048;
    const HOP_SIZE: usize = 512;

    let chroma_frames = compute_chroma(samples, sample_rate, FRAME_SIZE, HOP_SIZE);
    let n_frames = chroma_frames.len();
    let duration_frames = (duration_secs as usize * sample_rate as usize) / HOP_SIZE;

    if n_frames <= duration_frames {
        return 0;
    }

    // Compute global mean chroma as a fingerprint of the whole track.
    // The chorus is the most repeated section — its chroma is closest to
    // the global mean because it contributes to that mean multiple times.
    let global_mean = mean_chroma(&chroma_frames);

    // Skip first/last 10% to avoid intro and outro.
    let skip = n_frames / 10;
    let end = n_frames.saturating_sub(duration_frames + skip);

    let mut best_score = f32::NEG_INFINITY;
    let mut best_frame = skip;

    for i in skip..=end {
        let window_mean = mean_chroma(&chroma_frames[i..i + duration_frames]);
        let score = cosine_similarity(&window_mean, &global_mean);
        if score > best_score {
            best_score = score;
            best_frame = i;
        }
    }

    best_frame * HOP_SIZE
}

fn compute_chroma(
    samples: &[f32],
    sample_rate: u32,
    frame_size: usize,
    hop_size: usize,
) -> Vec<[f32; 12]> {
    let mut planner = FftPlanner::<f32>::new();
    let fft = planner.plan_fft_forward(frame_size);
    let mut buffer = vec![Complex::new(0.0f32, 0.0f32); frame_size];
    let mut chroma_frames = Vec::new();

    let n_frames = samples.len().saturating_sub(frame_size) / hop_size + 1;

    for i in 0..n_frames {
        let start = i * hop_size;

        // Fill buffer with Hann-windowed samples
        for j in 0..frame_size {
            let s = if start + j < samples.len() {
                samples[start + j]
            } else {
                0.0
            };
            let w = 0.5
                * (1.0
                    - (2.0 * std::f32::consts::PI * j as f32 / (frame_size - 1) as f32).cos());
            buffer[j] = Complex::new(s * w, 0.0);
        }

        fft.process(&mut buffer);

        let mut chroma = [0.0f32; 12];
        let sr = sample_rate as f32;

        for k in 1..(frame_size / 2) {
            let freq = k as f32 * sr / frame_size as f32;
            if freq < 32.7 || freq > 4186.0 {
                continue; // outside piano range
            }
            let pitch_class = freq_to_pitch_class(freq);
            chroma[pitch_class] += buffer[k].norm();
        }

        // L2 normalise
        let norm: f32 = chroma.iter().map(|&x| x * x).sum::<f32>().sqrt();
        if norm > 1e-6 {
            for x in chroma.iter_mut() {
                *x /= norm;
            }
        }

        chroma_frames.push(chroma);
    }

    chroma_frames
}

fn freq_to_pitch_class(freq: f32) -> usize {
    // Midi note number, then mod 12 for pitch class
    let midi = 12.0 * (freq / 440.0).log2() + 69.0;
    (midi.round() as i32).rem_euclid(12) as usize
}

fn mean_chroma(frames: &[[f32; 12]]) -> [f32; 12] {
    let mut mean = [0.0f32; 12];
    let n = frames.len() as f32;
    for frame in frames {
        for i in 0..12 {
            mean[i] += frame[i] / n;
        }
    }
    mean
}

fn cosine_similarity(a: &[f32; 12], b: &[f32; 12]) -> f32 {
    let dot: f32 = a.iter().zip(b.iter()).map(|(&x, &y)| x * y).sum();
    let na: f32 = a.iter().map(|&x| x * x).sum::<f32>().sqrt();
    let nb: f32 = b.iter().map(|&x| x * x).sum::<f32>().sqrt();
    if na < 1e-6 || nb < 1e-6 {
        return 0.0;
    }
    dot / (na * nb)
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use std::f32::consts::PI;

    fn sine_samples(freq: f32, duration_secs: f32, sample_rate: u32) -> Vec<f32> {
        let n = (duration_secs * sample_rate as f32) as usize;
        (0..n)
            .map(|i| (2.0 * PI * freq * i as f32 / sample_rate as f32).sin())
            .collect()
    }

    #[test]
    fn test_find_chorus_returns_valid_offset() {
        let sr = 22050u32;
        let samples = sine_samples(440.0, 60.0, sr); // 60s of 440Hz
        let start = find_chorus_start(&samples, sr, 15);
        // start must be a valid sample offset leaving room for 15s
        assert!(start + 15 * sr as usize <= samples.len());
    }

    #[test]
    fn test_find_chorus_short_audio_returns_zero() {
        let sr = 22050u32;
        let samples = sine_samples(440.0, 10.0, sr);
        // 10s audio, 15s duration → should return 0
        let start = find_chorus_start(&samples, sr, 15);
        assert_eq!(start, 0);
    }

    #[test]
    fn test_freq_to_pitch_class_a440() {
        assert_eq!(freq_to_pitch_class(440.0), 9); // A
    }

    #[test]
    fn test_freq_to_pitch_class_c4() {
        assert_eq!(freq_to_pitch_class(261.63), 0); // C
    }

    #[test]
    fn test_cosine_similarity_identical() {
        let a = [1.0f32, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0];
        assert!((cosine_similarity(&a, &a) - 1.0).abs() < 1e-5);
    }

    #[test]
    fn test_cosine_similarity_orthogonal() {
        let a = [1.0f32, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0];
        let b = [0.0f32, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0];
        assert!((cosine_similarity(&a, &b)).abs() < 1e-5);
    }
}
```

**Step 3: Build and run Rust tests**

```bash
cd chorus-detector && cargo test
```

Expected: all 5 tests PASS.

**Step 4: Build release binary**

```bash
cargo build --release
```

Expected: `target/release/chorus-detector` created.

**Step 5: Smoke test the binary**

```bash
# Create a test WAV with ffmpeg (30s sine wave)
ffmpeg -f lavfi -i "sine=frequency=440:duration=30" /tmp/test.wav
./target/release/chorus-detector /tmp/test.wav /tmp/chorus_out.wav --duration 15
echo "Exit code: $?"
# Verify output exists and is ~15s
ffprobe /tmp/chorus_out.wav 2>&1 | grep Duration
```

Expected: exit 0, duration ~00:00:15.

**Step 6: Commit**

```bash
cd ..
git add chorus-detector/
git commit -m "feat: add Rust chorus detector binary"
```

---

## Task 10: Remove obsolete files

**Step 1: Delete old files**

```bash
git rm vapor.py memory_utils.py requirements.txt runtime.txt Procfile Aptfile \
        test_chorus.py test_chorus_isolated.py test_memory.py MEMORY_MANAGEMENT.md
git rm -r docs/assets docs/font docs/index.html docs/style.css
```

**Step 2: Update `.gitignore`**

Add lines to existing `.gitignore`:

```
.env
.env.local
__pycache__/
*.pyc
.venv/
dist/
chorus-detector/target/
```

**Step 3: Run full test suite to confirm nothing broke**

```bash
uv run pytest -v
```

Expected: all tests PASS.

**Step 4: Commit**

```bash
git add .gitignore
git commit -m "chore: remove obsolete Telegram bot, pychorus, and Heroku files"
```

---

## Task 11: End-to-end smoke test

This is a manual test requiring `yt-dlp`, `ffmpeg`, and a built `chorus-detector` binary.

**Step 1: Set up environment**

```bash
cp .env.example .env
# Edit .env: set CHORUS_DETECTOR_BIN=./chorus-detector/target/release/chorus-detector
uv run virtualdreams &
```

**Step 2: Submit a job**

```bash
curl -s -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"query": "tame impala the less i know the better"}' | jq .
# → {"job_id": "some-uuid"}
```

**Step 3: Poll until completed**

```bash
JOB_ID="<job_id from above>"
watch -n 2 "curl -s http://localhost:8000/jobs/$JOB_ID | jq ."
# Wait for status: "completed"
```

**Step 4: Download audio**

```bash
curl -s -o vapor.wav http://localhost:8000/jobs/$JOB_ID/audio
file vapor.wav   # → RIFF (little-endian) data, WAVE audio
# Second fetch should return 410
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/jobs/$JOB_ID/audio
# → 410
```

**Step 5: Play and verify the vaporwave effect sounds correct**

```bash
ffplay vapor.wav
```

Expected: slowed-down, reverb-heavy audio.
