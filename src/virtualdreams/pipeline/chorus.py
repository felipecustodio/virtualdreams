import asyncio
import os
from pathlib import Path

CHORUS_DETECTOR_BIN = os.getenv(
    "CHORUS_DETECTOR_BIN",
    "./chorus-detector/target/release/chorus-detector",
)
CHORUS_DURATION = 15  # seconds


async def extract_chorus(
    input_path: Path, output_path: Path, duration: int = CHORUS_DURATION
) -> None:
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
