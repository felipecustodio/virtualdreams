# Project Overview

VirtualDreams is a headless REST API that turns any YouTube video into a vaporwave audio clip.
Given a search query or YouTube URL, it downloads the audio with `yt-dlp`, extracts the most
repeated segment (chorus) using a Rust binary built on chroma-based self-similarity, then applies
0.63× slowdown and reverb through `ffmpeg`. Jobs are processed asynchronously; the caller polls
for completion and fetches the resulting WAV once. No frontend, no Telegram bot, no persistent
storage — pure audio pipeline over HTTP.

---

## Repository Structure

```
virtualdreams/
├── src/virtualdreams/       Python package (FastAPI application)
│   ├── main.py              App factory, uvicorn entry point, lifespan
│   ├── api/routes.py        HTTP routes: POST /jobs, GET /jobs/{id}, GET /jobs/{id}/audio
│   ├── jobs/
│   │   ├── models.py        Job dataclass and JobStatus enum
│   │   └── manager.py       In-memory job registry, async pipeline dispatch, TTL cleanup
│   └── pipeline/
│       ├── download.py      yt-dlp subprocess wrapper
│       ├── chorus.py        Rust binary subprocess + ffmpeg trim fallback
│       └── effects.py       ffmpeg vaporwave filter chain
├── chorus-detector/         Rust crate — standalone chorus detection binary
│   ├── Cargo.toml
│   └── src/main.rs          WAV I/O, chroma STFT, cosine-similarity scoring
├── tests/                   pytest test suite (unit + integration)
├── docs/plans/              Design docs and implementation plans (Markdown)
├── pyproject.toml           Python project config: deps, ruff, pytest, hatchling
├── uv.lock                  Locked dependency manifest (commit this)
└── .env.example             Required environment variables
```

---

## Build & Development Commands

### System prerequisites

`yt-dlp`, `ffmpeg`, and a Rust toolchain (`rustup`) must be installed and on `PATH`.

```bash
# macOS (Homebrew)
brew install yt-dlp ffmpeg
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

### Python environment

```bash
# Install all dependencies (creates .venv automatically)
uv sync --extra dev

# Run the API server
uv run virtualdreams

# Or directly
uv run uvicorn virtualdreams.main:app --reload
```

### Rust chorus detector

```bash
# Run Rust unit tests
cargo test --manifest-path chorus-detector/Cargo.toml

# Build release binary (required before running the server)
cargo build --release --manifest-path chorus-detector/Cargo.toml
# Output: chorus-detector/target/release/chorus-detector
```

### Tests

```bash
# Full Python test suite
uv run pytest

# Verbose
uv run pytest -v

# Single module
uv run pytest tests/test_pipeline_download.py -v
```

### Lint & type check

```bash
# Lint (ruff)
uv run ruff check src/ tests/

# Format check
uv run ruff format --check src/ tests/

# Type check (ty)
uv run ty check src/
```

### Environment setup

```bash
cp .env.example .env
# Edit .env — set CHORUS_DETECTOR_BIN to the built binary path
```

---

## Code Style & Conventions

- **Formatter / linter:** `ruff`, line length 88, target Python 3.14.
- **Selected rules:** `E`, `F`, `I` (isort), `UP` (pyupgrade) — see `[tool.ruff.lint]` in
  `pyproject.toml`.
- **Type annotations:** required on all public functions and method signatures.
- **Naming:** `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE` for
  module-level constants.
- **Async:** all I/O uses `asyncio.create_subprocess_exec`; never block the event loop with
  synchronous subprocess calls.
- **Rust:** standard `cargo fmt` / `clippy` conventions; `edition = "2021"`.
- **Commit messages:** imperative present tense, prefixed with `feat:`, `fix:`, `chore:`,
  `docs:`, `test:` (e.g. `feat: add chorus extraction pipeline step`).

---

## Architecture Notes

```
Client
  │
  │  POST /jobs  {"query": "..."}
  ▼
┌─────────────────────────────────────────────┐
│  FastAPI  (src/virtualdreams/main.py)        │
│                                             │
│  JobManager (in-memory dict[str, Job])      │
│    ├─ create_job() → asyncio.create_task()  │
│    └─ _cleanup_loop() every 60s / TTL 600s  │
└────────────────┬────────────────────────────┘
                 │  background task
                 ▼
        tempfile.TemporaryDirectory
                 │
    ┌────────────▼────────────┐
    │  pipeline/download.py   │  yt-dlp subprocess → input.wav
    └────────────┬────────────┘
    ┌────────────▼────────────┐
    │  pipeline/chorus.py     │  chorus-detector binary → chorus.wav
    │  (ffmpeg trim fallback) │  (exits non-zero → ffmpeg -t 15)
    └────────────┬────────────┘
    ┌────────────▼────────────┐
    │  pipeline/effects.py    │  ffmpeg atempo+aecho → vapor.wav
    └────────────┬────────────┘
                 │  shutil.move → NamedTemporaryFile (persists past tmpdir)
                 ▼
        Job.audio_path set, status = COMPLETED

  Client polls GET /jobs/{id} → status: completed
  Client fetches GET /jobs/{id}/audio → WAV streamed, file deleted, 410 on re-fetch
