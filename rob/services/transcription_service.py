"""Local speech-to-text for Discord voice messages.

Transcription runs entirely on the host with `faster-whisper
<https://github.com/SYSTRAN/faster-whisper>`_ — a small CTranslate2 Whisper
model, no GPU or external API required. ``faster-whisper`` is an *optional*
dependency (see ``requirements-voice.txt``); it is imported lazily so the bot
runs fine without it, and the feature stays disabled until the operator installs
it and sets ``VOICE_TRANSCRIBE_ENABLED=true``.

All model work is blocking/CPU-bound and is therefore dispatched to a worker
thread via :func:`asyncio.to_thread`, and serialised with a semaphore, so the
Discord event loop never stalls.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    language: str | None = None
    duration_seconds: float | None = None


class TranscriptionService:
    def __init__(
        self,
        *,
        enabled: bool = False,
        model: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str | None = None,
        download_root: str | None = None,
        beam_size: int = 1,
        max_concurrency: int = 1,
    ) -> None:
        self.enabled = enabled
        self.model_name = model
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.download_root = download_root
        self.beam_size = max(1, beam_size)
        self._model = None
        self._unavailable = False
        self._load_lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))

    @property
    def available(self) -> bool:
        """Whether transcription can currently run (enabled and not known-broken)."""
        return self.enabled and not self._unavailable

    async def transcribe(
        self, audio_bytes: bytes, *, filename: str = "voice-message.ogg"
    ) -> TranscriptResult | None:
        if not self.available:
            return None
        model = await self._ensure_model()
        if model is None:
            return None
        async with self._semaphore:
            return await asyncio.to_thread(
                self._transcribe_blocking, model, audio_bytes, filename
            )

    async def _ensure_model(self):
        if self._model is not None:
            return self._model
        if self._unavailable:
            return None
        async with self._load_lock:
            if self._model is not None:
                return self._model
            if self._unavailable:
                return None
            model = await asyncio.to_thread(self._load_model_blocking)
            if model is None:
                # Don't retry a hopeless load (missing dep / bad model) forever.
                self._unavailable = True
            self._model = model
            return model

    def _load_model_blocking(self):
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            log.error(
                "Voice transcription is enabled but faster-whisper is not installed. "
                "Install it with `pip install -r requirements-voice.txt` (or "
                "`pip install faster-whisper`) and restart the bot."
            )
            return None
        try:
            log.info(
                "Loading Whisper model %s (device=%s, compute_type=%s) for voice transcription.",
                self.model_name,
                self.device,
                self.compute_type,
            )
            return WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
                download_root=self.download_root,
            )
        except Exception:
            log.exception("Failed to load the Whisper model %s.", self.model_name)
            return None

    def _transcribe_blocking(self, model, audio_bytes: bytes, filename: str):
        suffix = os.path.splitext(filename)[1] or ".ogg"
        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
                handle.write(audio_bytes)
                tmp_path = handle.name
            segments, info = model.transcribe(
                tmp_path,
                beam_size=self.beam_size,
                language=self.language,
                vad_filter=True,
            )
            parts = [segment.text.strip() for segment in segments]
            text = " ".join(part for part in parts if part).strip()
            return TranscriptResult(
                text=text,
                language=getattr(info, "language", None),
                duration_seconds=getattr(info, "duration", None),
            )
        except Exception:
            log.exception("Voice transcription failed.")
            return None
        finally:
            if tmp_path:
                try:
                    os.remove(tmp_path)
                except OSError:  # pragma: no cover - best-effort cleanup
                    pass
