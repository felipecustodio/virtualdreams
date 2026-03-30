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
