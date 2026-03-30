# VirtualDreams Modernization Design

**Date:** 2026-03-30
**Status:** Approved

## Summary

Revive and modernize VirtualDreams: strip out the Telegram bot, replace all obsolete dependencies, and expose the vaporwave pipeline as a clean async REST API. Chorus detection is rewritten in Rust as a standalone binary. Audio effects move to ffmpeg. YouTube downloading uses yt-dlp via subprocess.

---

## Stack

- **Python 3.14+** with `uv`, `ruff`, `ty`
- **FastAPI** — async HTTP API
- **yt-dlp** — YouTube download via subprocess (CLI)
- **ffmpeg** — vaporwave effects (slowdown + reverb) and audio fallback trim via subprocess
- **Rust** — chorus detector compiled to a standalone binary, called via subprocess

---

## Project Structure

```
virtualdreams/
├── src/
│   └── virtualdreams/
│       ├── __init__.py
│       ├── main.py              # FastAPI app, lifespan
│       ├── api/
│       │   └── routes.py        # POST /jobs, GET /jobs/{id}, GET /jobs/{id}/audio
│       ├── jobs/
│       │   ├── manager.py       # in-memory job registry, dispatch, TTL cleanup
│       │   └── models.py        # JobStatus enum, Job dataclass
│       └── pipeline/
│           ├── download.py      # yt-dlp subprocess
│           ├── chorus.py        # Rust binary subprocess
│           └── effects.py       # ffmpeg subprocess
├── chorus-detector/             # Rust crate
│   ├── Cargo.toml
│   └── src/
│       └── main.rs
├── tests/
├── pyproject.toml
└── .env.example
```

---

## API

### `POST /jobs`
**Request:**
```json
{ "query": "tame impala the less i know" }
```
`query` is either a search string or a YouTube URL.

**Response `202`:**
```json
{ "job_id": "uuid4" }
```

### `GET /jobs/{job_id}`
```json
{ "job_id": "...", "status": "pending" | "running" | "completed" | "failed", "error": null }
```

### `GET /jobs/{job_id}/audio`
- Returns the `.wav` file as `audio/wav` with `Content-Disposition: attachment`.
- File is deleted from disk immediately after the response is sent.
- Returns `404` if job not found or not completed.
- Returns `410 Gone` if audio was already fetched.

---

## Pipeline

Runs as a single `asyncio` background task inside a `tempfile.TemporaryDirectory()` (auto-cleaned on exit):

1. **Download** (`download.py`)
   - `yt-dlp` subprocess with `--default-search ytsearch1:` for non-URL queries
   - `--extract-audio --audio-format wav`
   - `--match-filter duration<=420` to enforce 7-minute limit

2. **Chorus detection** (`chorus.py`)
   - Invokes: `chorus-detector <input.wav> <output.wav> [--duration 15]`
   - On non-zero exit or missing output: fall back to ffmpeg trim of first 15 seconds
   - Single attempt, single fallback — no retry loop

3. **Vaporwave effects** (`effects.py`)
   - Single `ffmpeg` command: chained `atempo` filters for 0.63x speed, `aecho` for reverb
   - Output: `vapor.wav`

4. **Complete** — store `audio_path` in job record, set status to `completed`

All subprocess calls use `asyncio.create_subprocess_exec` — fully non-blocking.

---

## Job Manager

```python
@dataclass
class Job:
    job_id: str
    status: JobStatus          # pending | running | completed | failed
    error: str | None = None
    audio_path: str | None = None
    fetched: bool = False
    created_at: float = field(default_factory=time.time)
```

- Jobs stored in `dict[str, Job]` on FastAPI app state, initialized in lifespan.
- `POST /jobs` creates a job and dispatches `asyncio.create_task(run_pipeline(job_id))`.
- A background cleanup task runs every 60 seconds, evicting jobs older than **600 seconds** (TTL).
- Evicted jobs with unretrieved audio files have those files deleted from disk.
- Evicted job IDs return `404`.

---

## Rust Chorus Detector

- Standalone binary: `chorus-detector <input.wav> <output.wav> [--duration <secs>]`
- Algorithm: chroma-based self-similarity matrix to find the most repeated segment
- Exit code `0` on success, non-zero on failure
- Path configured via `CHORUS_DETECTOR_BIN` env var

---

## Removed

- `python-telegram-bot`, `telegram` — entire bot layer
- `youtube_dl` — replaced by `yt-dlp` subprocess
- `pychorus` — replaced by Rust binary
- `pysndfx` (sox) — replaced by ffmpeg
- `pydub` — replaced by ffmpeg
- `logzero` — replaced by stdlib `logging`
- `memory_utils.py` — obsolete; Rust + subprocess model eliminates memory pressure
- `emoji` — not needed without bot messages
- `python-dotenv` — replaced by `python-dotenv` via uv or stdlib
- Heroku `Procfile`, `Aptfile`, `runtime.txt`
- `docs/` static landing page and assets
