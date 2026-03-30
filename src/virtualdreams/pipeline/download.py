import asyncio
from pathlib import Path

YOUTUBE_URL_PREFIXES = (
    "https://www.youtube.com/",
    "http://www.youtube.com/",
    "https://youtu.be/",
    "http://youtu.be/",
    "youtube.com/",
    "youtu.be/",
)
MAX_DURATION = 420  # seconds


async def download_audio(query: str, output_dir: Path) -> Path:
    """Download audio from YouTube as WAV. Returns path to WAV file."""
    is_url = query.lower().startswith(YOUTUBE_URL_PREFIXES)

    args = [
        "yt-dlp",
        "-f", "bestaudio/best",
        "--extract-audio",
        "--audio-format", "wav",
        "--no-playlist",
        "--quiet",
        "-o", str(output_dir / "%(id)s.%(ext)s"),
    ]

    if not is_url:
        args += ["--default-search", "ytsearch1:"]

    args += ["--match-filter", f"duration<={MAX_DURATION}", query]

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {stderr.decode()}")

    wav_files = list(output_dir.glob("*.wav"))
    if not wav_files:
        raise RuntimeError("yt-dlp produced no WAV file")

    return wav_files[0]
