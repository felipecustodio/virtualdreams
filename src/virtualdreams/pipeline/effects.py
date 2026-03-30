import asyncio
from pathlib import Path

# atempo=0.8,atempo=0.7875 chains to 0.63× speed (safe across ffmpeg versions)
# aecho adds the signature vaporwave reverb
_VAPORWAVE_FILTER = "atempo=0.8,atempo=0.7875,aecho=0.8:0.88:60:0.4"


async def apply_vaporwave(input_path: Path, output_path: Path) -> None:
    """Apply vaporwave effects: 0.63× slowdown + reverb via ffmpeg."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-af", _VAPORWAVE_FILTER,
        str(output_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()
    if proc.returncode != 0 or not output_path.exists():
        raise RuntimeError("ffmpeg vaporwave effects failed")
