import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from virtualdreams.pipeline.chorus import extract_chorus


async def _mock_proc(returncode: int):
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(b"", b""))
    return proc


async def test_chorus_success(tmp_path):
    input_wav = tmp_path / "input.wav"
    output_wav = tmp_path / "chorus.wav"
    input_wav.write_bytes(b"RIFF")

    call_count = 0

    async def fake_exec(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        output_wav.write_bytes(b"RIFF")
        return await _mock_proc(0)

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        await extract_chorus(input_wav, output_wav)

    assert output_wav.exists()
    assert call_count == 1  # only chorus-detector, no fallback


async def test_chorus_fallback_on_nonzero(tmp_path):
    input_wav = tmp_path / "input.wav"
    output_wav = tmp_path / "chorus.wav"
    input_wav.write_bytes(b"RIFF")

    call_count = 0

    async def fake_exec(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return await _mock_proc(1)
        else:
            output_wav.write_bytes(b"RIFF")
            return await _mock_proc(0)

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        await extract_chorus(input_wav, output_wav)

    assert call_count == 2


async def test_chorus_fallback_on_missing_output(tmp_path):
    input_wav = tmp_path / "input.wav"
    output_wav = tmp_path / "chorus.wav"
    input_wav.write_bytes(b"RIFF")

    call_count = 0

    async def fake_exec(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # exits 0 but produces no file
            return await _mock_proc(0)
        else:
            output_wav.write_bytes(b"RIFF")
            return await _mock_proc(0)

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        await extract_chorus(input_wav, output_wav)

    assert call_count == 2


async def test_chorus_raises_if_fallback_fails(tmp_path):
    input_wav = tmp_path / "input.wav"
    output_wav = tmp_path / "chorus.wav"
    input_wav.write_bytes(b"RIFF")

    with patch("asyncio.create_subprocess_exec", return_value=await _mock_proc(1)):
        with pytest.raises(RuntimeError, match="ffmpeg trim"):
            await extract_chorus(input_wav, output_wav)
