import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from virtualdreams.pipeline.effects import apply_vaporwave


async def _mock_proc(returncode: int, stdout: bytes = b""):
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, b""))
    return proc


async def test_effects_success(tmp_path):
    input_wav = tmp_path / "chorus.wav"
    output_wav = tmp_path / "vapor.wav"
    input_wav.write_bytes(b"RIFF")

    call_count = 0

    async def fake_exec(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # ffprobe call
            return await _mock_proc(0, stdout=b"44100\n")
        # ffmpeg call
        output_wav.write_bytes(b"RIFF")
        return await _mock_proc(0)

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        await apply_vaporwave(input_wav, output_wav)

    assert output_wav.exists()


async def test_effects_raises_on_failure(tmp_path):
    input_wav = tmp_path / "chorus.wav"
    output_wav = tmp_path / "vapor.wav"
    input_wav.write_bytes(b"RIFF")

    call_count = 0

    async def fake_exec(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return await _mock_proc(0, stdout=b"44100\n")
        return await _mock_proc(1)

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        with pytest.raises(RuntimeError, match="ffmpeg vaporwave"):
            await apply_vaporwave(input_wav, output_wav)


async def test_effects_uses_asetrate_not_atempo(tmp_path):
    input_wav = tmp_path / "chorus.wav"
    output_wav = tmp_path / "vapor.wav"
    input_wav.write_bytes(b"RIFF")

    captured = []
    call_count = 0

    async def fake_exec(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return await _mock_proc(0, stdout=b"44100\n")
        captured.extend(args)
        output_wav.write_bytes(b"RIFF")
        return await _mock_proc(0)

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        await apply_vaporwave(input_wav, output_wav)

    cmd = " ".join(str(a) for a in captured)
    assert "asetrate" in cmd
    assert "aresample" in cmd
    assert "aecho" in cmd
    assert "atempo" not in cmd
