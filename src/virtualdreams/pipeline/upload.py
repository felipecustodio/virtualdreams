import asyncio
from pathlib import Path


async def normalize_uploaded_audio(input_path: Path, output_dir: Path) -> Path:
    """Convert an uploaded audio file into a normalized WAV for the pipeline."""
    output_path = output_dir / "input.wav"

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ac",
        "2",
        "-ar",
        "44100",
        str(output_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()
    if proc.returncode != 0 or not output_path.exists():
        raise RuntimeError("ffmpeg upload normalization failed")

    return output_path
