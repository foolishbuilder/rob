from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from rob.ui.cards.voice_transcription import transcript_card

if TYPE_CHECKING:
    from rob.discord.client import RobBot

log = logging.getLogger(__name__)


def _voice_attachment(message: discord.Message) -> discord.Attachment | None:
    """Return the audio attachment of a Discord voice message, if any.

    Discord flags true voice messages with ``MessageFlags.voice``; we also accept
    an audio attachment named like a voice note as a fallback for older clients."""

    flagged = bool(getattr(message.flags, "voice", False))
    for attachment in message.attachments:
        content_type = (attachment.content_type or "").lower()
        is_audio = content_type.startswith("audio")
        looks_like_voice = attachment.filename.lower().startswith("voice-message")
        if flagged or is_audio or looks_like_voice:
            return attachment
    return None


class VoiceTranscriptionCog(commands.Cog):
    """Listens for voice messages and replies (without pinging) with a transcript,
    produced by a local Whisper model. No-op unless the operator has enabled the
    feature and installed faster-whisper."""

    def __init__(self, bot: "RobBot") -> None:
        self.bot = bot

    def _service(self):
        return getattr(self.bot, "transcription_service", None)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        service = self._service()
        if service is None or not service.available:
            return
        if message.author.bot:
            return

        attachment = _voice_attachment(message)
        if attachment is None:
            return

        settings = self.bot.settings
        duration = getattr(attachment, "duration", None)
        if duration is not None and duration > settings.voice_transcribe_max_duration_seconds:
            log.info(
                "Skipping voice message %s: %.0fs exceeds max %ss.",
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
