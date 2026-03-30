---
name: virtualdreams-jobs
description: >
  Guide for working on the VirtualDreams job system: models.py and
  manager.py. Use when modifying job lifecycle, TTL behaviour, status
  transitions, in-memory storage, or the pipeline orchestration logic
  inside JobManager._run_pipeline.
---

# Job System

Two files: `models.py` defines the data shape, `manager.py` owns all runtime state.

## Data model

```python
@dataclass
class Job:
    job_id: str          # UUID4, generated on creation
    status: JobStatus    # pending → running → completed | failed
    error: str | None    # set on failure, None otherwise
    audio_path: str | None  # absolute path to the final WAV; None until completed
    fetched: bool        # True after GET /audio is served (prevents double-fetch)
    created_at: float    # time.time() at creation; used for TTL eviction
```

`JobStatus` is a `StrEnum` — values serialize directly to JSON strings
(`"pending"`, `"running"`, `"completed"`, `"failed"`).

## JobManager lifecycle

`JobManager` is instantiated once in `main.py:lifespan` and stored on `app.state`.

```
lifespan start → JobManager() → .start() → cleanup task begins
                                          ↓
                             asyncio background loop (every 60s)
                             evicts jobs older than JOB_TTL=600s
                             deletes orphaned audio files

lifespan end   → .stop() → cancels cleanup task
```

`create_job(query)` adds a `Job` to `_jobs` and fires `asyncio.create_task(_run_pipeline(...))`.
It returns immediately — the caller gets a job ID without waiting for the pipeline.

## Pipeline execution

`_run_pipeline` runs entirely inside a `tempfile.TemporaryDirectory`. The three pipeline
steps (`download_audio`, `extract_chorus`, `apply_vaporwave`) are awaited in sequence.

Before the temp dir is cleaned up, the final `vapor.wav` is moved to a
`tempfile.NamedTemporaryFile(delete=False)` so it survives the context manager exit.
This path is stored in `job.audio_path`.

On any exception, `job.status = FAILED` and `job.error = str(exc)`. The temp dir is
always cleaned up (context manager handles it regardless of success/failure).

## TTL eviction

`_evict_expired` is called every `CLEANUP_INTERVAL=60` seconds. It removes all jobs
where `time.time() - job.created_at > JOB_TTL`. If an evicted job has an `audio_path`
that still exists on disk, the file is deleted.

`JOB_TTL` and `CLEANUP_INTERVAL` are module-level constants. Promote to env vars if
runtime configurability is needed.

## State is in-memory only

There is no database. All jobs are lost on process restart. This is intentional for
the current design. If persistence is needed in future, `_jobs` dict and `_run_pipeline`
are the only two places that need to change.

## Testing

Tests that call `create_job()` must be `async` — `asyncio.create_task` requires a
running event loop. Mark them with `async def` (pytest-asyncio auto mode handles the rest).

Patch `_run_pipeline` with `AsyncMock` when testing the registry logic in isolation:

```python
with patch.object(manager, "_run_pipeline", new=AsyncMock()):
    job = manager.create_job("test query")
```

Patch the imported pipeline functions in `manager`'s namespace when testing orchestration:

```python
with patch("virtualdreams.jobs.manager.download_audio", side_effect=fake_download):
    ...
```

Run: `uv run pytest tests/test_job_models.py tests/test_job_manager.py tests/test_pipeline_orchestrator.py -v`
