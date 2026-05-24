from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands

from rob.ui.cards.errors import error_card
from rob.ui.cards.report import report_staff_card, report_submitted_card

if TYPE_CHECKING:
    from rob.discord.client import RobBot

log = logging.getLogger(__name__)


class _ReportModal(discord.ui.Modal, title="Report an issue with Rob"):
    def __init__(
        self,
        *,
        cog: "ReportsCog",
        fallback_attachment: Optional[discord.Attachment],
    ) -> None:
        super().__init__()
        self.cog = cog
        self.fallback_attachment = fallback_attachment
        self.issue = discord.ui.TextInput(
            label="What seems to be wrong?",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000,
        )
        self.acknowledgement = discord.ui.TextInput(
            label="Type YES to confirm this is an issue with Rob",
            style=discord.TextStyle.short,
            required=True,
            max_length=3,
        )
        self.add_item(self.issue)
        self.add_item(self.acknowledgement)
        # Discord currently rejects FileUpload inside modal components in this deployment path.
        # Use the slash-command attachment option as the supported screenshot fallback.
        self.file_upload = None

    async def on_submit(self, interaction: discord.Interaction) -> None:
        attachment: Optional[discord.Attachment] = self.fallback_attachment
        if self.file_upload is not None:
            values = list(getattr(self.file_upload, "values", []) or [])
            if values:
                first = values[0]
                if isinstance(first, discord.Attachment):
                    attachment = first
        await self.cog.submit_report(
            interaction,
            issue_text=str(self.issue.value).strip(),
            acknowledgement=str(self.acknowledgement.value).strip(),
            attachment=attachment,
        )


class ReportsCog(commands.Cog):
    def __init__(self, bot: RobBot) -> None:
        self.bot = bot

    @app_commands.command(name="report", description="Report an issue with Rob.")
    @app_commands.describe(
        screenshot="Optional screenshot to include with your report.",
    )
    async def report(
        self,
        interaction: discord.Interaction,
        screenshot: Optional[discord.Attachment] = None,
    ) -> None:
        await interaction.response.send_modal(
            _ReportModal(cog=self, fallback_attachment=screenshot)
        )

    async def _resolve_destination(
        self,
        interaction: discord.Interaction,
    ) -> Optional[discord.abc.Messageable]:
        if interaction.guild is not None:
            settings = await self.bot.guild_settings_repo.get(interaction.guild.id)
            channel_id = settings.report_channel_id if settings is not None else None
            if channel_id:
                channel = interaction.guild.get_channel(channel_id)
                if channel is None:
                    try:
                        channel = await interaction.guild.fetch_channel(channel_id)
                    except (discord.NotFound, discord.HTTPException):
                        channel = None
                if isinstance(channel, discord.TextChannel):
                    return channel

        try:
            app_info = await self.bot.application_info()
        except discord.HTTPException:
            return None
        owner = app_info.owner
        return owner

    async def submit_report(
        self,
        interaction: discord.Interaction,
        *,
        issue_text: str,
        acknowledgement: str,
        attachment: Optional[discord.Attachment],
    ) -> None:
        if not issue_text:
            await interaction.response.send_message(
                **error_card("Please include what seems to be wrong.").send_kwargs(),
                ephemeral=True,
            )
            return

        if acknowledgement.strip().upper() != "YES":
            await interaction.response.send_message(
                **error_card("Please type YES to confirm this report is about Rob.").send_kwargs(),
                ephemeral=True,
            )
            return

        destination = await self._resolve_destination(interaction)
        if destination is None:
            await interaction.response.send_message(
                **error_card(
                    "Rob could not find a report destination right now.",
                    "Please contact a moderator while we reconnect the report channel.",
                ).send_kwargs(),
                ephemeral=True,
            )
            return

        submitted_at = datetime.now(timezone.utc)
        server_label = (
            f"{interaction.guild.name} / {interaction.guild.id}"
            if interaction.guild is not None
            else "Direct Message / N/A"
        )
        report_card = report_staff_card(
            reporter_mention=interaction.user.mention,
            issue_text=issue_text,
            server_label=server_label,
            submitted_unix=int(submitted_at.timestamp()),
        )

        file_obj: discord.File | None = None
        if attachment is not None:
            try:
                file_obj = await attachment.to_file()
            except discord.HTTPException:
                file_obj = None

        try:
            send_kwargs = report_card.send_kwargs()
            if file_obj is not None:
                send_kwargs["files"] = [file_obj]
            elif attachment is not None:
                send_kwargs["content"] = f"Screenshot: {attachment.url}"
            await destination.send(**send_kwargs)
        except discord.HTTPException:
            log.warning("Failed to deliver /report submission.", exc_info=True)
            await interaction.response.send_message(
                **error_card(
                    "Rob could not deliver that report right now.",
                    "Please let a moderator know while this is fixed.",
                ).send_kwargs(),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            **report_submitted_card().send_kwargs(),
            ephemeral=True,
        )
