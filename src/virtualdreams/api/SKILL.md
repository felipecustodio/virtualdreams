---
name: virtualdreams-api
description: >
  Guide for working on the VirtualDreams HTTP API (routes.py and main.py).
  Use when adding endpoints, changing request/response shapes, modifying
  error handling, or working on the FastAPI app setup and lifespan.
---

# API Layer

`routes.py` defines three endpoints. `main.py` wires the app, lifespan, and entry point.

## Endpoints

### `POST /jobs` → 202

```
Request:  {"query": "search string or YouTube URL"}
Response: {"job_id": "<uuid4>"}
```

Creates a job and returns immediately. The pipeline runs in the background.
Always 202 — never blocks on pipeline completion.

### `GET /jobs/{job_id}` → 200 | 404

```
Response: {"job_id": "...", "status": "pending|running|completed|failed", "error": null}
```

Returns 404 if the job ID is unknown (including after TTL eviction).
`error` is `null` unless `status == "failed"`.

### `GET /jobs/{job_id}/audio` → 200 | 404 | 410

- 404 if job not found, or job not yet completed.
- 410 Gone if audio was already fetched (`job.fetched == True`).
- 200 streams the WAV as `audio/wav` with `Content-Disposition: attachment; filename="vapor.wav"`.
- File is deleted via `BackgroundTasks` after the response is sent.
- Sets `job.fetched = True` before returning — subsequent calls get 410.

## Accessing job state in routes

`JobManager` lives on `request.app.state.job_manager`. This is set in `main.py:lifespan`.

```python
job = request.app.state.job_manager.get_job(job_id)
```

## FastAPI app (`main.py`)

The lifespan context manager is the only place `JobManager` is created:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    job_manager = JobManager()
    app.state.job_manager = job_manager
    job_manager.start()   # starts the cleanup background task
    yield
    await job_manager.stop()
```

`run()` is the entry point registered as the `virtualdreams` CLI command in `pyproject.toml`.
It calls `uvicorn.run(...)` with host/port from environment.

## Testing routes

Use `httpx.AsyncClient` with `ASGITransport`. **Important:** `ASGITransport` does not trigger
the FastAPI lifespan, so `app.state.job_manager` will not be set automatically. Wire it
manually in the fixture:

```python
@pytest.fixture
async def client():
    from virtualdreams.main import app
    from virtualdreams.jobs.manager import JobManager
    app.state.job_manager = JobManager()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```

To simulate a completed job in tests, mutate the job object directly after creating it:

```python
job = job_manager.get_job(job_id)
job.status = JobStatus.COMPLETED
job.audio_path = str(some_temp_file)
```

Run: `uv run pytest tests/test_routes.py -v`
