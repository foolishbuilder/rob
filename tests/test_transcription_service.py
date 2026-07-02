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
    # loading the model fails (ImportError) and the service disables itself
    # permanently (never worth retrying a missing dependency).
    svc = TranscriptionService(enabled=True)
    assert svc.available is True  # before first use
    result = asyncio.run(svc.transcribe(b"audio-bytes"))
    assert result is None
    assert svc.available is False  # after a failed load it disables itself
    assert svc._permanent_fail is True


def test_transient_load_failure_backs_off_and_retries():
    # A non-ImportError load failure (e.g. a download blip) must NOT permanently
    # disable the feature — it backs off and becomes available again later.
    svc = TranscriptionService(enabled=True)

    def _boom():
        raise RuntimeError("network blip during model download")

    svc._load_model_blocking = _boom  # type: ignore[method-assign]

    assert asyncio.run(svc.transcribe(b"audio-bytes")) is None
    assert svc._permanent_fail is False
    assert svc.available is False  # inside the back-off window

    svc._retry_after = 0.0  # simulate the back-off elapsing
    assert svc.available is True  # retryable again
