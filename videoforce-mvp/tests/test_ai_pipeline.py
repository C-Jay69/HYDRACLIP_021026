"""Unit tests for the AI pipeline.

Every test here corresponds to a defect that made the module unusable. None of
this code had ever executed: nothing imported it, and its entry point raised on
its own return statement.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from apps.api.core.config import settings
from apps.api.services.ai_pipeline import (
    AIPipeline,
    OllamaLLM,
    PiperTTS,
    StageNotImplemented,
    WhisperSTT,
    _work_path,
    get_ai_pipeline,
)


# --- generate_script: the crash that made the pipeline unreachable -------------


@pytest.mark.asyncio
async def test_generate_script_returns_instead_of_raising():
    """Was: AttributeError from `subprocess.list2cmdline.__self__`.

    `list2cmdline` is a plain function with no __self__, and the bare `hasattr`
    builtin is always truthy, so the fallback branch was unreachable. Every
    call raised, even with a perfectly healthy LLM.
    """
    pipeline = AIPipeline()
    with patch.object(OllamaLLM, "generate", new=AsyncMock(return_value="Script body")):
        result = await pipeline.generate_script("coffee roasting")

    assert result["script"] == "Script body"
    assert result["topic"] == "coffee roasting"


@pytest.mark.asyncio
async def test_generate_script_result_is_json_serialisable():
    """The old generated_at would have been a module object even if it parsed."""
    pipeline = AIPipeline()
    with patch.object(OllamaLLM, "generate", new=AsyncMock(return_value="x")):
        result = await pipeline.generate_script("topic")

    json.dumps(result)  # must not raise
    assert result["generated_at"].endswith("+00:00")


@pytest.mark.asyncio
async def test_generate_script_passes_style_and_duration_into_the_prompt():
    pipeline = AIPipeline()
    mock = AsyncMock(return_value="x")
    with patch.object(OllamaLLM, "generate", new=mock):
        await pipeline.generate_script("bread", style="long_form", duration=45)

    prompt = mock.await_args.args[0]
    assert "bread" in prompt
    assert "45 seconds" in prompt
    assert "[PROBLEM]" in prompt  # the long_form template


@pytest.mark.asyncio
async def test_unknown_style_falls_back_to_short_form():
    pipeline = AIPipeline()
    mock = AsyncMock(return_value="x")
    with patch.object(OllamaLLM, "generate", new=mock):
        await pipeline.generate_script("bread", style="nonsense")

    assert "[HOOK]" in mock.await_args.args[0]


# --- configuration was hardcoded ------------------------------------------------


def test_llm_honours_configured_base_url_and_model(monkeypatch):
    """Was hardcoded to localhost:11434 / llama3.2, ignoring the settings."""
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "http://ollama.internal:11434")
    monkeypatch.setattr(settings, "OLLAMA_MODEL", "mistral")

    llm = OllamaLLM()
    assert llm.base_url == "http://ollama.internal:11434"
    assert llm.model == "mistral"


def test_whisper_honours_configured_model_size(monkeypatch):
    monkeypatch.setattr(settings, "WHISPER_MODEL_SIZE", "large-v3")
    assert WhisperSTT().model_size == "large-v3"


def test_piper_resolves_voices_under_the_configured_path(monkeypatch):
    monkeypatch.setattr(settings, "PIPER_MODEL_PATH", "/opt/voices")
    tts = PiperTTS(voice="isley")
    assert tts.model_path == "/opt/voices/en_US-isley-medium.onnx"


def test_explicit_arguments_still_win(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_MODEL", "mistral")
    assert OllamaLLM(model="phi3").model == "phi3"


# --- construction must stay cheap --------------------------------------------------


def test_whisper_does_not_load_the_model_at_construction():
    """_load_model() in __init__ pulled a large model into memory just to
    build the object — and AIPipeline is held in a module-level singleton."""
    assert WhisperSTT().model is None


def test_pipeline_construction_does_not_open_an_http_client():
    """An AsyncClient built in __init__ binds to whichever event loop is
    current at construction time, which for a singleton is the wrong one."""
    pipeline = AIPipeline()
    assert pipeline.llm._client is None

    client = pipeline.llm.client
    assert isinstance(client, httpx.AsyncClient)
    assert pipeline.llm.client is client  # cached


@pytest.mark.asyncio
async def test_close_is_safe_when_the_client_was_never_used():
    await OllamaLLM().close()  # must not raise AttributeError


# --- filesystem safety ---------------------------------------------------------------


def test_work_paths_are_unique():
    """TTS wrote to a fixed /tmp/tts_output.wav, so concurrent jobs
    overwrote each other's audio."""
    assert _work_path(".wav") != _work_path(".wav")


