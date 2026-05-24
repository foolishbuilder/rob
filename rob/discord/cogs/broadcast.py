from __future__ import annotations

import io
from dataclasses import dataclass
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from rob.ui.cards.errors import error_card, error_permission
from rob.ui.components import make_card, render
from rob.ui.theme import (
    COLOR_DANGER,
    COLOR_INFO,
    COLOR_LEADERBOARD,
    COLOR_ROB_PURPLE,
    COLOR_SUCCESS,
    COLOR_WARNING,
)

if TYPE_CHECKING:
    from rob.discord.client import RobBot


_STYLE_TO_COLOR = {
    "purple": COLOR_ROB_PURPLE,
    "info": COLOR_INFO,
    "success": COLOR_SUCCESS,
    "warning": COLOR_WARNING,
    "danger": COLOR_DANGER,
    "leaderboard": COLOR_LEADERBOARD,
}

_STYLE_OPTIONS = [
    discord.SelectOption(label="Rob Purple", value="purple", description="General Rob purple card."),
    discord.SelectOption(label="Info Blue", value="info", description="Informational update."),
    discord.SelectOption(label="Success Green", value="success", description="Success or celebration."),
    discord.SelectOption(label="Warning Gold", value="warning", description="Heads-up or warning."),
    discord.SelectOption(label="Danger Red", value="danger", description="Urgent or serious notice."),
    discord.SelectOption(label="Leaderboard Purple", value="leaderboard", description="Leaderboard-style card."),
]

_DM_ALL_ALIASES = {"all-members", "dm-all", "all", "members"}


@dataclass(frozen=True)
class _AttachmentPayload:
    filename: str
    data: bytes
    content_type: str | None
    description: str | None

    def to_file(self) -> discord.File:
        return discord.File(
            io.BytesIO(self.data),
            filename=self.filename,
            description=self.description,
        )

    @property
    def is_image(self) -> bool:
        return bool(self.content_type and self.content_type.startswith("image/"))


