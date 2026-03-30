import asyncio
import os
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
    js_runtime = os.getenv("YTDLP_JS_RUNTIME")
    cookies_file = os.getenv("YTDLP_COOKIES_FILE")
    cookies_content = os.getenv("YTDLP_COOKIES_CONTENT")
    yt_visitor_data = os.getenv("YTDLP_YT_VISITOR_DATA")
    yt_po_token = os.getenv("YTDLP_YT_PO_TOKEN")
    yt_player_client = os.getenv("YTDLP_YT_PLAYER_CLIENT")

    args = [
        "yt-dlp",
        "-f", "bestaudio/best",
        "--extract-audio",
        "--audio-format", "wav",
        "--no-playlist",
        "--quiet",
        "-o", str(output_dir / "%(id)s.%(ext)s"),
    ]

    if js_runtime:
        args += ["--js-runtimes", js_runtime]

    if cookies_file:
        args += ["--cookies", cookies_file]
    elif cookies_content:
        rendered_cookies = output_dir / "yt-dlp-cookies.txt"
        rendered_cookies.write_text(cookies_content)
        args += ["--cookies", str(rendered_cookies)]

    extractor_args: list[str] = []
    if yt_player_client:
        extractor_args.append(f"player_client={yt_player_client}")
    elif yt_po_token:
        extractor_args.append("player_client=mweb")

    if yt_visitor_data:
        extractor_args.append(f"visitor_data={yt_visitor_data}")
        extractor_args.append("player_skip=webpage,configs")

    if yt_po_token:
        extractor_args.append(f"po_token={yt_po_token}")

    if extractor_args:
        args += ["--extractor-args", f"youtube:{';'.join(extractor_args)}"]

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
