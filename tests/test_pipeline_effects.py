import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from virtualdreams.pipeline.effects import apply_vaporwave


async def _mock_proc(returncode: int):
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(b"", b""))
    return proc


async def test_effects_success(tmp_path):
    input_wav = tmp_path / "chorus.wav"
    output_wav = tmp_path / "vapor.wav"
    input_wav.write_bytes(b"RIFF")

    async def fake_exec(*args, **kwargs):
        output_wav.write_bytes(b"RIFF")
        return await _mock_proc(0)

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        await apply_vaporwave(input_wav, output_wav)

    assert output_wav.exists()


async def test_effects_raises_on_failure(tmp_path):
    input_wav = tmp_path / "chorus.wav"
    output_wav = tmp_path / "vapor.wav"
    input_wav.write_bytes(b"RIFF")

    with patch("asyncio.create_subprocess_exec", return_value=await _mock_proc(1)):
        with pytest.raises(RuntimeError, match="ffmpeg vaporwave"):
            await apply_vaporwave(input_wav, output_wav)


async def test_effects_uses_correct_filters(tmp_path):
    input_wav = tmp_path / "chorus.wav"
    output_wav = tmp_path / "vapor.wav"
    input_wav.write_bytes(b"RIFF")

    captured_args = []

    async def fake_exec(*args, **kwargs):
        captured_args.extend(args)
        output_wav.write_bytes(b"RIFF")
        return await _mock_proc(0)

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        await apply_vaporwave(input_wav, output_wav)

    cmd = " ".join(captured_args)
    assert "atempo" in cmd
    assert "aecho" in cmd