```

**Job lifecycle:** `pending → running → completed | failed`

**Memory model:** jobs live in a plain Python dict on `app.state`. There is no database. On
process restart all job state is lost. Audio files that are never fetched are deleted by the
TTL cleanup loop after 10 minutes.

**Chorus detection (Rust):** computes a short-time Fourier transform with a Hann window
(frame 2048, hop 512), maps magnitude bins to 12 chroma classes, L2-normalises each frame,
then scores candidate windows by cosine similarity to the global mean chroma. The first and
last 10% of the track are skipped to avoid intros and outros.

---

## Testing Strategy

All tests live in `tests/` and are discovered automatically by pytest.

| File | What it covers |
|------|---------------|
| `test_job_models.py` | `Job` defaults, UUID uniqueness, `JobStatus` values |
| `test_job_manager.py` | Registry CRUD, TTL eviction, orphaned file cleanup |
| `test_pipeline_download.py` | yt-dlp arg construction, error propagation, URL passthrough |
| `test_pipeline_chorus.py` | Binary success path, non-zero fallback, missing-output fallback |
| `test_pipeline_effects.py` | ffmpeg filter presence, error propagation |
| `test_pipeline_orchestrator.py` | Full pipeline wiring, failure → `FAILED` status |
| `test_routes.py` | All HTTP routes, 202/200/404/410 status codes |

Subprocess calls are mocked with `unittest.mock.patch("asyncio.create_subprocess_exec")`.
Route tests wire `app.state.job_manager` manually (ASGITransport does not trigger lifespan).

```bash
# Run all tests
uv run pytest

# With coverage (install pytest-cov first)
uv run pytest --cov=src/virtualdreams --cov-report=term-missing
```

Rust unit tests (pitch class, cosine similarity, chorus offset validity) run with:

```bash
cargo test --manifest-path chorus-detector/Cargo.toml
```

> TODO: Add a CI workflow (`.github/workflows/ci.yml`) that runs both suites on push.

---

## Security & Compliance

- **Secrets:** all configuration via environment variables; never hardcoded. `.env` is
  gitignored. Copy `.env.example` to `.env` locally.
- **Input validation:** `query` is passed directly to `yt-dlp` as a CLI argument via
  `asyncio.create_subprocess_exec` (list form) — not via shell string interpolation, so
  shell injection is not possible.
- **Ephemeral files:** downloaded and processed audio files live in `tempfile.TemporaryDirectory`
  and are deleted on pipeline exit (success or failure). The final WAV is deleted after first
  fetch or after TTL expiry.
- **No authentication:** the API has no auth layer. Deploy behind a reverse proxy or VPN
  if exposed publicly.
- **Dependencies:** managed by `uv`; lock file (`uv.lock`) is committed. Run
  `uv sync` to reproduce the exact environment.
- **License:** GPL (inherited from original project). All dependencies must be compatible.

> TODO: Add `dependabot` or `uv audit` to the CI pipeline for vulnerability scanning.

---

## Agent Guardrails

- **Never modify** `uv.lock` directly — always go through `uv add` / `uv remove`.
- **Never modify** `chorus-detector/src/main.rs` without also running
  `cargo test --manifest-path chorus-detector/Cargo.toml` and verifying all 6 tests pass.
- **Never** call subprocesses via shell string concatenation — always use list-form
  `asyncio.create_subprocess_exec`.
- **Never** add synchronous blocking I/O to `pipeline/` modules — all I/O must be `async`.
- **Do not** add new runtime dependencies without updating both `pyproject.toml` and `uv.lock`.
- **Do not** commit `.env`, `*.wav`, `*.mp3`, or `chorus-detector/target/` — all are gitignored.
- **Test coverage:** any change to `src/` must be accompanied by a corresponding test change
  in `tests/`.

---

## Extensibility Hooks

| Variable | Default | Purpose |
|----------|---------|---------|
| `CHORUS_DETECTOR_BIN` | `./chorus-detector/target/release/chorus-detector` | Path to compiled Rust binary |
| `HOST` | `0.0.0.0` | uvicorn bind address |
| `PORT` | `8000` | uvicorn port |

**Swapping the chorus detector:** `pipeline/chorus.py` reads `CHORUS_DETECTOR_BIN` at import
time. Point it at any binary that accepts `<input.wav> <output.wav> --duration <secs>` and
exits 0 on success.

**Adjusting vaporwave parameters:** the ffmpeg filter string is a single constant
`_VAPORWAVE_FILTER` in `pipeline/effects.py`. Edit it to change speed, reverb depth, or
add additional filters.

**Job TTL:** `JOB_TTL` and `CLEANUP_INTERVAL` are module-level constants in
`jobs/manager.py`. Promote them to env vars if runtime configurability is needed.

**Maximum video duration:** `MAX_DURATION` in `pipeline/download.py` (default 420 s / 7 min).

---

## Further Reading

- [`docs/plans/2026-03-30-modernization-design.md`](docs/plans/2026-03-30-modernization-design.md) —
  Architecture decisions and rationale for the modernization
- [`docs/plans/2026-03-30-modernization-plan.md`](docs/plans/2026-03-30-modernization-plan.md) —
  Full task-by-task implementation plan
- [`chorus-detector/src/main.rs`](chorus-detector/src/main.rs) — Inline comments explain the
  chroma STFT and scoring algorithm
