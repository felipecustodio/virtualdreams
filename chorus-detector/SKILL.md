---
name: virtualdreams-chorus-detector
description: >
  Guide for working on the chorus-detector Rust binary. Use when
  modifying the chorus detection algorithm, WAV I/O, CLI interface,
  or build process. Also covers the contract this binary must uphold
  for the Python pipeline to work correctly.
---

# chorus-detector (Rust)

Standalone binary: reads an input WAV, finds the most repeated segment, writes it to an
output WAV. Called by `src/virtualdreams/pipeline/chorus.py`.

## CLI contract

```
chorus-detector <input.wav> <output.wav> [--duration <secs>]
```

- Exit 0 on success, output file must exist and be a valid WAV.
- Exit 1 on any failure (stderr receives the error message).
- Default `--duration` is 15 seconds.
- **Python relies on this contract.** If the binary exits non-zero or the output file is
  missing, the Python side falls back to an ffmpeg trim. Do not change the exit code
  semantics or the argument order.

## Algorithm overview

1. Read WAV → convert to mono f32 samples (`read_wav_mono`)
2. Compute STFT frames (Hann window, frame=2048, hop=512) with `rustfft`
3. Map each frequency bin to one of 12 chroma classes (pitch class via MIDI formula)
4. L2-normalise each chroma frame
5. Score candidate windows by cosine similarity to the global mean chroma
6. Skip first and last 10% of track (avoids intro/outro)
7. Extract best-scoring window and write to output WAV (`write_wav_mono`)

The global-mean heuristic works because the chorus is the most repeated section —
it contributes to the global mean multiple times, so its chroma is closest to it.

## WAV format support

Reads: 16-bit PCM (`i16`) and 32-bit float. Returns `Err` for other formats.
Writes: 32-bit float WAV (WAVE_FORMAT_EXTENSIBLE). This is valid WAV but Python's
stdlib `wave` module cannot read it — use `hound`, `ffprobe`, or any real audio tool
to verify output.

`yt-dlp --audio-format wav` typically produces 16-bit PCM, so that path is the primary one.

## Key functions

| Function | Purpose |
|----------|---------|
| `read_wav_mono` | WAV → `Vec<f32>` mono samples + sample rate |
| `write_wav_mono` | `&[f32]` + sample rate → WAV file |
| `find_chorus_start` | Returns sample offset of best-scoring window |
| `compute_chroma` | STFT → chroma frames (`Vec<[f32; 12]>`) |
| `freq_to_pitch_class` | Frequency in Hz → 0–11 pitch class index |
| `mean_chroma` | Averages a slice of chroma frames |
| `cosine_similarity` | Dot product / (‖a‖ · ‖b‖) for two chroma vectors |

## Build

```bash
# Debug (fast compile, slow binary)
cargo build --manifest-path chorus-detector/Cargo.toml

# Release (required for production use)
cargo build --release --manifest-path chorus-detector/Cargo.toml
# Output: chorus-detector/target/release/chorus-detector
```

The `target/` directory is gitignored. After a fresh clone, the binary must be built
before the Python server can process jobs (unless `CHORUS_DETECTOR_BIN` points elsewhere).

## Testing

Six unit tests live in `#[cfg(test)]` at the bottom of `main.rs`:

```bash
cargo test --manifest-path chorus-detector/Cargo.toml
```

Tests cover: valid chorus offset bounds, short-audio fallback to offset 0,
pitch class of A440 and C4, cosine similarity (identical = 1.0, orthogonal = 0.0).

When adding new logic, add a test. Avoid touching existing tests unless the contract
genuinely changes — they serve as the binary's spec.

## Dependencies

```toml
clap = "4"      # CLI argument parsing (derive feature)
hound = "3"     # WAV read/write
rustfft = "6"   # FFT (Hann-windowed STFT)
```

No audio-specific crates — the chroma computation is implemented directly using rustfft.
