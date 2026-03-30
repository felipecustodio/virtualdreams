import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from virtualdreams.pipeline.download import download_audio


async def _mock_proc(returncode: int, stdout: bytes = b"", stderr: bytes = b""):
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


async def test_download_success(tmp_path):
    fake_wav = tmp_path / "abc123.wav"
    fake_wav.write_bytes(b"RIFF")

    with patch("asyncio.create_subprocess_exec", return_value=await _mock_proc(0)):
        result = await download_audio("lofi chill", tmp_path)

    assert result == fake_wav


async def test_download_raises_on_nonzero(tmp_path):
    with patch("asyncio.create_subprocess_exec", return_value=await _mock_proc(1, stderr=b"error")):
        with pytest.raises(RuntimeError, match="yt-dlp failed"):
            await download_audio("lofi chill", tmp_path)


async def test_download_raises_if_no_wav(tmp_path):
    with patch("asyncio.create_subprocess_exec", return_value=await _mock_proc(0)):
        with pytest.raises(RuntimeError, match="no WAV file"):
            await download_audio("lofi chill", tmp_path)


async def test_url_passthrough(tmp_path):
    fake_wav = tmp_path / "abc123.wav"
    fake_wav.write_bytes(b"RIFF")

    with patch("asyncio.create_subprocess_exec", return_value=await _mock_proc(0)) as mock_exec:
        await download_audio("https://www.youtube.com/watch?v=abc123", tmp_path)

    args = mock_exec.call_args[0]
    assert "-f" in args
    assert "bestaudio/best" in args
    assert "--default-search" not in args


async def test_download_uses_cookie_file_when_configured(tmp_path, monkeypatch):
    fake_wav = tmp_path / "abc123.wav"
    fake_wav.write_bytes(b"RIFF")
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n")
    monkeypatch.setenv("YTDLP_COOKIES_FILE", str(cookies))

    with patch("asyncio.create_subprocess_exec", return_value=await _mock_proc(0)) as mock_exec:
        await download_audio("https://www.youtube.com/watch?v=abc123", tmp_path)

    args = mock_exec.call_args[0]
    assert "--cookies" in args
    assert str(cookies) in args


async def test_download_renders_cookie_content_when_configured(tmp_path, monkeypatch):
    fake_wav = tmp_path / "abc123.wav"
    fake_wav.write_bytes(b"RIFF")
    monkeypatch.setenv("YTDLP_COOKIES_CONTENT", "# Netscape HTTP Cookie File\n.youtube.com\tTRUE")

    with patch("asyncio.create_subprocess_exec", return_value=await _mock_proc(0)) as mock_exec:
        await download_audio("https://www.youtube.com/watch?v=abc123", tmp_path)

    args = mock_exec.call_args[0]
    cookies_path = tmp_path / "yt-dlp-cookies.txt"
    assert "--cookies" in args
    assert str(cookies_path) in args
    assert cookies_path.exists()


async def test_download_uses_configured_js_runtime(tmp_path, monkeypatch):
    fake_wav = tmp_path / "abc123.wav"
    fake_wav.write_bytes(b"RIFF")
    monkeypatch.setenv("YTDLP_JS_RUNTIME", "bun")

    with patch("asyncio.create_subprocess_exec", return_value=await _mock_proc(0)) as mock_exec:
        await download_audio("https://www.youtube.com/watch?v=abc123", tmp_path)

    args = mock_exec.call_args[0]
    assert "--js-runtimes" in args
    assert "bun" in args


async def test_download_uses_logged_out_po_token_flow(tmp_path, monkeypatch):
    fake_wav = tmp_path / "abc123.wav"
    fake_wav.write_bytes(b"RIFF")
    monkeypatch.setenv("YTDLP_YT_VISITOR_DATA", "visitor-data-token")
    monkeypatch.setenv("YTDLP_YT_PO_TOKEN", "mweb.gvs+po-token")

    with patch("asyncio.create_subprocess_exec", return_value=await _mock_proc(0)) as mock_exec:
        await download_audio("https://www.youtube.com/watch?v=abc123", tmp_path)

    args = mock_exec.call_args[0]
    extractor_index = args.index("--extractor-args")
    extractor_args = args[extractor_index + 1]

    assert extractor_args.startswith("youtube:")
    assert "player_client=mweb" in extractor_args
    assert "visitor_data=visitor-data-token" in extractor_args
    assert "player_skip=webpage,configs" in extractor_args
    assert "po_token=mweb.gvs+po-token" in extractor_args