def test_work_paths_stay_inside_the_work_directory():
    path = Path(_work_path(".wav", prefix="tts"))
    assert path.parent == Path(settings.MEDIA_WORK_DIR)


@pytest.mark.asyncio
async def test_assembly_cannot_be_steered_by_the_topic():
    """Was: f"/tmp/video_{topic}.mp4" with the user's topic interpolated raw,
    so a crafted topic escaped /tmp entirely."""
    pipeline = AIPipeline()
    malicious = {"script": "x", "topic": "../../../etc/cron.d/pwned"}

    with patch.object(AIPipeline, "text_to_speech", new=AsyncMock(return_value="/tmp/a.wav")):
        with pytest.raises(StageNotImplemented):
            await pipeline.create_video_from_script(malicious)

    assert not Path("/etc/cron.d/pwned").exists()


# --- honesty about what is implemented -------------------------------------------------


@pytest.mark.asyncio
async def test_assembly_reports_not_implemented_instead_of_claiming_success():
    """Was: returned {"status": "generated"} having written no file at all,
    so callers would be told a video existed when none had been rendered."""
    pipeline = AIPipeline()
    with patch.object(AIPipeline, "text_to_speech", new=AsyncMock(return_value="/tmp/a.wav")):
        with pytest.raises(StageNotImplemented, match="not implemented"):
            await pipeline.create_video_from_script({"script": "x", "topic": "t"})


# --- availability probes ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unavailable_reason_reports_an_unreachable_ollama():
    llm = OllamaLLM(base_url="http://127.0.0.1:1")
    reason = await llm.unavailable_reason()
    assert reason is not None
    assert "unreachable" in reason


@pytest.mark.asyncio
async def test_unavailable_reason_reports_a_missing_model():
    llm = OllamaLLM(model="llama3.2")

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"models": [{"name": "qwen2:7b"}]}

    with patch.object(llm, "_client", AsyncMock()):
        llm._client.get = AsyncMock(return_value=FakeResponse())
        reason = await llm.unavailable_reason()

    assert reason is not None
    assert "not pulled" in reason
    assert "qwen2:7b" in reason


@pytest.mark.asyncio
async def test_unavailable_reason_accepts_a_tagged_model_name():
    """Ollama reports "llama3.2:latest"; a bare "llama3.2" must still match."""
    llm = OllamaLLM(model="llama3.2")

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"models": [{"name": "llama3.2:latest"}]}

    with patch.object(llm, "_client", AsyncMock()):
        llm._client.get = AsyncMock(return_value=FakeResponse())
        assert await llm.unavailable_reason() is None


def test_piper_unavailable_reason_names_the_missing_binary(monkeypatch):
    monkeypatch.setattr("apps.api.services.ai_pipeline.shutil.which", lambda _: None)
    reason = PiperTTS.unavailable_reason()
    assert reason is not None and "piper" in reason


def test_piper_unavailable_reason_names_the_missing_model(monkeypatch, tmp_path):
    monkeypatch.setattr("apps.api.services.ai_pipeline.shutil.which", lambda _: "/usr/bin/piper")
    monkeypatch.setattr(settings, "PIPER_MODEL_PATH", str(tmp_path))
    reason = PiperTTS.unavailable_reason()
    assert reason is not None and "voice model is missing" in reason


# --- singleton ---------------------------------------------------------------------------------


def test_get_ai_pipeline_returns_a_pipeline_and_caches_it():
    first = get_ai_pipeline()
    assert isinstance(first, AIPipeline)
    assert get_ai_pipeline() is first
