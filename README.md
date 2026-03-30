# VirtualDreams

VirtualDreams is a small FastAPI app that turns a YouTube video into a vaporwave clip.
It downloads audio with `yt-dlp`, finds the most repeated section with a Rust chorus detector,
then applies slowdown and ambience with `ffmpeg`.

It exposes a JSON API and also ships a lightweight static frontend at `/`.

## What It Does

- Accepts a YouTube URL or search query
- Starts an async background job
- Extracts a short repeated section from the track
- Applies a slowed, pitched-down vaporwave effect
- Streams job updates to the browser with Server-Sent Events
- Returns the generated WAV once

## Flow

```mermaid
flowchart TD
    A[User enters query or YouTube URL] --> B[POST /jobs]
    B --> C[JobManager creates in-memory job]
    C --> D[Background pipeline task]
    D --> E[yt-dlp downloads audio to WAV]
    E --> F[Rust chorus-detector finds best repeated segment]
    F --> G[ffmpeg applies vaporwave slowdown and ambience]
    G --> H[Final WAV moved to persistent temp file]
    H --> I[Job marked completed]
    I --> J[Browser listens on /jobs/{id}/events]
    J --> K[GET /jobs/{id}/audio]
```

## Architecture

- `src/virtualdreams/main.py`: FastAPI app, lifespan, static frontend mount
- `src/virtualdreams/api/routes.py`: job creation, status events, audio fetch
- `src/virtualdreams/jobs/manager.py`: in-memory job registry, async orchestration, TTL cleanup
- `src/virtualdreams/pipeline/download.py`: `yt-dlp` audio download
- `src/virtualdreams/pipeline/chorus.py`: Rust detector wrapper with ffmpeg trim fallback
- `src/virtualdreams/pipeline/effects.py`: ffmpeg vaporwave post-processing
- `chorus-detector/`: standalone Rust binary for chorus extraction

## Audio Pipeline

### 1. Download

`yt-dlp` fetches the source and extracts audio as WAV.

### 2. Chorus Detection

The Rust binary scans the track and picks a fixed-duration window that is most similar to the
track's global harmonic profile. In practice, this biases toward the chorus or hook.

If the detector fails, the Python wrapper falls back to trimming the first `N` seconds with `ffmpeg`.

### 3. Vaporwave Processing

The final clip is processed with `ffmpeg`:

- `asetrate` + `aresample` to preserve the classic slowed-and-pitched-down feel
- a denser `aecho` chain to add the wet, dreamy tail from the legacy project

The current profile is tuned to match the older `vapor.py` behavior more closely than the initial
modern rewrite.

## How The Rust Chorus Finder Works

The chorus detector in [`chorus-detector/src/main.rs`](chorus-detector/src/main.rs):

- reads the input WAV and mixes stereo to mono when needed
- computes a short-time Fourier transform with a Hann window
- maps frequency energy into 12 chroma classes
- L2-normalizes each frame
- computes the global mean chroma across the track
- scores each candidate window by cosine similarity to that mean
- skips the first and last 10% to avoid intros and outros
- writes the best-scoring segment back as a WAV

This is simple, fast, and robust enough for pop tracks where the chorus tends to be the most repeated section.

## API

### `POST /jobs`

Create a job:

```json
{"query": "barbie girl"}
```

Response:

```json
{"job_id": "..."}
```

### `GET /jobs/{id}`

Returns the current job state.

### `GET /jobs/{id}/events`

Streams job updates as Server-Sent Events.

### `GET /jobs/{id}/audio`

Returns the generated WAV. The file is deleted after the first successful fetch.

## Local Development

### Prerequisites

- `uv`
- `ffmpeg`
- `yt-dlp`
- Rust toolchain

### Setup

```bash
uv sync --extra dev
cargo build --release --manifest-path chorus-detector/Cargo.toml
cp .env.example .env
```

Set `CHORUS_DETECTOR_BIN` in `.env` if needed.

### Run

```bash
uv run virtualdreams
```

Or:

```bash
uv run uvicorn virtualdreams.main:app --reload
```

## Tests

```bash
uv run pytest
cargo test --manifest-path chorus-detector/Cargo.toml
```

## Notes

- Jobs are stored in memory only
- Generated audio expires after the TTL cleanup window
- There is no authentication layer
- The static frontend is optional convenience; the app can be used directly via HTTP
