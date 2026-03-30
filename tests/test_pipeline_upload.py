import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from virtualdreams.pipeline.upload import normalize_uploaded_audio


async def _mock_proc(returncode: int):
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(b"", b""))
    return proc


async def test_normalize_uploaded_audio_success(tmp_path):
    input_audio = tmp_path / "input.mp3"
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    input_audio.write_bytes(b"fake")
    output_wav = output_dir / "input.wav"

    async def fake_exec(*args, **kwargs):
        output_wav.write_bytes(b"RIFF")
        return await _mock_proc(0)

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        result = await normalize_uploaded_audio(input_audio, output_dir)

    assert result == output_wav
    assert output_wav.exists()


async def test_normalize_uploaded_audio_raises_on_failure(tmp_path):
    input_audio = tmp_path / "input.mp3"
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    input_audio.write_bytes(b"fake")

    with patch("asyncio.create_subprocess_exec", return_value=await _mock_proc(1)):
        with pytest.raises(RuntimeError, match="upload normalization"):
            await normalize_uploaded_audio(input_audio, output_dir)
