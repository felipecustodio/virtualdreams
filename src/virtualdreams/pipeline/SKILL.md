---
name: virtualdreams-pipeline
description: >
  Guide for working on the VirtualDreams audio pipeline modules:
  download.py, chorus.py, and effects.py. Use whenever adding,
  changing, or debugging any pipeline step — including swapping the
  chorus detector, tuning vaporwave parameters, or changing how
  yt-dlp is invoked.
---

# Pipeline Modules

Three independent async functions, each wrapping an external subprocess.
They are composed in `jobs/manager.py:_run_pipeline`.

## Module responsibilities

| Module | Binary | What it does |
|--------|--------|-------------|
| `download.py` | `yt-dlp` | Downloads YouTube audio as WAV into a temp dir |
| `chorus.py` | `chorus-detector` (Rust) + `ffmpeg` | Extracts the most repeated segment; falls back to first N seconds |
| `effects.py` | `ffmpeg` | Applies 0.63× slowdown + reverb |

## Non-negotiable patterns

All subprocess calls use **list-form** `asyncio.create_subprocess_exec` — never shell
string interpolation. This prevents shell injection.

All functions are `async` and must stay non-blocking. Never use `subprocess.run` or any
synchronous I/O inside these modules.

Every function receives `Path` objects and returns `Path` objects (or raises). They do not
own the temp directory — that is managed by `manager._run_pipeline`.

## download.py

```python
wav_path = await download_audio(query, output_dir)
```

- `query` is either a search string or a YouTube URL.
- URLs are detected by prefix (`YOUTUBE_URL_PREFIXES`). Non-URLs get
  `--default-search ytsearch1:` prepended.
- Duration is enforced server-side with `--match-filter duration<=420`.
- Raises `RuntimeError` on non-zero exit or if no `.wav` file appears in `output_dir`.
- `MAX_DURATION = 420` is a module constant — promote to env var if runtime config needed.

## chorus.py

```python
await extract_chorus(input_path, output_path, duration=15)
```

- Invokes `CHORUS_DETECTOR_BIN` (from env, default `./chorus-detector/target/release/chorus-detector`).
- If the binary exits non-zero **or** the output file is missing → falls back to
  `ffmpeg -t <duration> -c copy` (lossless trim of the first N seconds).
- Only one attempt + one fallback. No retry loop.
- Raises `RuntimeError` only if the ffmpeg fallback also fails.
- To swap the detector: set `CHORUS_DETECTOR_BIN` to any binary that accepts
  `<input.wav> <output.wav> --duration <secs>` and exits 0 on success.

## effects.py

```python
await apply_vaporwave(input_path, output_path)
```

- Single ffmpeg call: `atempo=0.8,atempo=0.7875,aecho=0.8:0.88:60:0.4`
- `atempo` is chained (0.8 × 0.7875 ≈ 0.63×) for compatibility with all ffmpeg versions.
- The entire filter string is `_VAPORWAVE_FILTER` at the top of the file — edit it there
  to change speed or reverb without touching the function.
- Raises `RuntimeError` if ffmpeg exits non-zero or output file is missing.

## Testing pipeline modules

Each module has its own test file in `tests/`. Subprocess calls are mocked with
`unittest.mock.patch("asyncio.create_subprocess_exec")`.

The mock must return a coroutine (use `AsyncMock` for `.communicate()`):

```python
async def _mock_proc(returncode: int):
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(b"", b""))
    return proc
```

To test fallback paths in `chorus.py`, use a counter to return different mocks
on successive calls. See `tests/test_pipeline_chorus.py` for the pattern.

Run: `uv run pytest tests/test_pipeline_*.py -v`
