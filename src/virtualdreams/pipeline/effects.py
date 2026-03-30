import asyncio
from pathlib import Path

# Vaporwave speed factor: reinterpret the sample rate so both pitch and tempo
# drop together (the "slowed record" effect), rather than time-stretching.
_SPEED = 0.8
# Reverb: in-gain, out-gain, delay-ms, decay
_ECHO = "aecho=0.8:0.88:60:0.4"


async def _probe_sample_rate(path: Path) -> int:
    """Return the sample rate of an audio file via ffprobe."""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=sample_rate",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()
    return int(stdout.strip()) if stdout.strip() else 44100


async def apply_vaporwave(input_path: Path, output_path: Path) -> None:
    """Apply vaporwave effects: pitch+tempo drop via asetrate, then reverb."""
    sr = await _probe_sample_rate(input_path)
    slowed_rate = int(sr * _SPEED)
    # asetrate reinterprets samples at a lower rate (pitch + speed drop).
    # aresample converts back to the original rate for a standards-compliant file.
    af = f"asetrate={slowed_rate},aresample={sr},{_ECHO}"

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-af", af,
        str(output_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()
    if proc.returncode != 0 or not output_path.exists():
        raise RuntimeError("ffmpeg vaporwave effects failed")
