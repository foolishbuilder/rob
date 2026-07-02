from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from rob.ui.cards.voice_transcription import transcript_card

if TYPE_CHECKING:
    from rob.discord.client import RobBot

log = logging.getLogger(__name__)


def _voice_attachment(message: discord.Message) -> discord.Attachment | None:
    """Return the attachment of a Discord *voice message*, if this is one.

    Discord flags true voice messages with ``MessageFlags.voice``; we also accept
    an audio attachment named like a voice note (``voice-message.*``) as a
    fallback for older clients. We deliberately do *not* match arbitrary audio
    uploads (mp3/wav) — only genuine voice notes — so Rob never auto-transcribes
    ordinary media files."""

    flagged = bool(getattr(message.flags, "voice", False))
    for attachment in message.attachments:
        looks_like_voice = attachment.filename.lower().startswith("voice-message")
        if flagged or looks_like_voice:
            return attachment
    return None


class VoiceTranscriptionCog(commands.Cog):
    """Listens for voice messages and replies (without pinging) with a transcript,
    produced by a local Whisper model. Replying to any (older) voice message
    while mentioning Rob requests its transcript on demand. No-op unless the
    operator has enabled the feature and installed faster-whisper."""

    def __init__(self, bot: "RobBot") -> None:
        self.bot = bot
        # Bound how many voice messages are being downloaded/transcribed at once,
        # so a burst can't hold many multi-MB audio buffers in memory while queued
        # behind the (typically single-slot) transcription semaphore.
        limit = max(1, getattr(bot.settings, "voice_transcribe_max_concurrency", 1)) + 2
        self._inflight = asyncio.Semaphore(limit)

    def _service(self):
        return getattr(self.bot, "transcription_service", None)

    def _mentions_me(self, message: discord.Message) -> bool:
        me = self.bot.user
        return me is not None and any(getattr(u, "id", None) == me.id for u in message.mentions)

    async def _resolve_reference(self, message: discord.Message) -> discord.Message | None:
        ref = message.reference
        if ref is None:
            return None
        resolved = ref.resolved
        if isinstance(resolved, discord.Message):
            return resolved
        if ref.message_id is None:
            return None
        try:
            return await message.channel.fetch_message(ref.message_id)
        except discord.HTTPException:
            return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        service = self._service()
        if service is None or not service.available:
            return
        if message.author.bot:
            return

        attachment = _voice_attachment(message)
        if attachment is not None:
            await self._transcribe_and_reply(message, attachment, service)
            return

        # On-demand path: replying to an (older) voice message while mentioning
        # Rob asks him to transcribe it — covers messages sent before this
        # feature existed or missed while transcription was disabled.
        if message.reference is None or not self._mentions_me(message):
            return
        target = await self._resolve_reference(message)
        if target is None or target.author.bot:
            return
        target_attachment = _voice_attachment(target)
        if target_attachment is None:
            return
        await self._transcribe_and_reply(target, target_attachment, service)

    async def _transcribe_and_reply(
        self,
        message: discord.Message,
        attachment: discord.Attachment,
        service,
    ) -> None:
        settings = self.bot.settings
        duration = getattr(attachment, "duration", None)
        # Real voice messages always carry a duration; if it's missing or over the
        # cap, skip — we won't transcribe audio whose length we can't bound.
        if duration is None or duration > settings.voice_transcribe_max_duration_seconds:
            log.info(
                "Skipping voice message %s: duration %s not within 0..%ss.",
                message.id,
                duration,
                settings.voice_transcribe_max_duration_seconds,
            )
            return
        max_bytes = settings.voice_transcribe_max_file_mb * 1024 * 1024
        if attachment.size and attachment.size > max_bytes:
            log.info(
                "Skipping voice message %s: %s bytes exceeds max %s.",
                message.id,
                attachment.size,
                max_bytes,
            )
            return

        async with self._inflight:
            try:
                audio_bytes = await attachment.read()
            except discord.HTTPException:
                log.warning("Failed to download voice message %s.", message.id, exc_info=True)
                return

            result = await service.transcribe(audio_bytes, filename=attachment.filename)
            if result is None:
                return

            card = transcript_card(
                text=result.text,
                language=result.language,
                duration_seconds=result.duration_seconds or duration,
            )
            try:
                await message.reply(
                    **card.send_kwargs(),
                    mention_author=False,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException:
                log.warning(
                    "Failed to post transcript for voice message %s.", message.id, exc_info=True
                )
