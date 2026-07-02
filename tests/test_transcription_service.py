from __future__ import annotations

import asyncio
from types import SimpleNamespace

from rob.services.transcription_service import TranscriptionService


class _FakeModel:
    def __init__(self, segments=None, info=None, error: Exception | None = None):
        self._segments = segments
        self._info = info
        self._error = error
        self.calls: list[str] = []

    def transcribe(self, path, beam_size=1, language=None, vad_filter=False):
        self.calls.append(path)
        if self._error is not None:
            raise self._error
        return self._segments, self._info


def test_disabled_service_is_unavailable_and_returns_none():
    svc = TranscriptionService(enabled=False)
    assert svc.available is False
    assert asyncio.run(svc.transcribe(b"data")) is None


def test_transcribe_joins_segment_text():
    svc = TranscriptionService(enabled=True)
    svc._model = _FakeModel(
        segments=[SimpleNamespace(text=" Hello there "), SimpleNamespace(text="world")],
        info=SimpleNamespace(language="en", duration=3.2),
    )
    result = asyncio.run(svc.transcribe(b"audio-bytes", filename="voice-message.ogg"))
    assert result is not None
    assert result.text == "Hello there world"
    assert result.language == "en"
    assert result.duration_seconds == 3.2


def test_transcribe_returns_none_on_model_error():
    svc = TranscriptionService(enabled=True)
    svc._model = _FakeModel(error=RuntimeError("decode failed"))
    result = asyncio.run(svc.transcribe(b"audio-bytes"))
    assert result is None


def test_empty_segments_yield_empty_text():
    svc = TranscriptionService(enabled=True)
    svc._model = _FakeModel(segments=[], info=SimpleNamespace(language="en", duration=0.0))
    result = asyncio.run(svc.transcribe(b"audio-bytes"))
    assert result is not None
    assert result.text == ""


def test_missing_faster_whisper_marks_unavailable():
    # faster-whisper is an optional dep and is not installed in the test env, so
    # loading the model fails and the service disables itself permanently.
    svc = TranscriptionService(enabled=True)
    assert svc.available is True  # before first use
    result = asyncio.run(svc.transcribe(b"audio-bytes"))
    assert result is None
    assert svc.available is False  # after a failed load it disables itself