class _BroadcastModal(discord.ui.Modal, title="Owner Broadcast"):
    def __init__(self, *, cog: "BroadcastCog") -> None:
        super().__init__()
        self.cog = cog

        self.target_input = discord.ui.TextInput(
            label="Target",
            style=discord.TextStyle.short,
            required=True,
            max_length=80,
            placeholder="guild_id:channel_id or guild_id:all-members",
        )
        self.title_input = discord.ui.TextInput(
            label="Card title",
            style=discord.TextStyle.short,
            required=True,
            max_length=120,
        )
        self.body_input = discord.ui.TextInput(
            label="Card body",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000,
        )
        self.style_select = discord.ui.Select(
            custom_id="broadcast_style",
            placeholder="Choose a card style",
            options=_STYLE_OPTIONS,
            required=True,
        )
        self.upload = discord.ui.FileUpload(
            custom_id="broadcast_upload",
            required=False,
            min_values=0,
            max_values=1,
        )

        self.add_item(self.target_input)
        self.add_item(self.title_input)
        self.add_item(self.body_input)
        self.add_item(
            discord.ui.Label(
                text="Card style",
                description="Pick the Rob card accent/style for this broadcast.",
                component=self.style_select,
            )
        )
        self.add_item(
            discord.ui.Label(
                text="Optional upload",
                description="Add one image or file to include with the broadcast.",
                component=self.upload,
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        style = self.style_select.values[0] if self.style_select.values else "purple"
        uploads = list(self.upload.values) if self.upload.values else []
        attachment = uploads[0] if uploads else None
        await self.cog.submit_broadcast(
            interaction,
            target_raw=str(self.target_input.value).strip(),
            title=str(self.title_input.value).strip(),
            body=str(self.body_input.value).strip(),
            style=style,
            attachment=attachment,
        )


class BroadcastCog(commands.Cog):
    def __init__(self, bot: RobBot) -> None:
        self.bot = bot

    async def _is_owner(self, user_id: int) -> bool:
        configured = getattr(self.bot.settings, "inactivity_owner_user_id", None)
        if configured is not None and configured == user_id:
            return True

        try:
            app_info = await self.bot.application_info()
        except discord.HTTPException:
            return False

        owner = app_info.owner
        if owner is None:
            return False
        if getattr(owner, "id", None) == user_id:
            return True

        members = getattr(owner, "members", None) or []
        return any(getattr(member, "id", None) == user_id for member in members)

    @staticmethod
    def _parse_target(target_raw: str) -> tuple[int, int | None, bool] | None:
        raw = target_raw.strip()
        if ":" not in raw:
            return None
        guild_raw, destination_raw = raw.split(":", 1)
        guild_raw = guild_raw.strip()
        destination_raw = destination_raw.strip().lower()
        if not guild_raw.isdigit():
            return None
        if destination_raw in _DM_ALL_ALIASES:
            return int(guild_raw), None, True
        if destination_raw.isdigit():
            return int(guild_raw), int(destination_raw), False
        return None

    async def _materialize_attachment(
        self,
        attachment: discord.Attachment | None,
    ) -> _AttachmentPayload | None:
        if attachment is None:
            return None
        return _AttachmentPayload(
            filename=attachment.filename,
            data=await attachment.read(use_cached=True),
            content_type=getattr(attachment, "content_type", None),
            description=getattr(attachment, "description", None),
        )

    def _build_broadcast_send_kwargs(
        self,
        *,
        title: str,
        body: str,
        style: str,
        attachment_payload: _AttachmentPayload | None,
    ) -> dict:
        image_url = None
        files: list[discord.File] = []
        if attachment_payload is not None:
            files.append(attachment_payload.to_file())
            if attachment_payload.is_image:
                image_url = f"attachment://{attachment_payload.filename}"

        rendered = render(
            make_card(
                title=title,
                body=body,
                color=_STYLE_TO_COLOR.get(style, COLOR_ROB_PURPLE),
                image_url=image_url,
            )
        )
        send_kwargs = rendered.send_kwargs()
        if files:
            send_kwargs["files"] = files
        return send_kwargs

    async def _list_human_members(self, guild: discord.Guild) -> list[discord.abc.User]:
        cached = [member for member in getattr(guild, "members", []) if not getattr(member, "bot", False)]
        if cached:
            return cached

        fetch_members = getattr(guild, "fetch_members", None)
        if fetch_members is None:
            return []

        members: list[discord.abc.User] = []
        async for member in fetch_members(limit=None):
            if not getattr(member, "bot", False):
                members.append(member)
        return members

    @app_commands.command(
        name="broadcast",
        description="Owner-only DM broadcast form for Rob cards.",
    )
    async def broadcast(self, interaction: discord.Interaction) -> None:
        if interaction.user is None:
            await interaction.response.send_message(
                **error_card("Rob could not resolve your user identity.").send_kwargs(),
                ephemeral=True,
            )
            return
        if interaction.guild is not None:
            await interaction.response.send_message(
                **error_permission("This command is DM-only. Open a DM with Rob to use /broadcast.").send_kwargs(),
                ephemeral=True,
            )
            return
        if not await self._is_owner(interaction.user.id):
            await interaction.response.send_message(
                **error_permission("Only the bot owner can run this command.").send_kwargs(),
            )
            return

        await interaction.response.send_modal(_BroadcastModal(cog=self))

    async def submit_broadcast(
        self,
        interaction: discord.Interaction,
        *,
        target_raw: str,
        title: str,
        body: str,
        style: str,
        attachment: discord.Attachment | None,
    ) -> None:
        if interaction.user is None or not await self._is_owner(interaction.user.id):
            await interaction.response.send_message(
                **error_permission("Only the bot owner can run this command.").send_kwargs(),
            )
            return

        parsed = self._parse_target(target_raw)
        if parsed is None:
            await interaction.response.send_message(
                **error_card(
                    "Broadcast target must look like `guild_id:channel_id` or `guild_id:all-members`."
                ).send_kwargs(),
            )
            return
        if not title or not body:
            await interaction.response.send_message(
                **error_card("Title and body are required.").send_kwargs(),
            )
            return

        guild_id, channel_id, dm_all = parsed
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            await interaction.response.send_message(
                **error_card(f"Rob is not currently in guild `{guild_id}`.").send_kwargs(),
            )
            return

        attachment_payload = await self._materialize_attachment(attachment)

        if dm_all:
            await interaction.response.defer()
            members = await self._list_human_members(guild)
            sent = 0
            failed = 0
            for member in members:
                try:
                    await member.send(
                        **self._build_broadcast_send_kwargs(
                            title=title,
                            body=body,
                            style=style,
                            attachment_payload=attachment_payload,
                        )
                    )
                    sent += 1
                except discord.HTTPException:
                    failed += 1

            confirmation = render(
                make_card(
                    title="Broadcast Sent",
                    body=(
                        f"Guild: **{guild.name}** (`{guild.id}`)\n"
                        f"Mode: **DM all members**\n"
                        f"Sent: **{sent}**\n"
                        f"Failed: **{failed}**"
                    ),
                    color=COLOR_SUCCESS if failed == 0 else COLOR_WARNING,
                )
            )
            await interaction.followup.send(**confirmation.send_kwargs())
            return

        assert channel_id is not None
        channel = guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except (discord.NotFound, discord.HTTPException):
                channel = None

        if not isinstance(channel, discord.TextChannel) or channel.guild.id != guild_id:
            await interaction.response.send_message(
                **error_card(
                    "Target channel was not found as a text channel in that guild.",
                    "Check the target field and try again.",
                ).send_kwargs(),
            )
            return

        try:
            message = await channel.send(
                **self._build_broadcast_send_kwargs(
                    title=title,
                    body=body,
                    style=style,
                    attachment_payload=attachment_payload,
                )
            )
        except discord.HTTPException:
            await interaction.response.send_message(
                **error_card("Broadcast failed to send to that channel.").send_kwargs(),
            )
            return

        confirmation = render(
            make_card(
                title="Broadcast Sent",
                body=(
                    f"Guild: **{guild.name}** (`{guild.id}`)\n"
                    f"Channel: <#{channel.id}>\n"
                    f"Message ID: `{message.id}`"
                ),
                color=COLOR_SUCCESS,
            )
        )
        await interaction.response.send_message(**confirmation.send_kwargs())
